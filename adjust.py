"""
The rating adjuster.

One week of stats in, one set of attribute changes out. The pipeline for a
single player-week:

  1. FIRE SIGNALS      every signal for his position that met its opportunity
                       floor produces a value (catch rate, EPA/att, sack rate...)

  2. PERCENTILE        each value is placed against a full prior season of real
                       games at that position -> 0..1

  3. IMPLIED RATING    that percentile is read back off the distribution of the
                       attribute among Madden players at the position, giving a
                       performance-implied rating on Madden's own scale

  4. BLEND             an attribute fed by several signals takes their weighted
                       mean, weighted by signal weight x confidence

  5. CONFIDENCE        n / (n + k) on opportunity count. Two targets moves almost
                       nothing; twelve targets moves a lot. This is what stops
                       one flukey garbage-time drive from repricing a player.

  6. VOLATILITY        the gap between implied and current is multiplied by the
                       attribute's volatility. SPEED barely budges, AWARENESS
                       moves freely.

  7. CLAMP TWICE       against the weekly step cap, then against cumulative drift
                       from the LAUNCH rating. The second clamp is the important
                       one: it is measured against launch, never against last
                       week, so drift cannot compound week over week into a
                       76 -> 95 runaway.

  8. RECOMPUTE OVR     via the fitted per-position weights, anchored at launch.

Players who did not record qualifying usage regress gently toward their launch
rating, so form that is not re-earned decays instead of sticking forever.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import baselines as bl
from . import calibration as calib
from . import ovr_model
from .config import (CONFIDENCE_K, GLOBAL_RATE, IDLE_REGRESSION, POSITION_GROUP,
                     RESPONSE_GAIN, SIGNALS, season_cap, weekly_cap)


class RatingEngine:
    def __init__(self, launch: pd.DataFrame, ref_stats: pd.DataFrame,
                 model: dict, attrs: list[str], curves: dict | None = None):
        self.launch = launch.reset_index(drop=True)
        self.attrs = attrs
        self.model = model
        self.group = self.launch["Position"].map(POSITION_GROUP)

        self.rating_baselines = bl.build_rating_baselines(self.launch, attrs)
        self.stat_baselines = bl.build_stat_baselines(ref_stats, self._group_of_statrow)
        self.rating_spreads = bl.build_rating_spreads(self.launch, attrs)
        self.curves = curves or {}

        # Each player's caliber (Overall percentile within his position group) and
        # the percentile of each of his launch attributes. Both are fixed at launch
        # so that expectations never drift with the ratings themselves.
        self.caliber = calib._ovr_percentiles(self.launch)
        self.attr_pct = {}
        grp_col = self.launch["Position"].map(POSITION_GROUP)
        for a in attrs:
            self.attr_pct[a] = self.launch.groupby(grp_col)[a].rank(pct=True)

        # Live state: current attribute values, starting at launch.
        self.current = self.launch[attrs].astype(float).copy()
        self.launch_attrs = self.launch[attrs].astype(float).copy()
        self.current_ovr = self.launch["OVERALL"].astype(float).copy()

        self.history: list[dict] = []
        self.week_log: list[dict] = []

    # -- helpers ----------------------------------------------------------

    def _group_of_statrow(self, row) -> str | None:
        from .config import NFL_POSITION_GROUP
        return NFL_POSITION_GROUP.get(str(row.get("position")), None)

    def _implied_targets(self, grp: str, idx: int, row: pd.Series) -> dict:
        """
        Run every signal for this position group.

        The value a signal implies is not read straight off the percentile. It is
        the player's own launch percentile shifted by how far he beat or missed
        what a player of his caliber normally does. Perform to expectation and
        nothing moves.

        Returns {attribute: [weighted_implied_sum, total_weight, best_confidence]}
        """
        acc: dict[str, list] = {}
        sb = self.stat_baselines.get(grp, {})
        rb = self.rating_baselines.get(grp, {})
        k = CONFIDENCE_K.get(grp, 20)
        caliber = float(self.caliber.loc[idx])

        for sig in SIGNALS.get(grp, []):
            opp = bl.opportunities(row, sig)
            if opp < max(sig.get("floor", 0), 1e-9):
                continue
            dist = sb.get(sig["key"])
            if dist is None:
                continue
            val = bl.compute_signal(row, sig)
            if val is None or not np.isfinite(val):
                continue

            observed = bl.percentile_of(val, dist)
            expected = calib.expected_percentile(self.curves, grp, sig["key"], caliber)
            surprise = observed - expected
            conf = opp / (opp + k)

            for attr, w in sig["attrs"].items():
                if attr not in rb:
                    continue
                spread = self.rating_spreads.get(grp, {}).get(attr, 8.0)
                launch_v = float(self.launch_attrs.at[idx, attr])
                implied = launch_v + surprise * spread * RESPONSE_GAIN
                acc.setdefault(attr, [0.0, 0.0, 0.0])
                acc[attr][0] += implied * w * conf
                acc[attr][1] += w * conf
                acc[attr][2] = max(acc[attr][2], conf)
        return acc

    # -- main -------------------------------------------------------------

    def process_week(self, week_stats: pd.DataFrame, season: int, week: int) -> dict:
        """Apply one week of stats. Returns a summary dict."""
        touched: set[int] = set()
        changes: list[dict] = []

        played = week_stats[week_stats["madden_idx"] >= 0]

        for _, row in played.iterrows():
            idx = int(row["madden_idx"])
            grp = POSITION_GROUP.get(self.launch.loc[idx, "Position"])
            if grp not in SIGNALS:
                continue

            acc = self._implied_targets(grp, idx, row)
            if not acc:
                continue
            touched.add(idx)

            attr_deltas = {}
            for attr, (wsum_implied, wsum, conf) in acc.items():
                if wsum <= 0:
                    continue
                implied = wsum_implied / wsum
                cur = float(self.current.at[idx, attr])
                launch_v = float(self.launch_attrs.at[idx, attr])

                from .config import VOLATILITY
                vol = VOLATILITY.get(attr, 0.3)

                raw = (implied - cur) * vol * conf * GLOBAL_RATE

                # clamp 1: per-week step
                cap_w = weekly_cap(attr)
                step = float(np.clip(raw, -cap_w, cap_w))

                # clamp 2: cumulative drift from LAUNCH, not from last week
                cap_s = season_cap(attr)
                proposed = cur + step
                proposed = float(np.clip(proposed, launch_v - cap_s, launch_v + cap_s))
                proposed = float(np.clip(proposed, 0, 99))

                if round(proposed) != round(cur):
                    attr_deltas[attr] = (round(cur), round(proposed))
                self.current.at[idx, attr] = proposed

            if attr_deltas:
                changes.append({"idx": idx, "attrs": attr_deltas})

        # idle regression toward launch for everyone who did not play
        for idx in range(len(self.launch)):
            if idx in touched:
                continue
            for attr in self.attrs:
                cur = float(self.current.at[idx, attr])
                lv = float(self.launch_attrs.at[idx, attr])
                if abs(cur - lv) < 1e-9:
                    continue
                self.current.at[idx, attr] = cur + (lv - cur) * IDLE_REGRESSION

        # recompute overalls
        prev_ovr = self.current_ovr.copy()
        for idx in range(len(self.launch)):
            pos = self.launch.loc[idx, "Position"]
            self.current_ovr.at[idx] = ovr_model.recompute_overall(
                pos,
                float(self.launch.loc[idx, "OVERALL"]),
                self.launch_attrs.loc[idx].to_dict(),
                self.current.loc[idx].to_dict(),
                self.model,
            )

        moved_up = int((self.current_ovr.round() > prev_ovr.round()).sum())
        moved_dn = int((self.current_ovr.round() < prev_ovr.round()).sum())

        self.history.append({
            "season": season, "week": week,
            "ovr": self.current_ovr.round().astype(int).tolist(),
            "played": sorted(touched),
        })

        summary = {
            "season": season, "week": week,
            "players_with_stats": int(len(played)),
            "players_adjusted": len(touched),
            "increased": moved_up,
            "decreased": moved_dn,
            "unchanged": len(self.launch) - moved_up - moved_dn,
            "attr_changes": int(sum(len(c["attrs"]) for c in changes)),
        }
        self.week_log.append(summary)
        return summary

    # -- outputs ----------------------------------------------------------

    def ovr_table(self) -> pd.DataFrame:
        out = self.launch[["Player", "Position", "Team", "OVERALL"]].copy()
        out = out.rename(columns={"OVERALL": "launch_ovr"})
        out["current_ovr"] = self.current_ovr.round().astype(int)
        out["delta"] = out["current_ovr"] - out["launch_ovr"]
        return out

    def export_roster(self) -> pd.DataFrame:
        """A Madden-shaped roster with live attributes swapped in."""
        out = self.launch.copy()
        for a in self.attrs:
            out[a] = self.current[a].round().astype(int)
        out["OVERALL"] = self.current_ovr.round().astype(int)
        out["Overall"] = out["OVERALL"]
        out["LAUNCH_OVERALL"] = self.launch["OVERALL"].astype(int)
        out["OVR_DELTA"] = out["OVERALL"] - out["LAUNCH_OVERALL"]
        return out
