"""Single-date water/non-water mapping and its evaluation.

Each config defines one or more *variants* (`extra.variants`, or the single top-level `method`). For every
variant and date: features -> classifier -> uint8 mask (1 water, 0 non-water, 255 nodata) -> COG + metrics
against the reference on `validation.split` blocks. Methods that learn something from data (a tuned
threshold, later supervised models) see TRAIN-block reference pixels only, pooled over all dates, via
`TrainData`; evaluation is on TEST blocks.

Classifiers are registered in METHODS: fn(features, params, train) -> (mask, diagnostics).
"""
from __future__ import annotations

from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nisar_water.classify import threshold
from nisar_water.classify.refine import refine
from nisar_water.features.pol import features_db, resolve_filter
from nisar_water.io.raster import write_cog
from nisar_water.tasks.common import load_reference, load_scene, to_canonical
from nisar_water.tasks.separability import best_threshold_f1
from nisar_water.validate.metrics import evaluate
from nisar_water.viz.maps import save_categorical

WATER_CLASSES = {0: ("Non-water", "#d9d6cc"), 1: ("Water", "#2a78d6")}
TEXT, MUTED, GRID_C = "#0b0b0b", "#52514e", "#e4e3df"
VARIANT_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # fixed order (dataviz reference palette)


@dataclass
class TrainData:
    """Pooled train-block samples per feature: water and land values (dB)."""
    water: dict[str, np.ndarray]
    land: dict[str, np.ndarray]
    samples: dict | None = None  # supervised: X (n, f), y, is_fit (FIT vs VAL blocks), names


# --- classifiers --------------------------------------------------------------------------------

def _threshold_method(features, params, train):
    feat = params.get("feature", "HH")
    db = features[feat]
    kind = params["kind"]
    info = {}
    if kind == "fixed":
        t = float(params["threshold_db"])
    elif kind == "tuned":
        t, info = _tuned(train, feat)
    elif kind == "otsu":
        t = threshold.otsu(db)
    elif kind == "kittler_illingworth":
        t = threshold.kittler_illingworth(db)
    elif kind == "tiled":
        t, info = threshold.tiled(db, **params.get("tiled", {}))
    else:
        raise NotImplementedError(f"threshold kind {kind!r}")
    if "hysteresis" in params:
        return threshold.hysteresis(db, t, **params["hysteresis"]), {"threshold_db": float(t), **info}
    return threshold.apply(db, t), {"threshold_db": float(t), **info}


_TUNED_CACHE: dict[str, tuple[float, dict]] = {}


def _tuned(train: TrainData, feat: str) -> tuple[float, dict]:
    """Threshold maximising F1 on pooled TRAIN pixels of all dates (computed once per feature)."""
    if feat not in _TUNED_CACHE:
        f1, t, direction = best_threshold_f1(train.water[feat], train.land[feat])
        if direction != "<":
            raise ValueError(f"{feat}: water is brighter than land on train data; '<' rule invalid")
        _TUNED_CACHE[feat] = (t, {"train_f1": round(f1, 4)})
    return _TUNED_CACHE[feat]


def _dualpol_and(features, params, train):
    """Water = HH < t_HH AND HV < t_HV, each threshold from its own per-scene tiled-KI (bounded) split."""
    t = {}
    for f in ("HH", "HV"):
        t[f], _ = threshold.tiled(features[f], **params.get("tiled", {}))
    ok = np.isfinite(features["HH"]) & np.isfinite(features["HV"])
    out = np.full(ok.shape, 255, np.uint8)
    out[ok] = ((features["HH"] < t["HH"]) & (features["HV"] < t["HV"]))[ok]
    return out, {"threshold_db": float(t["HH"]), "threshold_hv_db": float(t["HV"])}


def _gmm(features, params, train):
    from nisar_water.classify.unsupervised import gmm_water

    return gmm_water(features, params.get("features", ["HH", "HV"]), params.get("n_components", 3),
                     min_posterior=params.get("min_posterior", 0.5))


def _hand() -> np.ndarray:
    """HAND on the canonical grid, built once (Copernicus GLO-30 + pysheds) and cached in data/reference/."""
    from nisar_water.config import load_aoi, load_paths
    from nisar_water.features.terrain import build_hand
    from nisar_water.grid import load_grid
    from nisar_water.io.raster import read

    p = load_paths()["reference"] / "hand.tif"
    if not p.exists():
        build_hand(load_grid("bbox"), load_aoi()["bbox_wsen"], p)
    return read(p)[0]


