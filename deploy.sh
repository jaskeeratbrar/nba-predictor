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

# Ensure run_analysis.sh exists (may be wiped by git pull since it's gitignored)
if [ ! -f "run_analysis.sh" ]; then
    SCRIPT_DIR="$(pwd)"
    cat > run_analysis.sh << EOF
#!/bin/bash
cd "$SCRIPT_DIR"
YESTERDAY=\$(python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(1)).strftime('%Y-%m-%d'))")
curl -s "http://localhost:6789/analyze?date=\$YESTERDAY"
git add history/*.json performance/factor_accuracy.json 2>/dev/null || true
if ! git diff --staged --quiet; then
    git commit -m "analysis: \$YESTERDAY"
    git push
fi
EOF
    chmod +x run_analysis.sh
fi

# 0.5. Restart server to pick up any code changes from the pull
echo "[$TIMESTAMP] Restarting server..." >> "$LOG"
pkill -f "server.py 6789" 2>/dev/null || true
sleep 2
nohup python3 "$(pwd)/server.py" 6789 >> "$LOG" 2>&1 &
sleep 3  # wait for server to be ready
# 1. Run predictions (updates public/index.html as a side effect)
echo "[$TIMESTAMP] Running predictions..." >> "$LOG"
curl -s "http://localhost:6789/run?fmt=text" >> "$LOG" 2>&1

# 2. Commit and push public/index.html + history files → triggers Vercel redeploy
if [ -f "public/index.html" ]; then
    git add public/index.html
    git add history/*.json 2>/dev/null || true
    git add performance/factor_accuracy.json 2>/dev/null || true

    if ! git diff --staged --quiet; then
        git commit -m "picks: $DATE"
        git push
        echo "[$TIMESTAMP] Pushed to GitHub — Vercel redeploying..." >> "$LOG"
    else
        echo "[$TIMESTAMP] No changes to deploy." >> "$LOG"
    fi
fi

echo "[$TIMESTAMP] Done." >> "$LOG"
