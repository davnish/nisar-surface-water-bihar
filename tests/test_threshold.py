import numpy as np

from nisar_water.classify import threshold


def _bimodal(seed=0):
    rng = np.random.default_rng(seed)
    return np.concatenate([rng.normal(-22, 1.5, 4000), rng.normal(-8, 2.0, 6000)]).astype(np.float32)


def test_auto_thresholds_split_modes():
    db = _bimodal()
    for t in (threshold.otsu(db), threshold.kittler_illingworth(db)):
        assert -19 < t < -11


def test_apply_handles_nan():
    m = threshold.apply(np.array([-25, -5, np.nan], dtype=np.float32), -15)
    assert m.tolist() == [1, 0, 255]


def test_tiled_beats_global_when_water_is_rare():
    """Land has two spatially clustered classes and water is ~3% in one corner: global Otsu splits land."""
    rng = np.random.default_rng(1)
    patches = np.kron(rng.random((4, 4)) < 0.6, np.ones((256, 256), bool))  # 256 px land-class patches
    img = np.where(patches, rng.normal(-6, 1.5, (1024, 1024)), rng.normal(-12, 1.5, (1024, 1024)))
    img[:180, :180] = rng.normal(-22, 1.5, (180, 180))  # water body
    img = img.astype(np.float32)
    assert threshold.otsu(img) > -15  # global threshold lands between land classes
    t, info = threshold.tiled(img, tile=128)
    assert -20 < t < -14 and info["tiles_used"] > 0


def test_hysteresis_keeps_seeded_regions_only():
    db = np.full((20, 20), -8.0, np.float32)
    db[2:6, 2:6] = -20.0          # water body with a confident core
    db[2:6, 6] = -15.5            # fringe just above threshold, attached to water -> grown
    db[15, 15] = -16.5            # isolated speck below threshold, no seed -> dropped
    m = threshold.hysteresis(db, threshold=-16.0, seed_db=1.0, grow_db=1.0)
    assert m[3, 3] == 1 and m[3, 6] == 1 and m[15, 15] == 0


def test_bounded_ki_avoids_tail_solution():
    """Tiny water class + long bright tail: unbounded KI may split the tail; bounded KI stays between modes."""
    rng = np.random.default_rng(3)
    db = np.concatenate([rng.normal(-19, 1.2, 600), rng.normal(-10, 2.5, 20000), rng.normal(5, 1.0, 300)])
    lo, hi = -19.0, -10.0
    t = threshold.kittler_illingworth(db.astype(np.float32), bounds=(lo, hi))
    assert lo <= t <= hi
