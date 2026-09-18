"""
Recovers Madden's Overall formula from the launch dataset.

Madden's OVR is a weighted blend of a handful of attributes, and the weights
differ by position. We never see the formula, but we see 2,035 solved instances
of it, so we can fit it.

Two stages, because a plain regression on 54 attributes with only 60-200 players
per position overfits badly and produces unstable weights:

  1. Positive Lasso picks WHICH attributes matter (the support).
  2. Non-negative least squares refits on just those, giving unbiased weights.

Non-negativity is not a statistical convenience, it is a statement about
football: no attribute should make a player worse by going up.

The fit lands at R^2 0.83-0.98 per position with the weights summing to
approximately 1.0 everywhere, which is itself evidence the underlying formula
really is a convex blend.

How the weights are USED matters as much as the fit. We never predict an OVR
outright. We apply the fitted gradient to the *change* in attributes:

    OVR_new = OVR_launch + sum_a  w_a * (attr_new_a - attr_launch_a)

so any bias in the fitted intercept cancels exactly, and a player's OVR can only
move because a specific attribute moved.
"""

from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from sklearn.linear_model import LassoCV

warnings.filterwarnings("ignore")

EXCLUDE = {"OVERALL", "RUNNINGSTYLE", "ID"}


def attribute_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.isupper() and c not in EXCLUDE]


def fit_overall_weights(launch: pd.DataFrame, min_players: int = 25) -> dict:
    """Fit per-position OVR weights. Returns {position: {attr: weight, ...}}."""
    attrs = attribute_columns(launch)
    out: dict[str, dict] = {}

    for pos, grp in launch.groupby("Position"):
        if len(grp) < min_players:
            continue
        X = grp[attrs].astype(float).values
        y = grp["OVERALL"].astype(float).values

        lasso = LassoCV(cv=5, positive=True, max_iter=20000, n_alphas=60).fit(X, y)
        support = [i for i, c in enumerate(lasso.coef_) if c > 1e-6]
        if len(support) < 6:
            support = list(np.argsort(-lasso.coef_)[:8])

        design = np.c_[X[:, support], np.ones(len(X))]
        coef, _ = nnls(design, y)

        pred = design @ coef
        ss_res = float(((pred - y) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())

        weights = {attrs[i]: float(w) for i, w in zip(support, coef[:-1]) if w > 1e-6}
        out[pos] = {
            "weights": weights,
            "intercept": float(coef[-1]),
            "r2": 1 - ss_res / ss_tot if ss_tot else 0.0,
            "mae": float(np.abs(pred - y).mean()),
            "n": int(len(grp)),
            "weight_sum": float(sum(weights.values())),
        }
    return out


def recompute_overall(position: str, launch_ovr: float,
                      launch_attrs: dict, new_attrs: dict, model: dict) -> float:
    """
    Anchored OVR: start at the launch Overall and move it by the fitted gradient
    applied to whatever actually changed. If nothing changed, you get the launch
    Overall back exactly.
    """
    entry = model.get(position)
    if not entry:
        return launch_ovr
    delta = 0.0
    for attr, w in entry["weights"].items():
        delta += w * (new_attrs.get(attr, 0) - launch_attrs.get(attr, 0))
    return float(np.clip(launch_ovr + delta, 40, 99))


def save(model: dict, path: str) -> None:
    with open(path, "w") as fh:
        json.dump(model, fh, indent=1)


def load(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)
