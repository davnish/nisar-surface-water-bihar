"""L10 cross-check: full-footprint NISAR water vs Sentinel-1 water at 100 m (comparison, not truth).

For each NISAR date, Sentinel-1 RTC VV scenes within +-`--days` over the frame are mosaicked (closest acquisition
first) on a 100 m grid, and water is mapped with the same split-based Otsu threshold used for the R00 S1 maps
(one threshold per date, pooled over the most bimodal 25.6 km tiles). The NISAR 20 m mask is aggregated to 100 m
(water if >= 50 % of valid 20 m pixels). Writes tables/s1_crosscheck.csv (areas over the common valid area,
agreement F1) in the L10 run and, optionally, per-date water-fraction maps by 20 km block for the dates given in
--block-dates (tables/s1_crosscheck_blocks.csv).

Usage: uv run python scripts/l10_s1_crosscheck.py experiments/L10_full_footprint/runs/<run> [--dates ...]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from nisar_water.classify import threshold
from nisar_water.io import ancillary as anc

RES = 100.0


def nisar_100m(path: Path) -> tuple[np.ndarray, Affine, int]:
    with rasterio.open(path) as src:
        a = src.read(1)
        tr, epsg = src.transform, src.crs.to_epsg()
    k = int(RES / tr.a)
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    valid = (b != 255).sum((1, 3))
    wet = (b == 1).sum((1, 3))
    out = np.full(valid.shape, 255, np.uint8)
    ok = valid >= k * k // 2
    out[ok] = (wet[ok] >= valid[ok] / 2).astype(np.uint8)
    return out, Affine(RES, 0, tr.c, 0, -RES, tr.f), epsg


def s1_vv_db(date: str, shape, tr: Affine, epsg: int, days: int) -> tuple[np.ndarray, list[str]]:
    tf = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    xs = [tr.c, tr.c + tr.a * shape[1]]
    ys = [tr.f, tr.f + tr.e * shape[0]]
    lon, lat = tf.transform([xs[0], xs[1], xs[1], xs[0]], [ys[0], ys[0], ys[1], ys[1]])
    bb = [min(lon), min(lat), max(lon), max(lat)]
    t0 = pd.Timestamp(date)
    items = anc.search("sentinel-1-rtc", bb, t0 - pd.Timedelta(days=days), t0 + pd.Timedelta(days=days))
    items = sorted(items, key=lambda i: abs(pd.Timestamp(i.datetime).tz_localize(None) - t0))
    mos = np.full(shape, np.nan, np.float32)
    used = []
    for it in items:
        if np.isfinite(mos).mean() > 0.995:
            break
        lin = None
        for attempt in range(3):
            try:
                import planetary_computer
                href = planetary_computer.sign(it.assets["vv"].href)  # fresh token per read
                # overview level 2 (~80 m) is enough for a 100 m comparison and ~60x less to download
                with rasterio.open(href, overview_level=2) as src, WarpedVRT(
                        src, crs=f"EPSG:{epsg}", transform=tr, width=shape[1], height=shape[0],
                        resampling=Resampling.average) as vrt:
                    lin = vrt.read(1).astype(np.float32)
                    if vrt.nodata is not None:
                        lin[lin == vrt.nodata] = np.nan
                break
            except Exception as e:  # network / token errors: retry, then skip the scene
                print(f"  {it.id}: read failed ({type(e).__name__}), attempt {attempt + 1}", flush=True)
        if lin is None:
            continue
        lin[(lin <= 0) | ~np.isfinite(lin)] = np.nan
        fill = ~np.isfinite(mos) & np.isfinite(lin)
        if fill.any():
            mos[fill] = 10 * np.log10(lin[fill])
            used.append(f"{it.id} ({pd.Timestamp(it.datetime).date()})")
    return mos, used


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--dates", nargs="*")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--bbox-threshold", action="store_true",
                    help="use the date's R00 bbox S1 threshold (frame-wide Otsu splits land in low-water scenes)")
    ap.add_argument("--out", default="s1_crosscheck")
    a = ap.parse_args()
    files = sorted((a.run / "outputs" / "water").glob("water_*.tif"))
    rows, blocks = [], []
    for f in files:
        d = f.stem.removeprefix("water_")
        if a.dates and d not in a.dates:
            continue
        nis, tr, epsg = nisar_100m(f)
        vv, used = s1_vv_db(d, nis.shape, tr, epsg, a.days)
        common = (nis != 255) & np.isfinite(vv)
        if common.mean() < 0.2:
            print(d, "no S1 coverage")
            continue
        if a.bbox_threshold:
            from nisar_water.config import load_paths
            with rasterio.open(load_paths()["reference"] / f"s1_water_{d}.tif") as r:
                t = float(r.tags()["rule"].split()[-1])
        else:
            t, info = threshold.tiled(np.where(common, vv, np.nan), tile=256)
        s1 = np.isfinite(vv) & (vv < t)
        n, s = (nis == 1) & common, s1 & common
        tp, fp, fn = (n & s).sum(), (n & ~s).sum(), (~n & s).sum()
        px = RES * RES / 1e6
        row = {"date": d, "common_km2": common.sum() * px, "nisar_water_km2": n.sum() * px, "s1_water_km2": s.sum() * px,
               "f1_vs_s1": 2 * tp / (2 * tp + fp + fn), "nisar_only_km2": (n & ~s).sum() * px,
               "s1_only_km2": (~n & s).sum() * px, "s1_vv_threshold_db": round(float(t), 2), "s1_scenes": "; ".join(used)}
        rows.append(row)
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if k != "s1_scenes"}, flush=True)
        # per 20 km block (200 px at 100 m) water fractions, for locating disagreement
        B = 200
        for i in range(0, nis.shape[0], B):
            for j in range(0, nis.shape[1], B):
                c = common[i:i + B, j:j + B]
                if c.sum() < B * B * 0.3:
                    continue
                blocks.append({"date": d, "row": i, "col": j, "x_km": (tr.c + (j + B / 2) * RES) / 1000,
                               "y_km": (tr.f - (i + B / 2) * RES) / 1000,
                               "nisar_frac": n[i:i + B, j:j + B].sum() / c.sum(), "s1_frac": s[i:i + B, j:j + B].sum() / c.sum()})
    pd.DataFrame(rows).to_csv(a.run / "tables" / f"{a.out}.csv", index=False)
    pd.DataFrame(blocks).to_csv(a.run / "tables" / f"{a.out}_blocks.csv", index=False)


if __name__ == "__main__":
    main()
