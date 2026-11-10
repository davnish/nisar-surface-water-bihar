"""Map figures. Every map is stamped with acquisition date(s), CRS, resolution and data source."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, MaxNLocator


def _footer(ax, dates: str, epsg: int, resolution_m: float, source: str) -> None:
    ax.annotate(f"Date(s): {dates}  |  CRS: EPSG:{epsg}  |  Resolution: {resolution_m:g} m\nSource: {source}",
                xy=(0, -0.13), xycoords="axes fraction", fontsize=7, ha="left", va="top", color="#52514e")


def _axes_km(ax) -> None:
    km = FuncFormatter(lambda v, _: f"{v / 1000:.0f}")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_locator(MaxNLocator(nbins=6, steps=[1, 2, 5, 10]))
    ax.xaxis.set_major_formatter(km)
    ax.yaxis.set_major_formatter(km)
    ax.set_xlabel("Easting (km)", fontsize=9)
    ax.set_ylabel("Northing (km)", fontsize=9)
    ax.tick_params(labelsize=8)


def _extent(transform: tuple, shape: tuple[int, int]) -> list[float]:
    a, _, c, _, e, f = transform[:6]
    return [c, c + a * shape[1], f + e * shape[0], f]


def save_continuous(arr: np.ndarray, transform: tuple, epsg: int, path: Path, *, title: str, dates: str,
                    resolution_m: float, source: str, label: str = "dB", vmin=None, vmax=None,
                    cmap: str = "gray") -> Path:
    fig, ax = plt.subplots(figsize=(7, 7))
    lo, hi = np.nanpercentile(arr, [2, 98]) if vmin is None else (vmin, vmax)
    im = ax.imshow(arr, extent=_extent(transform, arr.shape), cmap=cmap, vmin=lo, vmax=hi)
    fig.colorbar(im, ax=ax, shrink=0.7, label=label)
    ax.set_title(title)
    _axes_km(ax)
    _footer(ax, dates, epsg, resolution_m, source)
    return _save(fig, path)


def save_categorical(arr: np.ndarray, transform: tuple, epsg: int, path: Path, *, title: str, dates: str,
                     resolution_m: float, source: str, classes: dict[int, tuple[str, str]]) -> Path:
    """classes: {value: (label, colour)}. Values not listed (e.g. nodata 255) are transparent."""
    vals = sorted(classes)
    cmap = ListedColormap([classes[v][1] for v in vals])
    norm = BoundaryNorm([v - 0.5 for v in vals] + [vals[-1] + 0.5], cmap.N)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(np.ma.masked_where(~np.isin(arr, vals), arr), extent=_extent(transform, arr.shape),
              cmap=cmap, norm=norm, interpolation="nearest")
    ax.legend(handles=[Patch(color=classes[v][1], label=classes[v][0]) for v in vals],
              loc="upper right", fontsize=7, framealpha=0.9)
    ax.set_title(title)
    _axes_km(ax)
    _footer(ax, dates, epsg, resolution_m, source)
    return _save(fig, path)


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def save_rgb(rgb: np.ndarray, transform: tuple, epsg: int, path: Path, *, title: str, dates: str,
             resolution_m: float, source: str, pct: tuple[float, float] = (2, 98)) -> Path:
    """rgb: (rows, cols, 3) reflectance; each band stretched to its own percentiles."""
    out = np.zeros_like(rgb, dtype=np.float32)
    for i in range(3):
        lo, hi = np.nanpercentile(rgb[..., i], pct)
        out[..., i] = np.clip((rgb[..., i] - lo) / (hi - lo + 1e-9), 0, 1)
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(np.nan_to_num(out), extent=_extent(transform, rgb.shape[:2]))
    ax.set_title(title)
    _axes_km(ax)
    _footer(ax, dates, epsg, resolution_m, source)
    return _save(fig, path)
