"""L01 channel separability: how well does each L-band feature separate water from land, per speckle filter?

For every date with an S2 reference, on TRAIN blocks only, with class interiors (edges eroded so mixed
pixels don't dominate):
- Jeffries-Matusita distance under a Gaussian class model (0..2; >~1.8 = well separable),
- the best F1 any single threshold on that feature can reach (an upper bound for threshold methods),
- class percentiles.
Also: an equivalent-number-of-looks (ENL) estimate from homogeneous land (needed by the Lee filter),
and an HV noise-floor check (water HV level vs. the NISAR NESZ requirement and across-range trend).
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import binary_erosion

from nisar_water.features.pol import estimate_enl, features_db
from nisar_water.preprocess.calibrate import to_db
from nisar_water.tasks.common import load_reference, load_scene

WATER_C, LAND_C, TEXT, MUTED, GRID_C = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"


def jm_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Jeffries-Matusita distance between two 1-D samples under a Gaussian model (Bhattacharyya-based)."""
    m1, m2, v1, v2 = a.mean(), b.mean(), a.var(), b.var()
    bd = (m1 - m2) ** 2 / (4 * (v1 + v2)) + 0.5 * np.log((v1 + v2) / (2 * np.sqrt(v1 * v2)))
    return float(2 * (1 - np.exp(-bd)))


def best_threshold_f1(water: np.ndarray, land: np.ndarray, n: int = 400) -> tuple[float, float, str]:
    """Best F1 for water over all single thresholds and both directions. Returns (f1, threshold, direction)."""
    lo, hi = np.percentile(np.concatenate([water, land]), [0.5, 99.5])
    ts = np.linspace(lo, hi, n)
    ws, ls = np.sort(water), np.sort(land)
    best = (0.0, float("nan"), "<")
    for direction in ("<", ">"):
        if direction == "<":
            tp = np.searchsorted(ws, ts)
            fp = np.searchsorted(ls, ts)
        else:
            tp = ws.size - np.searchsorted(ws, ts)
            fp = ls.size - np.searchsorted(ls, ts)
        fn = ws.size - tp
        f1 = 2 * tp / np.maximum(2 * tp + fp + fn, 1)
        i = int(np.argmax(f1))
        if f1[i] > best[0]:
            best = (float(f1[i]), float(ts[i]), direction)
    return best


