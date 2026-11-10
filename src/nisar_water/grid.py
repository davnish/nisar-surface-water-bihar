"""The canonical analysis grid and warping of external rasters onto it."""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import rasterio
import yaml
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.vrt import WarpedVRT

from nisar_water import REPO_ROOT

# streaming COGs over HTTPS: avoid directory listings, only fetch .tif
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF,.tiff")


@dataclass(frozen=True)
class Grid:
    epsg: int
    transform: tuple
    shape: tuple[int, int]

    @property
    def affine(self) -> Affine:
        return Affine(*self.transform[:6])

    @property
    def resolution(self) -> float:
        return abs(self.transform[0])

    @property
    def pixel_area_m2(self) -> float:
        return abs(self.transform[0] * self.transform[4])

    def xy(self) -> tuple[np.ndarray, np.ndarray]:
        """Pixel-centre coordinates."""
        a, _, c, _, e, f = self.transform[:6]
        return c + a * (np.arange(self.shape[1]) + 0.5), f + e * (np.arange(self.shape[0]) + 0.5)


def load_grid(name: str = "bbox") -> Grid:
    with open(REPO_ROOT / "configs" / f"grid_{name}.yaml") as f:
        g = yaml.safe_load(f)
    return Grid(int(g["epsg"]), tuple(g["transform"]), tuple(g["shape"]))


def warp_to_grid(href: str, grid: Grid, resampling: Resampling = Resampling.nearest,
                 band: int = 1, dtype=None) -> np.ndarray:
    """Read band `band` of any raster (local or HTTPS COG) resampled onto `grid`. Nodata -> NaN for floats."""
    with rasterio.open(href) as src, WarpedVRT(src, crs=f"EPSG:{grid.epsg}", transform=grid.affine,
                                                width=grid.shape[1], height=grid.shape[0],
                                                resampling=resampling) as vrt:
        arr = vrt.read(band)
        if dtype is not None:
            arr = arr.astype(dtype)
        if np.issubdtype(arr.dtype, np.floating) and vrt.nodata is not None:
            arr[arr == vrt.nodata] = np.nan
    return arr
