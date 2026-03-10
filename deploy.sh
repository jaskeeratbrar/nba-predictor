#!/bin/bash
# =============================================================================
# NBA Predictor — Deploy Script
# Called by cron at 6:00 PM ET daily.
# Runs predictions → updates public/index.html → commits → pushes to GitHub
# Vercel picks up the push and redeploys the dashboard automatically.
# =============================================================================

set -e
cd "$(dirname "$0")"

LOG="$(pwd)/cron.log"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date "+%Y-%m-%d %H:%M")

echo "[$TIMESTAMP] Starting deploy..." >> "$LOG"

# 0. Pull latest code changes from GitHub
git pull --rebase >> "$LOG" 2>&1

# 1. Run predictions (updates public/index.html as a side effect)
echo "[$TIMESTAMP] Running predictions..." >> "$LOG"
curl -s "http://localhost:6789/run?fmt=text" >> "$LOG" 2>&1

# 2. Commit and push public/index.html → triggers Vercel redeploy
if [ -f "public/index.html" ]; then
    git add public/index.html

    if ! git diff --staged --quiet; then
        git commit -m "picks: $DATE"
        git push
        echo "[$TIMESTAMP] Pushed to GitHub — Vercel redeploying..." >> "$LOG"
    else
        echo "[$TIMESTAMP] No changes to deploy." >> "$LOG"
    fi
fi

echo "[$TIMESTAMP] Done." >> "$LOG"
