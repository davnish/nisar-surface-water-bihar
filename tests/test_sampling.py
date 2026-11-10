from types import SimpleNamespace

import numpy as np

from nisar_water.validate.sampling import TEST, TRAIN, block_split


def test_block_split_is_blockwise_stratified_and_reproducible():
    strata = np.zeros((100, 100), bool)
    strata[:40, :40] = True  # 16 "water" blocks of 10x10
    a = block_split((100, 100), 10, 0.25, strata=strata, seed=1)
    assert set(np.unique(a)) == {TRAIN, TEST}
    # each 10x10 block is a single label
    assert all(len(np.unique(a[r:r + 10, c:c + 10])) == 1 for r in range(0, 100, 10) for c in range(0, 100, 10))
    # stratified: exactly 25% of the water blocks are test
    assert (a[:40, :40] == TEST).mean() == 0.25
    np.testing.assert_array_equal(a, block_split((100, 100), 10, 0.25, strata=strata, seed=1))


def test_cloud_buffer_skips_small_specks(monkeypatch):
    """Isolated SCL 'cloud' specks (bright sand) stay masked but are not buffered; real clouds are."""
    from nisar_water.grid import Grid
    from nisar_water.io import ancillary as anc

    scl = np.full((200, 200), 5, np.uint8)
    scl[10:12, 10:12] = 8            # 4 px speck
    scl[100:150, 100:150] = 9        # 2500 px cloud
    monkeypatch.setattr(anc, "warp_to_grid", lambda *a, **k: scl)
    item = SimpleNamespace(assets={"SCL": SimpleNamespace(href="scl.tif")}, properties={})
    clear, _ = anc.s2_clear_mask(item, Grid(32645, (10, 0, 0, 0, -10, 0), (200, 200)), blue_max=None,
                                 buffer_px=5, buffer_min_px=100)
    assert not clear[10, 10] and clear[10, 14]          # speck masked, not buffered
    assert not clear[100, 96] and clear[100, 92]        # cloud buffered by 5 px only
