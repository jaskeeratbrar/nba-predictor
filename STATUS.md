# NBA Predictor — Session Resume File

_Quick-start context for picking up where we left off. Read this first._

_Last updated: 2026-03-22_

---

## Model snapshot

| Stat | Value |
|------|-------|
| Season accuracy | 78.3% (101/129) |
| STRONG PICK accuracy | 90.0% |
| LEAN accuracy | 86.7% (26/30) |
| SKIP accuracy | 67.4% (29/43, expected — genuine toss-ups) |
| Active factors | 6 of 7 (rest_days frozen at 0.0) |
| Weights source | config.py (bumped 2026-03-22) + calibrate.py weekly |
| DB rows | on server — check via /stats endpoint |

## What's accumulating (don't touch, just let it run)

| Data | Started | Target | Check date | How to check |
|------|---------|--------|------------|-------------|
| ESPN team efficiency snapshots | 2026-03-16 | 2-3 weeks of daily snapshots | 2026-04-05 | `SELECT COUNT(DISTINCT snapshot_date) FROM team_efficiency_snapshots` |

## Code paths

| Trigger | Entry point | What it does |
|---------|------------|-------------|
| 6 PM cron | `deploy.sh` → `run_predictions.py` | Full pipeline: fetch → predict → dashboard → DB → git push |
| 1 AM cron | `run_analysis.sh` → `run_predictions.py --analyze` | Score yesterday's picks, update ledger |
| 8 AM cron | `push_morning.sh` | Re-run predictions + results tab → git push |
| Manual/API | `server.py /run` | Same as run_predictions.py but via HTTP |
| Manual/API | `server.py /stats` | Season accuracy + factor breakdown from DB |
| Manual/API | `server.py /history?team=X` | Team prediction history from DB |
| Manual/API | `server.py /misses?conf=0.7` | High-confidence wrong predictions from DB |
| Manual | `python3 calibrate.py` | Bayesian weight calibration → calibrated_weights.json |
| Manual | `python3 calibrate.py --dry-run` | Preview weight changes without writing |

## Active weights (config.py — updated 2026-03-22)

```
win_pct: 0.20  |  recent_form: 0.20  |  player_form: 0.20
home_away: 0.11 |  injuries: 0.14   |  streak: 0.03
net_rating: 0.05 (NEW — avg point differential last 10 games)
defense:    0.07 (NEW — avg opponent PPG allowed last 10 games)
rest_days:  0.00 (frozen — broken data source)
```

Run-time override priority:
1. `performance/calibrated_weights.json` (Bayesian calibrator — highest priority)
2. Ledger `weight_suggestions` (rolling heuristic — fallback if no calibrated file)
3. config.py WEIGHTS (baseline)

## Factor health

| Factor | Accuracy | Weight | Trend | Action needed |
|--------|----------|--------|-------|--------------|
| recent_form | 77.0% | 0.20 | Stable | None |
| player_form | 76.7% | 0.20 | Stable | None |
| win_pct | 75.0% | 0.20 | Stable | None |
| home_away | 75.0% | 0.11 | Rebounded ↑ | None (was 67.3%) |
| injuries | 73.4% | 0.14 | Stable | None |
| streak | 73.3% | 0.03 | Stable | None |
| net_rating | NEW | 0.05 | Accumulating | Check after 20+ votes |
| defense | NEW | 0.07 | Accumulating | Check after 20+ votes |
| rest_days | 53.3% | 0.00 | Frozen | Never re-enable without new data source |

## Known risks

1. **rest_days permanently frozen** — 53.3% is below random due to broken ESPN data.
   Never re-enable. Used only for edge scoring (rest_edge component in classify_play).

2. **Efficiency edge uncalibrated** — Shown on dashboard but not in model. Don't add
   to confidence until we can cross-reference with outcomes (~April 5).

3. **SKIP tier ceiling** — 67.4% accuracy on SKIP is expected (avg confidence 0.522).
   These are genuine coin flips. No model changes can reliably push this above ~72%.

## Next actions (by date)

| Date | Action |
|------|--------|
| Every Monday | Run `python3 calibrate.py` on server — update calibrated_weights.json |
| ~2026-04-05 | Check efficiency_edge correlation with outcomes. Worth adding as factor? |
| ~2026-04-05 | net_rating + defense: check vote counts + accuracy (need 20+ votes each) |
| End of season | Full season review — evaluate factor weights, home_away trend |
| ~Oct 2026 | Check if 200+ clean games exist. If yes → build logistic regression |

## New factors to watch (added 2026-03-22)

| Factor | Added | Min votes | Check command | Pass threshold | Fail threshold |
|--------|-------|-----------|---------------|----------------|----------------|
| net_rating | 2026-03-22 | 20 non-neutral | See query below | ≥70% → let calibrate.py increase weight | <60% after 30 votes → freeze at 0.0 |
| defense | 2026-03-22 | 20 non-neutral | See query below | ≥70% → let calibrate.py increase weight | <60% after 30 votes → freeze at 0.0 |

**How to check (run on server):**
```bash
python3 -c "
import json, os
from config import HISTORY_DIR

votes = {'net_rating': [0,0], 'defense': [0,0]}
for f in sorted(os.listdir(HISTORY_DIR)):
    if not f.endswith('_analysis.json'): continue
    date = f.replace('_analysis.json','')
    if date < '2026-03-22': continue   # only count post-addition games
    with open(os.path.join(HISTORY_DIR, f)) as fp:
        data = json.load(fp)
    for game in data.get('games', []):
        for factor in ['net_rating', 'defense']:
            fv = game.get('factor_votes', {}).get(factor, {})
            if not fv or fv.get('neutral', True): continue
            votes[factor][1] += 1
            if fv.get('correct'): votes[factor][0] += 1

for f, (c, t) in votes.items():
    acc = f'{c/t*100:.1f}%' if t else 'n/a'
    print(f'{f}: {c}/{t} = {acc}')
"
```

## Architecture reminders

- **This MacBook** = R&D only. No cron. Make changes → git push.
- **Linux server** = Production. Runs cron + server.py continuously. Pulls from git.
- **DB lives on Linux server.** Never migrate it. Access remotely via /stats, /history, /misses.
- **Dashboard** pushed to Vercel via public/index.html in git.
- **Generated files** (history/*.json, public/index.html) conflict often on pull — always
  take the server's version (`git checkout --theirs`).
- **calibrate.py** runs on server (has access to DB + full history). Run manually each Monday.

## Quick health check

```bash
# On the Linux server — verify everything is running
curl -s http://localhost:6789/status | python3 -m json.tool
curl -s http://localhost:6789/stats | python3 -m json.tool

# Run Bayesian weight calibration (each Monday)
python3 calibrate.py

# DB state
python3 -c "
import db; conn = db.get_connection()
for t in ['predictions','game_results','daily_summary','team_efficiency_snapshots']:
    r = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()
    print(f'  {t}: {r[0]} rows')
conn.close()
"
```
