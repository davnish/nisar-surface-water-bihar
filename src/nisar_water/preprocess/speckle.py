"""Speckle filters for linear-power intensity images (apply before converting to dB). NaNs are respected."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter


def _local_moments(img: np.ndarray, size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """NaN-aware local mean and variance over a size x size window, plus valid-pixel weight."""
    valid = np.isfinite(img)
    x = np.where(valid, img, 0.0).astype(np.float64)
    w = uniform_filter(valid.astype(np.float64), size)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = uniform_filter(x, size) / w
        var = uniform_filter(x * x, size) / w - mean**2
    return mean, np.maximum(var, 0), w


def boxcar(img: np.ndarray, size: int = 5) -> np.ndarray:
    mean, _, _ = _local_moments(img, size)
    return np.where(np.isfinite(img), mean, np.nan).astype(np.float32)


def lee(img: np.ndarray, size: int = 7, looks: float = 1.0) -> np.ndarray:
    """Lee (1980) MMSE filter. `looks` = equivalent number of looks of the input (GCOV: numberOfLooks layer)."""
    mean, var, _ = _local_moments(img, size)
    cu2 = 1.0 / looks  # squared speckle coefficient of variation for an L-look intensity image
    with np.errstate(invalid="ignore", divide="ignore"):
        ci2 = var / mean**2
        k = np.clip(1 - cu2 / ci2, 0, 1)
    out = mean + k * (img - mean)
    return np.where(np.isfinite(img), out, np.nan).astype(np.float32)


def apply(img: np.ndarray, spec: dict) -> np.ndarray:
    """spec from config: {name: none|boxcar|lee, size: int, looks: float}."""
    name = spec.get("name", "none")
    if name == "none":
        return img
    if name == "boxcar":
        return boxcar(img, spec.get("size", 5))
    if name == "lee":
        return lee(img, spec.get("size", 7), spec.get("looks", 1.0))
    raise NotImplementedError(f"speckle filter {name!r}")
