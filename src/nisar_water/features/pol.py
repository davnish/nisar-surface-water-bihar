"""Backscatter features from GCOV diagonal terms (dB), computed after speckle filtering in linear power."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter

from nisar_water.preprocess import speckle
from nisar_water.preprocess.calibrate import to_db


def estimate_enl(intensity: np.ndarray, mask: np.ndarray | None = None, win: int = 7, keep: float = 0.1) -> float:
    """Equivalent number of looks = median (mean/std)^2 over the most homogeneous `keep` fraction of windows.

    `mask` restricts windows to a region (e.g. reference land in L01); without it, all valid pixels are used,
    which keeps the operational pipeline reference-free.
    """
    region = np.isfinite(intensity) if mask is None else (mask & np.isfinite(intensity))
    x = np.where(region, intensity, 0.0).astype(np.float64)
    full = uniform_filter(region.astype(np.float64), win) > 0.999
    m = uniform_filter(x, win)
    v = uniform_filter(x * x, win) - m**2
    with np.errstate(invalid="ignore", divide="ignore"):
        enl = (m**2 / v)[full & (v > 0)]
    enl = np.sort(enl[np.isfinite(enl)])
    return float(np.median(enl[-max(1, int(keep * enl.size)):]))


def resolve_filter(spec: dict, hh: np.ndarray) -> dict:
    """Fill `looks: auto` for the Lee filter with a per-scene ENL estimate."""
    if spec.get("name") == "lee" and spec.get("looks", "auto") == "auto":
        return {**spec, "looks": estimate_enl(hh)}
    return spec


def features_db(ds, spec: dict) -> dict[str, np.ndarray]:
    """HH, HV (dB), HV-HH ratio (dB) and span = HH + HV (linear) in dB, after filtering in linear power."""
    hh = speckle.apply(ds["HHHH"].values, spec)
    out = {"HH": to_db(hh)}
    if "HVHV" in ds:
        hv = speckle.apply(ds["HVHV"].values, spec)
        out.update({"HV": to_db(hv), "HV-HH": to_db(hv) - out["HH"], "span": to_db(hh + hv)})
    return out
