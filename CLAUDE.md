# NBA Predictor — Claude Context

## Machine roles
- **This MacBook (jbrar)** — R&D only. No cron jobs, no server running.
  Used for analysis, model improvements, and pushing code changes to git.
  Never start the server here, never install cron jobs here.

- **Other machine (Linux server)** — Production. Runs cron + server.py 6789 continuously.
  Pulls from git and runs the daily cycle:
    - 6 PM  deploy.sh         (predictions → push)
    - 1 AM  run_analysis.sh   (score yesterday → update ledger, no push)
    - 8 AM  push_morning.sh   (re-run predictions + results tab → push)
    - 10 AM DB backup

## Workflow
1. Make changes here on the MacBook
2. Test locally if needed (manually run server.py temporarily, kill when done)
3. git push
4. SSH to server and git pull — cron picks up the rest automatically

## Key files
- `IMPROVEMENTS.md`   — model improvement tracker and priorities
- `API_REFERENCE.md`  — ESPN API documentation, response shapes, known quirks
- `deploy.sh`         — 6 PM cron: pull + restart + predict + push
- `run_analysis.sh`   — 1 AM cron: score yesterday's picks, no push
- `push_morning.sh`   — 8 AM cron: morning push with results tab
