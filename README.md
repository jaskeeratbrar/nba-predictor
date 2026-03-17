# NBA Predictor

Daily NBA game prediction engine. Pulls live data from ESPN, scores each matchup, and outputs picks with confidence levels. Tracks its own accuracy over time and adjusts automatically.

---

## New Machine Setup — Read This First

**This is the only file you need. Do everything in order.**

### Step 1 — Prerequisites

Install these before running anything:

| Requirement | How to check | Install |
|-------------|-------------|---------|
| Python 3.8+ | `python3 --version` | [python.org](https://python.org) or `brew install python` |
| curl | `curl --version` | Pre-installed on macOS/Linux |
| git | `git --version` | `brew install git` or `apt install git` |

### Step 2 — GitHub SSH access

The 6 PM cron auto-commits and pushes to GitHub. That only works if the machine can authenticate with GitHub without a password prompt.

**Check if it already works:**
```bash
ssh -T git@github.com
# Should print: Hi jaskeeratbrar! You've successfully authenticated...
```

**If it doesn't work, set up an SSH key:**
```bash
ssh-keygen -t ed25519 -C "your@email.com"   # press Enter through all prompts
cat ~/.ssh/id_ed25519.pub                    # copy this entire line
```
Then go to: GitHub → Settings → SSH and GPG keys → New SSH key → paste it in.

Test again: `ssh -T git@github.com`

### Step 3 — Clone and run setup

```bash
git clone git@github.com:jaskeeratbrar/nba-predictor.git
cd nba-predictor
bash setup.sh
```

The setup script will:
- Verify Python version
- Create required directories (`data/`, `history/`, `reports/`, `backups/`)
- Initialize the SQLite database and import existing learning history
- Start the HTTP server as a background service (survives reboots)
- Ask for your git name/email for cron commits (only if not already set)
- Verify GitHub push access
- Install all three cron jobs automatically

### Step 4 — Verify it worked

```bash
curl http://localhost:6789/status
# Should return: {"status": "ok", ...}

curl "http://localhost:6789/run?fmt=text"
# Should return today's picks
```

### Step 5 — Vercel dashboard (one-time, optional)

If you want the live public dashboard at `your-project.vercel.app`:

1. Go to [vercel.com](https://vercel.com) → Add New Project
2. Import the `nba-predictor` GitHub repo
3. Set **Output Directory** to `public`, leave build command blank
4. Click Deploy

After that, every time the 6 PM cron runs, it pushes `public/index.html` to GitHub and Vercel auto-redeploys within ~30 seconds. No manual steps needed.

### Step 6 — Timezone check

The cron jobs are installed at 6 PM, 9 AM, and 10 AM. These assume your machine's local time is **ET (Eastern Time)**.

```bash
date
# Check what timezone your machine is in
```

If your machine is UTC, edit crontab and shift: 6 PM ET = 11 PM UTC, 9 AM ET = 2 PM UTC, 10 AM ET = 3 PM UTC.

```bash
crontab -e
```

---

## When to Run — Optimal Timing

**The cron handles this automatically. This section is just context.**

Run at 6:00–6:30 PM ET on game days.

| Time (ET) | What's happening |
|-----------|-----------------|
| 2:00–4:00 PM | Teams announce load management / rest decisions |
| **5:00 PM** | **NBA deadline — all teams must file official injury report** |
| 5:30–6:00 PM | ESPN updates its API with finalized reports |
| **6:00 PM** | Best time to run — full injury data, games haven't started |
| 7:00–7:30 PM | First games tip off |
| 10:00–10:30 PM | West Coast games tip off |

**Weekend afternoon games:** Some tip at 1:00 or 3:30 PM ET. Their injury reports drop by ~11:00 AM ET. The 6 PM run will miss those. Add a second cron at 11:30 AM on weekends if you want full coverage.

**Late scratches:** Players hurt 15–30 min before tip-off won't appear in any pre-game data. The 6 PM window captures everything knowable.

---

## Cron Schedule (auto-installed by setup.sh)

```
6:00 PM  — Run predictions → generate dashboard → commit → push → Vercel redeploys
9:00 AM  — Post-game analysis, update learning ledger
10:00 AM — Database backup
```

---

## HTTP Server

The server runs on port `6789` and stays alive in the background.

| Endpoint | What it does |
|----------|-------------|
| `GET /run` | Today's predictions (JSON) |
| `GET /run?date=2026-03-15` | Predictions for a specific date |
| `GET /run?fmt=text` | Plain text output |
| `GET /analyze?date=2026-03-07` | Post-game analysis for a past date |
| `GET /status` | Health check |

---

## Manual Commands

```bash
# Predict today's games
python3 run_predictions.py

# Predict a specific date
python3 run_predictions.py 2026-03-15

# Post-game analysis (how did the model do?)
python3 run_predictions.py --analyze 2026-03-07

# One-time: import old JSON history into the database
python3 migrate.py
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

`performance/factor_accuracy.json` is committed to this repo so a new machine starts with accumulated learning rather than from scratch.

---

## Project Structure

```
nba-predictor/
├── README.md              # This file — all setup info lives here
├── setup.sh               # Run once on a new machine
├── deploy.sh              # Called by 6 PM cron — runs predictions + git push
├── run_analysis.sh        # Created by setup.sh — called by 9 AM cron
├── run_predictions.py     # Main CLI
├── server.py              # HTTP server (port 6789)
├── config.py              # Configuration
├── data_manager.py        # ESPN data fetching + caching
├── prediction_engine.py   # Prediction model
├── analyzer.py            # Post-game analysis + learning
├── dashboard.py           # HTML report generator
├── db.py                  # SQLite database layer
├── migrate.py             # Import JSON history into DB
├── vercel.json            # Vercel static site config
├── public/
│   └── index.html         # Live dashboard (auto-updated by cron)
├── performance/
│   └── factor_accuracy.json  # Accumulated learning (committed)
├── data/                  # Cached ESPN responses (gitignored)
├── history/               # Daily prediction records (gitignored)
├── reports/               # HTML dashboards (gitignored)
└── backups/               # DB backups (gitignored)
```

---

## Logs

```bash
# Server logs
tail -f server.log

# Cron output
tail -f cron.log

# Linux — service status
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

# Manual fallback (any OS)
python3 server.py &
```

**No games found for a date:**
ESPN's API occasionally has downtime. The model falls back to cached data automatically. Re-run in 10 minutes.

**Cron ran but no picks generated:**
Check the server is running first (`curl http://localhost:6789/status`). The cron hits the server endpoint — if the server is down, cron silently does nothing.

**Git push failing from cron:**
Run `ssh -T git@github.com` on the machine. If it fails, the SSH key isn't set up. See Step 2 above.

**Vercel not updating:**
Check that `public/index.html` is being committed — look at the GitHub repo after 6 PM. If no commit appeared, check `cron.log` for errors.
