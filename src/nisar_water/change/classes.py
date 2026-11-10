"""Change classes between two water masks (problem statement section 6)."""
from __future__ import annotations

import numpy as np

NODATA = 255
STABLE_NONWATER, STABLE_WATER, WATER_GAIN, WATER_LOSS = 0, 1, 2, 3
LABELS = {STABLE_NONWATER: "Stable non-water", STABLE_WATER: "Stable water",
          WATER_GAIN: "Newly detected water (gain)", WATER_LOSS: "Water loss (receded)"}


def change_map(earlier: np.ndarray, later: np.ndarray) -> np.ndarray:
    """uint8 change classes from two uint8 water masks (1 water, 0 non-water, 255 nodata)."""
    out = np.full(earlier.shape, NODATA, dtype=np.uint8)
    ok = (earlier != NODATA) & (later != NODATA)
    e, l = earlier == 1, later == 1
    out[ok & ~e & ~l] = STABLE_NONWATER
    out[ok & e & l] = STABLE_WATER
    out[ok & ~e & l] = WATER_GAIN
    out[ok & e & ~l] = WATER_LOSS
    return out


def new_water_outside_persistent(change: np.ndarray, persistent: np.ndarray) -> np.ndarray:
    """Boolean: water gain on pixels that are not persistent water (potential temporary inundation)."""
    return (change == WATER_GAIN) & (persistent != 1)


def class_areas_km2(change: np.ndarray, pixel_area_m2: float) -> dict[str, float]:
    return {LABELS[c]: float(np.sum(change == c) * pixel_area_m2 / 1e6) for c in LABELS}
