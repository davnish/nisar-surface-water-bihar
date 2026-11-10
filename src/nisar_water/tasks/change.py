"""L09: date-to-date water change (problem statement section 6) and its assessment.

Methods (extra.methods):
- pcc: post-classification comparison of two single-date water masks from a mapping experiment.
- logratio: change from the HH log-ratio r = HH_later - HH_earlier (dB, Lee filtered). The earlier date's
  mask gives the starting state; a pixel changes only where |r| exceeds `t_db` in the physically expected
  direction (darkening -> water gain, brightening -> water loss). This suppresses the date-independent
  false positives (e.g. dark sand) that PCC carries over from both masks.

Assessment: for pairs where both dates have an S2 reference, the change classes are compared with the
S2-derived change map on TEST blocks (per-class F1 for gain and loss, overall accuracy). For every pair we
report the area of each class and the newly detected water outside persistent water (Task E). Also
writes per-date water area and a water-occurrence map (% of dates classified water).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nisar_water import REPO_ROOT
from nisar_water.change.classes import (LABELS, NODATA, STABLE_NONWATER, STABLE_WATER, WATER_GAIN, WATER_LOSS,
                                        change_map, new_water_outside_persistent)
from nisar_water.config import load_paths
from nisar_water.features.pol import features_db, resolve_filter
from nisar_water.io.raster import read, write_cog
from nisar_water.report import latest_run
from nisar_water.tasks.common import acq_date, load_reference, load_scene
from nisar_water.viz.maps import save_categorical, save_continuous

CHANGE_CLASSES = {STABLE_NONWATER: ("Stable non-water", "#d9d6cc"), STABLE_WATER: ("Stable water", "#2a78d6"),
                  WATER_GAIN: ("Newly detected water (gain)", "#1baf7a"),
                  WATER_LOSS: ("Water loss (receded)", "#eb6834")}
NEW_WATER_CLASSES = {0: ("Other", "#d9d6cc"), 1: ("Persistent water", "#2a78d6"),
                     2: ("New water outside persistent water", "#eda100")}


def _masks(spec: dict) -> dict[str, tuple[np.ndarray, tuple, int]]:
    run = REPO_ROOT / spec["run"] if spec.get("run") else latest_run(REPO_ROOT / "experiments" / spec["experiment"])
    out = {}
    for p in sorted((run / "outputs" / spec["variant"]).glob("water_*.tif")):
        arr, prof = read(p)
        out[p.stem.removeprefix("water_")] = (arr, tuple(prof["transform"])[:6], prof["epsg"])
    if not out:
        raise FileNotFoundError(f"no water masks in {run}/outputs/{spec['variant']}")
    return out, run


def _logratio_change(early_mask: np.ndarray, r_db: np.ndarray, t_db: float) -> np.ndarray:
    out = np.full(early_mask.shape, NODATA, np.uint8)
    ok = (early_mask != NODATA) & np.isfinite(r_db)
    w = early_mask == 1
    out[ok & ~w] = STABLE_NONWATER
    out[ok & w] = STABLE_WATER
    out[ok & ~w & (r_db < -t_db)] = WATER_GAIN
    out[ok & w & (r_db > t_db)] = WATER_LOSS
    return out


def _class_scores(pred: np.ndarray, ref: np.ndarray) -> dict:
    ok = (pred != NODATA) & (ref != NODATA)
    p, r = pred[ok], ref[ok]
    res = {"n": int(ok.sum()), "oa": float((p == r).mean()) if ok.any() else np.nan}
    for c, name in ((WATER_GAIN, "gain"), (WATER_LOSS, "loss"), (STABLE_WATER, "stable_water")):
        tp, fp, fn = np.sum((p == c) & (r == c)), np.sum((p == c) & (r != c)), np.sum((p != c) & (r == c))
        res[f"{name}_f1"] = float(2 * tp / (2 * tp + fp + fn)) if (tp + fp + fn) else np.nan
        res[f"{name}_precision"] = float(tp / (tp + fp)) if (tp + fp) else np.nan
        res[f"{name}_recall"] = float(tp / (tp + fn)) if (tp + fn) else np.nan
    return res


def run(ctx) -> None:
    cfg, p = ctx.cfg, ctx.cfg.extra
    tables = ctx.run_dir / "tables"
    tables.mkdir(exist_ok=True)
    masks, src_run = _masks(p["masks"])
    # optional extra mask sources for side-by-side comparison (e.g. L-only / S-only / L+S): method spec {"source": label}
    sources = {m["label"]: _masks(m)[0] for m in p.get("mask_sources", [])}
    ctx.log.info("masks: %s / %s (%d dates)", src_run, p["masks"]["variant"], len(masks))
    pers_path = (REPO_ROOT / p["persistent"]) if p.get("persistent") else load_paths()["reference"] / "persistent_water.tif"
    if p.get("persistent_from_run"):
        pers_path = src_run / "outputs" / "persistent_water.tif"
    persistent, _ = read(pers_path)
    pers_src = ("NISAR dry-season water ∪ JRC ≥50% (" + p["masks"].get("experiment", "") + ")") if p.get("persistent_from_run") \
        else "dry-season S2 (R00)"
    any_arr, transform, epsg = next(iter(masks.values()))
    px_km2 = abs(transform[0] * transform[4]) / 1e6
    source = f"NISAR L2 GCOV L-band (ASF DAAC); masks: {p['masks'].get('experiment', '')} {p['masks']['variant']}"

    # per-date area + occurrence
    area = pd.DataFrame([{"date": d, "water_km2": float((m == 1).sum() * px_km2),
                          "valid_km2": float((m != NODATA).sum() * px_km2)} for d, (m, _, _) in masks.items()])
    area.to_csv(tables / "water_area_by_date.csv", index=False)
    # incremental counts (a full-frame stack of all dates would not fit in memory)
    valid = np.zeros(any_arr.shape, np.uint8)
    wet = np.zeros(any_arr.shape, np.uint8)
    for m, _, _ in masks.values():
        valid += m != NODATA
        wet += m == 1
    with np.errstate(invalid="ignore", divide="ignore"):
        occ = np.where(valid > 0, np.float32(100) * wet / np.maximum(valid, 1), np.nan).astype(np.float32)
    del wet
    write_cog(occ, ctx.outputs / "water_occurrence_pct.tif", transform, epsg,
              tags={"dates": ",".join(masks), "units": "% of valid dates classified water"})
    dates_all = list(masks)
    dec = max(1, occ.shape[0] // 2000)
    save_continuous(occ[::dec, ::dec], (transform[0] * dec, 0, transform[2], 0, transform[4] * dec, transform[5]), epsg, ctx.figures / "water_occurrence.png",
                    title=f"Water occurrence over {len(dates_all)} dates (% of dates)", dates=f"{dates_all[0]} – {dates_all[-1]}",
                    resolution_m=abs(transform[0]), source=source, label="% of dates water", vmin=0, vmax=100,
                    cmap="Blues")

    # HH (dB) per date, needed only for the log-ratio method
    hh = {}
    if any(mp.get("kind", m) == "logratio" for m, mp in p["methods"].items()):
        for g in cfg.data.granules:
            d = acq_date(g)
            if d in masks:
                ds = load_scene(cfg, g, ctx)
                hh[d] = features_db(ds, resolve_filter(cfg.preprocess.speckle, ds["HHHH"].values))["HH"]

    rows, assess = [], []
    for pair in p["pairs"]:
        e, l = pair["dates"]
        if e not in masks or l not in masks or any(e not in m or l not in m for m in sources.values()):
            ctx.log.warning("pair %s-%s: missing mask, skipped", e, l)
            continue
        for method, mp in p["methods"].items():
            kind = mp.get("kind", method)
            mm = sources[mp["source"]] if mp.get("source") else masks
            if kind == "pcc":
                ch = change_map(mm[e][0], mm[l][0])
            elif kind == "logratio":
                ch = _logratio_change(masks[e][0], hh[l] - hh[e], float(mp["t_db"]))
            else:
                raise NotImplementedError(method)
            name = f"{method}_{e}_{l}"
            new = new_water_outside_persistent(ch, persistent)
            write_cog(ch, ctx.outputs / method / f"change_{e}_{l}.tif", transform, epsg,
                      tags={"earlier": e, "later": l, "method": method,
                            "classes": "0 stable non-water, 1 stable water, 2 gain, 3 loss, 255 nodata"})
            nw = np.where(ch == NODATA, 255, np.where(new, 2, np.where(persistent == 1, 1, 0))).astype(np.uint8)
            write_cog(nw, ctx.outputs / method / f"new_water_{e}_{l}.tif", transform, epsg,
                      tags={"earlier": e, "later": l, "classes": "0 other, 1 persistent water, 2 new water outside persistent"})
            row = {"pair": pair.get("label", f"{e}→{l}"), "earlier": e, "later": l, "method": method,
                   **{LABELS[c] + " (km²)": float((ch == c).sum() * px_km2) for c in LABELS},
                   "New water outside persistent (km²)": float(new.sum() * px_km2)}
            rows.append(row)
            if pair.get("plot"):
                title = f"Water change {e} → {l} ({method.upper()})"
                dec = max(1, ch.shape[0] // 2000)
                ftr = (transform[0] * dec, 0, transform[2], 0, transform[4] * dec, transform[5])
                save_categorical(ch[::dec, ::dec], ftr, epsg, ctx.figures / f"change_{name}.png", title=title, dates=f"{e}, {l}",
                                 resolution_m=abs(transform[0]), source=source, classes=CHANGE_CLASSES)
                save_categorical(nw[::dec, ::dec], ftr, epsg, ctx.figures / f"new_water_{name}.png",
                                 title=f"Newly detected water outside persistent water {e} → {l} ({method.upper()})",
                                 dates=f"{e}, {l}", resolution_m=abs(transform[0]), source=source + f"; persistent water: {pers_src}",
                                 classes=NEW_WATER_CLASSES)
            # assessment against S2-derived change where both dates have an S2 reference (TEST blocks)
            ref_pat = cfg.validation.reference
            s2e = load_reference(ref_pat, e, cfg.validation.split) if ref_pat else None
            s2l = load_reference(ref_pat, l, cfg.validation.split) if ref_pat else None
            if s2e is not None and s2l is not None:
                ref = change_map(s2e, s2l)
                sc = _class_scores(ch, ref)
                assess.append({"pair": row["pair"], "method": method, **sc,
                               "ref_gain_km2": float((ref == WATER_GAIN).sum() * px_km2),
                               "ref_loss_km2": float((ref == WATER_LOSS).sum() * px_km2),
                               "map_gain_km2_test": float(((ch == WATER_GAIN) & (ref != NODATA)).sum() * px_km2),
                               "map_loss_km2_test": float(((ch == WATER_LOSS) & (ref != NODATA)).sum() * px_km2)})
            ctx.log.info("%s: %s", name, {k: round(v, 2) for k, v in row.items() if isinstance(v, float)})

    df = pd.DataFrame(rows)
    df.to_csv(tables / "change_areas.csv", index=False)
    a = pd.DataFrame(assess)
    a.to_csv(tables / "change_assessment.csv", index=False)
    tabs = {"Change-class areas per pair (km², full bbox)": df.drop(columns=["earlier", "later"]).to_markdown(index=False, floatfmt=".2f"),
            "Water area per date (km²)": area.to_markdown(index=False, floatfmt=".2f")}
    head = {"name": "no S2-referenced pairs", "value": float("nan")}
    if not a.empty:
        tabs["Assessment vs S2-derived change (TEST blocks; S2 pairs only)"] = a.to_markdown(index=False, floatfmt=".3f")
        m = a.groupby("method")[["oa", "gain_f1", "loss_f1"]].mean()
        tabs["Mean over S2 pairs"] = m.to_markdown(floatfmt=".3f")
        best = m[["gain_f1", "loss_f1"]].mean(1).idxmax()
        head = {"name": f"best method = {best} (mean gain/loss F1 vs S2 change, test blocks)",
                "value": float(m.loc[best, ["gain_f1", "loss_f1"]].mean())}
    ctx.metrics.update({"headline": head, "source_run": str(src_run.relative_to(REPO_ROOT)), "tables": tabs})
