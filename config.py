"""
Configuration for the Madden 26 Live Rating Adjuster.

Three things live here:
  1. POSITION_GROUP  - collapses Madden's 22 position labels into stat-bearing groups
  2. VOLATILITY      - how far each attribute is allowed to be moved by on-field play
  3. SIGNALS         - the stat -> attribute mapping, per position group

Design note on VOLATILITY
-------------------------
Ratings are not equally earnable. A receiver can show you he catches the ball;
he cannot show you he got faster in a week. Physical/measured traits are pinned
near their launch value, learned/mental traits are allowed to move. Every
attribute's weekly and season caps are derived from its volatility, so there is
exactly one number to tune per attribute.
"""

# --------------------------------------------------------------------------
# Position grouping
# --------------------------------------------------------------------------

POSITION_GROUP = {
    "Quarterback": "QB",
    "Halfback": "HB",
    "Fullback": "HB",
    "Wide Receiver": "WR",
    "Tight End": "TE",
    "Left Tackle": "OL",
    "Right Tackle": "OL",
    "Left Guard": "OL",
    "Right Guard": "OL",
    "Center": "OL",
    "Defensive Tackle": "DL",
    "Left Edge": "EDGE",
    "Right Edge": "EDGE",
    "Mike Backer": "LB",
    "Weak Backer": "LB",
    "Sam Backer": "LB",
    "Cornerback": "CB",
    "Free Safety": "S",
    "Strong Safety": "S",
    "Kicker": "K",
    "Punter": "P",
    "Long Snapper": "LS",
}

# nflverse position codes -> our groups, used to sanity-check a name match
NFL_POSITION_GROUP = {
    "QB": "QB", "RB": "HB", "FB": "HB", "WR": "WR", "TE": "TE",
    "T": "OL", "G": "OL", "C": "OL", "OL": "OL", "OT": "OL", "OG": "OL",
    "DT": "DL", "NT": "DL", "DL": "DL", "DE": "EDGE", "EDGE": "EDGE",
    "OLB": "EDGE", "LB": "LB", "ILB": "LB", "MLB": "LB",
    "CB": "CB", "DB": "CB", "S": "S", "SS": "S", "FS": "S", "SAF": "S",
    "K": "K", "P": "P", "LS": "LS",
}

# Groups that are allowed to be confused with each other when matching, because
# nflverse and EA disagree constantly about edge/LB and CB/S.
COMPATIBLE_GROUPS = [
    {"EDGE", "DL", "LB"},
    {"CB", "S"},
    {"HB", "WR", "TE"},
    {"OL"},
]


# --------------------------------------------------------------------------
# Attribute volatility  (0.0 = frozen at launch, 1.0 = fully performance-driven)
# --------------------------------------------------------------------------

