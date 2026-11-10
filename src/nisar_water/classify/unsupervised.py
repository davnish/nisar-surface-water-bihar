"""Unsupervised per-scene classifiers on multi-feature stacks (no reference used)."""
from __future__ import annotations

import numpy as np
from sklearn.mixture import GaussianMixture


def gmm_water(features: dict[str, np.ndarray], names: list[str], n_components: int = 3, sample: int = 200_000,
              min_posterior: float = 0.5, seed: int = 0) -> tuple[np.ndarray, dict]:
    """Fit a Gaussian mixture to (feature_1, ..., feature_k) per scene; water = the component with the lowest
    mean of the first feature (HH), pixels with posterior >= min_posterior. Land is multimodal (fields, sand,
    settlements), hence > 2 components. uint8 mask (1 water, 0 non-water, 255 nodata)."""
    stack = np.stack([features[n] for n in names], axis=-1)
    ok = np.all(np.isfinite(stack), axis=-1)
    x = stack[ok]
    rng = np.random.default_rng(seed)
    fit = x[rng.choice(len(x), size=min(sample, len(x)), replace=False)]
    gm = GaussianMixture(n_components=n_components, covariance_type="full", random_state=seed).fit(fit)
    water_k = int(np.argmin(gm.means_[:, 0]))
    post = gm.predict_proba(x)[:, water_k]
    out = np.full(ok.shape, 255, np.uint8)
    out[ok] = (post >= min_posterior).astype(np.uint8)
    return out, {"water_component_mean": [round(float(v), 2) for v in gm.means_[water_k]],
                 "water_weight": round(float(gm.weights_[water_k]), 4)}
