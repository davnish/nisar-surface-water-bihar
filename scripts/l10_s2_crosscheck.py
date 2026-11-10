"""L10 accuracy outside the reference box: full-footprint NISAR water vs a frame-wide Sentinel-2 water reference.

R00 built S2 references for the 20 km box only. Here the same rules are applied over the whole frame at 40 m
(the 10 m bands' second overview, the 20 m bands' first): S2 L2A scenes within +-`--days` of the NISAR date are
mosaicked (closest in time first, clear pixels only); clear = SCL not cloud/shadow/snow/nodata and not a white
pixel (B02 > 0.2 and B02/B04 >= 0.85, R00), invalid clusters dilated by 200 m; water = MNDWI > 0 (Xu 2006). The
NISAR 20 m mask is aggregated to 40 m (water if >= 2 of 4 valid pixels). Scores are reported for the whole frame,
inside the reference box and outside it (all pixels, not only test blocks: the box's train blocks were used to fit
the model, so 'inside' is optimistic), plus MNDWI-vs-NDWI agreement as reference QC, and per-20 km-block errors.

Usage: uv run python scripts/l10_s2_crosscheck.py experiments/L10_full_footprint/runs/<run> --dates 2026-01-15 ...
Writes tables/s2_crosscheck.csv, tables/s2_crosscheck_blocks.csv and outputs/s2_frame/s2_water_<date>.tif.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import planetary_computer
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from scipy.ndimage import binary_dilation

from nisar_water.grid import load_grid
from nisar_water.io import ancillary as anc
from nisar_water.io.raster import write_cog

RES = 40.0
SCL_INVALID = [0, 1, 3, 8, 9, 10, 11]  # nodata, saturated, cloud shadow, cloud medium/high, cirrus, snow
OVR = {"B02": 1, "B03": 1, "B04": 1, "B08": 1, "B11": 0, "SCL": 0}  # overview index giving 40 m


def read_band(item, band: str, tr: Affine, shape, epsg: int, resampling=Resampling.average) -> np.ndarray | None:
    for attempt in range(3):
        try:
            href = planetary_computer.sign(item.assets[band].href)
            with rasterio.open(href, overview_level=OVR[band]) as src, WarpedVRT(
                    src, crs=f"EPSG:{epsg}", transform=tr, width=shape[1], height=shape[0], resampling=resampling,
                    src_nodata=0, nodata=0) as vrt:
                return vrt.read(1)
        except Exception as e:  # network / token errors
            print(f"  {item.id} {band}: read failed ({type(e).__name__}), attempt {attempt + 1}", flush=True)
    return None


def refl(item, band, tr, shape, epsg):
    dn = read_band(item, band, tr, shape, epsg)
    if dn is None:
        return None
    dn = dn.astype(np.float32)
    off = 1000.0 if float(item.properties.get("s2:processing_baseline", "0")) >= 4.0 else 0.0
    r = (dn - off) / 10000.0
    r[dn == 0] = np.nan
    return r


def nisar_40m(path: Path):
    with rasterio.open(path) as src:
        a = src.read(1)
        tr, epsg = src.transform, src.crs.to_epsg()
    k = int(RES / tr.a)
    h, w = a.shape[0] // k * k, a.shape[1] // k * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    valid = (b != 255).sum((1, 3))
    wet = (b == 1).sum((1, 3))
    out = np.full(valid.shape, 255, np.uint8)
    ok = valid >= (k * k + 1) // 2
    out[ok] = (wet[ok] * 2 >= valid[ok]).astype(np.uint8)
    return out, Affine(RES, 0, tr.c, 0, -RES, tr.f), epsg


def scores(n, s, m):
    n, s = n[m], s[m]
    tp, fp, fn = np.sum(n & s), np.sum(n & ~s), np.sum(~n & s)
    return {"f1": 2 * tp / max(2 * tp + fp + fn, 1), "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
            "nisar_km2": float(n.sum() * RES * RES / 1e6), "s2_km2": float(s.sum() * RES * RES / 1e6),
            "n_km2": float(m.sum() * RES * RES / 1e6)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--dates", nargs="+", required=True)
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args()
    rows, blocks = [], []
    bg = load_grid("bbox")
    for d in a.dates:
        nis, tr, epsg = nisar_40m(a.run / "outputs" / "water" / f"water_{d}.tif")
        shape = nis.shape
        tf = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
        xs, ys = [tr.c, tr.c + RES * shape[1]], [tr.f, tr.f - RES * shape[0]]
        lon, lat = tf.transform([xs[0], xs[1], xs[1], xs[0]], [ys[0], ys[0], ys[1], ys[1]])
        t0 = pd.Timestamp(d)
        items = anc.search("sentinel-2-l2a", [min(lon), min(lat), max(lon), max(lat)],
                           t0 - pd.Timedelta(days=a.days), t0 + pd.Timedelta(days=a.days))
        items = sorted(items, key=lambda i: (abs(pd.Timestamp(i.datetime).tz_localize(None) - t0),
                                             i.properties.get("eo:cloud_cover", 100)))
        print(d, len(items), "S2 items", flush=True)
        mnd = np.full(shape, np.nan, np.float32)
        ndw = np.full(shape, np.nan, np.float32)
        need = nis != 255
        used = []
        for it in items:
            if not (need & np.isnan(mnd)).any():
                break
            if it.properties.get("eo:cloud_cover", 0) > 90:
                continue
            scl = read_band(it, "SCL", tr, shape, epsg, Resampling.nearest)
            if scl is None:
                continue
            todo = need & np.isnan(mnd) & (scl != 0)
            if todo.sum() < 1000:
                continue
            bands = {b: refl(it, b, tr, shape, epsg) for b in ("B02", "B04", "B03", "B11", "B08")}
            if any(v is None for v in bands.values()):
                continue
            with np.errstate(invalid="ignore", divide="ignore"):
                bad = np.isin(scl, SCL_INVALID) | ((bands["B02"] > 0.2) & (bands["B02"] / bands["B04"] >= 0.85))
                bad = binary_dilation(bad, iterations=5)  # 200 m
                clear = ~bad & (scl != 0)
                m = (bands["B03"] - bands["B11"]) / (bands["B03"] + bands["B11"])
                n = (bands["B03"] - bands["B08"]) / (bands["B03"] + bands["B08"])
            fill = todo & clear & np.isfinite(m)
            mnd[fill], ndw[fill] = m[fill], n[fill]
            used.append(f"{it.id}")
            print(f"  {it.id}: +{fill.sum() * RES * RES / 1e6:.0f} km2 clear", flush=True)
        ref = np.full(shape, 255, np.uint8)
        ok = np.isfinite(mnd)
        ref[ok] = (mnd[ok] > 0).astype(np.uint8)
        (a.run / "outputs" / "s2_frame").mkdir(exist_ok=True)
        write_cog(ref, a.run / "outputs" / "s2_frame" / f"s2_water_{d}.tif", tuple(tr)[:6], epsg,
                  tags={"rule": "MNDWI > 0, frame mosaic at 40 m", "scenes": ";".join(used)})
        common = ok & (nis != 255)
        if common.sum() == 0:
            continue
        nw, sw = nis == 1, ref == 1
        # reference box on the 40 m grid
        rr, cc = np.indices(shape)
        x = tr.c + (cc + .5) * RES
        y = tr.f - (rr + .5) * RES
        bx0, by1 = bg.transform[2], bg.transform[5]
        bx1, by0 = bx0 + bg.transform[0] * bg.shape[1], by1 + bg.transform[4] * bg.shape[0]
        inbox = (x >= bx0) & (x < bx1) & (y <= by1) & (y > by0)
        qc = scores(ndw > 0, sw, common)["f1"]
        for region, mm in (("frame", common), ("inside box", common & inbox), ("outside box", common & ~inbox)):
            r = {"date": d, "region": region, **scores(nw, sw, mm), "mndwi_vs_ndwi_f1": qc,
                 "clear_frac_of_frame": float(common.sum() / max((nis != 255).sum(), 1)), "s2_scenes": len(used)}
            rows.append(r)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
        B = 500  # 20 km blocks
        for i in range(0, shape[0], B):
            for j in range(0, shape[1], B):
                mm = common[i:i + B, j:j + B]
                if mm.sum() < B * B * 0.3:
                    continue
                s = scores(nw[i:i + B, j:j + B], sw[i:i + B, j:j + B], mm)
                blocks.append({"date": d, "x_km": (tr.c + (j + B / 2) * RES) / 1000, "y_km": (tr.f - (i + B / 2) * RES) / 1000, **s})
        pd.DataFrame(rows).to_csv(a.run / "tables" / "s2_crosscheck.csv", index=False)
        pd.DataFrame(blocks).to_csv(a.run / "tables" / "s2_crosscheck_blocks.csv", index=False)


if __name__ == "__main__":
    main()