VOLATILITY = {
    # --- measured physical traits: essentially frozen -----------------------
    "SPEED": 0.06, "ACCELERATION": 0.06, "AGILITY": 0.06,
    "STRENGTH": 0.04, "JUMPING": 0.04, "CHANGEOFDIRECTION": 0.06,
    "THROWPOWER": 0.05, "INJURY": 0.00, "TOUGHNESS": 0.04,
    "STAMINA": 0.10, "RUNNINGSTYLE": 0.00,

    # --- ball skills --------------------------------------------------------
    "CATCHING": 0.55, "CATCHINTRAFFIC": 0.50, "SPECTACULARCATCH": 0.45,
    "CARRYING": 0.60,

    # --- route running ------------------------------------------------------
    "SHORTROUTERUNNING": 0.50, "MEDIUMROUTERUNNING": 0.50,
    "DEEPROUTERUNNING": 0.50, "RELEASE": 0.45,

    # --- ball carrier -------------------------------------------------------
    "BCVISION": 0.55, "BREAKTACKLE": 0.50, "TRUCKING": 0.45,
    "STIFFARM": 0.40, "JUKEMOVE": 0.45, "SPINMOVE": 0.40,

    # --- passing ------------------------------------------------------------
    "THROWACCURACYSHORT": 0.50, "THROWACCURACYMID": 0.50,
    "THROWACCURACYDEEP": 0.50, "THROWONTHERUN": 0.40,
    "THROWUNDERPRESSURE": 0.50, "PLAYACTION": 0.35, "BREAKSACK": 0.45,

    # --- blocking (thin public data; kept deliberately sluggish) ------------
    "PASSBLOCK": 0.25, "PASSBLOCKPOWER": 0.20, "PASSBLOCKFINESSE": 0.20,
    "RUNBLOCK": 0.25, "RUNBLOCKPOWER": 0.20, "RUNBLOCKFINESSE": 0.20,
    "IMPACTBLOCKING": 0.20, "LEADBLOCK": 0.20,

    # --- defense ------------------------------------------------------------
    "TACKLE": 0.50, "HITPOWER": 0.40, "PURSUIT": 0.50,
    "BLOCKSHEDDING": 0.45, "POWERMOVES": 0.45, "FINESSEMOVES": 0.45,
    "MANCOVERAGE": 0.50, "ZONECOVERAGE": 0.50, "PRESS": 0.40,

    # --- mental: the most responsive of all ---------------------------------
    "AWARENESS": 0.70, "PLAYRECOGNITION": 0.60,

    # --- kicking ------------------------------------------------------------
    "KICKACCURACY": 0.55, "KICKPOWER": 0.30, "KICKRETURN": 0.35,
}

# Caps derived from volatility. A fully-volatile attribute can move 3 points in
# a week and 12 across a season; a frozen one barely moves at all.
MAX_WEEKLY_STEP = 3.0     # points, at volatility 1.0
MAX_SEASON_DRIFT = 12.0   # points from launch, at volatility 1.0

# Pulled back toward the launch rating each week a player records no qualifying
# usage. Form fades if it is not re-earned.
IDLE_REGRESSION = 0.08

# Opportunity counts needed before a signal is fully trusted. Below this the
# move is scaled down smoothly (n / (n + k)), so a 2-target game barely registers.
#
# The units differ by group and that has to be respected. Offensive skill players
# are measured in touches, so k is a number of touches. Defenders have no public
# snap-level opportunity count, so their signals are per-game and k is a number
# of GAMES. Carrying the touch-scale k over to defence sets confidence to
# 1/(1+22) = 0.04 and freezes every defender at his launch rating permanently.
CONFIDENCE_K = {
    # measured in touches / attempts
    "QB": 18, "HB": 10, "WR": 6, "TE": 5,
    "K": 3, "P": 4,
    # measured in games
    "OL": 2, "DL": 1.5, "EDGE": 1.5, "LB": 1.5, "CB": 1.5, "S": 1.5,
    "LS": 99,
}

# Global throttle on the whole system. Lower = more conservative ratings.
GLOBAL_RATE = 0.70

# How many standard deviations of rating a full 1.0 performance surprise is
# worth. Surprises in practice run about -0.5..+0.5, so a gain of 2.0 means a
# very large surprise is worth roughly 1.5 standard deviations of the attribute.
RESPONSE_GAIN = 3.0


# --------------------------------------------------------------------------
# Signals:  stat -> attribute
# --------------------------------------------------------------------------
# Each signal is a dict:
#   key        unique id
#   num/den    the rate is num/den (den omitted => per-game)
#   invert     True if a LOW value is good (fumbles, INTs, sacks taken)
#   opp        which column carries the opportunity count for confidence
#   attrs      {ATTRIBUTE: weight} - weights within a signal need not sum to 1
#   floor      minimum opportunities in the week for the signal to fire at all
#
# A single stat can feed several attributes, and a single attribute can be fed
# by several stats; the engine averages the implied targets weighted by both the
# signal weight and its confidence.

