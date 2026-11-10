"""L10 post-fix: widen the far-range edge mask on the dry-season dates of an L10 run (in place).

Why: on the 5 dry-season granules (X0500x processing) the GCOV mask layer marks a near-zero-power strip at far
range (east edge, ascending pass) as valid. L10 drops everything within 10 km of that strip (`extra.edge_mask`),
but the water fraction along the new edge is still 0.31 falling to the 0.05 background only 6-8 km inland, i.e.
the backscatter ramp is wider than 10 km. The classifier is per pixel (32 px halo), so masking its output is
equivalent to masking its input; this avoids a 2.3 h rerun.

What: for each dry date, pixels within `--km` of the east-facing data boundary (direction to the nearest no-data
pixel within 35 deg of the boundary normal) are set to no-data (255). Then water_area_full.csv, persistent water
(same rule as production.py), the per-date figures and metrics.json are rewritten. A log of the change is written
to tables/edge_postfix.csv.

Usage: uv run python scripts/l10_edge_postfix.py experiments/L10_full_footprint/runs/<run> [--km 8]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.ndimage import binary_fill_holes, distance_transform_edt, zoom

from nisar_water.io.raster import read, write_cog
from nisar_water.tasks.production import WATER_CLASSES
from nisar_water.viz.maps import save_categorical


def east_edge_zone(valid: np.ndarray, km: float, res_m: float, step: int = 4) -> np.ndarray:
    # only the outer frame boundary counts: interior no-data holes are filled first
    v = binary_fill_holes(valid[::step, ::step])
    dist, (ri, ci) = distance_transform_edt(v, return_indices=True)
    rr, cc = np.indices(v.shape)
    dy, dx = ri - rr, ci - cc
    norm = np.hypot(dx, dy) + 1e-9
    # boundary normal of the east (far-range) edge in this frame: ~ (0.955 east, 0.296 north) -> rows go south
    nx, ny = 0.955, -0.296
    east = (dx * nx + dy * ny) / norm > np.cos(np.radians(35))
    zone = v & east & (dist * step * res_m <= km * 1000)
    up = zoom(zone.astype(np.uint8), step, order=0)[: valid.shape[0], : valid.shape[1]].astype(bool)
    pad = np.zeros(valid.shape, bool)
    pad[: up.shape[0], : up.shape[1]] = up
    return pad & valid


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--km", type=float, default=8.0)
    a = ap.parse_args()
    run = a.run
    cfg = yaml.safe_load((run / "config.yaml").read_text())
    pw = cfg["extra"]["persistent"]
    dry = pw["dry_dates"]
    out = run / "outputs"
    area = pd.read_csv(run / "tables" / "water_area_full.csv", dtype={"date": str})
    log, stack = [], []
    for d in dry:
        p = out / "water" / f"water_{d}.tif"
        m, prof = read(p)
        tr, epsg = tuple(prof["transform"])[:6], prof["epsg"]
        res = abs(tr[0])
        z = east_edge_zone(m != 255, a.km, res)
        px = res * res / 1e6
        log.append({"date": d, "dropped_km2": float(z.sum() * px), "water_dropped_km2": float((z & (m == 1)).sum() * px),
                    "water_frac_dropped": float((m[z] == 1).mean()) if z.any() else np.nan})
        m[z] = 255
        write_cog(m, p, tr, epsg, tags={"date": d, "postfix": f"east far-range edge widened by {a.km} km"})
        area.loc[area.date == d, ["water_km2", "valid_km2"]] = [float((m == 1).sum() * px), float((m != 255).sum() * px)]
        dec = max(1, m.shape[0] // 2000)
        save_categorical(m[::dec, ::dec], (tr[0] * dec, 0, tr[2], 0, tr[4] * dec, tr[5]), epsg,
                         run / "figures" / f"water_full_{d}.png", title=f"Water mask (full footprint) — {d}", dates=d,
                         resolution_m=res, source=f"NISAR L2 GCOV L-band frequency A (ASF DAAC); model "
                         f"{cfg['extra']['model'].split('/')[-2]}", classes=WATER_CLASSES)
        stack.append(m)
        print(log[-1])
    area.to_csv(run / "tables" / "water_area_full.csv", index=False)
    pd.DataFrame(log).to_csv(run / "tables" / "edge_postfix.csv", index=False)

    # persistent water, same rule as production.py
    pers, prof = read(out / "persistent_water.tif")
    tr, epsg = tuple(prof["transform"])[:6], prof["epsg"]
    st = np.stack(stack)
    nis = (st == 1).sum(0) >= int(pw.get("min_dry", len(dry) - 1))
    jrc, _ = read(out / "jrc_occurrence.tif")
    new = (nis | (jrc >= float(pw["jrc_min_pct"]))).astype(np.uint8)
    new[pers == 255] = 255
    write_cog(new, out / "persistent_water.tif", tr, epsg,
              tags={"definition": f"NISAR water on >= {pw.get('min_dry')} of dry dates {dry} OR JRC occurrence >= "
                                  f"{pw.get('jrc_min_pct')}% (dry dates edge-postfixed {a.km} km)"})
    px = abs(tr[0] * tr[4]) / 1e6

    mp = run / "metrics.json"
    met = json.loads(mp.read_text())
    met["persistent_water_km2"] = float((new == 1).sum() * px)
    met["headline"]["value"] = float(area.water_km2.mean())
    met.setdefault("tables", {})["Water area per date, full footprint (km²)"] = area.to_markdown(index=False, floatfmt=".1f")
    met["tables"]["Edge post-fix (dry dates)"] = pd.DataFrame(log).to_markdown(index=False, floatfmt=".2f")
    met["edge_postfix_km"] = a.km
    mp.write_text(json.dumps(met, indent=2, ensure_ascii=False))
    print("persistent water km2:", met["persistent_water_km2"])
    print(area.to_string())


if __name__ == "__main__":
    main()
