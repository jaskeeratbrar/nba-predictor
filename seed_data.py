#!/usr/bin/env python3
"""
Seed initial data from web search results for March 8, 2026.
This is used when the ESPN API isn't reachable (e.g., sandbox environment).
Run once to bootstrap, then run_predictions.py will use live APIs going forward.
"""

import os
import json

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR
os.makedirs(DATA_DIR, exist_ok=True)

# ── March 8, 2026 Schedule (from ESPN/web search) ──────────────────────────
schedule = [
    {
        "home": {"abbr": "CLE", "name": "Cleveland Cavaliers", "wins": 39, "losses": 24, "score": 0},
        "away": {"abbr": "BOS", "name": "Boston Celtics", "wins": 42, "losses": 20, "score": 0},
        "date": "2026-03-08",
        "time": "2026-03-08T18:00Z",
        "status": "STATUS_SCHEDULED",
        "venue": "Rocket Mortgage FieldHouse"
    },
    {
        "home": {"abbr": "LAL", "name": "Los Angeles Lakers", "wins": 36, "losses": 24, "score": 0},
        "away": {"abbr": "NYK", "name": "New York Knicks", "wins": 40, "losses": 22, "score": 0},
        "date": "2026-03-08",
        "time": "2026-03-08T20:30Z",
        "status": "STATUS_SCHEDULED",
        "venue": "Crypto.com Arena"
    },
    {
        "home": {"abbr": "MIL", "name": "Milwaukee Bucks", "wins": 26, "losses": 35, "score": 0},
        "away": {"abbr": "ORL", "name": "Orlando Magic", "wins": 33, "losses": 28, "score": 0},
        "date": "2026-03-08",
        "time": "2026-03-08T19:00Z",
        "status": "STATUS_SCHEDULED",
        "venue": "Fiserv Forum"
    },
    {
        "home": {"abbr": "NOP", "name": "New Orleans Pelicans", "wins": 20, "losses": 45, "score": 0},
        "away": {"abbr": "WAS", "name": "Washington Wizards", "wins": 16, "losses": 47, "score": 0},
        "date": "2026-03-08",
        "time": "2026-03-08T20:00Z",
        "status": "STATUS_SCHEDULED",
        "venue": "Smoothie King Center"
    },
    {
        "home": {"abbr": "MIA", "name": "Miami Heat", "wins": 34, "losses": 29, "score": 0},
        "away": {"abbr": "DET", "name": "Detroit Pistons", "wins": 45, "losses": 16, "score": 0},
        "date": "2026-03-08",
        "time": "2026-03-08T20:00Z",
        "status": "STATUS_SCHEDULED",
        "venue": "Kaseya Center"
    },
    {
        "home": {"abbr": "TOR", "name": "Toronto Raptors", "wins": 22, "losses": 41, "score": 0},
        "away": {"abbr": "DAL", "name": "Dallas Mavericks", "wins": 21, "losses": 42, "score": 0},
        "date": "2026-03-08",
        "time": "2026-03-08T18:00Z",
        "status": "STATUS_SCHEDULED",
        "venue": "Scotiabank Arena"
    },
    {
        "home": {"abbr": "SAS", "name": "San Antonio Spurs", "wins": 46, "losses": 17, "score": 0},
        "away": {"abbr": "HOU", "name": "Houston Rockets", "wins": 38, "losses": 22, "score": 0},
        "date": "2026-03-08",
        "time": "2026-03-09T01:00Z",
        "status": "STATUS_SCHEDULED",
        "venue": "Frost Bank Center"
    },
]

