"""Export layers for the QGIS project and write a manifest that tools/build_qgis_project.py turns into a .qgz.

Exports (to data/processed/qgis/, git-ignored, rebuilt on demand):
- HH and HV gamma0 dB (Lee 7x7, per-scene ENL) for every cached asc 98/14 window,
- Sentinel-2 true-colour (8-bit, 2-98 % stretch) for every NISAR date with an S2 reference.
Existing products are referenced in place: R00 reference rasters, L00 footprints, water masks of the
latest L02 / L04 runs. Paths in the manifest are relative to the repo root.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from nisar_water import REPO_ROOT
from nisar_water.config import ExperimentCfg, load_paths
from nisar_water.features.pol import features_db, resolve_filter
from nisar_water.grid import load_grid
from nisar_water.io.raster import write_cog
from nisar_water.report import latest_run
from nisar_water.tasks.common import acq_date, load_scene

EXP = REPO_ROOT / "experiments"
# water-mask layers shown in QGIS: (experiment, variant, label)
MASK_LAYERS = [
    ("L02_global_threshold", "hh_tuned", "Water — B0 HH < −15.9 dB (L02)"),
    ("L04_tiled_threshold", "hh_tiled_ki_bounded", "Water — C1 tiled KI bounded (L04)"),
    ("L06_contextual_refinement", "C1_mmu25", "Water — C2: C1 + MMU 0.25 ha (L06)"),
    ("L07_supervised_rf_lgbm", "lgbm_rel_full_mmu25", "Water — C3 champion: LightGBM, scene-relative features (L07)"),
    ("F01_L_S_fusion", "S_lgbm", "Water — S-band LightGBM, Jul–Oct 2026 (F01)"),
    ("F01_L_S_fusion", "LS_lgbm", "Water — L+S fusion LightGBM, Jul–Oct 2026 (F01)"),
]
# change layers from L09: (method, label)
CHANGE_LAYERS = [("pcc", "Change — PCC of C3 masks (L09)")]


def _rel(p: Path) -> str:
    return str(p.resolve().relative_to(REPO_ROOT))


def export(out_dir: Path | None = None, s2: bool = True, log=print) -> Path:
    paths = load_paths()
    out_dir = out_dir or paths["processed"] / "qgis"
    out_dir.mkdir(parents=True, exist_ok=True)
    grid = load_grid("bbox")
    layers: list[dict] = []

    def add(**kw):
        layers.append(kw)

    # --- AOI ------------------------------------------------------------------------------------
    add(group="AOI", name="Reference bbox (problem statement)", path="data/bbox.geojson", kind="vector", style="bbox")
    l00 = latest_run(EXP / "L00_data_inventory")
    if l00 and (l00 / "tables" / "footprints.geojson").exists():
        add(group="AOI", name="GCOV frame footprints (L00)", path=_rel(l00 / "tables" / "footprints.geojson"),
            kind="vector", style="footprints", visible=False)

    # --- NISAR backscatter ----------------------------------------------------------------------
    cfg = ExperimentCfg(id="qgis", question="export", task="water_mask")
    for nc in sorted((paths["interim"] / "nisar_L").glob("*_frequencyA_bbox.nc")):
        granule = nc.name.split("_frequencyA")[0]
        date = acq_date(granule)
        hh_p, hv_p = out_dir / f"nisar_L_HH_db_lee7_{date}.tif", out_dir / f"nisar_L_HV_db_lee7_{date}.tif"
        if not (hh_p.exists() and hv_p.exists()):
            ds = load_scene(cfg, granule)
            spec = resolve_filter({"name": "lee", "size": 7, "looks": "auto"}, ds["HHHH"].values)
            f = features_db(ds, spec)
            tags = {"date": date, "source": granule, "filter": f"lee7 ENL {spec['looks']:.2f}", "units": "gamma0 dB"}
            write_cog(f["HH"].astype(np.float32), hh_p, grid.transform, grid.epsg, tags=tags)
            write_cog(f["HV"].astype(np.float32), hv_p, grid.transform, grid.epsg, tags=tags)
            log(f"exported HH/HV dB {date}")
        add(group="NISAR L-band asc 98/14 — HH γ0 dB (Lee 7×7)", name=f"HH dB {date}", path=_rel(hh_p),
            kind="raster", style="db_hh", date=date)
        add(group="NISAR L-band asc 98/14 — HV γ0 dB (Lee 7×7)", name=f"HV dB {date}", path=_rel(hv_p),
            kind="raster", style="db_hv", date=date, visible=False)

    # --- water masks from experiments ------------------------------------------------------------
    for exp, variant, label in MASK_LAYERS:
        run = latest_run(EXP / exp)
        if run is None:
            continue
        for tif in sorted((run / "outputs" / variant).glob("water_*.tif")):
            date = tif.stem.removeprefix("water_")
            add(group=label, name=f"{variant} {date}", path=_rel(tif), kind="raster", style="water", date=date)

    # --- change maps (L09): not time-enabled (they span two dates) --------------------------------
    l09 = latest_run(EXP / "L09_change_detection")
    if l09:
        for method, label in CHANGE_LAYERS:
            for tif in sorted((l09 / "outputs" / method).glob("change_*.tif")):
                pair = tif.stem.removeprefix("change_").replace("_", " → ")
                add(group=label, name=f"change {pair}", path=_rel(tif), kind="raster", style="change", visible=False)
            for tif in sorted((l09 / "outputs" / method).glob("new_water_*.tif")):
                pair = tif.stem.removeprefix("new_water_").replace("_", " → ")
                add(group=label.replace("Change", "New water outside persistent"), name=f"new water {pair}",
                    path=_rel(tif), kind="raster", style="new_water", visible=False)
        occ = l09 / "outputs" / "water_occurrence_pct.tif"
        if occ.exists():
            add(group="Change — PCC of C3 masks (L09)", name="Water occurrence, 15 dates (%)", path=_rel(occ),
                kind="raster", style="occurrence", visible=False)

    # --- full scene footprint (L10 production masks at 20 m, L10b change): off by default (large) ----
    l10 = latest_run(EXP / "L10_full_footprint")
    if l10:
        g = "Full footprint — water, production model, 20 m (L10)"
        for tif in sorted((l10 / "outputs" / "water").glob("water_*.tif")):
            date = tif.stem.removeprefix("water_")
            add(group=g, name=f"water {date}", path=_rel(tif), kind="raster", style="water", date=date, visible=False)
        if (l10 / "outputs" / "persistent_water.tif").exists():
            add(group=g, name="Persistent water (NISAR dry season ∪ JRC)", path=_rel(l10 / "outputs" / "persistent_water.tif"),
                kind="raster", style="persistent", visible=False)
        for tif in sorted((l10 / "outputs" / "s2_frame").glob("s2_water_*.tif")):
            add(group=g, name=f"S2 water, frame mosaic 40 m {tif.stem[-10:]} (validation)", path=_rel(tif),
                kind="raster", style="s2_water", date=tif.stem[-10:], visible=False)
    l10b = latest_run(EXP / "L10b_change_full_footprint")
    if l10b:
        g = "Full footprint — change, PCC (L10b)"
        for tif in sorted((l10b / "outputs" / "pcc").glob("change_*.tif")):
            add(group=g, name=f"change {tif.stem.removeprefix('change_').replace('_', ' → ')}", path=_rel(tif),
                kind="raster", style="change", visible=False)
        for tif in sorted((l10b / "outputs" / "pcc").glob("new_water_*.tif")):
            add(group=g, name=f"new water {tif.stem.removeprefix('new_water_').replace('_', ' → ')}", path=_rel(tif),
                kind="raster", style="new_water", visible=False)
        if (l10b / "outputs" / "water_occurrence_pct.tif").exists():
            add(group=g, name="Water occurrence (%)", path=_rel(l10b / "outputs" / "water_occurrence_pct.tif"),
                kind="raster", style="occurrence", visible=False)

    # --- inspection windows (scripts/inspect_window.py): NISAR HH/HV dB and S2 true colour at 10 m ------------
    for tif in sorted(out_dir.glob("inspect_*.tif")):
        _, name, kind, *rest = tif.stem.split("_")
        date = tif.stem[-10:]
        if kind.startswith("water-"):  # scripts/l13_tile_maps.py
            style = "water"
            label = {"water-tile": "Water, per-tile threshold (L10 it. 2)",
                     "water-bbox-1": "Water, box threshold − 1 dB (L13 fix)"}.get(kind, kind)
        else:
            style = {"hh": "db_hh", "hv": "db_hv", "s2": "rgb"}[kind]
            label = {"hh": "NISAR HH γ0 dB (Lee 7×7)", "hv": "NISAR HV γ0 dB (Lee 7×7)", "s2": "S2 true colour"}[kind]
        add(group=f"Inspection window — {name}", name=f"{label} {date}", path=_rel(tif), kind="raster", style=style,
            date=date, visible=kind == "s2")

    # --- reference data (R00) -------------------------------------------------------------------
    ref = paths["reference"]
    add(group="Reference (R00)", name="Persistent water (dry-season S2)", path=_rel(ref / "persistent_water.tif"),
        kind="raster", style="persistent")
    add(group="Reference (R00)", name="JRC GSW occurrence 1984–2020 (%)", path=_rel(ref / "jrc_occurrence.tif"),
        kind="raster", style="occurrence", visible=False)
    add(group="Reference (R00)", name="Train/test blocks", path=_rel(ref / "split_blocks.tif"),
        kind="raster", style="split", visible=False)
    for tif in sorted(ref.glob("s2_water_*.tif")):
        add(group="Reference (R00) — S2 water (MNDWI > 0)", name=f"S2 water {tif.stem[-10:]}", path=_rel(tif),
            kind="raster", style="s2_water", date=tif.stem[-10:], visible=False)
    for tif in sorted(ref.glob("s1_water_*.tif")):
        add(group="Reference (R00) — S1 water (comparison only)", name=f"S1 water {tif.stem[-10:]}", path=_rel(tif),
            kind="raster", style="s1_water", date=tif.stem[-10:], visible=False)

    # --- Sentinel-2 true colour for referenced dates (s2=False: only reuse already-exported files) ----
    layers += _export_s2_rgb(out_dir, grid, log, download=s2)

    manifest = {"crs": f"EPSG:{grid.epsg}", "extent_transform": list(grid.transform), "shape": list(grid.shape),
                "layers": layers}
    mp = out_dir / "manifest.json"
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    log(f"manifest: {mp} ({len(layers)} layers)")
    return mp


def _export_s2_rgb(out_dir: Path, grid, log, download: bool = True) -> list[dict]:
    """8-bit true-colour COG per S2 reference scene (scene ids from the latest R00 availability table)."""
    import rasterio

    from nisar_water.io import ancillary as anc

    r00 = latest_run(EXP / "R00_reference_build")
    if r00 is None:
        return []
    av = pd.read_csv(r00 / "tables" / "reference_availability.csv")
    out = []
    for _, row in av[av["s2_built"]].drop_duplicates("s2_scene").iterrows():
        scene = row["s2_scene"]
        s2_date = f"{scene[11:15]}-{scene[15:17]}-{scene[17:19]}"
        p = out_dir / f"s2_rgb_{s2_date}.tif"
        if not p.exists() and not download:
            continue
        if not p.exists():
            item = anc.catalog().get_collection("sentinel-2-l2a").get_item(scene)
            bands = []
            for b in ("B04", "B03", "B02"):
                r = anc.s2_reflectance(item, b, grid)
                lo, hi = np.nanpercentile(r, [2, 98])
                bands.append(np.clip((r - lo) / (hi - lo) * 254 + 1, 1, 255).astype(np.uint8))  # 0 = nodata
            with rasterio.open(p, "w", driver="COG", height=grid.shape[0], width=grid.shape[1], count=3,
                               dtype="uint8", crs=f"EPSG:{grid.epsg}", transform=grid.affine, nodata=0,
                               compress="deflate") as dst:
                dst.write(np.stack(bands))
                dst.update_tags(scene=scene, stretch="2-98 % per band")
            log(f"exported S2 RGB {s2_date}")
        out.append({"group": "Sentinel-2 true colour (reference scenes)", "name": f"S2 RGB {s2_date}",
                    "path": _rel(p), "kind": "raster", "style": "rgb", "date": s2_date, "visible": False})
    return out
