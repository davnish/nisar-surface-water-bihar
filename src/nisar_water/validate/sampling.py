"""Spatial-block train/test split, so spatial autocorrelation does not leak between training and evaluation."""
from __future__ import annotations

import numpy as np

TRAIN, TEST, NODATA = 1, 2, 0


def block_split(shape: tuple[int, int], block_px: int, test_fraction: float, strata: np.ndarray | None = None,
                seed: int = 42) -> np.ndarray:
    """uint8 raster of TRAIN/TEST blocks. If `strata` (bool raster) is given, blocks containing any True
    pixel and blocks without are split separately, so both sets get the same share of e.g. water blocks."""
    rng = np.random.default_rng(seed)
    nby, nbx = -(-shape[0] // block_px), -(-shape[1] // block_px)
    block_ids = np.arange(nby * nbx).reshape(nby, nbx)
    if strata is None:
        has = np.zeros(nby * nbx, bool)
    else:
        pad = np.zeros((nby * block_px, nbx * block_px), bool)
        pad[: shape[0], : shape[1]] = strata
        has = pad.reshape(nby, block_px, nbx, block_px).any(axis=(1, 3)).ravel()
    is_test = np.zeros(nby * nbx, bool)
    for group in (np.flatnonzero(has), np.flatnonzero(~has)):
        n_test = int(round(len(group) * test_fraction))
        is_test[rng.permutation(group)[:n_test]] = True
    blocks = np.where(is_test, TEST, TRAIN).astype(np.uint8)[block_ids]
    return np.kron(blocks, np.ones((block_px, block_px), np.uint8))[: shape[0], : shape[1]]
