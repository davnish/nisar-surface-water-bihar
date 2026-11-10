"""Contextual post-processing of water masks (uint8: 1 water, 0 non-water, 255 nodata)."""
from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_closing, binary_opening, label


def refine(mask: np.ndarray, mmu_px: int = 0, open_px: int = 0, close_px: int = 0,
           hand: np.ndarray | None = None, hand_max_m: float | None = None) -> np.ndarray:
    """Apply, in order: HAND exclusion (water above hand_max_m -> non-water), morphological opening and
    closing with a (2r+1)^2 square, and a minimum mapping unit (water objects < mmu_px pixels removed,
    8-connectivity). Nodata stays nodata."""
    nod = mask == 255
    w = mask == 1
    if hand is not None and hand_max_m is not None:
        w &= ~(hand > hand_max_m)
    if open_px:
        w = binary_opening(w, np.ones((2 * open_px + 1,) * 2, bool))
    if close_px:
        w = binary_closing(w, np.ones((2 * close_px + 1,) * 2, bool))
    if mmu_px:
        lab, _ = label(w, structure=np.ones((3, 3), bool))
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        w = sizes[lab] >= mmu_px
    out = w.astype(np.uint8)
    out[nod] = 255
    return out
