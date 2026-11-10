import numpy as np

from nisar_water.change.classes import (STABLE_NONWATER, STABLE_WATER, WATER_GAIN, WATER_LOSS,
                                        change_map, class_areas_km2, new_water_outside_persistent)
from nisar_water.validate.metrics import evaluate


def test_metrics_known_confusion():
    pred = np.array([1, 1, 1, 0, 0, 0, 255], dtype=np.uint8)
    ref = np.array([1, 1, 0, 1, 0, 0, 1], dtype=np.uint8)
    m = evaluate(pred, ref)
    assert m["confusion"] == {"tp": 2, "fp": 1, "fn": 1, "tn": 2}
    assert np.isclose(m["precision"], 2 / 3) and np.isclose(m["recall"], 2 / 3)
    assert np.isclose(m["f1"], 2 / 3) and np.isclose(m["iou"], 0.5)
    assert np.isclose(m["overall_accuracy"], 4 / 6)


def test_change_truth_table():
    earlier = np.array([0, 1, 0, 1, 255, 0], dtype=np.uint8)
    later = np.array([0, 1, 1, 0, 1, 255], dtype=np.uint8)
    assert change_map(earlier, later).tolist() == [STABLE_NONWATER, STABLE_WATER, WATER_GAIN, WATER_LOSS, 255, 255]


def test_new_water_outside_persistent_and_area():
    change = np.array([WATER_GAIN, WATER_GAIN, STABLE_WATER, WATER_LOSS], dtype=np.uint8)
    persistent = np.array([1, 0, 1, 0], dtype=np.uint8)
    assert new_water_outside_persistent(change, persistent).tolist() == [False, True, False, False]
    areas = class_areas_km2(change, pixel_area_m2=20 * 20)
    assert np.isclose(areas["Newly detected water (gain)"], 2 * 400 / 1e6)
