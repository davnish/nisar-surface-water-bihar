"""Full-polarimetric features from NISAR L2 GCOV quad-pol covariance terms (L08, Task H).

Inputs are the 10 GCOV terms of frequency A for QP modes (HHHH, HHHV, HHVH, HHVV, HVHV, HVVH, HVVV, VHVH,
VHVV, VVVV). Every term is boxcar-averaged (NaN-aware, real and imaginary parts separately) before any
non-linear descriptor, as decompositions require an ensemble-averaged covariance. GCOV is not
polarimetrically symmetrised; reciprocity is imposed here (S_X = (S_HV + S_VH)/2), and a co-pol phase
offset estimated on coherent distributed targets is removed from the VV-related terms before decompositions.

Descriptors (all from the vendored nisar-polarimetric-training toolkit, conventions documented there):
- backscatter (dB): HH, HV, VV, span; ratios VV-HH (co-pol), HV-VV and HV-HH (cross/co)
- co-pol coherence |<HH VV*>| / sqrt(<|HH|^2><|VV|^2>) and HH-VV phase difference (deg)
- Cloude-Pottier entropy H, anisotropy A, mean alpha (deg), from the Pauli coherency matrix T3
- Pauli powers (dB): |HH+VV|^2/2 (surface), |HH-VV|^2/2 (double bounce), 2|HV|^2 (volume)
- Freeman-Durden surface / double-bounce / volume fractions of span
"""
from __future__ import annotations

import numpy as np

from nisar_water._npt import polarimetry as pol
from nisar_water.preprocess.calibrate import to_db
from nisar_water.preprocess.speckle import boxcar

QP_TERMS = ["HHHH", "HHHV", "HHVH", "HHVV", "HVHV", "HVVH", "HVVV", "VHVH", "VHVV", "VVVV"]


def _avg(a: np.ndarray, size: int) -> np.ndarray:
    a = np.asarray(a)
    if np.iscomplexobj(a):
        return (boxcar(a.real, size) + 1j * boxcar(a.imag, size)).astype(np.complex64)
    return boxcar(a.astype(np.float32), size)


def features_polsar(ds, spec: dict) -> dict[str, np.ndarray]:
    size = int(spec.get("size", 5)) if spec.get("name") != "none" else 1
    t = {k: (_avg(ds[k].values, size) if size > 1 else ds[k].values) for k in QP_TERMS if k in ds}
    if spec.get("symmetrize", True) and all(k in t for k in ("VHVH", "HVVH", "HHVH", "VHVV")):
        # reciprocal symmetrization (GCOV: polarimetricSymmetrizationApplied = False): S_X = (S_HV + S_VH) / 2
        t["HVHV"] = 0.25 * (np.real(t["HVHV"]) + np.real(t["VHVH"]) + 2 * np.real(t["HVVH"]))
        t["HHHV"] = 0.5 * (t["HHHV"] + t["HHVH"])
        t["HVVV"] = 0.5 * (t["HVVV"] + t["VHVV"])
        for k in ("HHVH", "VHVV", "VHVH", "HVVH"):
            t.pop(k)
    hh, hv, vv = (np.real(t[k]).astype(np.float32) for k in ("HHHH", "HVHV", "VVVV"))
    valid = np.isfinite(hh) & np.isfinite(hv) & np.isfinite(vv) & (hh > 0) & (vv > 0)
    out = {"HH": to_db(hh), "HV": to_db(hv), "VV": to_db(vv)}
    out["HV-HH"] = out["HV"] - out["HH"]
    out["VV-HH"] = out["VV"] - out["HH"]
    out["HV-VV"] = out["HV"] - out["VV"]

    if spec.get("copol_phase_cal", True):
        # co-pol phase calibration on distributed targets: the scene's coherent pixels (|gamma_HHVV| > 0.6) are
        # dominated by surface-like scattering whose HH-VV phase should be ~0 deg; the delivered terms show a
        # large systematic offset (about -158 deg on 2025-11-30), so the circular-mean offset is removed from
        # HHVV (and, consistently, from the VV-related cross terms) before any decomposition.
        with np.errstate(all="ignore"):
            g = np.abs(t["HHVV"]) / np.sqrt(hh * vv)
        sel = valid & (g > 0.6)
        phi0 = float(np.angle(np.nanmean(t["HHVV"][sel] / np.abs(t["HHVV"][sel])))) if sel.sum() > 1000 else 0.0
        rot = np.exp(-1j * phi0).astype(np.complex64)
        t["HHVV"] = t["HHVV"] * rot
        for k in ("HVVV", "VHVV"):  # <S_xy S_VV*>: a VV phase offset phi0 enters conjugated, same as in HHVV
            if k in t:
                t[k] = t[k] * rot
        ds.attrs["copol_phase_offset_deg"] = round(float(np.degrees(phi0)), 2)
    C = pol.covariance_hermitian_from_terms(t)
    C[~valid] = np.nan
    Cs = pol.nisar_c3_to_standard_c3(C)
    T = pol.standard_c3_to_t3(Cs)
    with np.errstate(all="ignore"):
        hhvv = t["HHVV"]
        out["copol_coh"] = (np.abs(hhvv) / np.sqrt(hh * vv)).astype(np.float32)
        out["copol_phase_deg"] = np.degrees(np.angle(hhvv)).astype(np.float32)
        eig = pol.eigen_analysis(T, clip_negative=True)
        out["H"] = eig["entropy"].astype(np.float32)
        out["A"] = eig["anisotropy"].astype(np.float32)
        out["alpha_deg"] = np.degrees(pol.cloude_pottier_mean_alpha(eig["eigenvectors"], eig["probabilities"])).astype(np.float32)
        span = np.real(T[..., 0, 0] + T[..., 1, 1] + T[..., 2, 2]).astype(np.float32)
        out["span"] = to_db(span)
        for i, name in enumerate(("pauli_surface", "pauli_double", "pauli_volume")):
            out[name] = to_db(np.maximum(np.real(T[..., i, i]), 1e-10).astype(np.float32))
        fd = pol.fullpol_freeman_durden(C)
        for k in ("surface", "double_bounce", "volume"):
            out[f"fd_{k}_frac"] = (fd[k] / np.maximum(fd["span"], 1e-10)).astype(np.float32)
    return {k: np.where(valid, v, np.nan).astype(np.float32) for k, v in out.items()}
