"""Ancillary reference data from Microsoft Planetary Computer (STAC): Sentinel-2 L2A, JRC GSW, Sentinel-1 RTC.

Everything is read straight from cloud COGs onto the analysis grid (nothing is downloaded whole).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
import planetary_computer as pc
import pystac_client
from rasterio.enums import Resampling
from scipy.ndimage import binary_dilation, label

from nisar_water.grid import Grid, warp_to_grid

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
# Sentinel-2 Scene Classification: 0 nodata, 1 saturated/defective, 3 cloud shadow, 8/9 cloud, 10 cirrus
SCL_INVALID = (0, 1, 3, 8, 9, 10)
SCL_WATER = 6


@lru_cache(maxsize=1)
def catalog():
    return pystac_client.Client.open(STAC_URL, modifier=pc.sign_inplace)


def search(collection: str, bbox_wsen: list[float], start: pd.Timestamp, end: pd.Timestamp) -> list:
    rng = f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    return list(catalog().search(collections=[collection], bbox=bbox_wsen, datetime=rng).items())


# --- Sentinel-2 -------------------------------------------------------------------------------

def s2_clear_mask(item, grid: Grid, blue_max: float | None = 0.2, blue_red_min: float = 0.85,
                  buffer_px: int = 0, buffer_min_px: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """Clear-sky mask: SCL valid and not a bright *white* pixel, with invalid areas dilated by buffer_px.

    SCL alone misses broken cumulus fields (R00: 2026-01-01 scene, ~90% cumulus, SCL 99.5% "clear").
    Cloud is bright and spectrally flat (B02/B04 0.90-1.01 in that scene), while bright sand bars and
    settlements are yellow-red (B02/B04 0.71-0.81 on the clear 2026-01-16 scene), so a pixel is cloud if
    B02 > blue_max AND B02/B04 >= blue_red_min. A brightness test alone removed ~14% of clear scenes
    (sand + buffer), biasing the reference away from sand bars, the main SAR false-positive zone.

    Only invalid clusters of >= buffer_min_px pixels are buffered (disk of radius buffer_px): SCL flags
    isolated bright-sand specks as cloud (class 8), and buffering those punched 400 m holes in the sand bars.
    """
    scl = warp_to_grid(item.assets["SCL"].href, grid, Resampling.nearest)
    invalid = np.isin(scl, SCL_INVALID)
    if blue_max is not None:
        blue, red = s2_reflectance(item, "B02", grid), s2_reflectance(item, "B04", grid)
        with np.errstate(invalid="ignore", divide="ignore"):
            invalid |= (blue > blue_max) & (blue / red >= blue_red_min)
        invalid |= ~np.isfinite(blue)
    if buffer_px:
        labels, _ = label(invalid)
        sizes = np.bincount(labels.ravel())
        sizes[0] = 0
        big = sizes[labels] >= buffer_min_px
        yy, xx = np.mgrid[-buffer_px:buffer_px + 1, -buffer_px:buffer_px + 1]
        invalid |= binary_dilation(big, structure=xx**2 + yy**2 <= buffer_px**2)
    return ~invalid, scl


def s2_reflectance(item, band: str, grid: Grid) -> np.ndarray:
    """Surface reflectance on the grid. Processing baseline >= 04.00 adds a +1000 DN offset (removed here)."""
    dn = warp_to_grid(item.assets[band].href, grid, Resampling.bilinear, dtype=np.float32)
    offset = 1000.0 if float(item.properties.get("s2:processing_baseline", "0")) >= 4.0 else 0.0
    refl = (dn - offset) / 10000.0
    refl[dn == 0] = np.nan  # DN 0 = nodata
    return refl


def mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Modified NDWI (Xu 2006): (G - SWIR1) / (G + SWIR1)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return (green - swir) / (green + swir)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI (McFeeters 1996): (G - NIR) / (G + NIR)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return (green - nir) / (green + nir)


# --- JRC Global Surface Water ------------------------------------------------------------------

def jrc_layer(layer: str, grid: Grid, bbox_wsen: list[float]) -> np.ndarray:
    """JRC GSW v1.3 (1984-2020) layer on the grid, e.g. 'occurrence' (0-100 %), 'seasonality' (months)."""
    items = catalog().search(collections=["jrc-gsw"], bbox=bbox_wsen).item_collection()
    return warp_to_grid(items[0].assets[layer].href, grid, Resampling.nearest)


# --- Sentinel-1 RTC ----------------------------------------------------------------------------

def s1_db(item, pol: str, grid: Grid) -> np.ndarray:
    """Sentinel-1 RTC gamma0 (linear in the COG) on the grid, in dB."""
    lin = warp_to_grid(item.assets[pol.lower()].href, grid, Resampling.bilinear, dtype=np.float32)
    lin[(lin <= 0) | ~np.isfinite(lin)] = np.nan
    return 10 * np.log10(lin)