# ── Current Standings (compiled from multiple web search results) ──────────
standings = {
    "OKC": {"name": "Oklahoma City Thunder", "abbr": "OKC", "conference": "West",
            "wins": 49, "losses": 15, "win_pct": 0.766, "streak": "W4",
            "home_record": "28-5", "away_record": "21-10", "last_10": "8-2"},
    "SAS": {"name": "San Antonio Spurs", "abbr": "SAS", "conference": "West",
            "wins": 46, "losses": 17, "win_pct": 0.730, "streak": "W3",
            "home_record": "26-6", "away_record": "20-11", "last_10": "7-3"},
    "DET": {"name": "Detroit Pistons", "abbr": "DET", "conference": "East",
            "wins": 45, "losses": 16, "win_pct": 0.738, "streak": "W5",
            "home_record": "25-5", "away_record": "20-11", "last_10": "8-2"},
    "BOS": {"name": "Boston Celtics", "abbr": "BOS", "conference": "East",
            "wins": 42, "losses": 20, "win_pct": 0.677, "streak": "W2",
            "home_record": "24-7", "away_record": "18-13", "last_10": "7-3"},
    "NYK": {"name": "New York Knicks", "abbr": "NYK", "conference": "East",
            "wins": 40, "losses": 22, "win_pct": 0.645, "streak": "W1",
            "home_record": "23-8", "away_record": "17-14", "last_10": "6-4"},
    "CLE": {"name": "Cleveland Cavaliers", "abbr": "CLE", "conference": "East",
            "wins": 39, "losses": 24, "win_pct": 0.619, "streak": "L1",
            "home_record": "23-9", "away_record": "16-15", "last_10": "5-5"},
    "DEN": {"name": "Denver Nuggets", "abbr": "DEN", "conference": "West",
            "wins": 39, "losses": 25, "win_pct": 0.609, "streak": "W2",
            "home_record": "23-9", "away_record": "16-16", "last_10": "6-4"},
    "HOU": {"name": "Houston Rockets", "abbr": "HOU", "conference": "West",
            "wins": 38, "losses": 22, "win_pct": 0.633, "streak": "L2",
            "home_record": "22-8", "away_record": "16-14", "last_10": "5-5"},
    "MIN": {"name": "Minnesota Timberwolves", "abbr": "MIN", "conference": "West",
            "wins": 38, "losses": 23, "win_pct": 0.623, "streak": "W1",
            "home_record": "22-9", "away_record": "16-14", "last_10": "6-4"},
    "LAL": {"name": "Los Angeles Lakers", "abbr": "LAL", "conference": "West",
            "wins": 36, "losses": 24, "win_pct": 0.600, "streak": "W3",
            "home_record": "21-9", "away_record": "15-15", "last_10": "7-3"},
    "PHX": {"name": "Phoenix Suns", "abbr": "PHX", "conference": "West",
            "wins": 34, "losses": 26, "win_pct": 0.567, "streak": "L1",
            "home_record": "20-11", "away_record": "14-15", "last_10": "5-5"},
    "MIA": {"name": "Miami Heat", "abbr": "MIA", "conference": "East",
            "wins": 34, "losses": 29, "win_pct": 0.540, "streak": "W1",
            "home_record": "20-12", "away_record": "14-17", "last_10": "5-5"},
    "PHI": {"name": "Philadelphia 76ers", "abbr": "PHI", "conference": "East",
            "wins": 34, "losses": 28, "win_pct": 0.548, "streak": "L2",
            "home_record": "20-11", "away_record": "14-17", "last_10": "4-6"},
    "ORL": {"name": "Orlando Magic", "abbr": "ORL", "conference": "East",
            "wins": 33, "losses": 28, "win_pct": 0.541, "streak": "W2",
            "home_record": "19-12", "away_record": "14-16", "last_10": "6-4"},
    "CHA": {"name": "Charlotte Hornets", "abbr": "CHA", "conference": "East",
            "wins": 32, "losses": 32, "win_pct": 0.500, "streak": "L3",
            "home_record": "18-14", "away_record": "14-18", "last_10": "4-6"},
    "GSW": {"name": "Golden State Warriors", "abbr": "GSW", "conference": "West",
            "wins": 32, "losses": 30, "win_pct": 0.516, "streak": "L1",
            "home_record": "19-12", "away_record": "13-18", "last_10": "5-5"},
    "ATL": {"name": "Atlanta Hawks", "abbr": "ATL", "conference": "East",
            "wins": 30, "losses": 33, "win_pct": 0.476, "streak": "W1",
            "home_record": "17-14", "away_record": "13-19", "last_10": "5-5"},
    "POR": {"name": "Portland Trail Blazers", "abbr": "POR", "conference": "West",
            "wins": 30, "losses": 34, "win_pct": 0.469, "streak": "L2",
            "home_record": "18-14", "away_record": "12-20", "last_10": "4-6"},
    "IND": {"name": "Indiana Pacers", "abbr": "IND", "conference": "East",
            "wins": 28, "losses": 34, "win_pct": 0.452, "streak": "L1",
            "home_record": "16-15", "away_record": "12-19", "last_10": "4-6"},
    "LAC": {"name": "LA Clippers", "abbr": "LAC", "conference": "West",
            "wins": 27, "losses": 35, "win_pct": 0.435, "streak": "L2",
            "home_record": "16-15", "away_record": "11-20", "last_10": "3-7"},
    "MIL": {"name": "Milwaukee Bucks", "abbr": "MIL", "conference": "East",
            "wins": 26, "losses": 35, "win_pct": 0.426, "streak": "L4",
            "home_record": "15-16", "away_record": "11-19", "last_10": "3-7"},
    "CHI": {"name": "Chicago Bulls", "abbr": "CHI", "conference": "East",
            "wins": 26, "losses": 37, "win_pct": 0.413, "streak": "L1",
            "home_record": "15-16", "away_record": "11-21", "last_10": "4-6"},
    "MEM": {"name": "Memphis Grizzlies", "abbr": "MEM", "conference": "West",
            "wins": 23, "losses": 38, "win_pct": 0.377, "streak": "W1",
            "home_record": "14-17", "away_record": "9-21", "last_10": "3-7"},
    "TOR": {"name": "Toronto Raptors", "abbr": "TOR", "conference": "East",
            "wins": 22, "losses": 41, "win_pct": 0.349, "streak": "L2",
            "home_record": "13-19", "away_record": "9-22", "last_10": "3-7"},
    "DAL": {"name": "Dallas Mavericks", "abbr": "DAL", "conference": "West",
            "wins": 21, "losses": 42, "win_pct": 0.333, "streak": "L5",
            "home_record": "12-20", "away_record": "9-22", "last_10": "2-8"},
    "NOP": {"name": "New Orleans Pelicans", "abbr": "NOP", "conference": "West",
            "wins": 20, "losses": 45, "win_pct": 0.308, "streak": "L3",
            "home_record": "12-21", "away_record": "8-24", "last_10": "2-8"},
    "UTA": {"name": "Utah Jazz", "abbr": "UTA", "conference": "West",
            "wins": 19, "losses": 44, "win_pct": 0.302, "streak": "L2",
            "home_record": "12-20", "away_record": "7-24", "last_10": "3-7"},
    "WAS": {"name": "Washington Wizards", "abbr": "WAS", "conference": "East",
            "wins": 16, "losses": 47, "win_pct": 0.254, "streak": "L4",
            "home_record": "10-22", "away_record": "6-25", "last_10": "2-8"},
    "BKN": {"name": "Brooklyn Nets", "abbr": "BKN", "conference": "East",
            "wins": 15, "losses": 47, "win_pct": 0.242, "streak": "L6",
            "home_record": "9-23", "away_record": "6-24", "last_10": "1-9"},
    "SAC": {"name": "Sacramento Kings", "abbr": "SAC", "conference": "West",
            "wins": 14, "losses": 50, "win_pct": 0.219, "streak": "L3",
            "home_record": "9-24", "away_record": "5-26", "last_10": "2-8"},
}

