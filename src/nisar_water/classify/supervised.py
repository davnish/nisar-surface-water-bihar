"""Supervised pixel classifiers (L07): LightGBM and random forest on a feature stack.

Fitting uses TRAIN-block reference pixels from FIT blocks only; the probability threshold is chosen to
maximise F1 on held-out VAL blocks (a fixed subset of the train blocks), so model and threshold selection
never touch the TEST blocks.
"""
from __future__ import annotations

import numpy as np

from nisar_water.tasks.separability import best_threshold_f1


def make_model(kind: str, params: dict, seed: int = 42):
    if kind == "lgbm":
        import lightgbm as lgb
        defaults = dict(n_estimators=400, learning_rate=0.05, num_leaves=63, min_child_samples=50,
                        subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                        random_state=seed, n_jobs=-1, verbose=-1)
        return lgb.LGBMClassifier(**{**defaults, **params})
    if kind == "rf":
        from sklearn.ensemble import RandomForestClassifier
        defaults = dict(n_estimators=150, max_depth=18, min_samples_leaf=20, max_features="sqrt",
                        n_jobs=-1, random_state=seed)
        return RandomForestClassifier(**{**defaults, **params})
    raise NotImplementedError(kind)


def fit(kind: str, X: np.ndarray, y: np.ndarray, Xv: np.ndarray, yv: np.ndarray, params: dict | None = None):
    """Fit on (X, y); pick the probability threshold maximising F1 on (Xv, yv). Returns (model, threshold, val_f1)."""
    model = make_model(kind, params or {})
    model.fit(X, y)
    pv = model.predict_proba(Xv)[:, 1]
    f1, t, direction = best_threshold_f1(pv[yv == 1], pv[yv == 0])
    if direction != ">":
        raise ValueError("validation probabilities are inverted")
    return model, float(t), float(f1)


def predict(model, features: dict[str, np.ndarray], names: list[str], threshold: float,
            chunk: int = 1_000_000) -> tuple[np.ndarray, np.ndarray]:
    """uint8 mask (1 water, 0 non-water, 255 nodata) and float32 probability for a full scene."""
    shape = features[names[0]].shape
    X = np.stack([features[n].ravel() for n in names], 1).astype(np.float32)
    ok = np.isfinite(features["HH"].ravel())
    prob = np.full(X.shape[0], np.nan, np.float32)
    idx = np.flatnonzero(ok)
    for s in range(0, idx.size, chunk):
        sl = idx[s:s + chunk]
        prob[sl] = model.predict_proba(X[sl])[:, 1]
    mask = np.full(X.shape[0], 255, np.uint8)
    mask[idx] = (prob[idx] > threshold).astype(np.uint8)
    return mask.reshape(shape), prob.reshape(shape)


def importance(model, names: list[str]) -> dict[str, float]:
    if hasattr(model, "booster_"):
        g = model.booster_.feature_importance(importance_type="gain")
    else:
        g = model.feature_importances_
    g = np.asarray(g, float)
    g = g / g.sum() if g.sum() else g
    return dict(sorted(zip(names, g.round(4)), key=lambda kv: -kv[1]))
