"""S-band compact-polarimetric (CP: circular transmit, H/V receive) features from NISAR GCOV (Task H iii).

GCOV CP products store the 2x2 covariance of the received H and V channels for circular transmit
(terms named e.g. RHRH, RHRV, RVRV). Terms are boxcar-averaged before the non-linear descriptors.
Stokes vector and child parameters use the vendored nisar-polarimetric-training conventions
(chirality sign -1, i.e. right-circular transmit as in its notebooks):
- g0 (total power), RH, RV (dB), RV - RH
- degree of polarisation m, ellipticity chi (deg), relative phase delta (deg), alpha_s (deg)
- m-chi decomposition (Raney et al. 2012): surface / double-bounce / volume powers (dB) and fractions.
"""
from __future__ import annotations

import numpy as np

from nisar_water._npt import polarimetry as pol
from nisar_water.features.polsar import _avg
from nisar_water.preprocess.calibrate import to_db


def cp_terms(ds) -> tuple[str, str, str]:
    names = [v for v in ds.data_vars if len(v) == 4 and v.isupper() and v != "mask"]
    diag = sorted(v for v in names if v[:2] == v[2:])
    off = [v for v in names if v[:2] != v[2:]]
    if len(diag) != 2 or not off:
        raise KeyError(f"not a compact-pol covariance: {names}")
    h = next(d for d in diag if d.endswith("H"))
    v = next(d for d in diag if d.endswith("V"))
    return h, off[0], v


def features_compact(ds, spec: dict) -> dict[str, np.ndarray]:
    size = int(spec.get("size", 3)) if spec.get("name") != "none" else 1
    th, tx, tv = cp_terms(ds)
    a = {k: (_avg(ds[k].values, size) if size > 1 else ds[k].values) for k in (th, tx, tv)}
    rh, rv = np.real(a[th]).astype(np.float32), np.real(a[tv]).astype(np.float32)
    valid = np.isfinite(rh) & np.isfinite(rv) & (rh > 0) & (rv > 0)
    with np.errstate(all="ignore"):
        g0, g1, g2, g3 = pol.stokes_from_compact_terms(rh, a[tx], rv)
        ch = pol.compact_child_parameters(g0, g1, g2, g3)
        mc = pol.m_chi_decomposition(g0, ch["m"], ch["chi2"])
        out = {"HH": to_db(rh), "RV": to_db(rv), "g0": to_db(g0)}  # 'HH' key = RH power, so texture/thresholds work
        out["RV-RH"] = out["RV"] - out["HH"]
        out["m"] = ch["m"]
        out["chi_deg"] = np.degrees(ch["chi2"]) / 2
        out["delta_deg"] = np.degrees(ch["delta"])
        out["alpha_s_deg"] = np.degrees(ch["alpha_s"])
        for k, v in mc.items():
            out[f"mchi_{k}"] = to_db(np.maximum(v, 1e-10))
            out[f"mchi_{k}_frac"] = v / np.maximum(g0, 1e-10)
    return {k: np.where(valid, np.asarray(v, np.float32), np.nan).astype(np.float32) for k, v in out.items()}