# ── Injuries (from web search results, March 7-8, 2026) ──────────────────
injuries = {
    "PHI": [
        {"name": "Joel Embiid", "position": "C", "status": "Out", "injury": "Oblique Strain", "detail": "Expected out at least a week"},
        {"name": "Johni Broome", "position": "C", "status": "Out", "injury": "Knee Surgery", "detail": "Longer recovery period"},
    ],
    "HOU": [
        {"name": "Fred VanVleet", "position": "PG", "status": "Out", "injury": "Season-Ending", "detail": "Season-ending injury"},
        {"name": "Steven Adams", "position": "C", "status": "Out", "injury": "Season-Ending", "detail": "Season-ending injury"},
    ],
    "DAL": [
        {"name": "Kyrie Irving", "position": "PG", "status": "Out", "injury": "ACL Tear", "detail": "Season-ending, torn late February"},
        {"name": "Dereck Lively II", "position": "C", "status": "Out", "injury": "Foot", "detail": "Out since December"},
        {"name": "Marvin Bagley III", "position": "PF", "status": "Out", "injury": "Neck Sprain", "detail": "Recent game injury"},
    ],
    "IND": [
        {"name": "Tyrese Haliburton", "position": "PG", "status": "Out", "injury": "Season-Ending", "detail": "Out for season"},
        {"name": "Johnny Furphy", "position": "SF", "status": "Out", "injury": "Season-Ending", "detail": "Out for season"},
    ],
    "CHA": [
        {"name": "LaMelo Ball", "position": "PG", "status": "Out", "injury": "Undisclosed", "detail": "Creating significant void in backcourt"},
    ],
    "MIA": [
        {"name": "Nikola Jovic", "position": "PF", "status": "Out", "injury": "Undisclosed", "detail": ""},
        {"name": "Simone Fontecchio", "position": "SF", "status": "Out", "injury": "Undisclosed", "detail": ""},
    ],
}

# Save all data
for filename, data in [
    ("schedule_2026-03-08.json", schedule),
    ("standings_current.json", standings),
    ("injuries_current.json", injuries),
]:
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ Saved {filename}")

print("\n  Data seeded successfully! Now run: python run_predictions.py")