_MODELS: dict[str, tuple] = {}


def _supervised(features, params, train):
    """LightGBM / RF fitted once per variant on FIT-block samples; probability threshold chosen on VAL blocks."""
    from nisar_water.classify import supervised

    key = params.get("model_key", params["_variant"])  # variants differing only in post-processing share a fit
    names = params["features"]
    if key not in _MODELS:
        S = train.samples
        X, y = S["X"][S["is_fit"]][:, [S["names"].index(n) for n in names]], S["y"][S["is_fit"]]
        Xv, yv = S["X"][~S["is_fit"]][:, [S["names"].index(n) for n in names]], S["y"][~S["is_fit"]]
        model, t, vf1 = supervised.fit(params["model"], X, y, Xv, yv, params.get("model_params"))
        _MODELS[key] = (model, t, {"prob_threshold": round(t, 4), "val_f1_samples": round(vf1, 4),
                                   "importance": supervised.importance(model, names)})
    model, t, info = _MODELS[key]
    mask, prob = supervised.predict(model, features, names, t)
    post = params.get("post")
    if post:
        mask = _post_prob(prob, t, post)
        info = {**info, "post": post}
    return mask, info


def _post_prob(prob: np.ndarray, t: float, post: dict) -> np.ndarray:
    """Spatial post-processing of the water probability (fixed settings per variant, selected on VAL blocks):
    smooth: k -> k x k mean of the probability before thresholding at t (suppresses speckle-like flicker);
    hysteresis: {low, high} -> water = connected regions of prob > t - low that contain prob > t + high
    (recovers narrow channels/edges attached to confident water, drops isolated low-confidence specks)."""
    from scipy.ndimage import uniform_filter
    from skimage.filters import apply_hysteresis_threshold

    ok = np.isfinite(prob)
    p = np.where(ok, prob, 0).astype(np.float32)
    if post.get("smooth"):
        k = int(post["smooth"])
        w = uniform_filter(ok.astype(np.float32), k)
        p = np.where(w > 0, uniform_filter(p, k) / np.maximum(w, 1e-6), 0)
    if post.get("hysteresis"):
        h = post["hysteresis"]
        water = apply_hysteresis_threshold(p, low=t - float(h.get("low", 0.15)), high=t + float(h.get("high", 0.2)))
    else:
        water = p > t
    out = np.full(prob.shape, 255, np.uint8)
    out[ok] = water[ok]
    return out


METHODS = {"threshold": _threshold_method, "dualpol_and": _dualpol_and, "gmm": _gmm, "supervised": _supervised}


