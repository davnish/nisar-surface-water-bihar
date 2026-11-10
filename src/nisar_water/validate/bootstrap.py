"""Spatial-block bootstrap of F1 and F1 differences between maps (uncertainty of a comparison).

Test pixels are grouped by their 2 km block; blocks are resampled with replacement, confusion matrices are
summed over the drawn blocks, and F1 (and differences against a baseline) are recomputed per draw. Blocks,
not pixels, are the sampling unit, so spatial autocorrelation does not shrink the intervals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def block_ids(shape: tuple[int, int], block_px: int) -> np.ndarray:
    nbx = -(-shape[1] // block_px)
    return (np.arange(shape[0])[:, None] // block_px) * nbx + np.arange(shape[1])[None, :] // block_px


def per_block_cm(pred: np.ndarray, ref: np.ndarray, bid: np.ndarray) -> pd.DataFrame:
    ok = (pred != 255) & (ref != 255)
    p, r, b = pred[ok] == 1, ref[ok] == 1, bid[ok]
    df = pd.DataFrame({"b": b, "tp": p & r, "fp": p & ~r, "fn": ~p & r})
    return df.groupby("b")[["tp", "fp", "fn"]].sum()


def bootstrap_f1(cms: dict[str, pd.DataFrame], baseline: str, n: int = 2000, seed: int = 0) -> pd.DataFrame:
    """cms: variant -> per-block confusion (same blocks). Returns F1 and F1 - baseline with 95 % intervals."""
    blocks = cms[baseline].index.values
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(blocks), size=(n, len(blocks)))
    out = {}
    for v, cm in cms.items():
        a = cm.reindex(blocks, fill_value=0)[["tp", "fp", "fn"]].to_numpy(float)
        s = a[draws].sum(1)
        out[v] = 2 * s[:, 0] / np.maximum(2 * s[:, 0] + s[:, 1] + s[:, 2], 1)
    rows = []
    for v, f in out.items():
        d = f - out[baseline]
        rows.append({"variant": v, "f1_median": np.median(f), "f1_lo": np.percentile(f, 2.5), "f1_hi": np.percentile(f, 97.5),
                     f"dF1_vs_{baseline}": np.median(d), "dF1_lo": np.percentile(d, 2.5), "dF1_hi": np.percentile(d, 97.5),
                     "p_better": float((d > 0).mean())})
    return pd.DataFrame(rows).set_index("variant")
