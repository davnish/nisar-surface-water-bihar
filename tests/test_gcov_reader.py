"""GCOV reader on a synthetic HDF5 mimicking the L2 GCOV grid layout."""
import h5py
import numpy as np
import pytest

from nisar_water.io.gcov import read_gcov

NAME = "NISAR_L2_PR_GCOV_033_098_A_014_4005_DHDH_A_20261018T233811_20261018T233845_P05023_N_F_J_001.h5"


@pytest.fixture
def gcov_file(tmp_path):
    p = tmp_path / NAME
    ny, nx = 60, 50
    x = 500_000 + 20.0 * np.arange(nx) + 10   # UTM 45N, pixel centres
    y = 2_830_000 - 20.0 * np.arange(ny) - 10
    with h5py.File(p, "w") as f:
        g = f.create_group("science/LSAR/GCOV/grids/frequencyA")
        g["xCoordinates"], g["yCoordinates"] = x, y
        g["xCoordinateSpacing"], g["yCoordinateSpacing"] = 20.0, -20.0
        g.create_dataset("projection", data=np.uint32(32645)).attrs["epsg_code"] = 32645
        hh = np.full((ny, nx), 0.1, np.float32)
        hh[:, :10] = 0.001  # dark "water" strip
        g["HHHH"], g["HVHV"] = hh, hh / 10
        mask = np.ones((ny, nx), np.uint8)
        mask[0, :] = 255
        g["mask"] = mask
    return p, x, y


def test_full_read_masks_fill(gcov_file):
    p, _, _ = gcov_file
    ds = read_gcov(p)
    assert set(ds.data_vars) == {"HHHH", "HVHV", "mask"}
    assert np.isnan(ds.HHHH.values[0]).all() and np.isfinite(ds.HHHH.values[1:]).all()
    assert ds.attrs["epsg"] == 32645 and ds.attrs["spacing_m"] == (20.0, 20.0)
    a, _, c, _, e, f = ds.attrs["transform"]
    assert (a, e, c, f) == (20.0, -20.0, 500_000.0, 2_830_000.0)


def test_bbox_window(gcov_file):
    p, x, y = gcov_file
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:32645", "EPSG:4326", always_xy=True)
    w, s = t.transform(x[5], y[40])
    e, n = t.transform(x[20], y[10])
    ds = read_gcov(p, terms=["HHHH"], bbox_wsen=[w, s, e, n])
    assert 0 < ds.sizes["x"] < len(x) and 0 < ds.sizes["y"] < len(y)
    assert ds.x.values.min() >= x[4] and ds.x.values.max() <= x[21]


def test_missing_term_raises(gcov_file):
    p, _, _ = gcov_file
    with pytest.raises(KeyError):
        read_gcov(p, terms=["VVVV"])


def test_window_cache_roundtrip(gcov_file, tmp_path):
    from nisar_water.io.gcov import fetch_window, load_window, window_path

    p, x, y = gcov_file
    out = window_path(tmp_path, p.name, "frequencyA")
    fetch_window(p, out)
    ds, cached = read_gcov(p), load_window(out)
    np.testing.assert_array_equal(ds.HHHH.values, cached.HHHH.values)
    assert cached.attrs["transform"] == ds.attrs["transform"] and cached.attrs["epsg"] == 32645