def _val_blocks(shape, block_px: int, fraction: float, seed: int = 7) -> np.ndarray:
    """Boolean raster: a random `fraction` of the R00 TRAIN blocks held out as VAL (model/threshold selection)."""
    from nisar_water.config import load_paths
    from nisar_water.io.raster import read
    from nisar_water.validate.sampling import TRAIN

    blocks, _ = read(load_paths()["reference"] / "split_blocks.tif")
    nby, nbx = -(-shape[0] // block_px), -(-shape[1] // block_px)
    bid = (np.arange(shape[0])[:, None] // block_px) * nbx + np.arange(shape[1])[None, :] // block_px
    train_ids = np.unique(bid[blocks == TRAIN])
    rng = np.random.default_rng(seed)
    val_ids = rng.permutation(train_ids)[: int(round(fraction * train_ids.size))]
    return (blocks == TRAIN) & np.isin(bid, val_ids)


# --- task ---------------------------------------------------------------------------------------

def _second_band(cfg, sb: dict, date: str, ctx) -> dict[str, np.ndarray]:
    """Features of a second frequency (e.g. S-band) acquired on the same date, on the same canonical grid,
    prefixed (default 'S_'). Same pipeline as the first band: Lee filter with its own per-scene ENL, dB
    features, and (if configured) texture and scene-relative features from its own tiled-KI threshold."""
    from nisar_water.tasks.common import acq_date

    g = next((x for x in sb["granules"] if acq_date(x) == date), None)
    if g is None:
        raise ValueError(f"no {sb['band']}-band granule for {date}")
    c2 = cfg.model_copy(deep=True)
    c2.data.band, c2.data.terms = sb["band"], sb.get("terms", ["HHHH", "HVHV"])
    ds = load_scene(c2, g, ctx)
    spec = resolve_filter(sb.get("speckle", cfg.preprocess.speckle), ds["HHHH"].values)
    f = features_db(ds, spec)
    f, _ = to_canonical(f, dict(ds.attrs))
    st = cfg.extra.get("stack") or {}
    if st.get("texture"):
        from nisar_water.features.stack import texture
        f.update(texture(f))
    if st.get("relative"):
        from nisar_water.features.stack import relative
        t, _ = threshold.tiled(f["HH"], **st["relative"])
        f.update(relative(f, t))
        ctx.log.info("%s %s-band: ENL %.2f, scene threshold %.2f dB", date, sb["band"], spec.get("looks", np.nan), t)
    pre = sb.get("prefix", f"{sb['band']}_")
    return {pre + k: v for k, v in f.items()}


def _variants(cfg) -> list[dict]:
    if cfg.extra.get("variants"):
        return cfg.extra["variants"]
    return [{"name": cfg.method.name, "method": cfg.method.name, "params": cfg.method.params}]


def run(ctx) -> None:
    cfg, extra = ctx.cfg, ctx.cfg.extra
    if not cfg.data.granules:
        raise ValueError("config data.granules is empty")
    variants = _variants(cfg)
    _TUNED_CACHE.clear()

    # pass 1: features per date (+ pooled train samples for methods that tune)
    scenes, train_w, train_l = {}, {}, {}
    for g in cfg.data.granules:
        ds = load_scene(cfg, g, ctx)
        if extra.get("features") == "compact":
            from nisar_water.features.compact import features_compact
            spec = cfg.preprocess.speckle
            feats = features_compact(ds, spec)
        elif extra.get("features") == "polsar":
            from nisar_water.features.polsar import features_polsar
            spec = cfg.preprocess.speckle
            feats = features_polsar(ds, spec)
        else:
            spec = resolve_filter(cfg.preprocess.speckle, ds["HHHH"].values)
            feats = features_db(ds, spec)
        feats, attrs = to_canonical(feats, dict(ds.attrs))
        date = ds.attrs["date"]
        if extra.get("second_band"):
            feats.update(_second_band(cfg, extra["second_band"], date, ctx))
        scenes[date] = (attrs, feats, spec.get("looks"))
        tr_ref = load_reference(cfg.validation.reference, date, "train") if cfg.validation.reference else None
        if tr_ref is not None:
            for k, v in feats.items():
                ok = np.isfinite(v)
                train_w.setdefault(k, []).append(v[(tr_ref == 1) & ok])
                train_l.setdefault(k, []).append(v[(tr_ref == 0) & ok])
        ctx.log.info("%s: features ready (ENL %s)", date, spec.get("looks"))
    train = TrainData({k: np.concatenate(v) for k, v in train_w.items()},
                      {k: np.concatenate(v) for k, v in train_l.items()})

    if extra.get("separability"):
        # per-feature water/land separability on pooled TRAIN pixels: JM distance and best single-threshold F1
        from nisar_water.tasks.separability import jm_distance
        rng = np.random.default_rng(0)
        sep = []
        for k in train.water:
            w, l = train.water[k], train.land[k]
            w, l = w[np.isfinite(w)], l[np.isfinite(l)]
            w = rng.choice(w, min(w.size, 500_000), replace=False)
            l = rng.choice(l, min(l.size, 500_000), replace=False)
            f1, t, d = best_threshold_f1(w, l)
            sep.append({"feature": k, "jm": jm_distance(w, l), "best_f1_train": f1, "threshold": t, "water_is": d,
                        "water_p50": float(np.median(w)), "land_p50": float(np.median(l))})
        sep = pd.DataFrame(sep).sort_values("best_f1_train", ascending=False)
        (ctx.run_dir / "tables").mkdir(exist_ok=True)
        sep.to_csv(ctx.run_dir / "tables" / "separability.csv", index=False)
        ctx.metrics["separability_table"] = sep.to_markdown(index=False, floatfmt=".3f")

    # optional contextual stack (L07): texture per date, temporal stats over all dates, HAND
    st = extra.get("stack") or {}
    if st:
        from nisar_water.features.stack import temporal, texture
        tstats = temporal({k: [f[k] for _, f, _ in scenes.values()] for k in ("HH", "HV")}) if st.get("temporal") else {}
        hand_f = _hand().astype(np.float32) if st.get("hand") else None
        for date, (attrs, feats, enl) in scenes.items():
            if st.get("texture"):
                feats.update(texture(feats))
            if st.get("relative"):
                from nisar_water.features.stack import relative
                t_scene, _ = threshold.tiled(feats["HH"], **st["relative"])
                feats.update(relative(feats, t_scene))
                attrs["scene_threshold_db"] = float(t_scene)
            feats.update(tstats)
            if "HH_tmed" in feats:
                feats["HH_anom"] = (feats["HH"] - feats["HH_tmed"]).astype(np.float32)
            if hand_f is not None:
                feats["HAND"] = hand_f
        ctx.log.info("feature stack: %s", sorted(next(iter(scenes.values()))[1]))
    val = None
    if extra.get("val_fraction"):
        shape = next(iter(scenes.values()))[1]["HH"].shape
        val = _val_blocks(shape, int(extra.get("block_px", 200)), float(extra["val_fraction"]))
        train.samples = _samples(cfg, scenes, val, int(extra.get("samples_per_date", 150_000)))
        ctx.log.info("samples: %d (fit %d, val %d, water %.3f)", len(train.samples["y"]), train.samples["is_fit"].sum(),
                     (~train.samples["is_fit"]).sum(), train.samples["y"].mean())
    _MODELS.clear()

    # pass 2: classify + evaluate
    hand = _hand() if any("hand_max_m" in v.get("refine", {}) for v in variants) else None

    rows = []
    for var in variants:
        for date, (attrs, feats, enl) in scenes.items():
            mask, diag = METHODS[var["method"]](feats, {**var.get("params", {}), "_variant": var["name"]}, train)
            imp = diag.pop("importance", None)
            if imp is not None:
                ctx.metrics.setdefault("importance", {})[var["name"]] = imp
            if var.get("refine"):
                mask = refine(mask, **var["refine"], hand=hand)
            tr, epsg, res = attrs["transform"], attrs["epsg"], attrs["spacing_m"][0]
            write_cog(mask, ctx.outputs / var["name"] / f"water_{date}.tif", tr, epsg,
                      tags={"date": date, "source": attrs["source"], "variant": var["name"], **diag})
            row = {"variant": var["name"], "date": date, **{k: v for k, v in diag.items() if not isinstance(v, dict)},
                   "water_km2": float((mask == 1).sum() * res * attrs["spacing_m"][1] / 1e6)}
            ref = load_reference(cfg.validation.reference, date, cfg.validation.split) if cfg.validation.reference else None
            if ref is not None:
                m = evaluate(mask, ref)
                row.update({k: m[k] for k in ("f1", "iou", "precision", "recall", "overall_accuracy", "kappa")})
                row.update({f"cm_{k}": v for k, v in m["confusion"].items()})
            if val is not None:
                tr_ref = load_reference(cfg.validation.reference, date, "train")
                if tr_ref is not None:
                    vref = np.where(val, tr_ref, 255).astype(np.uint8)
                    row.update({f"val_cm_{k}": v for k, v in evaluate(mask, vref)["confusion"].items()})
            if extra.get("select_on_train"):
                tr_ref = load_reference(cfg.validation.reference, date, "train")
                if tr_ref is not None:
                    row.update({f"train_cm_{k}": v for k, v in evaluate(mask, tr_ref)["confusion"].items()})
            if extra.get("compare_reference"):
                # cross-sensor agreement (e.g. S1), all pixels: a consistency check for dates without S2, NOT accuracy
                cmp_ref = load_reference(extra["compare_reference"], date, "all")
                if cmp_ref is not None:
                    m = evaluate(mask, cmp_ref)
                    row.update({"cmp_f1": m["f1"], "cmp_precision": m["precision"], "cmp_recall": m["recall"],
                                "cmp_water_km2": float((cmp_ref == 1).sum() * res * attrs["spacing_m"][1] / 1e6)})
            rows.append(row)
            if date == extra.get("plot_date"):
                _map(mask, attrs, date, var["name"], cfg, ctx.figures / f"water_{var['name']}_{date}.png")
            ctx.log.info("%s %s: %s", var["name"], date,
                         {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items() if k in ("threshold_db", "f1", "iou")})

    if _MODELS:
        # fitted models for production (L10): {model, threshold, feature names, filter spec}
        import joblib
        for v in variants:
            if v["name"] in _MODELS:
                model, t, info = _MODELS[v["name"]]
                joblib.dump({"model": model, "threshold": t, "features": v["params"]["features"],
                             "speckle": cfg.preprocess.speckle, "stack": extra.get("stack"), "refine": v.get("refine")},
                            ctx.outputs / v["name"] / "model.joblib")

    df = pd.DataFrame(rows)
    (ctx.run_dir / "tables").mkdir(exist_ok=True)
    if extra.get("bootstrap") and cfg.validation.reference:
        # spatial-block bootstrap of test F1 (pooled over referenced dates) and of differences vs a baseline
        from nisar_water.io.raster import read
        from nisar_water.validate.bootstrap import block_ids, bootstrap_f1, per_block_cm
        bs = extra["bootstrap"]
        cms = {}
        for var in variants:
            parts = []
            for date in scenes:
                ref = load_reference(cfg.validation.reference, date, cfg.validation.split)
                tif = ctx.outputs / var["name"] / f"water_{date}.tif"
                if ref is None or not tif.exists():
                    continue
                pred, _ = read(tif)
                cm = per_block_cm(pred, ref, block_ids(ref.shape, int(extra.get("block_px", 200))))
                cm.index = [f"{date}_{b}" for b in cm.index]
                parts.append(cm)
            if parts:
                cms[var["name"]] = pd.concat(parts)
        bt = bootstrap_f1(cms, bs["baseline"], int(bs.get("n", 2000)))
        bt.to_csv(ctx.run_dir / "tables" / "bootstrap_f1.csv")
        ctx.metrics.setdefault("extra_tables_bt", bt.to_markdown(floatfmt=".3f"))
    df.to_csv(ctx.run_dir / "tables" / "scores.csv", index=False)
    _summarise(df, ctx)


def _samples(cfg, scenes, val, per_date: int, seed: int = 42) -> dict:
    """Random TRAIN-block pixels per referenced date (all stack features finite), tagged FIT or VAL."""
    rng = np.random.default_rng(seed)
    names = sorted(next(iter(scenes.values()))[1])
    Xs, ys, fits = [], [], []
    for date, (_, feats, _) in scenes.items():
        ref = load_reference(cfg.validation.reference, date, "train") if cfg.validation.reference else None
        if ref is None:
            continue
        ok = ref != 255
        for k in names:
            ok &= np.isfinite(feats[k])
        idx = np.flatnonzero(ok.ravel())
        idx = rng.choice(idx, min(per_date, idx.size), replace=False)
        Xs.append(np.stack([feats[k].ravel()[idx] for k in names], 1).astype(np.float32))
        ys.append(ref.ravel()[idx].astype(np.uint8))
        fits.append(~val.ravel()[idx])
    return {"X": np.concatenate(Xs), "y": np.concatenate(ys), "is_fit": np.concatenate(fits), "names": names}


def _summarise(df: pd.DataFrame, ctx) -> None:
    scored = df.dropna(subset=["f1"]) if "f1" in df else df.iloc[0:0]
    if scored.empty:
        ctx.metrics["headline"] = {"name": "no reference: mean water km²", "value": float(df["water_km2"].mean())}
        return
    # pooled metrics: sum the confusion matrices over dates (each date weighted by its scored pixels)
    pooled = scored.groupby("variant")[["cm_tp", "cm_fp", "cm_fn", "cm_tn"]].sum()
    pooled["f1_pooled"] = 2 * pooled.cm_tp / (2 * pooled.cm_tp + pooled.cm_fp + pooled.cm_fn)
    pooled["iou_pooled"] = pooled.cm_tp / (pooled.cm_tp + pooled.cm_fp + pooled.cm_fn)
    summary = scored.groupby("variant")[["f1", "iou", "precision", "recall"]].mean().add_suffix("_mean")
    summary = summary.join(pooled[["f1_pooled", "iou_pooled"]])
    if "val_cm_tp" in scored:
        # model selection on held-out VAL blocks (a subset of train blocks never used for fitting)
        t = scored.groupby("variant")[["val_cm_tp", "val_cm_fp", "val_cm_fn"]].sum()
        summary["val_f1_pooled"] = 2 * t.val_cm_tp / (2 * t.val_cm_tp + t.val_cm_fp + t.val_cm_fn)
        summary = summary.sort_values("val_f1_pooled", ascending=False)
    elif "train_cm_tp" in scored:
        # model selection on TRAIN blocks; test scores are reported, not used to choose
        t = scored.groupby("variant")[["train_cm_tp", "train_cm_fp", "train_cm_fn"]].sum()
        summary["train_f1_pooled"] = 2 * t.train_cm_tp / (2 * t.train_cm_tp + t.train_cm_fp + t.train_cm_fn)
        summary = summary.sort_values("train_f1_pooled", ascending=False)
    else:
        summary = summary.sort_values("f1_pooled", ascending=False)
    best = summary.index[0]
    _f1_plot(scored, list(summary.index), ctx.figures / "f1_by_date.png")
    if "cmp_f1" in df:
        cmp = df.pivot(index="date", columns="variant", values="cmp_f1")
        area = df.pivot(index="date", columns="variant", values="water_km2")
        area["comparison_reference_km2"] = df.groupby("date")["cmp_water_km2"].first()
        ctx.metrics.setdefault("tables", {})
        ctx.metrics["extra_tables"] = {
            "Agreement with comparison reference (F1, all pixels; consistency, not accuracy)": cmp.to_markdown(floatfmt=".3f"),
            "Mapped water area per date (km²)": area.to_markdown(floatfmt=".1f"),
        }
    ctx.metrics.update({
        "headline": {"name": f"selected variant = {best} ({'chosen on val' if 'val_f1_pooled' in summary else 'chosen on train' if 'train_f1_pooled' in summary else 'best'}; test F1 pooled)",
                     "value": float(summary.loc[best, "f1_pooled"])},
        "best_variant": best,
        "tables": {
            "Test-block scores by variant (mean over dates, and pooled confusion matrix)": summary.to_markdown(floatfmt=".3f"),
            **ctx.metrics.pop("extra_tables", {}),
            **({"Spatial-block bootstrap (2 km test blocks, 2000 draws): F1 and difference vs baseline, 95 % intervals": ctx.metrics.pop("extra_tables_bt")}
               if "extra_tables_bt" in ctx.metrics else {}),
            **({"Per-feature separability on TRAIN pixels (JM, best single-threshold F1)": ctx.metrics.pop("separability_table")}
               if "separability_table" in ctx.metrics else {}),
            **({"Feature importance (gain share)": pd.DataFrame(ctx.metrics["importance"]).to_markdown(floatfmt=".3f")}
               if ctx.metrics.get("importance") else {}),
            "Per date": scored[["variant", "date"] + [c for c in ("threshold_db", "f1", "iou", "precision", "recall", "water_km2")
                                                       if c in scored]].to_markdown(index=False, floatfmt=".3f"),
        },
    })


def _map(mask, attrs, date, name, cfg, path) -> None:
    save_categorical(mask, attrs["transform"], attrs["epsg"], path, title=f"Water mask — {name} — {date}",
                     dates=date, resolution_m=attrs["spacing_m"][0],
                     source=f"NISAR L2 GCOV {cfg.data.band}-band {cfg.data.frequency}, ASF DAAC", classes=WATER_CLASSES)


def _f1_plot(df: pd.DataFrame, order: list[str], path) -> None:
    """Dot plot: test F1 per date (x) for each variant (fixed colour order, direct labels on the last date)."""
    if len(order) > len(VARIANT_COLOURS):
        order = order[:len(VARIANT_COLOURS)]  # never cycle colours: plot the best variants only
    dates = sorted(df["date"].unique())
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, v in enumerate(order):
        sub = df[df["variant"] == v].set_index("date").reindex(dates)
        ax.plot(range(len(dates)), sub["f1"], color=VARIANT_COLOURS[i], linewidth=2, marker="o", markersize=8,
                markeredgecolor="#fcfcfb", markeredgewidth=1.5, label=v, zorder=3)
    ax.set_xticks(range(len(dates)), dates, fontsize=8)
    ax.set_ylabel("F1 (test blocks)", color=MUTED, fontsize=9)
    ax.set_title("Water-mask F1 per date and variant", color=TEXT, fontsize=10, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color=GRID_C, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
