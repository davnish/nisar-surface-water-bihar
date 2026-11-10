"""Export an inspection window for QGIS: NISAR HH/HV dB (Lee 7x7) and Sentinel-2 true colour at 10 m.

Used to look at where the full-frame model fails (e.g. the southern plain, L10). Files go to the QGIS export
folder as inspect_<name>_{hh_db,hv_db,s2_rgb}_<date>.tif and are picked up by `nisar-water qgis`.

Usage: uv run python scripts/inspect_window.py --name south --x-km 430 --y-km 2710 --size-km 40 --date 2026-01-15
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer

from nisar_water.config import load_paths
from nisar_water.features.pol import features_db, resolve_filter
from nisar_water.grid import Grid
from nisar_water.io import ancillary as anc
from nisar_water.io.gcov import read_gcov
from nisar_water.io.raster import write_cog


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="south")
    ap.add_argument("--x-km", type=float, required=True)
    ap.add_argument("--y-km", type=float, required=True)
    ap.add_argument("--size-km", type=float, default=40)
    ap.add_argument("--date", required=True)
    a = ap.parse_args()
    paths = load_paths()
    out = paths["processed"] / "qgis"
    out.mkdir(parents=True, exist_ok=True)
    half = a.size_km * 500
    x0, x1, y0, y1 = a.x_km * 1000 - half, a.x_km * 1000 + half, a.y_km * 1000 - half, a.y_km * 1000 + half
    tf = Transformer.from_crs(32645, 4326, always_xy=True)
    lon, lat = tf.transform([x0, x1, x1, x0], [y0, y0, y1, y1])
    bbox = [min(lon), min(lat), max(lon), max(lat)]

    # NISAR: the asc 98/14 granule of that date, same Lee 7x7 / dB features as the bbox QGIS layers
    h5 = next((paths["raw_nisar_L"]).glob(f"*_098_A_014_*_{a.date.replace('-', '')}T*.h5"))
    ds = read_gcov(h5, terms=["HHHH", "HVHV"], bbox_wsen=bbox, aux=False)
    spec = resolve_filter({"name": "lee", "size": 7, "looks": "auto"}, ds["HHHH"].values)
    f = features_db(ds, spec)
    tr, epsg = ds.attrs["transform"], ds.attrs["epsg"]
    tags = {"date": a.date, "source": h5.stem, "filter": f"lee7 ENL {spec['looks']:.2f}", "units": "gamma0 dB"}
    write_cog(f["HH"].astype(np.float32), out / f"inspect_{a.name}_hh_db_{a.date}.tif", tr, epsg, tags=tags)
    write_cog(f["HV"].astype(np.float32), out / f"inspect_{a.name}_hv_db_{a.date}.tif", tr, epsg, tags=tags)
    print("NISAR", h5.stem, ds["HHHH"].shape)

    # Sentinel-2 true colour on the same 10 m grid: closest clear scenes within +-3 days, mosaicked
    grid = Grid(epsg, tuple(tr), ds["HHHH"].shape)
    t0 = pd.Timestamp(a.date)
    items = sorted(anc.search("sentinel-2-l2a", bbox, t0 - pd.Timedelta(days=3), t0 + pd.Timedelta(days=3)),
                   key=lambda i: (abs(pd.Timestamp(i.datetime).tz_localize(None) - t0), i.properties.get("eo:cloud_cover", 100)))
    rgb = np.full((3,) + grid.shape, np.nan, np.float32)
    used = []
    for it in items:
        if np.isfinite(rgb[0]).all():
            break
        bands = [anc.s2_reflectance(it, b, grid) for b in ("B04", "B03", "B02")]
        fill = ~np.isfinite(rgb[0]) & np.isfinite(bands[0])
        if fill.sum() < 1000:
            continue
        for k in range(3):
            rgb[k][fill] = bands[k][fill]
        used.append(it.id)
    img = np.zeros(rgb.shape, np.uint8)
    for k in range(3):
        lo, hi = np.nanpercentile(rgb[k], [2, 98])
        img[k] = np.where(np.isfinite(rgb[k]), np.clip((rgb[k] - lo) / (hi - lo) * 254 + 1, 1, 255), 0).astype(np.uint8)
    p = out / f"inspect_{a.name}_s2_rgb_{a.date}.tif"
    with rasterio.open(p, "w", driver="COG", height=grid.shape[0], width=grid.shape[1], count=3, dtype="uint8",
                       crs=f"EPSG:{epsg}", transform=grid.affine, nodata=0, compress="deflate") as dst:
        dst.write(img)
        dst.update_tags(scenes=";".join(used), stretch="2-98 % per band")
    print("S2", used)


if __name__ == "__main__":
    main()
