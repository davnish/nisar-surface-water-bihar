"""R00 reference build, on the canonical grid (configs/grid_bbox.yaml):

1. Sentinel-2 L2A water masks (MNDWI) for every NISAR acquisition with a near-coincident, mostly cloud-free scene.
2. Persistent water = water in every clear dry-season S2 reference (needed for "new water outside persistent
   water"). JRC GSW occurrence is kept as long-term context only: this river migrates too much for a
   1984-2020 climatology to define current permanent water.
3. Sentinel-1 RTC VV Otsu water masks, a cross-sensor comparison only (not truth).
4. A spatial-block train/test split, stratified on persistent water.

Rasters go to data/reference/ (uint8: 1 water, 0 non-water, 255 nodata/cloud). Run folders keep tables and figures.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nisar_water import REPO_ROOT
from nisar_water.classify import threshold
from nisar_water.config import load_aoi, load_paths
from nisar_water.grid import load_grid
from nisar_water.io import ancillary as anc
from nisar_water.io.raster import read, write_cog
from nisar_water.report import latest_run
from nisar_water.validate.metrics import evaluate
from nisar_water.validate.sampling import TEST, TRAIN, block_split
from nisar_water.viz.maps import save_categorical, save_continuous, save_rgb

WATER_CLASSES = {0: ("Non-water", "#d9d6cc"), 1: ("Water", "#2a78d6")}
TEXT, MUTED, GRID_C = "#0b0b0b", "#52514e", "#e4e3df"


def run(ctx) -> None:
    p = ctx.cfg.extra
    grid, bbox = load_grid("bbox"), load_aoi()["bbox_wsen"]
    ref_dir = load_paths()["reference"]
    ref_dir.mkdir(parents=True, exist_ok=True)
    for stale in [*ref_dir.glob("s2_water_*.tif"), *ref_dir.glob("s1_water_*.tif")]:
        stale.unlink()  # outputs are rebuilt from scratch so a rejected date can't leave an old reference behind
    tables = ctx.run_dir / "tables"
    tables.mkdir(exist_ok=True)
    tr, epsg, res = grid.transform, grid.epsg, grid.resolution

    inv_path = latest_run(REPO_ROOT / "experiments" / "L00_data_inventory") / "tables" / "inventory.csv"
    inv = pd.read_csv(inv_path, parse_dates=["start_time"])
    inv = inv[inv["track"].isin(p["nisar_tracks"])].sort_values("start_time")
    ctx.log.info("%d NISAR acquisitions on tracks %s (from %s)", len(inv), p["nisar_tracks"], inv_path.name)

    # --- JRC GSW: long-term context (1984-2020) --------------------------------------------------
    occ = anc.jrc_layer("occurrence", grid, bbox)
    occ_valid = occ <= 100
    jrc_persistent = np.where(occ_valid, (occ >= p["jrc_persistent_occurrence"]).astype(np.uint8), 255).astype(np.uint8)
    write_cog(np.where(occ_valid, occ, 255).astype(np.uint8), ref_dir / "jrc_occurrence.tif", tr, epsg,
              tags={"source": "JRC GSW v1.3 occurrence (1984-2020), Planetary Computer"})
    write_cog(jrc_persistent, ref_dir / "jrc_persistent.tif", tr, epsg,
              tags={"source": "JRC GSW v1.3", "rule": f"occurrence >= {p['jrc_persistent_occurrence']}%"})
    jrc_src = "JRC Global Surface Water v1.3 (Pekel et al. 2016), resampled 30 m → 10 m nearest"
    save_continuous(np.where(occ_valid, occ, np.nan).astype(np.float32), tr, epsg, ctx.figures / "jrc_occurrence.png",
                    title="JRC GSW water occurrence 1984–2020 (%)", dates="1984–2020", resolution_m=res,
                    source=jrc_src, label="occurrence (%)", vmin=0, vmax=100, cmap="Blues")
    save_categorical(jrc_persistent, tr, epsg, ctx.figures / "jrc_persistent.png",
                     title=f"JRC persistent water (occurrence ≥ {p['jrc_persistent_occurrence']}%)", dates="1984–2020",
                     resolution_m=res, source=jrc_src, classes=WATER_CLASSES)

    # --- Sentinel-2 / Sentinel-1 per NISAR acquisition ---------------------------------------
    rows = []
    for _, acq in inv.iterrows():
        t0 = acq["start_time"].tz_localize(None) if acq["start_time"].tzinfo else acq["start_time"]
        date = t0.strftime("%Y-%m-%d")  # NISAR UTC start date: the key used in reference filenames
        row = {"nisar_date": date, "nisar_time_utc": t0.strftime("%H:%M"), "track": acq["track"],
               "pol": acq["polarization_code"]}
        row.update(_s2(acq, t0, date, grid, bbox, p, ref_dir, jrc_persistent, ctx))
        row.update(_s1(t0, date, grid, bbox, p, ref_dir, ctx, row.get("s2_built")))
        ctx.log.info("%s: %s", date, {k: v for k, v in row.items() if k.startswith(("s2", "s1"))})
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(tables / "reference_availability.csv", index=False)

    # --- persistent water: water in every clear dry-season S2 reference ------------------------
    dry = df[df["s2_built"] & pd.to_datetime(df["nisar_date"]).dt.month.isin(p["dry_season_months"])]
    dry_dates = sorted(set(dry["nisar_date"]) - set(p.get("persistent_exclude_dates", [])))
    # the same S2 scene can serve two NISAR dates: count each scene once
    scenes = dry.drop_duplicates("s2_scene")["nisar_date"]
    dry_dates = [d for d in dry_dates if d in set(scenes)]
    n_water = np.zeros(grid.shape, np.int16)
    n_valid = np.zeros(grid.shape, np.int16)
    for d in dry_dates:
        ref, _ = read(ref_dir / f"s2_water_{d}.tif")
        n_valid += ref != 255
        n_water += ref == 1
    enough = n_valid >= p["persistent_min_obs"]
    persistent = np.where(enough, (n_water == n_valid).astype(np.uint8), 255).astype(np.uint8)
    write_cog(persistent, ref_dir / "persistent_water.tif", tr, epsg,
              tags={"rule": f"water in every clear dry-season S2 reference (>= {p['persistent_min_obs']} obs)",
                    "dates": ",".join(dry_dates)})
    save_categorical(persistent, tr, epsg, ctx.figures / "persistent_water.png",
                     title="Persistent water: water in every clear dry-season S2 reference",
                     dates=", ".join(dry_dates), resolution_m=res,
                     source="Sentinel-2 L2A MNDWI references (this experiment)", classes=WATER_CLASSES)

    # --- spatial-block split -----------------------------------------------------------------
    split = block_split(grid.shape, int(p["block_size_m"] / res), p["test_fraction"],
                        strata=persistent == 1, seed=p["seed"])
    write_cog(split, ref_dir / "split_blocks.tif", tr, epsg, nodata=0,
              tags={"values": "1 train, 2 test", "block_m": p["block_size_m"], "seed": p["seed"]})
    save_categorical(split, tr, epsg, ctx.figures / "split_blocks.png",
                     title=f"Spatial-block split ({p['block_size_m'] / 1000:g} km blocks, stratified on persistent water)",
                     dates="—", resolution_m=res, source="this work",
                     classes={TRAIN: ("Train", "#2a78d6"), TEST: ("Test", "#eb6834")})

    _availability_plot(df, p["s2_min_clear"], ctx.figures / "s2_availability.png")

    built = df[df["s2_built"]]
    ctx.metrics.update({
        "headline": {"name": "NISAR dates with S2 reference", "value": f"{len(built)}/{len(df)}"},
        "n_nisar_acquisitions": len(df),
        "n_s2_reference": int(df["s2_built"].sum()),
        "n_s2_rejected_qc": int((df["s2_status"] == "rejected_qc").sum()),
        "n_s1_comparison": int(df["s1_built"].sum()),
        "persistent_water_km2": float((persistent == 1).sum() * grid.pixel_area_m2 / 1e6),
        "persistent_water_dates": ", ".join(dry_dates),
        "jrc_persistent_water_km2": float((jrc_persistent == 1).sum() * grid.pixel_area_m2 / 1e6),
        "test_block_fraction": float((split == TEST).mean()),
        "tables": {"Reference availability per NISAR acquisition": df.to_markdown(index=False, floatfmt=".3f")},
    })


def _s2(acq, t0, date, grid, bbox, p, ref_dir, jrc_persistent, ctx) -> dict:
    dt = pd.Timedelta(days=p["s2_max_days"])
    items = anc.search("sentinel-2-l2a", bbox, t0 - dt, t0 + dt)
    best = None
    for it in items:
        clear, scl = anc.s2_clear_mask(it, grid, p["s2_blue_max"], p["s2_blue_red_min"],
                                        int(p["s2_cloud_buffer_m"] / grid.resolution),
                                        int(p["s2_buffer_min_cloud_m2"] / grid.pixel_area_m2))
        frac = float(clear.mean())
        hours = abs((pd.Timestamp(it.datetime).tz_localize(None) - t0).total_seconds()) / 3600
        if best is None or (frac, -hours) > (best[1], -best[2]):
            best = (it, frac, hours, clear, scl)
    if best is None:
        return {"s2_scene": None, "s2_clear_frac": 0.0, "s2_dt_hours": None, "s2_built": False, "s2_status": "no_scene"}
    it, frac, hours, clear, scl = best
    out = {"s2_scene": it.id, "s2_clear_frac": frac, "s2_dt_hours": round(hours, 1), "s2_built": False,
           "s2_status": "too_cloudy"}
    if frac < p["s2_min_clear"]:
        return out

    g, sw, nir = (anc.s2_reflectance(it, b, grid) for b in ("B03", "B11", "B08"))
    idx = anc.mndwi(g, sw)
    valid = clear & np.isfinite(idx)
    ref = np.full(grid.shape, 255, np.uint8)
    ref[valid] = (idx[valid] > p["mndwi_threshold"]).astype(np.uint8)
    s2_date = pd.Timestamp(it.datetime).strftime("%Y-%m-%d")

    # QC: two independent water indices must broadly agree, otherwise residual cloud/haze/shadow is likely
    nd = anc.ndwi(g, nir)
    ndwi_water = np.where(valid, (nd > 0).astype(np.uint8), 255).astype(np.uint8)
    f1_ndwi = evaluate(ref, ndwi_water)["f1"]
    out["f1_vs_ndwi"] = round(f1_ndwi, 3)
    if not f1_ndwi >= p["qc_min_f1_mndwi_vs_ndwi"]:
        out["s2_status"] = "rejected_qc"
        (ref_dir / f"s2_water_{date}.tif").unlink(missing_ok=True)
        return out
    write_cog(ref, ref_dir / f"s2_water_{date}.tif", grid.transform, grid.epsg,
              tags={"nisar_date": date, "s2_scene": it.id, "rule": f"MNDWI > {p['mndwi_threshold']}",
                    "dt_hours": round(hours, 1)})

    # further diagnostics: S2's own SCL water class and JRC persistent water
    scl_water = np.where(clear, (scl == anc.SCL_WATER).astype(np.uint8), 255).astype(np.uint8)
    out.update({
        "s2_built": True,
        "s2_status": "built",
        "s2_water_frac": float(ref[valid].mean()),
        "mndwi_otsu": round(threshold.otsu(idx[valid]), 3),
        "f1_vs_scl_water": round(evaluate(ref, scl_water)["f1"], 3),
        "recall_of_jrc_persistent": round(evaluate(ref, jrc_persistent)["recall"], 3),
    })
    src = f"Sentinel-2 L2A {it.id[:3]} ({s2_date}), Planetary Computer"
    rgb = np.dstack([anc.s2_reflectance(it, "B04", grid), g, anc.s2_reflectance(it, "B02", grid)])
    save_rgb(rgb, grid.transform, grid.epsg, ctx.figures / f"s2_rgb_{date}.png",
             title=f"Sentinel-2 true colour {s2_date} (NISAR {date}, Δt {hours:.0f} h)", dates=s2_date,
             resolution_m=grid.resolution, source=src)
    save_categorical(ref, grid.transform, grid.epsg, ctx.figures / f"s2_water_{date}.png",
                     title=f"S2 reference water (MNDWI > {p['mndwi_threshold']}) {s2_date}", dates=s2_date,
                     resolution_m=grid.resolution, source=src, classes=WATER_CLASSES)
    return out


def _s1(t0, date, grid, bbox, p, ref_dir, ctx, figure: bool) -> dict:
    dt = pd.Timedelta(days=p["s1_max_days"])
    items = anc.search("sentinel-1-rtc", bbox, t0 - dt, t0 + dt)
    if not items:
        return {"s1_scene": None, "s1_dt_hours": None, "s1_built": False}
    it = min(items, key=lambda i: abs(pd.Timestamp(i.datetime).tz_localize(None) - t0))
    hours = abs((pd.Timestamp(it.datetime).tz_localize(None) - t0).total_seconds()) / 3600
    vv = anc.s1_db(it, "VV", grid)
    if np.isfinite(vv).mean() < 0.5:
        return {"s1_scene": it.id, "s1_dt_hours": round(hours, 1), "s1_built": False}
    t, info = threshold.tiled(vv, tile=p["s1_tile_px"])
    mask = threshold.apply(vv, t)
    write_cog(mask, ref_dir / f"s1_water_{date}.tif", grid.transform, grid.epsg,
              tags={"nisar_date": date, "s1_scene": it.id, "rule": f"VV dB < tiled Otsu {t:.2f}", **info, "dt_hours": round(hours, 1)})
    if figure:
        save_categorical(mask, grid.transform, grid.epsg, ctx.figures / f"s1_water_{date}.png",
                         title=f"S1 VV tiled-Otsu water ({t:.1f} dB), comparison only", dates=str(pd.Timestamp(it.datetime).date()),
                         resolution_m=grid.resolution, source=f"Sentinel-1 RTC {it.id[:3]}, Planetary Computer",
                         classes=WATER_CLASSES)
    return {"s1_scene": it.id, "s1_dt_hours": round(hours, 1), "s1_vv_threshold_db": round(t, 2),
            "s1_tiles_used": info["tiles_used"], "s1_built": True}


def _availability_plot(df: pd.DataFrame, min_clear: float, path) -> None:
    d = df.assign(x=pd.to_datetime(df["nisar_date"]))
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.axhline(min_clear, color=MUTED, linewidth=1, linestyle="--")
    ax.annotate(f"build threshold {min_clear:.0%}", (d["x"].min(), min_clear), xytext=(0, 4),
                textcoords="offset points", fontsize=8, color=MUTED)
    for status, (colour, marker, label) in {"built": ("#2a78d6", "o", "S2 reference built"),
                                            "too_cloudy": ("#eb6834", "X", "too cloudy / no scene"),
                                            "no_scene": ("#eb6834", "X", None),
                                            "rejected_qc": ("#1baf7a", "D", "rejected by MNDWI–NDWI QC")}.items():
        sub = d[d["s2_status"] == status]
        ax.scatter(sub["x"], sub["s2_clear_frac"], s=64, color=colour, marker=marker, edgecolor="#fcfcfb",
                   linewidth=1.5, label=label, zorder=3)
    ax.set_ylim(-0.03, 1.05)
    ax.set_ylabel("Best S2 clear fraction over bbox", color=MUTED, fontsize=9)
    ax.set_title("Sentinel-2 cloud-free coverage near each NISAR acquisition (±3 days, after cloud screening)", color=TEXT,
                 fontsize=10, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color=GRID_C, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
