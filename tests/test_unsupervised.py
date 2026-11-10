import numpy as np

from nisar_water.classify.unsupervised import gmm_water


def test_gmm_finds_dark_water_component():
    rng = np.random.default_rng(0)
    hh = rng.normal(-10, 1.5, (200, 200)).astype(np.float32)
    hv = rng.normal(-18, 1.5, (200, 200)).astype(np.float32)
    hh[:40, :40] = rng.normal(-20, 1.0, (40, 40))
    hv[:40, :40] = rng.normal(-26, 1.0, (40, 40))
    hh[0, 0] = np.nan
    m, info = gmm_water({"HH": hh, "HV": hv}, ["HH", "HV"], n_components=2)
    assert m[0, 0] == 255 and m[10:30, 10:30].mean() > 0.99 and m[100:, 100:].mean() < 0.01
    assert info["water_component_mean"][0] < -15
