"""GeoTIFF/COG writing and reading for masks and features."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine


def write_cog(arr: np.ndarray, path: Path, transform: tuple, epsg: int, nodata=None,
              tags: dict | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if nodata is None:
        nodata = 255 if arr.dtype == np.uint8 else np.nan
    with rasterio.open(path, "w", driver="COG", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype=str(arr.dtype), crs=f"EPSG:{epsg}", transform=Affine(*transform[:6]),
                       nodata=nodata, compress="deflate") as dst:
        dst.write(arr, 1)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    return path


def read(path: Path) -> tuple[np.ndarray, dict]:
    with rasterio.open(path) as src:
        return src.read(1), {"transform": tuple(src.transform)[:6], "epsg": src.crs.to_epsg(), "nodata": src.nodata}
