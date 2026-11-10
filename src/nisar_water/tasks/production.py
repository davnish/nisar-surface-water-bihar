"""L10: full-footprint production of the champion water classifier on whole GCOV frames.

The frames are processed in tiles (with a halo for the speckle filter and texture windows), entirely in
the same way as the bbox experiments: Lee 7x7 (per-scene ENL) -> dB features -> texture -> temporal
statistics over every date of the stack -> the fitted model from L07 (`extra.model`, a model.joblib).
To keep the run tractable on a laptop, features are computed at the native 10 m posting and the
classifier is evaluated on every k-th pixel (`out_res_m`, default 20 m): each output cell takes the
label of the 10 m sample at its upper-left corner (<= 5 m offset; documented in the outputs' tags).

Also writes, on the same output grid:
- persistent water = NISAR dry-season water (classified water on >= `persistent.min_dry` of the dry-season
  dates) OR JRC GSW occurrence >= `persistent.jrc_min_pct`;
- a consistency check on the bbox: the production map cropped to the bbox vs the S2 reference on TEST
  blocks at the sampled pixels (must reproduce the L07 bbox scores).
Change maps / areas are produced by the `change` task (L09 config pattern) pointed at this run.
"""
from __future__ import annotations

import time

import h5py
import joblib
import numpy as np
import pandas as pd

from nisar_water import REPO_ROOT
from nisar_water.classify.refine import refine
from nisar_water.config import load_aoi, load_paths
from nisar_water.features.pol import estimate_enl
from nisar_water.features.stack import temporal, texture
from nisar_water.grid import Grid, load_grid
from nisar_water.io.gcov import MASK_INVALID_VALUES, grid_path
from nisar_water.io.raster import write_cog
from nisar_water.preprocess import speckle
from nisar_water.preprocess.calibrate import to_db
from nisar_water.tasks.common import acq_date, load_reference
from nisar_water.validate.metrics import evaluate
from nisar_water.viz.maps import save_categorical

from nisar_water._npt import gcov as npt_gcov

WATER_CLASSES = {0: ("Non-water", "#d9d6cc"), 1: ("Water", "#2a78d6")}


def _frame_grid(files) -> tuple[tuple, tuple[int, int], int]:
    ref = None
    for p in files:
        with h5py.File(p, "r") as f:
            gp = grid_path(f)
            x, y = npt_gcov.get_grid_coordinates(f, gp)
            epsg = int(f[f"{gp}/projection"].attrs["epsg_code"])
            g = (float(x[0]), float(y[0]), float(x[1] - x[0]), float(y[1] - y[0]), len(y), len(x), epsg)
        if ref is None:
            ref = g
        elif g != ref:
            raise ValueError(f"{p.name}: frame grid {g} differs from {ref}; resampling not implemented")
    x0, y0, dx, dy, ny, nx, epsg = ref
    transform = (dx, 0.0, x0 - dx / 2, 0.0, dy, y0 - dy / 2)
    return transform, (ny, nx), epsg


def _read(f, gp, term, r0, r1, c0, c1, invalid) -> np.ndarray:
    a = npt_gcov.read_window(f, f"{gp}/{term}", r0, r1, c0, c1).astype(np.float32)
    a[invalid | ~np.isfinite(a)] = np.nan
    return a


def regularise_tile_thresholds(df: pd.DataFrame, min_tiles: int = 3, max_dev_db: float = 3.0,
                               radius: int = 2) -> pd.DataFrame:
    """Per date, keep tile thresholds that are bimodal (tiles_used >= min_tiles) and within max_dev_db of the
    date's median of such tiles; replace every other tile (fallback, or an outlier, e.g. KI splitting the land
    histogram at -10 dB in a tile with little water) by the median of the kept tiles within `radius` tiles
    (Chebyshev), else the date median. Adds columns t_raw, kept."""
    out = []
    for d, g in df.groupby("date"):
        g = g.copy()
        g["t_raw"] = g["t_db"]
        bim = g.tiles_used >= min_tiles
        med = float(g.loc[bim, "t_db"].median()) if bim.any() else float(g["t_db"].median())
        kept = bim & ((g["t_db"] - med).abs() <= max_dev_db)
        g["kept"] = kept
        T = np.diff(np.unique(g.r0))[0] if g.r0.nunique() > 1 else 1
        K = g[kept]
        for i in g.index[~kept]:
            near = K[((K.r0 - g.at[i, "r0"]).abs() <= radius * T) & ((K.c0 - g.at[i, "c0"]).abs() <= radius * T)]
            g.at[i, "t_db"] = float(near["t_db"].median()) if len(near) else med
        out.append(g)
    return pd.concat(out)


