"""
Expectation curves: what should a player of THIS caliber actually do?

This module exists to fix a bias that sinks the naive version of this system.

The naive approach converts a weekly stat to a percentile and reads the matching
rating off Madden's distribution. It is systematically, badly wrong at the top.
Measured on real Week 1 data, a 98-CATCHING receiver who caught 50% of his
targets landed at the 21st percentile of single-game catch rates, implying a
rating of 81, a 17-point downgrade for an ordinary afternoon. Every star drifted
down; the league-wide result was 162 downgrades against 9 upgrades.

The reason is that a single game's percentile is not a true-talent percentile.
Catch rate in one game is dominated by how hard the targets were. Elite
receivers post 50% catch rates constantly. The median single-game percentile for
a star is nowhere near his rating percentile, it is somewhere near the middle.

So the comparison has to be relative to expectation:

    surprise      = observed_percentile - expected_percentile(caliber)
    implied_pct   = player's own launch percentile + surprise
    implied       = the rating sitting at implied_pct for his position

A player who performs exactly as a player of his rating normally performs gets
surprise = 0 and therefore no change at all, which is the behaviour we want. The
expectation curve is learned, not assumed: we bin a full reference season of
player-weeks by the player's Overall percentile and record the median
performance percentile in each bin.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import baselines as bl
from .config import POSITION_GROUP, SIGNALS

N_BINS = 6
BIN_EDGES = np.linspace(0.0, 1.0, N_BINS + 1)


def _ovr_percentiles(launch: pd.DataFrame) -> pd.Series:
    """Each player's Overall percentile within his own position group."""
    grp = launch["Position"].map(POSITION_GROUP)
    return launch.groupby(grp)["OVERALL"].rank(pct=True)


def build_expectation_curves(ref_stats: pd.DataFrame, launch: pd.DataFrame,
                             stat_baselines: dict) -> dict:
    """
    {group: {signal_key: np.array of length N_BINS}}

    Entry [b] is the MEAN performance percentile posted by players whose Overall
    percentile falls in bin b.

    The mean rather than the median, because most defensive stats are heavily
    zero-inflated. An elite pass rusher records no sack in the majority of his
    games, so the median percentile for every caliber of rusher is identical:
    the middle of the zero mass. Expectation then never rises with quality, a
    zero-sack game is never a disappointment, and ratings can only ratchet up.
    Measured over a full season this produced a mean drift of exactly +1.0 for
    every defensive position, with no player ever falling. The mean is sensitive
    to the upper tail where these stats actually live, so a great rusher is
    correctly expected to beat the zero mass and is marked down when he doesn't.
    """
    ovr_pct = _ovr_percentiles(launch)
    samples: dict[str, dict[str, list[list[float]]]] = {}

    for _, row in ref_stats.iterrows():
        idx = row.get("madden_idx", -1)
        if idx is None or idx < 0:
            continue
        idx = int(idx)
        grp = POSITION_GROUP.get(launch.loc[idx, "Position"])
        if grp not in SIGNALS:
            continue

        caliber = float(ovr_pct.loc[idx])
        b = min(int(caliber * N_BINS), N_BINS - 1)

        for sig in SIGNALS[grp]:
            if bl.opportunities(row, sig) < max(sig.get("floor", 0), 1e-9):
                continue
            dist = stat_baselines.get(grp, {}).get(sig["key"])
            if dist is None:
                continue
            val = bl.compute_signal(row, sig)
            if val is None or not np.isfinite(val):
                continue
            pct = bl.percentile_of(val, dist)
            samples.setdefault(grp, {}).setdefault(sig["key"],
                                                   [[] for _ in range(N_BINS)])[b].append(pct)

    curves: dict[str, dict[str, np.ndarray]] = {}
    for grp, sigs in samples.items():
        for key, bins in sigs.items():
            curve = np.full(N_BINS, np.nan)
            for b, vals in enumerate(bins):
                if len(vals) >= 25:
                    curve[b] = float(np.mean(vals))
            if np.isnan(curve).all():
                continue
            # fill gaps by interpolation, then flatten the ends
            good = ~np.isnan(curve)
            curve = np.interp(np.arange(N_BINS), np.arange(N_BINS)[good], curve[good])
            # expectation should not decrease with caliber
            curve = np.maximum.accumulate(curve)
            curves.setdefault(grp, {})[key] = curve
    return curves


def expected_percentile(curves: dict, grp: str, key: str, caliber: float) -> float:
    """Read the expectation curve at a player's caliber, interpolating between bins."""
    curve = curves.get(grp, {}).get(key)
    if curve is None:
        return 0.5
    x = float(np.clip(caliber, 0.0, 1.0)) * (N_BINS - 1)
    lo = int(np.floor(x))
    hi = min(lo + 1, N_BINS - 1)
    frac = x - lo
    return float(curve[lo] * (1 - frac) + curve[hi] * frac)
