"""
NBA Predictor Configuration
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_DIR = os.path.join(BASE_DIR, "history")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
PERFORMANCE_DIR = os.path.join(BASE_DIR, "performance")

# Ensure directories exist
for d in [DATA_DIR, HISTORY_DIR, REPORTS_DIR, PERFORMANCE_DIR]:
    os.makedirs(d, exist_ok=True)

# Prediction confidence thresholds
CONFIDENCE_HIGH = 0.70      # Strong pick
CONFIDENCE_MODERATE = 0.60  # Lean pick
CONFIDENCE_LOW = 0.55       # Skip / too close to call

# Minimum weight floor for any factor (prevents zeroing out)
MIN_WEIGHT = 0.03

# Weighting factors for the prediction model
# rest_days zeroed out: 33.3% accuracy (ESPN doesn't provide pre-game rest data reliably).
# Its 0.08 weight redistributed proportionally to reliable factors.
# rest_days is still computed and used as a raw edge signal in risk/reward classification.
WEIGHTS = {
    "win_pct":          0.24,   # Overall season win percentage (reduced from 0.27 — 2026-03-22)
    "recent_form":      0.22,   # Last 10 games performance
    "player_form":      0.22,   # Individual player performance last 5 games
    "home_away":        0.12,   # Home court advantage / road record
    "injuries":         0.15,   # Key player availability (bumped from 0.12 — 79 votes @ 73.4%)
    "rest_days":        0.00,   # Excluded from confidence (33% accuracy); used only for edge scoring
    "streak":           0.05,   # Current win/loss streak
}

# Risk / Reward classification thresholds
RISK_HIGH     = 0.55   # risk_score >= this → HIGH RISK
RISK_MODERATE = 0.30   # risk_score >= this → MODERATE RISK (below = LOW RISK)
EDGE_STRONG   = 0.40   # edge_score >= this → STRONG EDGE
EDGE_MODERATE = 0.20   # edge_score >= this → MODERATE EDGE (below = WEAK)

# Home court advantage baseline (historically ~60% home win rate in NBA)
HOME_COURT_BOOST = 0.035

# NBA Teams metadata
TEAMS = {
    "ATL": {"name": "Atlanta Hawks",          "conference": "East"},
    "BOS": {"name": "Boston Celtics",         "conference": "East"},
    "BKN": {"name": "Brooklyn Nets",          "conference": "East"},
    "CHA": {"name": "Charlotte Hornets",      "conference": "East"},
    "CHI": {"name": "Chicago Bulls",          "conference": "East"},
    "CLE": {"name": "Cleveland Cavaliers",    "conference": "East"},
    "DAL": {"name": "Dallas Mavericks",       "conference": "West"},
    "DEN": {"name": "Denver Nuggets",         "conference": "West"},
    "DET": {"name": "Detroit Pistons",        "conference": "East"},
    "GSW": {"name": "Golden State Warriors",  "conference": "West"},
    "HOU": {"name": "Houston Rockets",        "conference": "West"},
    "IND": {"name": "Indiana Pacers",         "conference": "East"},
    "LAC": {"name": "LA Clippers",            "conference": "West"},
    "LAL": {"name": "Los Angeles Lakers",     "conference": "West"},
    "MEM": {"name": "Memphis Grizzlies",      "conference": "West"},
    "MIA": {"name": "Miami Heat",             "conference": "East"},
    "MIL": {"name": "Milwaukee Bucks",        "conference": "East"},
    "MIN": {"name": "Minnesota Timberwolves", "conference": "West"},
    "NOP": {"name": "New Orleans Pelicans",   "conference": "West"},
    "NYK": {"name": "New York Knicks",        "conference": "East"},
    "OKC": {"name": "Oklahoma City Thunder",  "conference": "West"},
    "ORL": {"name": "Orlando Magic",          "conference": "East"},
    "PHI": {"name": "Philadelphia 76ers",     "conference": "East"},
    "PHX": {"name": "Phoenix Suns",           "conference": "West"},
    "POR": {"name": "Portland Trail Blazers", "conference": "West"},
    "SAC": {"name": "Sacramento Kings",       "conference": "West"},
    "SAS": {"name": "San Antonio Spurs",      "conference": "West"},
    "TOR": {"name": "Toronto Raptors",        "conference": "East"},
    "UTA": {"name": "Utah Jazz",              "conference": "West"},
    "WAS": {"name": "Washington Wizards",     "conference": "East"},
}
