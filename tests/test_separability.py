import numpy as np

from nisar_water.tasks.separability import best_threshold_f1, jm_distance


def test_jm_distance_limits():
    rng = np.random.default_rng(0)
    a = rng.normal(0, 1, 50_000)
    assert jm_distance(a, rng.normal(0, 1, 50_000)) < 0.01
    assert jm_distance(a, rng.normal(10, 1, 50_000)) > 1.99


def test_best_threshold_f1_finds_gap_and_direction():
    water = np.full(1000, -22.0)
    land = np.full(4000, -8.0)
    f1, t, direction = best_threshold_f1(water, land)
    assert f1 == 1.0 and -22 < t <= -8 and direction == "<"
    f1, _, direction = best_threshold_f1(land, water)  # "water" brighter -> '>' direction
    assert f1 == 1.0 and direction == ">"
