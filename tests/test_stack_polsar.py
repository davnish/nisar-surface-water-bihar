import numpy as np
import xarray as xr

from nisar_water.features.polsar import QP_TERMS, features_polsar
from nisar_water.features.stack import temporal, texture


def _qp(hh, hv, vv, hhvv):
    shape = (20, 20)
    vals = {"HHHH": hh, "HVHV": hv, "VHVH": hv, "VVVV": vv, "HHVV": hhvv}
    data = {}
    for t in QP_TERMS:
        v = vals.get(t, 0.0)
        dtype = np.complex64 if t[:2] != t[2:] else np.float32
        data[t] = (("y", "x"), np.full(shape, v, dtype))
    return xr.Dataset(data)


def test_pure_surface_scatterer_has_zero_entropy_and_alpha():
    # S = diag(1, 1) (HH = VV, in phase, no cross-pol): T3 = diag(2, 0, 0)
    f = features_polsar(_qp(1.0, 1e-9, 1.0, 1.0 + 0j), {"name": "boxcar", "size": 3})
    assert np.nanmax(f["H"]) < 0.01
    assert np.nanmax(f["alpha_deg"]) < 1.0
    assert np.allclose(f["copol_coh"][5:-5, 5:-5], 1.0, atol=1e-3)
    assert np.allclose(f["VV-HH"][5:-5, 5:-5], 0.0, atol=1e-3)


def test_dihedral_has_alpha_90():
    # HH = -VV: T3 = diag(0, 2, 0) -> alpha = 90 deg
    f = features_polsar(_qp(1.0, 1e-9, 1.0, -1.0 + 0j), {"name": "boxcar", "size": 3})
    assert np.nanmin(f["alpha_deg"][5:-5, 5:-5]) > 89.0


def test_texture_and_temporal_shapes_and_values():
    rng = np.random.default_rng(0)
    hh = rng.normal(-12, 1, (40, 40)).astype(np.float32)
    hh[0, 0] = np.nan
    t = texture({"HH": hh, "HV": hh - 8})
    assert set(t) >= {"HH_m5", "HH_s5", "HH_m15", "HH_s15", "HH_min15", "HV_m15"}
    assert np.isnan(t["HH_m5"][0, 0]) and np.isfinite(t["HH_m5"][20, 20])
    assert t["HH_min15"][20, 20] <= hh[20, 20]
    st = temporal({"HH": [hh, hh + 2, hh - 2], "HV": [hh - 8] * 3})
    assert np.allclose(st["HH_tmed"][20, 20], hh[20, 20])
    assert np.allclose(st["HH_tmax"][20, 20] - st["HH_tmin"][20, 20], 4)
