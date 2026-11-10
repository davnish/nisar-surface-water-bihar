"""Zone-wise scores and areas of an L10 full-footprint run (and optionally its L10b change run).

Zones: the Ganga floodplain belt (northing >= 2,775 km, the landscape the model was trained in) and the southern
plain. Writes into the L10 run's tables/:
- s2_zone_scores.csv : NISAR water (2026-01-15, aggregated to 40 m) vs a frame-wide S2 water mosaic (from
  scripts/l10_s2_crosscheck.py), for frame / inside box / outside box / belt / south;
- s1_zone_ratios.csv : mean NISAR vs Sentinel-1 water fraction per 20 km block by zone and date (S1 block fractions
  from scripts/l10_s1_crosscheck.py --bbox-threshold; NISAR aggregated to 100 m as there);
- water_area_by_zone.csv : water area per date and zone;
and, with --change-run, change_areas_by_zone.csv into the L10b run's tables/.

Usage: uv run python scripts/l10_zone_scores.py <L10 run> --s2 <s2_water_2026-01-15.tif> --s1-blocks <csv> [--change-run <L10b run>]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

sys.path.insert(0, str(Path(__file__).parent))
from l10_s1_crosscheck import nisar_100m  # noqa: E402
from l10_s2_crosscheck import RES as RES40, nisar_40m, scores  # noqa: E402

from nisar_water.grid import load_grid  # noqa: E402

BELT_Y = 2775e3
PAIRS = [("2025-11-28", "2026-01-15"), ("2026-01-15", "2026-09-12"), ("2026-09-12", "2026-10-18"),
         ("2026-01-15", "2026-10-18"), ("2026-06-20", "2026-09-12")]


def ygrid(shape, tr):
    return tr.f + (np.arange(shape[0]) + .5) * tr.e


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--s2", type=Path, required=True)
    ap.add_argument("--s1-blocks", type=Path, required=True)
    ap.add_argument("--change-run", type=Path)
    a = ap.parse_args()
    tab = a.run / "tables"

    # S2 (01-15, 40 m)
    n, tr, epsg = nisar_40m(a.run / "outputs" / "water" / "water_2026-01-15.tif")
    with rasterio.open(a.s2) as src:
        s2 = src.read(1)
    dst = a.run / "outputs" / "s2_frame"
    dst.mkdir(exist_ok=True)
    if a.s2.resolve() != (dst / a.s2.name).resolve():
        shutil.copy2(a.s2, dst / a.s2.name)
    h, w = min(n.shape[0], s2.shape[0]), min(n.shape[1], s2.shape[1])
    n, s2 = n[:h, :w], s2[:h, :w]
    common = (n != 255) & (s2 != 255)
    north = (ygrid((h, w), tr) >= BELT_Y)[:, None] & np.ones(w, bool)
    bg = load_grid("bbox")
    x = tr.c + (np.arange(w) + .5) * RES40
    y = ygrid((h, w), tr)
    bx0, by1 = bg.transform[2], bg.transform[5]
    bx1, by0 = bx0 + bg.transform[0] * bg.shape[1], by1 + bg.transform[4] * bg.shape[0]
    inbox = ((y <= by1) & (y > by0))[:, None] & ((x >= bx0) & (x < bx1))[None, :]
    rows = []
    for region, m in (("frame", common), ("inside box", common & inbox), ("outside box", common & ~inbox),
                      ("floodplain belt", common & north), ("southern plain", common & ~north)):
        rows.append({"region": region, **{k: float(v) for k, v in scores(n == 1, s2 == 1, m).items()}})
    s2t = pd.DataFrame(rows)
    s2t.to_csv(tab / "s2_zone_scores.csv", index=False)
    print(s2t.round(3).to_string())

    # S1 block ratios (100 m, 20 km blocks as in l10_s1_crosscheck.py)
    b = pd.read_csv(a.s1_blocks)
    out = []
    B = 200
    for d, bb in b.groupby("date"):
        f = a.run / "outputs" / "water" / f"water_{d}.tif"
        if not f.exists():
            continue
        m100, _, _ = nisar_100m(f)
        for r in bb.itertuples():
            blk = m100[int(r.row): int(r.row) + B, int(r.col): int(r.col) + B]
            v = blk != 255
            out.append({"date": d, "zone": "floodplain belt" if r.y_km >= BELT_Y / 1000 else "southern plain",
                        "nisar_frac": float((blk == 1).sum() / max(v.sum(), 1)), "s1_frac": r.s1_frac})
    s1t = pd.DataFrame(out).groupby(["date", "zone"])[["nisar_frac", "s1_frac"]].mean().reset_index()
    s1t["ratio"] = s1t.nisar_frac / s1t.s1_frac
    s1t.to_csv(tab / "s1_zone_ratios.csv", index=False)
    print(s1t.round(3).to_string())

    # water area per date and zone
    ar = []
    for f in sorted((a.run / "outputs" / "water").glob("water_*.tif")):
        with rasterio.open(f) as src:
            m, t = src.read(1), src.transform
        nm = (ygrid(m.shape, t) >= BELT_Y)[:, None]
        px = abs(t.a * t.e) / 1e6
        ar.append({"date": f.stem[-10:], "belt_water_km2": float(((m == 1) & nm).sum() * px),
                   "belt_valid_km2": float(((m != 255) & nm).sum() * px), "south_water_km2": float(((m == 1) & ~nm).sum() * px),
                   "south_valid_km2": float(((m != 255) & ~nm).sum() * px)})
    art = pd.DataFrame(ar)
    art.to_csv(tab / "water_area_by_zone.csv", index=False)
    print(art.round(0).to_string())

    if a.change_run:
        rows = []
        for e, l in PAIRS:
            with rasterio.open(a.change_run / "outputs" / "pcc" / f"change_{e}_{l}.tif") as src:
                ch, t = src.read(1), src.transform
            with rasterio.open(a.change_run / "outputs" / "pcc" / f"new_water_{e}_{l}.tif") as src:
                nw = src.read(1)
            nm = (ygrid(ch.shape, t) >= BELT_Y)[:, None]
            px = abs(t.a * t.e) / 1e6
            for z, m in (("floodplain belt", nm), ("southern plain", ~nm)):
                rows.append({"pair": f"{e} → {l}", "zone": z, "stable water": float(((ch == 1) & m).sum() * px),
                             "gain": float(((ch == 2) & m).sum() * px), "loss": float(((ch == 3) & m).sum() * px),
                             "new outside persistent": float(((nw == 2) & m).sum() * px),
                             "valid": float(((ch != 255) & m).sum() * px)})
        ct = pd.DataFrame(rows)
        ct.to_csv(a.change_run / "tables" / "change_areas_by_zone.csv", index=False)
        print(ct.round(0).to_string())


if __name__ == "__main__":
    main()
