"""Radiometric conversions for GCOV backscatter terms."""
from __future__ import annotations

import numpy as np


def to_db(linear: np.ndarray, floor: float = 1e-6) -> np.ndarray:
    """Linear power -> dB. Values <= 0 are clipped to `floor` before the log; NaN stays NaN."""
    with np.errstate(invalid="ignore"):
        return (10.0 * np.log10(np.maximum(linear, floor))).astype(np.float32)


def from_db(db: np.ndarray) -> np.ndarray:
    return (10.0 ** (db / 10.0)).astype(np.float32)


def gamma0_to_sigma0(gamma0: np.ndarray, rtc_gamma_to_sigma: np.ndarray) -> np.ndarray:
    """Apply the GCOV `rtcGammaToSigmaFactor` layer (linear) to get sigma0. GCOV is gamma0 by default."""
    return gamma0 * rtc_gamma_to_sigma
