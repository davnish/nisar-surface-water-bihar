"""Binary water-mask accuracy metrics. Masks are uint8: 1 water, 0 non-water, 255 nodata."""
from __future__ import annotations

import numpy as np

NODATA = 255


def confusion(pred: np.ndarray, ref: np.ndarray) -> dict[str, int]:
    ok = (pred != NODATA) & (ref != NODATA)
    p, r = pred[ok] == 1, ref[ok] == 1
    return {"tp": int(np.sum(p & r)), "fp": int(np.sum(p & ~r)),
            "fn": int(np.sum(~p & r)), "tn": int(np.sum(~p & ~r))}


def scores(cm: dict[str, int]) -> dict[str, float]:
    tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]
    n = tp + fp + fn + tn

    def div(a, b):
        return float(a / b) if b else float("nan")

    precision, recall = div(tp, tp + fp), div(tp, tp + fn)
    oa = div(tp + tn, n)
    pe = div((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn), n * n)
    return {
        "precision": precision,
        "recall": recall,
        "f1": div(2 * tp, 2 * tp + fp + fn),
        "iou": div(tp, tp + fp + fn),
        "overall_accuracy": oa,
        "kappa": div(oa - pe, 1 - pe),
        "n_pixels": n,
    }


def evaluate(pred: np.ndarray, ref: np.ndarray) -> dict:
    cm = confusion(pred, ref)
    return {"confusion": cm, **scores(cm)}