SIGNALS = {
    "QB": [
        dict(key="comp_pct", num="completions", den="attempts", floor=8,
             opp="attempts", attrs={"THROWACCURACYSHORT": 0.5, "THROWACCURACYMID": 0.3}),
        dict(key="cpoe", num="passing_cpoe", den=None, raw=True, floor=8,
             opp="attempts", attrs={"THROWACCURACYSHORT": 0.4, "THROWACCURACYMID": 0.4,
                                    "AWARENESS": 0.2}),
        dict(key="epa_play", num="passing_epa", den="attempts", floor=8,
             opp="attempts", attrs={"AWARENESS": 0.5, "PLAYACTION": 0.25,
                                    "THROWACCURACYMID": 0.25}),
        dict(key="ypa", num="passing_yards", den="attempts", floor=8,
             opp="attempts", attrs={"THROWACCURACYMID": 0.4, "THROWACCURACYDEEP": 0.3,
                                    "AWARENESS": 0.3}),
        dict(key="deep_rate", num=("passing_20", "passing_40"), den="attempts", floor=8,
             opp="attempts", attrs={"THROWACCURACYDEEP": 0.6, "THROWPOWER": 0.4}),
        dict(key="air_per_att", num="passing_air_yards", den="attempts", floor=8,
             opp="attempts", attrs={"THROWPOWER": 0.7, "THROWACCURACYDEEP": 0.3}),
        dict(key="sack_rate", num="sacks_suffered", den="attempts", invert=True, floor=8,
             opp="attempts", attrs={"THROWUNDERPRESSURE": 0.5, "BREAKSACK": 0.5}),
        dict(key="int_rate", num="passing_interceptions", den="attempts", invert=True,
             floor=8, opp="attempts",
             attrs={"AWARENESS": 0.6, "THROWUNDERPRESSURE": 0.4}),
        dict(key="scramble", num="rushing_yards", den=None, floor=0,
             opp="attempts", attrs={"THROWONTHERUN": 0.5, "BREAKSACK": 0.3, "SPEED": 0.2}),
        dict(key="qb_fumble", num="fumbles_total", den="attempts", invert=True, floor=8,
             opp="attempts", attrs={"CARRYING": 1.0}),
    ],

    "WR": [
        dict(key="catch_rate", num="receptions", den="targets", floor=2,
             opp="targets", attrs={"CATCHING": 0.7, "CATCHINTRAFFIC": 0.3}),
        dict(key="fd_per_rec", num="receiving_first_downs", den="receptions", floor=2,
             opp="receptions", attrs={"CATCHINTRAFFIC": 0.5, "SPECTACULARCATCH": 0.3,
                                      "AWARENESS": 0.2}),
        dict(key="deep_rate", num=("receiving_20", "receiving_40"), den="targets", floor=2,
             opp="targets", attrs={"DEEPROUTERUNNING": 0.7, "SPECTACULARCATCH": 0.3}),
        dict(key="air_share", num="air_yards_share", den=None, raw=True, floor=2,
             opp="targets", attrs={"DEEPROUTERUNNING": 0.5, "RELEASE": 0.5}),
        dict(key="tgt_share", num="target_share", den=None, raw=True, floor=2,
             opp="targets", attrs={"RELEASE": 0.6, "SHORTROUTERUNNING": 0.4}),
        dict(key="yac_per_rec", num="receiving_yards_after_catch", den="receptions", floor=2,
             opp="receptions", attrs={"BCVISION": 0.3, "BREAKTACKLE": 0.3,
                                      "JUKEMOVE": 0.2, "SPEED": 0.1, "ACCELERATION": 0.1}),
        dict(key="epa_tgt", num="receiving_epa", den="targets", floor=2,
             opp="targets", attrs={"AWARENESS": 0.5, "MEDIUMROUTERUNNING": 0.5}),
        dict(key="short_rate", num="receiving_10", den="targets", floor=2,
             opp="targets", attrs={"SHORTROUTERUNNING": 1.0}),
        dict(key="mid_rate", num="receiving_16", den="targets", floor=2,
             opp="targets", attrs={"MEDIUMROUTERUNNING": 1.0}),
        dict(key="td_rate", num="receiving_tds", den="targets", floor=2,
             opp="targets", attrs={"SPECTACULARCATCH": 0.4, "CATCHINTRAFFIC": 0.3,
                                   "RELEASE": 0.3}),
        dict(key="wr_fumble", num="fumbles_total", den="receptions", invert=True, floor=2,
             opp="receptions", attrs={"CARRYING": 1.0}),
        dict(key="wopr", num="wopr", den=None, raw=True, floor=2,
             opp="targets", attrs={"RELEASE": 0.6, "PRESS": 0.4}),
    ],

    "HB": [
        dict(key="ypc", num="rushing_yards", den="carries", floor=3,
             opp="carries", attrs={"BCVISION": 0.5, "BREAKTACKLE": 0.25, "TRUCKING": 0.25}),
        dict(key="epa_carry", num="rushing_epa", den="carries", floor=3,
             opp="carries", attrs={"BCVISION": 0.6, "AWARENESS": 0.4}),
        dict(key="explosive", num=("rushing_20", "rushing_40"), den="carries", floor=3,
             opp="carries", attrs={"SPEED": 0.3, "ACCELERATION": 0.3, "JUKEMOVE": 0.2,
                                   "BCVISION": 0.2}),
        dict(key="fd_rate", num="rushing_first_downs", den="carries", floor=3,
             opp="carries", attrs={"BREAKTACKLE": 0.4, "TRUCKING": 0.3, "STIFFARM": 0.3}),
        dict(key="chunk_rate", num="rushing_10", den="carries", floor=3,
             opp="carries", attrs={"JUKEMOVE": 0.4, "SPINMOVE": 0.3, "BREAKTACKLE": 0.3}),
        dict(key="rb_fumble", num="fumbles_total", den="carries", invert=True, floor=3,
             opp="carries", attrs={"CARRYING": 1.0}),
        dict(key="rb_catch", num="receptions", den="targets", floor=2,
             opp="targets", attrs={"CATCHING": 0.7, "SHORTROUTERUNNING": 0.3}),
        dict(key="rb_td", num="rushing_tds", den="carries", floor=3,
             opp="carries", attrs={"TRUCKING": 0.4, "AWARENESS": 0.3, "BREAKTACKLE": 0.3}),
        # Volume reflects coaching trust, not play quality. It feeds stamina only;
        # letting it touch AWARENESS would pay a back simply for carrying the ball.
        dict(key="usage", num="carries", den=None, floor=0,
             opp="carries", attrs={"STAMINA": 1.0}),
    ],

    "DL": [
        dict(key="sacks", num="def_sacks", den=None, floor=0, opp="_games",
             attrs={"POWERMOVES": 0.35, "FINESSEMOVES": 0.35, "PURSUIT": 0.3}),
        dict(key="qb_hits", num="def_qb_hits", den=None, floor=0, opp="_games",
             attrs={"POWERMOVES": 0.4, "FINESSEMOVES": 0.3, "PURSUIT": 0.3}),
        dict(key="tfl", num="def_tackles_for_loss", den=None, floor=0, opp="_games",
             attrs={"BLOCKSHEDDING": 0.6, "PURSUIT": 0.4}),
        dict(key="tackles", num=("def_tackles_solo", "def_tackle_assists"), den=None,
             floor=0, opp="_games", attrs={"TACKLE": 0.7, "PURSUIT": 0.3}),
        dict(key="ff", num="def_fumbles_forced", den=None, floor=0, opp="_games",
             attrs={"HITPOWER": 0.7, "TACKLE": 0.3}),
        dict(key="pbu", num="def_pass_defended", den=None, floor=0, opp="_games",
             attrs={"PLAYRECOGNITION": 0.6, "AWARENESS": 0.4}),
    ],

    "LB": [
        dict(key="tackles", num=("def_tackles_solo", "def_tackle_assists"), den=None,
             floor=0, opp="_games", attrs={"TACKLE": 0.6, "PURSUIT": 0.4}),
        dict(key="tfl", num="def_tackles_for_loss", den=None, floor=0, opp="_games",
             attrs={"BLOCKSHEDDING": 0.5, "PURSUIT": 0.3, "PLAYRECOGNITION": 0.2}),
        dict(key="sacks", num="def_sacks", den=None, floor=0, opp="_games",
             attrs={"POWERMOVES": 0.4, "FINESSEMOVES": 0.3, "PURSUIT": 0.3}),
        dict(key="pbu", num="def_pass_defended", den=None, floor=0, opp="_games",
             attrs={"ZONECOVERAGE": 0.5, "PLAYRECOGNITION": 0.5}),
        dict(key="ints", num="def_interceptions", den=None, floor=0, opp="_games",
             attrs={"ZONECOVERAGE": 0.4, "PLAYRECOGNITION": 0.4, "AWARENESS": 0.2}),
        dict(key="ff", num="def_fumbles_forced", den=None, floor=0, opp="_games",
             attrs={"HITPOWER": 1.0}),
    ],

    "CB": [
        dict(key="pbu", num="def_pass_defended", den=None, floor=0, opp="_games",
             attrs={"MANCOVERAGE": 0.45, "ZONECOVERAGE": 0.35, "PLAYRECOGNITION": 0.2}),
        dict(key="ints", num="def_interceptions", den=None, floor=0, opp="_games",
             attrs={"PLAYRECOGNITION": 0.4, "ZONECOVERAGE": 0.3, "MANCOVERAGE": 0.3}),
        dict(key="tackles", num=("def_tackles_solo", "def_tackle_assists"), den=None,
             floor=0, opp="_games", attrs={"TACKLE": 0.7, "PURSUIT": 0.3}),
        dict(key="tfl", num="def_tackles_for_loss", den=None, floor=0, opp="_games",
             attrs={"PURSUIT": 0.6, "TACKLE": 0.4}),
        dict(key="ff", num="def_fumbles_forced", den=None, floor=0, opp="_games",
             attrs={"HITPOWER": 0.6, "PRESS": 0.4}),
    ],

    "K": [
        dict(key="fg_pct", num="fg_made", den="fg_att", floor=1,
             opp="fg_att", attrs={"KICKACCURACY": 1.0}),
        dict(key="long_fg", num=("fg_made_50_59", "fg_made_60_"), den=None, floor=0,
             opp="fg_att", attrs={"KICKPOWER": 1.0}),
        dict(key="fg_long", num="fg_long", den=None, raw=True, floor=1,
             opp="fg_att", attrs={"KICKPOWER": 0.7, "KICKACCURACY": 0.3}),
    ],

    "P": [
        dict(key="net_avg", num="pt_net_yards", den="pt_att", floor=2,
             opp="pt_att", attrs={"KICKPOWER": 0.6, "KICKACCURACY": 0.4}),
        dict(key="in20", num="pt_inside_20", den="pt_att", floor=2,
             opp="pt_att", attrs={"KICKACCURACY": 1.0}),
    ],

    # Offensive line and long snappers have essentially no public box-score
    # footprint. Penalties are the only honest signal available, so that is the
    # only thing the engine will act on for them.
    "OL": [
        dict(key="penalties", num="penalties", den=None, invert=True, floor=0,
             opp="_games", attrs={"AWARENESS": 0.6, "PASSBLOCK": 0.2, "RUNBLOCK": 0.2}),
    ],
    "LS": [],
}

SIGNALS["TE"] = SIGNALS["WR"] + [
    dict(key="te_pen", num="penalties", den=None, invert=True, floor=0, opp="_games",
         attrs={"RUNBLOCK": 0.5, "AWARENESS": 0.5}),
]
SIGNALS["EDGE"] = SIGNALS["DL"]
SIGNALS["S"] = SIGNALS["CB"]


def weekly_cap(attr: str) -> float:
    return MAX_WEEKLY_STEP * VOLATILITY.get(attr, 0.3)


def season_cap(attr: str) -> float:
    return MAX_SEASON_DRIFT * VOLATILITY.get(attr, 0.3)
