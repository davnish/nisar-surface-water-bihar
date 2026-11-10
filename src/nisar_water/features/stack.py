"""Contextual feature stack for supervised classifiers (L07): local texture and multi-temporal statistics.

All inputs are the per-date dB features from `features.pol.features_db` (already speckle filtered). Texture
is computed per date; temporal statistics use every date of the same track/frame stack, so they are
reference-free and identical for all dates of a pixel (except the per-date anomaly).
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import minimum_filter

from nisar_water.preprocess.speckle import _local_moments


def texture(feats: dict[str, np.ndarray], sizes=(5, 15)) -> dict[str, np.ndarray]:
    """Local mean / std (dB) of HH at each window size, local minimum of HH and local mean of HV at the largest."""
    hh = feats["HH"]
    out = {}
    for s in sizes:
        m, v, _ = _local_moments(hh, s)
        out[f"HH_m{s}"] = m.astype(np.float32)
        out[f"HH_s{s}"] = np.sqrt(v).astype(np.float32)
    big = max(sizes)
    out[f"HH_min{big}"] = minimum_filter(np.where(np.isfinite(hh), hh, np.inf), big).astype(np.float32)
    if "HV" in feats:
        out[f"HV_m{big}"] = _local_moments(feats["HV"], big)[0].astype(np.float32)
    ok = np.isfinite(hh)
    return {k: np.where(ok & np.isfinite(v), v, np.nan).astype(np.float32) for k, v in out.items()}


def temporal(stack: dict[str, list[np.ndarray]]) -> dict[str, np.ndarray]:
    """Per-pixel statistics over dates. stack: feature name -> list of 2-D arrays (one per date)."""
    hh = np.stack(stack["HH"]).astype(np.float32)
    with np.errstate(all="ignore"), _quiet():
        out = {"HH_tmin": np.nanmin(hh, 0), "HH_tmed": np.nanmedian(hh, 0), "HH_tmax": np.nanmax(hh, 0),
               "HH_tstd": np.nanstd(hh, 0),
               "HH_tfrac_dark": np.nanmean(np.where(np.isfinite(hh), hh < -16.0, np.nan), 0)}
        if "HV" in stack:
            out["HV_tmed"] = np.nanmedian(np.stack(stack["HV"]).astype(np.float32), 0)
    return {k: v.astype(np.float32) for k, v in out.items()}


class _quiet:
    def __enter__(self):
        import warnings
        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", RuntimeWarning)

    def __exit__(self, *a):
        self._w.__exit__(*a)


REL_BASE = ("HH", "HH_m5", "HH_m15", "HH_min15")


def relative(feats: dict[str, np.ndarray], t_db: float) -> dict[str, np.ndarray]:
    """Scene-relative HH features: value minus the scene's own water/land threshold (tiled KI, reference-free).

    L-band water is brighter in the monsoon (wind/rain roughening, shallow water over crops): the C2 threshold
    moves from about -16 dB (dry season) to -11 dB. Relative features let a classifier trained on dry-season
    labels carry that per-scene adaptation over to unreferenced dates.
    """
    return {f"{k}_rel": (feats[k] - t_db).astype(np.float32) for k in REL_BASE if k in feats}
