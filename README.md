# NBA Predictor

Daily NBA game prediction engine that analyzes team performance, injuries, streaks, and more to predict winners.

## Quick Start

```bash
cd nba_predictor

# Predict today's games
python run_predictions.py

# Predict tomorrow's games
python run_predictions.py tomorrow

# Predict a specific date
python run_predictions.py 2026-03-15

# Verify past predictions against actual results
python run_predictions.py --verify 2026-03-08
```

## How It Works

The model scores each team across **7 weighted factors**:

| Factor | Weight | Description |
|--------|--------|-------------|
| Win % | 25% | Overall season win percentage (power-scaled) |
| Recent Form | 20% | Last 10 games performance |
| Home/Away | 15% | Home court advantage + home/road records |
| Injuries | 15% | Key player availability impact |
| Streak | 10% | Current winning/losing streak momentum |
| Head-to-Head | 10% | Season series record |
| Rest Days | 5% | Back-to-back detection |

### Recommendations

- **STRONG PICK** (70%+) — High confidence, clear mismatch
- **LEAN** (60-70%) — Moderate edge, reasonable pick
- **SLIGHT LEAN** (55-60%) — Small edge detected
- **SKIP** (<55%) — Too close to call, don't risk it

## Data Sources

The system fetches from ESPN's public API:
- Game schedules and scores
- Team standings and records
- Injury reports
- Recent game results

Data is cached locally so the model works offline with the last-fetched data.

## Project Structure

```
nba_predictor/
├── run_predictions.py    # Main entry point
├── config.py             # Weights, thresholds, team data
├── data_manager.py       # Data fetching and caching
├── prediction_engine.py  # The prediction model
├── dashboard.py          # HTML report generator
├── seed_data.py          # Bootstrap data when API unavailable
├── data/                 # Cached API responses
├── history/              # Daily prediction records
└── reports/              # HTML dashboards
```

## Daily Workflow

1. Run `python run_predictions.py` or `python run_predictions.py tomorrow`
2. Check the console output for quick picks
3. Open the HTML report in `reports/` for the visual dashboard
4. The system auto-verifies yesterday's predictions when you run today's

## Tuning

Edit `config.py` to adjust:
- `WEIGHTS` — Change how much each factor matters
- `CONFIDENCE_HIGH/MODERATE/LOW` — Adjust recommendation thresholds
- `HOME_COURT_BOOST` — Tweak home court advantage
