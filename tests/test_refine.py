import numpy as np

from nisar_water.classify.refine import refine


def test_mmu_removes_small_objects_and_keeps_nodata():
    m = np.zeros((30, 30), np.uint8)
    m[2:8, 2:8] = 1      # 36 px lake
    m[20, 20] = 1        # 1 px speck
    m[25:27, 25:27] = 1  # 4 px pond
    m[0, 29] = 255
    out = refine(m, mmu_px=5)
    assert out[4, 4] == 1 and out[20, 20] == 0 and out[25, 25] == 0 and out[0, 29] == 255


def test_hand_exclusion():
    m = np.ones((4, 4), np.uint8)
    hand = np.zeros((4, 4), np.float32)
    hand[0, :] = 30.0
    out = refine(m, hand=hand, hand_max_m=15)
    assert out[0].sum() == 0 and out[1:].all()
