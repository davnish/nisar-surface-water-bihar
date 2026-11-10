"""Terrain context: Height Above Nearest Drainage (HAND) from Copernicus GLO-30, on the analysis grid."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine

from nisar_water.grid import Grid, warp_to_grid

DEM_COLLECTION = "cop-dem-glo-30"


def build_hand(grid: Grid, bbox_wsen: list[float], out: Path, margin_m: float = 5000, res_m: float = 30,
               channel_km2: float = 1.0) -> Path:
    """Compute HAND at the DEM's native ~30 m on the grid extent + margin (limits edge effects on drainage),
    then resample bilinearly onto `grid`. Channels = flow accumulation >= channel_km2.
    Note: GLO-30 is a DSM (trees/buildings included); on this flat plain HAND is a coarse proxy."""
    if not hasattr(np, "in1d"):  # pysheds 0.5 still calls np.in1d (removed in NumPy 2.4); np.isin is its replacement
        np.in1d = lambda a, b, **kw: np.isin(np.ravel(a), b, **kw)
    from pysheds.grid import Grid as PGrid

    from nisar_water.io.ancillary import catalog

    a, _, c, _, e, f = grid.transform[:6]
    x0, y1 = c - margin_m, f + margin_m
    x1, y0 = c + a * grid.shape[1] + margin_m, f + e * grid.shape[0] - margin_m
    cols, rows = int((x1 - x0) / res_m), int((y1 - y0) / res_m)
    coarse = Grid(grid.epsg, (res_m, 0.0, x0, 0.0, -res_m, y1), (rows, cols))

    items = list(catalog().search(collections=[DEM_COLLECTION], bbox=bbox_wsen).items())
    if len(items) != 1:
        raise NotImplementedError(f"{len(items)} DEM tiles; mosaicking not implemented")
    dem = warp_to_grid(items[0].assets["data"].href, coarse, Resampling.bilinear, dtype=np.float32)

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "dem.tif"
        with rasterio.open(p, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32",
                           crs=f"EPSG:{grid.epsg}", transform=Affine(*coarse.transform[:6]), nodata=-9999) as dst:
            dst.write(dem, 1)
        pg = PGrid.from_raster(str(p))
        d = pg.read_raster(str(p))
        inflated = pg.resolve_flats(pg.fill_depressions(pg.fill_pits(d)))
        fdir = pg.flowdir(inflated)
        acc = pg.accumulation(fdir)
        hand = pg.compute_hand(fdir, inflated, acc >= channel_km2 * 1e6 / res_m**2)
        hp = Path(tmp) / "hand30.tif"
        with rasterio.open(hp, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32",
                           crs=f"EPSG:{grid.epsg}", transform=Affine(*coarse.transform[:6]), nodata=-9999) as dst:
            dst.write(np.asarray(hand, dtype=np.float32), 1)
        fine = warp_to_grid(str(hp), grid, Resampling.bilinear, dtype=np.float32)

    from nisar_water.io.raster import write_cog
    out.parent.mkdir(parents=True, exist_ok=True)
    write_cog(fine.astype(np.float32), out, grid.transform, grid.epsg,
              tags={"source": f"Copernicus GLO-30 ({items[0].id}) via Planetary Computer; pysheds HAND",
                    "channel_threshold_km2": channel_km2, "dem_res_m": res_m})
    return out
