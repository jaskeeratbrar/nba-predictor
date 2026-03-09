# NBA Predictor

Daily NBA game prediction engine. Pulls live data from ESPN, scores each matchup, and outputs picks with confidence levels. Tracks its own accuracy over time and adjusts automatically.

---

## Setting Up on a New Machine

```bash
git clone https://github.com/jaskeeratbrar/nba-predictor.git
cd nba-predictor
bash setup.sh
```

That's it. The script will:
- Initialize the SQLite database and import existing learning history
- Start the HTTP server as a background service (survives reboots)
- Install all three cron jobs automatically

**Requires:** Python 3.8+, `curl`

---

## ⏰ When to Run — Optimal Timing

**Run at 6:00–6:30 PM ET on game days.**

| Time (ET) | What's happening |
|-----------|-----------------|
| 2:00–4:00 PM | Teams announce load management / rest decisions |
| **5:00 PM** | **NBA deadline — all teams must file official injury report** |
| 5:30–6:00 PM | ESPN updates its API with finalized reports |
| **6:00 PM** | ✅ **Best time to run** — full injury data, games haven't started |
| 7:00–7:30 PM | First games tip off |
| 10:00–10:30 PM | West Coast games tip off |

### Weekend afternoon games

Some weekend/holiday games tip at 1:00 or 3:30 PM ET. Their injury reports drop by ~11:00 AM ET. Add a second cron at **11:30 AM ET on weekends** if you want coverage for those, or accept that the 6 PM run won't catch them.

### Late scratches (warmup injuries)

Players hurt 15–30 min before tip-off won't appear in any pre-game data. Nothing you can do — even Vegas doesn't reliably price these in. The 6 PM window captures everything knowable.

---

## Cron Schedule (auto-installed by setup.sh)

```
6:00 PM  — Run predictions, save picks
9:00 AM  — Post-game analysis, update learning ledger
10:00 AM — Database backup
```

**Timezone note:** The cron times above assume your machine is set to ET. If it's UTC, shift +5 hours (11 PM, 2 PM, 3 PM UTC). Check your machine's timezone with `date`.

To manually adjust after setup:

```bash
crontab -e
```

---

## HTTP Server

The server runs on port `6789` and stays alive in the background.

| Endpoint | What it does |
|----------|-------------|
| `GET /run` | Today's predictions (JSON) |
| `GET /run?date=2026-03-15` | Predictions for a specific date |
| `GET /run?fmt=text` | Plain text — use this for cron output / notifications |
| `GET /analyze?date=2026-03-07` | Post-game analysis for a past date |
| `GET /status` | Health check |

**Quick test after setup:**
```bash
curl http://localhost:6789/status
curl http://localhost:6789/run?fmt=text
```

---

## Manual Commands

```bash
# Predict today's games
python run_predictions.py

# Predict a specific date
python run_predictions.py 2026-03-15

# Post-game analysis (how did the model do?)
python run_predictions.py --analyze 2026-03-07

# One-time: import old JSON history into the database
python migrate.py
```

---

## How the Model Improves Over Time

The model tracks how accurate each factor is and adjusts its weights automatically.

```
Every morning (9 AM cron):
  → Fetches final scores from ESPN
  → Compares predictions vs actual results
  → Updates the accuracy ledger (performance/factor_accuracy.json)
  → After 50+ analyzed games, switches to learned weights automatically
```

The `performance/factor_accuracy.json` file is committed to this repo so a new machine starts with accumulated learning rather than from scratch.

---

## Project Structure

```
nba-predictor/
├── setup.sh               # Run once on a new machine
├── run_analysis.sh         # Created by setup.sh, used by cron
├── run_predictions.py      # Main CLI
├── server.py               # HTTP server
├── config.py               # Configuration
├── data_manager.py         # ESPN data fetching + caching
├── prediction_engine.py    # Prediction model
├── analyzer.py             # Post-game analysis + learning
├── dashboard.py            # HTML report generator
├── db.py                   # SQLite database layer
├── migrate.py              # Import JSON history into DB
├── performance/
│   └── factor_accuracy.json  # Accumulated learning (committed)
├── data/                   # Cached ESPN responses (gitignored)
├── history/                # Daily prediction records (gitignored)
├── reports/                # HTML dashboards (gitignored)
└── backups/                # DB backups (gitignored)
```

---

## Logs

```bash
# Server logs
tail -f server.log

# Cron output
tail -f cron.log

# On Linux — service status
sudo systemctl status nba-predictor
sudo journalctl -u nba-predictor -f
```

---

## Troubleshooting

**Server not running after setup:**
```bash
# Linux
sudo systemctl restart nba-predictor

# macOS
launchctl unload ~/Library/LaunchAgents/com.nbapredictor.server.plist
launchctl load ~/Library/LaunchAgents/com.nbapredictor.server.plist

# Manual (any OS)
python server.py &
```

**No games found for a date:**
ESPN's API occasionally has downtime. The model falls back to cached data automatically. Re-run in 10 minutes.

**Cron ran but no output:**
Check that the server is running first (`curl http://localhost:6789/status`). The cron jobs hit the server endpoint — if the server is down, cron silently fails.
