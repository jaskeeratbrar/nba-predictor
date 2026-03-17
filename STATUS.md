# NBA Predictor — Session Resume File

_Quick-start context for picking up where we left off. Read this first._

_Last updated: 2026-03-16_

---

## Model snapshot

| Stat | Value |
|------|-------|
| Season accuracy | 77.4% (41/53) |
| STRONG PICK accuracy | 85.7% |
| LEAN accuracy | 100% (8/8, small sample) |
| Active factors | 6 of 7 (rest_days frozen at 0.0) |
| Weights source | Learned (53 games analyzed), with config exclusions enforced |
| DB rows | 56 predictions, 42 results, 7 daily summaries |

## What's accumulating (don't touch, just let it run)

| Data | Started | Target | Check date | How to check |
|------|---------|--------|------------|-------------|
| Injury factor clean votes | 2026-03-09 | 15+ votes | 2026-03-25 | See IMPROVEMENTS.md query |
| ESPN team efficiency snapshots | 2026-03-16 | 2-3 weeks of daily snapshots | 2026-04-05 | `SELECT COUNT(DISTINCT snapshot_date) FROM team_efficiency_snapshots` |
| Clean games for calibrate.py | 2026-03-09 | 30+ games | 2026-03-31 | See IMPROVEMENTS.md query |

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

## Active weights (config.py)

```
win_pct: 0.27  |  recent_form: 0.22  |  player_form: 0.22
home_away: 0.12 |  injuries: 0.12    |  streak: 0.05
rest_days: 0.00 (frozen — broken data source, used only for edge scoring)
```

Learned weights override these at runtime (both run_predictions.py and server.py)
but config exclusions (rest_days=0.0) are enforced before set_weights().

## Factor health

| Factor | Accuracy | Weight | Trend | Action needed |
|--------|----------|--------|-------|--------------|
| recent_form | 80.8% | 0.22 | Stable | None |
| streak | 77.5% | 0.05 | Stable | None |
| injuries | 75.0% | 0.12 | Accumulating | Bump to 0.15 after 15+ votes |
| player_form | 72.4% | 0.22 | Stable | None |
| win_pct | 72.0% | 0.27 | Stable | None |
| home_away | 67.3% | 0.12 | Watch | Reduce to 0.08 if drops below 65% |
| rest_days | 33.3% | 0.00 | Frozen | Never re-enable without new data source |

## Known risks

1. **Injury sample too small** — Only 8 clean votes. Weight adjustment deferred.
   If injury accuracy tanks below 60% on more data, don't increase weight.

2. **home_away weakest factor** — 67.3% is borderline. NBA home court advantage is
   genuinely shrinking. Monitor through March; reduce weight if it doesn't hold.

3. **Efficiency edge uncalibrated** — Shown on dashboard but not in model. Don't add
   to confidence until we can cross-reference with outcomes (~April).

## Next actions (by date)

| Date | Action |
|------|--------|
| ~2026-03-25 | Check injury votes (15+?). If yes + 70%+ accuracy → bump weight to 0.15 |
| ~2026-03-31 | Check clean games (30+?). If yes → build calibrate.py |
| ~2026-04-05 | Check efficiency_edge correlation with outcomes. Worth adding as factor? |
| End of season | Evaluate home_away factor. Consider weight reduction or removal |
| ~Oct 2026 | Check if 200+ clean games exist. If yes → build logistic regression |

## Architecture reminders

- **This MacBook** = R&D only. No cron. Make changes → git push.
- **Linux server** = Production. Runs cron + server.py continuously. Pulls from git.
- **DB lives on Linux server.** Never migrate it. Access remotely via /stats, /history, /misses.
- **Dashboard** pushed to Vercel via public/index.html in git.
- **Generated files** (history/*.json, public/index.html) conflict often on pull — always
  take the server's version (`git checkout --theirs`).

## Quick health check

```bash
# On the Linux server — verify everything is running
curl -s http://localhost:6789/status | python3 -m json.tool
curl -s http://localhost:6789/stats | python3 -m json.tool

# Check DB state
python3 -c "
import db; conn = db.get_connection()
for t in ['predictions','game_results','daily_summary','team_efficiency_snapshots']:
    r = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()
    print(f'  {t}: {r[0]} rows')
conn.close()
"
```
