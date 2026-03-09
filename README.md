# NBA Predictor

Daily NBA game prediction engine. Pulls live data from ESPN, scores each matchup across 7 weighted factors, and outputs picks with confidence levels. Tracks its own accuracy over time and adjusts factor weights accordingly.

---

## Quick Start

```bash
# Predict today's games
python run_predictions.py

# Predict a specific date
python run_predictions.py 2026-03-15

# Post-game analysis (how did we do yesterday?)
python run_predictions.py --analyze 2026-03-07

# Start the HTTP server (for cron / remote access)
python server.py
```

---

## ⏰ When to Run — Optimal Timing

**TL;DR: Run at 6:00–6:30 PM ET on game days.**

### Why that window?

The NBA has mandatory injury disclosure rules that determine when you have complete information:

| Time (ET) | What happens |
|-----------|-------------|
| ~2:00–4:00 PM | Load management / rest decisions typically announced |
| **5:00 PM** | **NBA deadline — all teams must submit official injury report** |
| 5:30–6:00 PM | ESPN updates its API with the finalized reports (15–30 min lag) |
| 7:00–7:30 PM | First wave of games tips off |
| 10:00–10:30 PM | West Coast games tip off |

Running at **6:00–6:30 PM ET** means you have:
- The finalized injury report (5 PM deadline has passed)
- Time before tip-off to act on picks
- Full coverage of both East and West Coast games

### Cron setup

```bash
# Run at 6:00 PM ET every day
0 18 * * *   /path/to/python /path/to/run_predictions.py

# Or ping the server endpoint (if server.py is running)
0 18 * * *   curl -s http://localhost:6789/run?fmt=text

# If your machine is UTC
0 23 * * *   curl -s http://localhost:6789/run?fmt=text
```

### Weekend afternoon games

Some weekend/holiday games tip at 1:00 PM or 3:30 PM ET. Their injury reports drop by ~11:00 AM ET. If you care about those games, add a second cron at **11:30 AM ET on weekends**. Otherwise, the 6 PM run will still get the picks right — just without injury data for those early games.

### Late scratches

Players hurt in warmups (15–30 min before tip-off) won't appear in any pre-game run. Nothing you can do about those — even professional lines don't reliably price them in. The model's player form data partially compensates by knowing the team's depth.

---

## How the Model Works

Each game is scored across multiple weighted factors covering team performance, player availability, momentum, and rest. The team with the higher weighted score wins the prediction.

### Confidence tiers

| Label | Meaning |
|-------|---------|
| STRONG PICK | Clear edge — model is confident |
| LEAN | Meaningful edge, reasonable pick |
| SLIGHT LEAN | Small edge detected |
| SKIP | Too close to call |

### Injury handling

The model doesn't treat all absences equally — a star sitting out for load management hits the model significantly harder than a bench player. Star and starter absences are flagged in the output with their stats so you always know when a key absence is influencing a pick.

---

## Self-Improving Weights

The model tracks how accurate each factor is over time. After 50+ analyzed games, it automatically switches from config weights to **learned weights** derived from real performance data.

```bash
# Run post-game analysis to update the accuracy ledger
python run_predictions.py --analyze 2026-03-08

# View current factor accuracy
cat performance/factor_accuracy.json
```

The `performance/factor_accuracy.json` ledger shows each factor's accuracy, current weight, and suggested weight. The model will auto-apply suggestions once the sample is large enough to be statistically meaningful.

---

## HTTP Server (for cron/remote access)

```bash
python server.py          # starts on port 6789
python server.py 8080     # custom port
```

| Endpoint | Description |
|----------|-------------|
| `GET /run` | Today's predictions (JSON) |
| `GET /run?date=2026-03-08` | Specific date |
| `GET /run?fmt=text` | Plain text — good for notifications/cron output |
| `GET /analyze?date=2026-03-07` | Post-game analysis |
| `GET /status` | Health check |

The text format (`?fmt=text`) is designed for cron output emails or Slack/webhook notifications.

---

## Project Structure

```
nba_predictor/
├── run_predictions.py     # Main CLI entry point
├── server.py              # HTTP API server
├── config.py              # Weights, thresholds, team metadata
├── data_manager.py        # ESPN data fetching and caching
├── prediction_engine.py   # Prediction model and factor calculations
├── analyzer.py            # Post-game analysis and weight suggestions
├── dashboard.py           # HTML report generator
├── db.py                  # SQLite database layer
├── migrate.py             # One-time import of JSON history into DB
├── nba_predictor.db       # SQLite database (long-term storage)
├── data/                  # Cached ESPN API responses (JSON)
├── history/               # Daily prediction + analysis records (JSON)
├── performance/           # Factor accuracy ledger
└── reports/               # HTML dashboards
```

---

## Data Sources

All data is pulled from ESPN's public APIs (no API key required):

- Scoreboard / schedule
- Standings (wins, losses, streak, home/road splits, last 10)
- Injury reports (official NBA injury designations)
- Team game logs (recent form, scores)
- Player boxscores (last 5 games per player for form scoring)

Data is cached locally. If an API call fails, the model falls back to the last cached version so predictions still run.

---

## Self-Tuning

Once enough games have been analyzed, the model automatically adjusts its internal weights based on which factors have been most accurate. No manual tuning needed — it improves itself over the course of the season.