def run(ctx) -> None:
    cfg, p = ctx.cfg, ctx.cfg.extra
    tables = ctx.run_dir / "tables"
    tables.mkdir(exist_ok=True)
    filters = p["filters"]
    erode = np.ones((2 * p["erode_px"] + 1,) * 2, bool)

    rows, noise_rows, enls = [], [], []
    for g in cfg.data.granules:
        ds = load_scene(cfg, g, ctx)
        date = ds.attrs["date"]
        ref = load_reference(cfg.validation.reference, date, cfg.validation.split)
        if ref is None:
            ctx.log.warning("%s: no reference, skipped", date)
            continue
        water = binary_erosion(ref == 1, erode)
        land = binary_erosion(ref == 0, erode)

        enl = estimate_enl(ds["HHHH"].values, land)  # land-only: L01 design reference value
        enls.append(enl)
        for spec in filters:
            spec = {**spec, "looks": enl} if spec["name"] == "lee" else spec
            name = _label(spec)
            for feat, arr in features_db(ds, spec).items():
                ok = np.isfinite(arr)
                w, l = arr[water & ok], arr[land & ok]
                f1, t, direction = best_threshold_f1(w, l)
                rows.append({"date": date, "filter": name, "feature": feat, "jm": jm_distance(w, l),
                             "best_f1": f1, "best_threshold_db": t, "water_is": direction,
                             "water_p05": np.percentile(w, 5), "water_p50": np.median(w), "water_p95": np.percentile(w, 95),
                             "land_p05": np.percentile(l, 5), "land_p50": np.median(l), "land_p95": np.percentile(l, 95),
                             "n_water": w.size, "n_land": l.size})

        # HV noise floor: water HV level and its trend across range (columns ~ range direction)
        hv = to_db(ds["HVHV"].values)
        cols = np.nonzero(water)[1]
        wv = hv[water]
        ok = np.isfinite(wv)
        slope = np.polyfit(cols[ok] * ds.attrs["spacing_m"][0] / 1000, wv[ok], 1)[0]
        noise_rows.append({"date": date, "hv_water_p50": float(np.median(wv[ok])),
                           "hv_water_p05": float(np.percentile(wv[ok], 5)),
                           "hh_water_p50": float(np.nanmedian(to_db(ds["HHHH"].values)[water])),
                           "hv_water_slope_db_per_km": float(slope)})
        if date == p["plot_date"]:
            _histograms(ds, water, land, date, p["plot_filter"], enl, ctx.figures / f"histograms_{date}.png")
            anatomy = _error_anatomy(ds, ref, p["plot_filter"], enl, date, ctx)
        ctx.log.info("%s: ENL %.1f", date, enl)

    df = pd.DataFrame(rows)
    df.to_csv(tables / "separability.csv", index=False)
    noise = pd.DataFrame(noise_rows)
    noise.to_csv(tables / "hv_noise_check.csv", index=False)

    mean = df.groupby(["feature", "filter"])[["jm", "best_f1"]].mean().reset_index()
    jm_tab = mean.pivot(index="feature", columns="filter", values="jm")[[_label(f) for f in filters]]
    f1_tab = mean.pivot(index="feature", columns="filter", values="best_f1")[[_label(f) for f in filters]]
    _heatmap(f1_tab, "Best single-threshold F1 (mean over dates, train blocks)", ctx.figures / "best_f1_heatmap.png")
    best = mean.sort_values(["best_f1", "jm"], ascending=False).iloc[0]
    ctx.metrics.update({
        "headline": {"name": f"best feature/filter = {best['feature']} / {best['filter']} (oracle F1)",
                     "value": float(best["best_f1"])},
        "enl_median": float(np.median(enls)),
        "nesz_requirement_db": p["nesz_requirement_db"],
        "tables": {
            "Jeffries-Matusita distance (mean over dates)": jm_tab.to_markdown(floatfmt=".3f"),
            "Best single-threshold F1 (mean over dates)": f1_tab.to_markdown(floatfmt=".3f"),
            "Per-date best threshold, unfiltered": df[df["filter"] == "none"][
                ["date", "feature", "best_f1", "best_threshold_db", "water_is", "water_p50", "land_p50"]
            ].to_markdown(index=False, floatfmt=".3f"),
            "HV noise-floor check (water pixels)": noise.to_markdown(index=False, floatfmt=".2f"),
            f"Error anatomy at the oracle HH threshold ({p['plot_date']}, {_label(p['plot_filter'])})":
                pd.DataFrame([anatomy]).T.rename(columns={0: "value"}).to_markdown(floatfmt=".3f"),
        },
    })


