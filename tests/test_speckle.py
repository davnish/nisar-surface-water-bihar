import numpy as np

from nisar_water.preprocess import speckle


def test_filters_reduce_speckle_and_keep_mean():
    rng = np.random.default_rng(0)
    img = rng.exponential(0.1, (200, 200)).astype(np.float32)  # 1-look speckle, mean 0.1
    for f in (speckle.boxcar(img, 7), speckle.lee(img, 7, looks=1)):
        assert abs(np.nanmean(f) - 0.1) < 0.005
        assert np.nanstd(f) < 0.5 * np.std(img)


def test_nan_preserved():
    img = np.full((20, 20), 0.1, np.float32)
    img[5, 5] = np.nan
    out = speckle.lee(img, 5)
    assert np.isnan(out[5, 5]) and np.isfinite(out[5, 6])
