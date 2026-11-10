"""Histogram-threshold water classifiers on a single dB channel (water = darker than threshold)."""
from __future__ import annotations

import numpy as np
from skimage.filters import apply_hysteresis_threshold, threshold_otsu


def _valid(db: np.ndarray) -> np.ndarray:
    return db[np.isfinite(db)]


def otsu(db: np.ndarray, bins: int = 256) -> float:
    return float(threshold_otsu(_valid(db), nbins=bins))


def kittler_illingworth(db: np.ndarray, bins: int = 256, bounds: tuple[float, float] | None = None) -> float:
    """Minimum-error threshold (Kittler & Illingworth 1986) assuming two Gaussian classes.

    `bounds` restricts candidate thresholds to [lo, hi]. When one class is tiny, the criterion can be
    minimised by a degenerate split in a histogram tail (seen in L03/L04); a valid water/land split must
    lie between the two class means, which is what callers pass as bounds.
    """
    v = _valid(db)
    hist, edges = np.histogram(v, bins=bins)
    p = hist / hist.sum()
    centres = 0.5 * (edges[1:] + edges[:-1])
    best_t, best_j = float(np.median(v)), np.inf
    for i in range(1, bins - 1):
        if bounds is not None and not (bounds[0] <= edges[i] <= bounds[1]):
            continue
        p1, p2 = p[:i].sum(), p[i:].sum()
        if p1 < 1e-6 or p2 < 1e-6:
            continue
        m1 = (p[:i] * centres[:i]).sum() / p1
        m2 = (p[i:] * centres[i:]).sum() / p2
        s1 = np.sqrt((p[:i] * (centres[:i] - m1) ** 2).sum() / p1)
        s2 = np.sqrt((p[i:] * (centres[i:] - m2) ** 2).sum() / p2)
        if s1 < 1e-6 or s2 < 1e-6:
            continue
        j = 1 + 2 * (p1 * np.log(s1) + p2 * np.log(s2)) - 2 * (p1 * np.log(p1) + p2 * np.log(p2))
        if j < best_j:
            best_j, best_t = j, float(edges[i])
    return best_t


def tiled(db: np.ndarray, tile: int = 256, n_tiles: int = 10, min_class_frac: float = 0.1,
          min_ashman_d: float = 2.0, method: str = "otsu", bounded: bool = False) -> tuple[float, dict]:
    """Split-based thresholding (after Martinis et al. 2009; Chini et al. 2017).

    Global histograms are dominated by land when water is a few % of the scene, so global Otsu/KI tend to
    split land classes instead. Here, tiles whose own histogram is clearly bimodal (Ashman D >= min_ashman_d,
    both classes >= min_class_frac) are selected, the n_tiles most bimodal are pooled, and the threshold is
    computed on the pooled pixels. Falls back to the global threshold if no tile qualifies.

    bounded=True (KI only): restrict the KI search to [mean of lower class, mean of upper class] of the
    pooled sample's Otsu split, ruling out degenerate tail solutions.
    """
    fn = otsu if method == "otsu" else kittler_illingworth
    scored = []
    for r in range(0, db.shape[0] - tile + 1, tile):
        for c in range(0, db.shape[1] - tile + 1, tile):
            v = db[r:r + tile, c:c + tile]
            v = v[np.isfinite(v)]
            if v.size < 0.9 * tile * tile:
                continue
            t = threshold_otsu(v)
            lo, hi = v[v < t], v[v >= t]
            p = lo.size / v.size
            if not (min_class_frac <= p <= 1 - min_class_frac):
                continue
            d = np.sqrt(2) * abs(hi.mean() - lo.mean()) / np.sqrt(lo.var() + hi.var())
            if d >= min_ashman_d:
                scored.append((d, r, c))
    if not scored:
        return fn(db), {"tiles_used": 0, "fallback": "global"}
    scored.sort(reverse=True)
    pooled = np.concatenate([db[r:r + tile, c:c + tile].ravel() for _, r, c in scored[:n_tiles]])
    info = {"tiles_used": min(n_tiles, len(scored)), "tiles_bimodal": len(scored),
            "best_ashman_d": round(float(scored[0][0]), 2)}
    if method != "otsu" and bounded:
        p = pooled[np.isfinite(pooled)]
        t0 = threshold_otsu(p)
        lo, hi = float(p[p < t0].mean()), float(p[p >= t0].mean())
        return kittler_illingworth(pooled, bounds=(lo, hi)), {**info, "ki_bounds": (round(lo, 2), round(hi, 2))}
    return fn(pooled), info


def apply(db: np.ndarray, threshold: float) -> np.ndarray:
    """uint8 mask: 1 water, 0 non-water, 255 nodata."""
    out = np.full(db.shape, 255, dtype=np.uint8)
    ok = np.isfinite(db)
    out[ok] = (db[ok] < threshold).astype(np.uint8)
    return out


def hysteresis(db: np.ndarray, threshold: float, seed_db: float = 1.0, grow_db: float = 1.5) -> np.ndarray:
    """Region growing by hysteresis: water = connected regions of (db < threshold + grow_db) that contain at
    least one seed pixel (db < threshold - seed_db). Removes isolated dark specks without a confident core
    and recovers darker-than-land fringes attached to water. uint8 mask (1 water, 0 non-water, 255 nodata)."""
    out = np.full(db.shape, 255, dtype=np.uint8)
    ok = np.isfinite(db)
    x = np.where(ok, -db, -np.inf)  # flip: water = high
    out[ok] = apply_hysteresis_threshold(x, low=-(threshold + grow_db), high=-(threshold - seed_db))[ok]
    return out
