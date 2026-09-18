# Madden 26 Live Rating Adjuster

Takes the 2,035-player Madden 26 launch roster, pulls real NFL results every week,
and works out what each player's attributes *should* be given how he's actually
playing. The launch rating is preserved permanently, so every number is measured
against what the player shipped with.

This is running on live data, not a simulation. Weekly stats come from
[nflverse](https://github.com/nflverse/nflverse-data), which publishes player box
scores as public CSV release assets and refreshes them within hours of the last
whistle. No API key, no scraping.

```
NFL games  ->  weekly stats  ->  percentile vs expectation  ->  attribute deltas
           ->  recomputed Overall  ->  rating history  ->  exported roster
```

![Biggest movers](out/figures/biggest_movers.png)

---

## Running it

```bash
python run_week.py                 # every completed week of the 2026 season
python run_week.py --through 4     # stop after week 4
python run_week.py --refresh       # re-download stats first
python charts.py                   # regenerate the PNGs
python build_site.py               # rebuild the dashboard
```

Everything is cached under `data/`, so re-running a week is free and the tool works
offline once primed.

Output lands in `out/`:

| File | What it is |
|---|---|
| `Madden_26_Live_Ratings.csv` | The launch roster with live attributes swapped in, plus `LAUNCH_OVERALL` and `OVR_DELTA`. Same shape as the input. |
| `ovr_table.csv` | One row per player: launch Overall, live Overall, change. |
| `ovr_weights.json` | The recovered Overall formula, per position. |
| `run_summary.json` | Per-week counts, match report, model fit stats. |
| `index.html` | The dashboard. |
| `figures/*.png` | The charts in this README. |

---

## How a rating actually changes

Eight steps, for one player in one week.

**1. Fire the signals.** Every signal for his position that met its opportunity
floor produces a value: catch rate, EPA per attempt, sack rate, fumble rate.

**2. Percentile it.** Raw stats mean nothing on their own. "9 catches for 142"
only matters relative to what receivers do, so every value is placed against a
full prior season of real games at that position.

**3. Compare to expectation, not to the league.** This is the part that makes the
system work, and it's covered in detail below.

**4. Blend.** An attribute fed by several signals takes their weighted mean.

**5. Confidence.** Scaled by `n / (n + k)` on opportunity count. Two targets moves
almost nothing; twelve targets moves a lot. This is what stops one flukey
garbage-time drive from repricing a player.

**6. Volatility.** The gap between implied and current is multiplied by the
attribute's own volatility. A receiver can show you he catches the ball; he can't
show you he got faster in a week.

| | Volatility | Max move in a week | Max drift all season |
|---|---|---|---|
| Awareness | 0.70 | 2.1 | 8.4 |
| Catching | 0.55 | 1.7 | 6.6 |
| Man coverage | 0.50 | 1.5 | 6.0 |
| Speed / Acceleration | 0.06 | 0.2 | 0.7 |
| Strength / Jumping | 0.04 | 0.1 | 0.5 |
| Injury | 0.00 | — | — |

**7. Clamp twice.** Against the weekly step cap, then against cumulative drift
from the **launch** rating. The second clamp is the important one: it's measured
against launch, never against last week, so drift can't compound into an 82 → 95
runaway. Over a full 18-week season the largest observed drift was 4 points.

**8. Recompute Overall** from the fitted position weights, anchored at launch.

Players who record no qualifying usage regress 8% toward their launch rating each
week, so form that isn't re-earned decays instead of sticking forever.

---

## Madden's Overall formula, recovered

Rather than inventing an Overall calculation, the engine fits Madden's own from
the launch data. We never see the formula, but we see 2,035 solved instances of it.

Two stages, because a plain regression on 54 attributes with 60–200 players per
position overfits badly and produces unstable weights:

1. **Positive Lasso** picks *which* attributes matter.
2. **Non-negative least squares** refits on just those, giving unbiased weights.

Non-negativity isn't a statistical convenience, it's a statement about football:
no attribute should make a player worse by going up.

![Overall model](out/figures/overall_model.png)

The fit lands at **R² 0.83–0.98** per position, and the weights **sum to ~1.0 at
every position without being constrained to** — which is itself evidence the real
formula is a convex blend. The recovered weights are football-sane: quarterbacks
lean on Awareness and deep accuracy, left tackles on Pass Block Power, corners on
Man Coverage, halfbacks on Ball Carrier Vision.

How the weights are *used* matters as much as the fit. The engine never predicts
an Overall outright. It applies the fitted gradient to the **change**:

```
OVR_new = OVR_launch + Σ  wₐ · (attr_newₐ − attr_launchₐ)
```

Any bias in the fitted intercept cancels exactly, and a player's Overall can only
move because a specific attribute moved.

---

## The bug that sinks the obvious version

The intuitive approach is: convert the week's stat to a percentile, read the
matching rating off Madden's distribution. It is systematically, badly wrong, and
it fails worst on exactly the players you care about.

On real Week 1 data, a **98-CATCHING receiver who caught 50% of his targets landed
at the 21st percentile** of single-game catch rates, implying a rating of 81 — a
17-point downgrade for an ordinary afternoon. League-wide the first run produced
**162 downgrades against 9 upgrades**.

A single game's percentile is not a true-talent percentile. Catch rate in one game
is dominated by how hard the targets were; elite receivers post 50% catch rates
constantly. So the comparison has to be relative to expectation:

```
surprise    = observed percentile − expected percentile for his calibre
implied_pct = the player's own launch percentile + surprise
```

A player who performs exactly as a player of his rating normally performs gets
`surprise = 0` and therefore **no change at all**. The expectation curve is
learned, not assumed: a full reference season of player-weeks is binned by the
player's Overall percentile and the mean performance percentile recorded per bin.

### Two more biases that only showed up in an 18-week test

**Zero-inflation ratchet.** Most football counting stats are mostly zero — most
backs have no 20-yard run in a given week, most rushers no sack. With a
left-insertion percentile, zero scores 0.00, so the expected value for *every*
calibre is also 0.00. Having no explosive run cost nothing; having one was a +0.93
surprise. Ratings could only go up. Measured over a season this produced a mean
drift of **exactly +1.00 for every defensive position, with no player ever
falling.** Fixed by taking the **mid-rank of ties** (so "no explosive run" sits in
the middle of the zero mass) and by building expectations from the **mean rather
than the median** (the median is identical for all calibres when the stat is
mostly zero; the mean is sensitive to the tail where these stats actually live).

**Asymmetric headroom at the top.** Reading the implied rating off the attribute's
quantile function is badly asymmetric at the edges: a player already at the 99th
percentile has almost no room to rise in percentile space but the full range in
which to fall. Elite players bled rating for average play — **−0.87 mean drift in
the top decile against +0.8 in the decile below**. Fixed by scaling the surprise
by a constant spread per position, so a +0.3 surprise is worth exactly as much as
a −0.3 one wherever the player sits.

### Calibration after the fixes

Full season, 2025 played through with baselines from 2024:

| Check | Result |
|---|---|
| Drift by calibre decile | −0.43 to +0.10 — flat, no top-end collapse |
| Position groups moving | all 12 |
| Net drift | −0.05 points per player |
| Max drift, 18 weeks | 4 points — caps hold, no runaway |
| Upgrades vs downgrades | balanced week to week |

![Weekly flow](out/figures/weekly_flow.png)
![Rating changes](out/figures/rating_changes.png)

---

## Attribute mapping

Each attribute gets its own statistical relationship rather than "he had a good
game, raise the number." A stat can feed several attributes and an attribute can
be fed by several stats.

**Quarterback**

| Attribute | Driven by |
|---|---|
| Throw Accuracy Short / Mid | completion %, CPOE |
| Throw Accuracy Deep | 20+ and 40+ yard completion rate, air yards per attempt |
| Throw Under Pressure, Break Sack | sack rate taken (inverted) |
| Awareness | EPA per dropback, interception rate (inverted) |
| Throw On The Run | scramble production |
| Throw Power | air yards per attempt — barely moves by design |
| Carrying | fumble rate (inverted) |

**Wide receiver / tight end**

| Attribute | Driven by |
|---|---|
| Catching | catch rate |
| Catch In Traffic | first downs per reception, catch rate |
| Deep Route Running | 20+/40+ rate, air yards share |
| Short / Medium Route Running | 10+ and 16+ yard reception rate |
| Release, Press | target share, WOPR |
| Ball Carrier Vision, Break Tackle, Juke | yards after catch per reception |
| Spectacular Catch | touchdown rate, explosive catch rate |
| Carrying | fumbles (inverted) |

**Halfback**

| Attribute | Driven by |
|---|---|
| Ball Carrier Vision | yards per carry, EPA per carry |
| Break Tackle, Trucking, Stiff Arm | first-down rate per carry |
| Juke, Spin | 10+ yard run rate |
| Speed / Acceleration | 20+/40+ run rate — capped hard |
| Carrying | fumble rate (inverted) |
| Stamina | carry volume |

**Defense** — Tackle and Pursuit from tackles and tackles for loss; Power/Finesse
Moves from sacks and QB hits; Block Shedding from TFL; Man/Zone Coverage and Play
Recognition from passes defended and interceptions; Hit Power from forced fumbles.

**Kickers and punters** — Kick Accuracy from FG% and punts inside the 20; Kick
Power from 50+ makes, long, and net punt average.

---

## Rating history

Every week is appended, never overwritten, and week 0 is always the launch rating.

![Rating history](out/figures/rating_history.png)

The dashboard shows the same trail per player, alongside every attribute that has
moved off its launch value.

---

## What this can't do

Worth being straight about, because these are limits of the public data rather
than things left undone.

- **Offensive line is nearly static.** Public box scores have essentially no OL
  footprint. Penalties are the only honest signal available, so linemen are
  deliberately sluggish rather than given fabricated movement. Real OL ratings
  need PFF-grade or snap-level charting.
- **Some mappings are proxies, not measurements.** There's no public
  contested-catch rate or press-success rate, so Catch In Traffic is inferred from
  first-downs-per-reception and Release from target share. Direct relationships
  (catch rate → Catching, fumbles → Carrying, FG% → Kick Accuracy) are exact;
  these are not.
- **Speed is not tracking data.** Real Next Gen Stats speed isn't public, so
  Speed and Acceleration move only slightly off explosive-play rate, with volatility
  near zero. Treat them as pinned.
- **~86% live match rate** against 96% on the reference season. The gap is 2026
  rookies and practice-squad callups who aren't in an August 2025 launch roster.
  Unmatched players simply keep their launch rating; they're listed in
  `run_summary.json`.
- **Name collisions are dropped, not guessed.** Matching normalises accents,
  punctuation, generational suffixes and common nicknames, then verifies against
  position, then team. Genuine ambiguity is flagged in the match report.

---

## Layout

```
run_week.py            season runner
build_site.py          builds out/index.html
charts.py              builds out/figures/*.png
site/LiveRatings.jsx   the same board as a React component
engine/
  config.py            volatility, caps, and the stat -> attribute mapping
  ingest.py            nflverse download + cache
  matching.py          nflverse <-> Madden player matching
  baselines.py         percentile machinery
  calibration.py       expectation curves
  ovr_model.py         recovers Madden's Overall formula
  adjust.py            the adjuster
```

## Tuning

The knobs worth touching all live in `engine/config.py`:

| Setting | Default | Effect |
|---|---|---|
| `GLOBAL_RATE` | 0.70 | Master throttle. Lower is more conservative. |
| `RESPONSE_GAIN` | 3.0 | Rating points per unit of surprise. |
| `MAX_WEEKLY_STEP` | 3.0 | Ceiling on a week's move, before volatility. |
| `MAX_SEASON_DRIFT` | 12.0 | Ceiling on drift from launch, before volatility. |
| `IDLE_REGRESSION` | 0.08 | Pull back toward launch when a player doesn't play. |
| `VOLATILITY` | per attribute | How earnable each attribute is. |
| `CONFIDENCE_K` | per position | Opportunities before a signal is trusted. Note the units differ: touches for skill players, **games** for defenders. |

Data: [nflverse-data](https://github.com/nflverse/nflverse-data) (weekly player
stats, public domain). Madden 26 launch ratings are EA's.