def edge_mask(h, gp, step: int = 16, zero_db: float = -60.0, buffer_m: float = 10_000.0, posting_m: float = 10.0):
    """Coarse (every `step`-th 10 m pixel) mask of pixels to drop at the swath edge: the GCOV `mask` layer marks
    a strip of near-zero power (< zero_db, e.g. -146 dB) at far range as valid, and backscatter ramps down over
    ~7 km towards it (antenna pattern), which reads as water. Drops everything within buffer_m of such pixels."""
    from scipy.ndimage import distance_transform_edt
    a = h[f"{gp}/HHHH"][::step, ::step].astype(np.float32)
    m = h[f"{gp}/mask"][::step, ::step]
    valid = ~np.isin(m, MASK_INVALID_VALUES) & np.isfinite(a)
    with np.errstate(divide="ignore", invalid="ignore"):
        zero = valid & ~(10 * np.log10(np.where(a > 0, a, 1e-30)) > zero_db)
    if not zero.any():
        return np.zeros_like(zero)
    return distance_transform_edt(~zero) * step * posting_m <= buffer_m


def run(ctx) -> None:
    cfg, p = ctx.cfg, ctx.cfg.extra
    bundle = joblib.load(REPO_ROOT / p["model"])
    model, thr, names = bundle["model"], bundle["threshold"], bundle["features"]
    thr = float(p.get("prob_threshold", thr))  # L13: stricter cut-off for transfer outside the training box
    lee = {k: v for k, v in bundle["speckle"].items() if k != "looks"}
    raw = load_paths()[f"raw_nisar_{cfg.data.band}"]
    files = [raw / (g if g.endswith(".h5") else f"{g}.h5") for g in cfg.data.granules]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"granules not downloaded: {missing}")
    dates = [acq_date(g) for g in cfg.data.granules]
    ctx.inputs.extend(files)
    tr10, shape10, epsg = _frame_grid(files)
    k = int(round(p.get("out_res_m", 20) / tr10[0]))
    oshape = (shape10[0] // k, shape10[1] // k)
    otr = (tr10[0] * k, 0.0, tr10[2], 0.0, tr10[4] * k, tr10[5])
    ctx.log.info("frame %s at %g m -> output %s at %g m; %d dates; model %s (%d features, threshold %.3f)",
                 shape10, tr10[0], oshape, otr[0], len(dates), p["model"], len(names), thr)

    hs = [h5py.File(f, "r") for f in files]
    gps = [grid_path(h) for h in hs]
    # per-scene ENL from a central 2048 x 2048 window (reference-free, as in the bbox runs)
    cy, cx = shape10[0] // 2, shape10[1] // 2
    enl = []
    for h, gp in zip(hs, gps):
        r0, r1, c0, c1 = cy - 1024, cy + 1024, cx - 1024, cx + 1024
        inv = np.isin(h[f"{gp}/mask"][r0:r1, c0:c1], MASK_INVALID_VALUES)
        enl.append(estimate_enl(_read(h, gp, "HHHH", r0, r1, c0, c1, inv)))
    ctx.log.info("ENL per date: %s", dict(zip(dates, np.round(enl, 2))))
    em_cfg = p.get("edge_mask")
    edges, estep = None, 1
    if em_cfg:
        estep = int(em_cfg.get("step", 16))
        edges = [edge_mask(h, gp, step=estep, zero_db=float(em_cfg.get("zero_db", -60)),
                           buffer_m=float(em_cfg.get("buffer_m", 10_000)), posting_m=tr10[0]) for h, gp in zip(hs, gps)]
        ctx.log.info("edge mask (km² dropped per date): %s",
                     {d: round(float(e.sum()) * (estep * tr10[0]) ** 2 / 1e6, 1) for d, e in zip(dates, edges)})
    tile_t = {}
    if p.get("tile_thresholds"):
        tt = p["tile_thresholds"]
        reg = regularise_tile_thresholds(pd.read_csv(REPO_ROOT / tt["from"]), min_tiles=int(p.get("min_tiles", 3)),
                                         max_dev_db=float(tt.get("max_dev_db", 3.0)), radius=int(tt.get("radius", 2)))
        (ctx.run_dir / "tables").mkdir(exist_ok=True)
        reg.to_csv(ctx.run_dir / "tables" / "tile_thresholds_regularised.csv", index=False)
        tile_t = {(r.date, int(r.r0), int(r.c0)): float(r.t_db) for r in reg.itertuples()}
        ctx.log.info("tile thresholds from %s: %d replaced of %d", tt["from"], int((~reg.kept).sum()), len(reg))

    stack_cfg = bundle.get("stack") or {}
    rel_cfg = stack_cfg.get("relative")
    fallback_t = {}
    if rel_cfg:
        # fallback scene threshold per date (tiles without bimodal water/land sub-tiles): the bbox C1 threshold
        sc = pd.read_csv(REPO_ROOT / p["fallback_thresholds"])
        fallback_t = sc[sc.variant == p.get("fallback_variant", "C2")].set_index("date")["threshold_db"].to_dict()
    t_rows = []
    # parallel runs: `shard: [i, n]` processes every n-th tile into an on-disk label stack and stops;
    # `merge_shards: [run dirs]` skips the tile loop, merges those stacks and runs the normal post-processing
    shard, merge = p.get("shard"), p.get("merge_shards")
    if shard:
        out = np.lib.format.open_memmap(ctx.outputs / "label_stack.npy", mode="w+", dtype=np.uint8,
                                        shape=(len(dates),) + oshape)
        out[:] = 255
    else:
        out = np.full((len(dates),) + oshape, 255, np.uint8)
    if merge:
        for sd in merge:
            m = np.load(REPO_ROOT / sd / "outputs" / "label_stack.npy", mmap_mode="r")
            for di in range(len(dates)):
                part = np.asarray(m[di])
                sel = part != 255
                out[di][sel] = part[sel]
            del m
            tp = REPO_ROOT / sd / "tables" / "tile_thresholds.csv"
            if tp.exists():
                t_rows += pd.read_csv(tp).to_dict("records")
        ctx.log.info("merged label stacks of %d shards", len(merge))
    T, pad = int(p.get("tile", 2048)), int(p.get("pad", 32))
    assert T % k == 0 and pad % k == 0
    t_start, n_tiles = time.time(), 0
    tiles = [(r, c) for r in range(0, shape10[0], T) for c in range(0, shape10[1], T)]
    bg0 = load_grid("bbox")
    b_r0 = int(round((bg0.transform[5] - tr10[5]) / tr10[4]))
    b_c0 = int(round((bg0.transform[2] - tr10[2]) / tr10[0]))
    if p.get("only_bbox_tiles"):  # smoke test: only tiles overlapping the reference bbox
        tiles = [(r, c) for r, c in tiles if r < b_r0 + bg0.shape[0] and r + T > b_r0 and c < b_c0 + bg0.shape[1] and c + T > b_c0]
    if shard:
        tiles = tiles[int(shard[0])::int(shard[1])]
    if merge:
        tiles = []
    ctx.log.info("bbox at 10 m rows %d.., cols %d..; %d tiles to process", b_r0, b_c0, len(tiles))
    for ti, (r0, c0) in enumerate(tiles):
        r1, c1 = min(r0 + T, shape10[0]), min(c0 + T, shape10[1])
        R0, R1, C0, C1 = max(0, r0 - pad), min(shape10[0], r1 + pad), max(0, c0 - pad), min(shape10[1], c1 + pad)
        invs = [np.isin(h[f"{gp}/mask"][R0:R1, C0:C1], MASK_INVALID_VALUES) for h, gp in zip(hs, gps)]
        if edges is not None:
            ri, ci = np.arange(R0, R1) // estep, np.arange(C0, C1) // estep
            invs = [i | e[np.ix_(np.minimum(ri, e.shape[0] - 1), np.minimum(ci, e.shape[1] - 1))] for i, e in zip(invs, edges)]
        if all(i.all() for i in invs):
            continue
        # pass A: filtered HH/HV for every date (kept: needed for the temporal statistics)
        per_date = []
        for h, gp, inv, L in zip(hs, gps, invs, enl):
            hh = speckle.apply(_read(h, gp, "HHHH", R0, R1, C0, C1, inv), {**lee, "looks": L})
            hv = speckle.apply(_read(h, gp, "HVHV", R0, R1, C0, C1, inv), {**lee, "looks": L})
            per_date.append({"HH": to_db(hh), "HV": to_db(hv)})
            del hh, hv
        tst = temporal({n: [f[n] for f in per_date] for n in ("HH", "HV")}) if stack_cfg.get("temporal") else {}
        # sampled pixels of the core (tile without halo): 10 m rows/cols that are multiples of k
        rs = np.arange(r0 - R0, r1 - R0, k)
        cs = np.arange(c0 - C0, c1 - C0, k)
        # pass B: per date, derived features -> prediction -> discard (memory ~ one date of features)
        for di, base in enumerate(per_date):
            f = dict(base)
            f["HV-HH"] = f["HV"] - f["HH"]
            if stack_cfg.get("texture"):
                f.update(texture(f))
            f.update(tst)
            if rel_cfg:
                from nisar_water.classify.threshold import tiled
                from nisar_water.features.stack import relative
                core = f["HH"][r0 - R0: r1 - R0, c0 - C0: c1 - C0]
                key = (dates[di], r0, c0)
                rt = p.get("relative_threshold") or {}
                if rt.get("mode") == "bbox":  # L13: the threshold the model was trained against, for every tile
                    t, info = fallback_t[dates[di]] + float(rt.get("offset_db", 0.0)), {"tiles_used": int(p.get("min_tiles", 3))}
                elif key in tile_t:  # regularised threshold from a previous run's table (same data and algorithm)
                    t, info = tile_t[key], {"tiles_used": int(p.get("min_tiles", 3))}
                else:
                    t, info = (tiled(core, **rel_cfg) if np.isfinite(core).mean() > 0.2 else (np.nan, {"tiles_used": 0}))
                lo, hi = p.get("t_bounds_db", [-20.0, -10.0])
                # implausible tile thresholds (few water pixels: the most bimodal sub-tiles split land from bright
                # targets, e.g. t = -4 dB on the low-water desc 2026-06-22 scene in L08) fall back to the date's
                # bbox threshold; observed water/land thresholds over all 20 scenes span -11.0 to -18.8 dB
                if info.get("tiles_used", 0) < int(p.get("min_tiles", 3)) or not (lo <= t <= hi):
                    info = {**info, "tiles_used": 0}
                    t = fallback_t[dates[di]]
                t_rows.append({"date": dates[di], "r0": r0, "c0": c0, "t_db": float(t), "tiles_used": info.get("tiles_used", 0)})
                f.update(relative(f, t))
            if "HH_tmed" in f:
                f["HH_anom"] = f["HH"] - f["HH_tmed"]
            X = np.stack([f[n][np.ix_(rs, cs)].ravel() for n in names], 1).astype(np.float32)
            ok = np.isfinite(f["HH"][np.ix_(rs, cs)].ravel()) & np.isfinite(X).all(1)
            lab = np.full(X.shape[0], 255, np.uint8)
            if ok.any():
                lab[ok] = (model.predict_proba(X[ok])[:, 1] > thr).astype(np.uint8)
            out[di, r0 // k: r0 // k + len(rs), c0 // k: c0 // k + len(cs)] = lab.reshape(len(rs), len(cs))[
                : oshape[0] - r0 // k, : oshape[1] - c0 // k]
            del f, X
        n_tiles += 1
        el = time.time() - t_start
        ctx.log.info("tile %d/%d (%d,%d) done; %d processed, %.0f s elapsed", ti + 1, len(tiles), r0, c0, n_tiles, el)
    for h in hs:
        h.close()
    if shard:
        out.flush()
        (ctx.run_dir / "tables").mkdir(exist_ok=True)
        pd.DataFrame(t_rows).to_csv(ctx.run_dir / "tables" / "tile_thresholds.csv", index=False)
        ctx.metrics["headline"] = {"name": f"shard {shard[0]}/{shard[1]}: tiles processed", "value": float(n_tiles)}
        return

    # post-processing (C2 MMU 0.25 ha = 25 px at 10 m -> 25/k^2 px at the output posting)
    ref_cfg = bundle.get("refine") or p.get("refine")
    res = abs(otr[0])
    rows = []
    for di, d in enumerate(dates):
        m = out[di]
        if ref_cfg and ref_cfg.get("mmu_px"):
            m = refine(m, mmu_px=max(1, int(round(ref_cfg["mmu_px"] / k**2))))
            out[di] = m
        write_cog(m, ctx.outputs / "water" / f"water_{d}.tif", otr, epsg,
                  tags={"date": d, "source": cfg.data.granules[di], "model": p["model"], "posting_m": res,
                        "sampling": f"label of the 10 m sample at each cell's upper-left corner (k={k})"})
        valid = m != 255
        rows.append({"date": d, "water_km2": float((m == 1).sum() * res * res / 1e6),
                     "valid_km2": float(valid.sum() * res * res / 1e6)})
        dec = max(1, oshape[0] // 2000)
        save_categorical(m[::dec, ::dec], (otr[0] * dec, 0, otr[2], 0, otr[4] * dec, otr[5]), epsg,
                         ctx.figures / f"water_full_{d}.png", title=f"Water mask (full footprint) — {d}", dates=d,
                         resolution_m=res, source=f"NISAR L2 GCOV L-band frequency A (ASF DAAC); model {p['model'].split('/')[-2]}",
                         classes=WATER_CLASSES)
    if t_rows:
        tdf = pd.DataFrame(t_rows)
        (ctx.run_dir / "tables").mkdir(exist_ok=True)
        tdf.to_csv(ctx.run_dir / "tables" / "tile_thresholds.csv", index=False)
        ctx.metrics["tile_threshold_summary"] = tdf.groupby("date").agg(
            t_median=("t_db", "median"), t_p10=("t_db", lambda v: v.quantile(.1)), t_p90=("t_db", lambda v: v.quantile(.9)),
            frac_fallback=("tiles_used", lambda v: float((v < int(p.get("min_tiles", 3))).mean()))).round(2).to_dict("index")
    area = pd.DataFrame(rows)
    (ctx.run_dir / "tables").mkdir(exist_ok=True)
    area.to_csv(ctx.run_dir / "tables" / "water_area_full.csv", index=False)

    # persistent water on the output grid
    pw = p.get("persistent", {})
    dry = [i for i, d in enumerate(dates) if d in pw.get("dry_dates", [])]
    persistent = np.zeros(oshape, np.uint8)
    if dry:
        persistent |= ((out[dry] == 1).sum(0) >= int(pw.get("min_dry", len(dry) - 1))).astype(np.uint8)
    if pw.get("jrc_min_pct"):
        from nisar_water.io import ancillary as anc
        from pyproj import Transformer
        tf = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
        xs = [otr[2], otr[2] + otr[0] * oshape[1]]
        ys = [otr[5], otr[5] + otr[4] * oshape[0]]
        lon, lat = tf.transform([xs[0], xs[1], xs[1], xs[0]], [ys[0], ys[0], ys[1], ys[1]])
        bb = [min(lon), min(lat), max(lon), max(lat)]
        g = Grid(epsg, otr, oshape)
        items = anc.catalog().search(collections=["jrc-gsw"], bbox=bb).item_collection()
        from nisar_water.grid import warp_to_grid
        occ = np.zeros(oshape, np.float32)
        for it in items:
            a = warp_to_grid(it.assets["occurrence"].href, g).astype(np.float32)
            a[~np.isfinite(a) | (a > 100)] = 0
            occ = np.maximum(occ, a)
        persistent |= (occ >= float(pw["jrc_min_pct"])).astype(np.uint8)
        write_cog(occ.astype(np.uint8), ctx.outputs / "jrc_occurrence.tif", otr, epsg, nodata=None,
                  tags={"source": "JRC GSW v1.3 occurrence (1984-2020), max over tiles"})
    persistent[np.all(out == 255, 0)] = 255
    write_cog(persistent, ctx.outputs / "persistent_water.tif", otr, epsg,
              tags={"definition": f"NISAR water on >= {pw.get('min_dry')} of dry dates {pw.get('dry_dates')} "
                                  f"OR JRC occurrence >= {pw.get('jrc_min_pct')}%"})

    # bbox consistency check vs S2 (TEST blocks) at the sampled pixels
    bg = load_grid("bbox")
    roff = int(round((bg.transform[5] - tr10[5]) / tr10[4]))  # bbox top row in the 10 m frame
    coff = int(round((bg.transform[2] - tr10[2]) / tr10[0]))
    chk = []
    for di, d in enumerate(dates):
        ref = load_reference(cfg.validation.reference, d, "test") if cfg.validation.reference else None
        if ref is None:
            continue
        i0, j0 = -(-roff // k), -(-coff // k)
        i1, j1 = (roff + bg.shape[0]) // k, (coff + bg.shape[1]) // k
        crop = out[di, i0:i1, j0:j1]
        rr = np.arange(i0, i1) * k - roff
        cc = np.arange(j0, j1) * k - coff
        m = evaluate(crop, ref[np.ix_(rr, cc)])
        chk.append({"date": d, **{x: m[x] for x in ("f1", "iou", "precision", "recall")}})
    chk = pd.DataFrame(chk)
    chk.to_csv(ctx.run_dir / "tables" / "bbox_check.csv", index=False)
    full_km2 = float((np.any(out != 255, 0)).sum() * res * res / 1e6)
    ctx.metrics.update({
        "headline": {"name": "full-footprint mean water area (km²)", "value": float(area.water_km2.mean())},
        "footprint_km2": full_km2, "enl": dict(zip(dates, map(float, enl))), "output_posting_m": res,
        "persistent_water_km2": float((persistent == 1).sum() * res * res / 1e6),
        "tables": {"Water area per date, full footprint (km²)": area.to_markdown(index=False, floatfmt=".1f"),
                   **({"bbox consistency vs S2 (TEST blocks, sampled pixels)": chk.to_markdown(index=False, floatfmt=".3f")}
                      if not chk.empty else {})},
    })