def _error_anatomy(ds, ref, filt, enl, date, ctx) -> dict:
    """Where does the best possible single HH threshold fail? Guides the context experiments (L04-L06)."""
    from scipy.ndimage import binary_dilation, label

    from nisar_water.viz.maps import save_categorical

    spec = {**filt, "looks": enl} if filt["name"] == "lee" else filt
    hh = features_db(ds, spec)["HH"]
    v = ref != 255
    f1, t, _ = best_threshold_f1(hh[v & (ref == 1)], hh[v & (ref == 0)])
    pred = hh < t
    tp, fp, fn = pred & (ref == 1), pred & (ref == 0), ~pred & (ref == 1)
    near = binary_dilation(ref == 1, iterations=2)
    lab, _ = label(ref == 1)
    wsize = np.bincount(lab.ravel())
    wsize[0] = 0
    lab2, _ = label(fp)
    fsize = np.bincount(lab2.ravel())
    fsize[0] = 0
    big_fp = fp & (fsize[lab2] >= 100)
    south = np.zeros(ref.shape, bool)
    south[int(0.75 * ref.shape[0]):] = True
    err = np.full(ref.shape, 255, np.uint8)
    err[v] = 0
    err[tp], err[fp], err[fn] = 1, 2, 3
    save_categorical(err, ds.attrs["transform"], ds.attrs["epsg"], ctx.figures / f"oracle_errors_{date}.png",
                     title=f"Oracle HH threshold {t:.1f} dB ({_label(filt)}) vs S2, train blocks — {date}",
                     dates=date, resolution_m=ds.attrs["spacing_m"][0],
                     source="NISAR L2 GCOV L-band (asc 98/14); reference Sentinel-2 MNDWI",
                     classes={0: ("True negative", "#e4e3df"), 1: ("True positive (water)", "#2a78d6"),
                              2: ("False positive", "#eb6834"), 3: ("False negative", "#1baf7a")})
    return {"oracle_threshold_db": t, "oracle_f1": f1, "tp_px": int(tp.sum()), "fp_px": int(fp.sum()),
            "fn_px": int(fn.sum()),
            "fp_share_within_20m_of_water": float((fp & near).sum() / fp.sum()),
            "fp_share_in_specks_lt_0.1ha": float((fsize[lab2] < 10)[fp].mean()),
            "fp_share_in_clusters_ge_1ha": float(big_fp.sum() / fp.sum()),
            "share_of_large_fp_in_southern_quarter": float((big_fp & south).sum() / max(big_fp.sum(), 1)),
            "fn_share_in_water_bodies_lt_0.5ha": float((fn & (wsize[lab] < 50)).sum() / fn.sum())}


def _label(spec: dict) -> str:
    return spec["name"] if spec["name"] == "none" else f"{spec['name']}{spec.get('size', '')}"


def _style(ax) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color=GRID_C, linewidth=0.6)
    ax.set_axisbelow(True)


def _histograms(ds, water, land, date, filt, enl, path) -> None:
    feats = {"none": features_db(ds, {"name": "none"}),
             _label(filt): features_db(ds, {**filt, "looks": enl} if filt["name"] == "lee" else filt)}
    fig, axes = plt.subplots(2, 3, figsize=(12, 6.5), sharey="row")
    for r, (fname, fs) in enumerate(feats.items()):
        for c, feat in enumerate(("HH", "HV", "HV-HH")):
            ax = axes[r, c]
            a = fs[feat]
            bins = np.linspace(*np.nanpercentile(a, [0.5, 99.5]), 120)
            for mask, colour, label in ((land, LAND_C, "land (S2)"), (water, WATER_C, "water (S2)")):
                v = a[mask & np.isfinite(a)]
                ax.hist(v, bins=bins, density=True, histtype="stepfilled", alpha=0.35, color=colour)
                ax.hist(v, bins=bins, density=True, histtype="step", linewidth=1.5, color=colour, label=label)
            ax.set_title(f"{feat} — {fname}", fontsize=9, color=TEXT, loc="left")
            ax.set_xlabel("dB", fontsize=8, color=MUTED)
            _style(ax)
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Water vs land γ0 distributions, {date} (S2 reference, train blocks, edges eroded)",
                 fontsize=10, x=0.01, ha="left", color=TEXT)
    fig.text(0.01, -0.01, "Source: NISAR L2 GCOV L-band freq A (asc 98/14, 10 m, EPSG:32645); reference: Sentinel-2 MNDWI",
             fontsize=7, color=MUTED)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _heatmap(tab: pd.DataFrame, title: str, path) -> None:
    fig, ax = plt.subplots(figsize=(1.2 * tab.shape[1] + 2, 0.6 * tab.shape[0] + 1.5))
    vals = tab.values
    im = ax.imshow(vals, cmap="Blues", vmin=np.floor(vals.min() * 20) / 20, vmax=1.0, aspect="auto")
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            v = vals[i, j]
            ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=8,
                    color="#fcfcfb" if v > (vals.min() + vals.max()) / 2 else TEXT)
    ax.set_xticks(range(tab.shape[1]), tab.columns, fontsize=8)
    ax.set_yticks(range(tab.shape[0]), tab.index, fontsize=8)
    ax.set_title(title, fontsize=10, loc="left", color=TEXT)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
