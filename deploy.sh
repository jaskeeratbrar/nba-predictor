#!/bin/bash
# =============================================================================
# NBA Predictor — Deploy Script
# Called by cron at 6:00 PM ET daily.
# Runs predictions → updates public/index.html → commits → pushes to GitHub
# Vercel picks up the push and redeploys the dashboard automatically.
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG="$SCRIPT_DIR/cron.log"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date "+%Y-%m-%d %H:%M")
PORT=6789

echo "" >> "$LOG"
echo "[$TIMESTAMP] ====== DEPLOY (predictions) ======" >> "$LOG"

# 0. Pull latest code changes from GitHub
echo "[$TIMESTAMP] Pulling latest code..." >> "$LOG"
git pull --rebase >> "$LOG" 2>&1

# 1. Restart server to pick up any code changes from the pull
echo "[$TIMESTAMP] Restarting server..." >> "$LOG"

# Kill by PID file first (most reliable), fall back to pkill
if [ -f "$SCRIPT_DIR/server.pid" ]; then
    OLD_PID=$(cat "$SCRIPT_DIR/server.pid")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        kill "$OLD_PID" 2>/dev/null || true
        echo "[$TIMESTAMP]   Killed PID $OLD_PID" >> "$LOG"
    fi
    rm -f "$SCRIPT_DIR/server.pid"
fi
# Belt-and-suspenders: also pkill any stray processes
pkill -f "server.py $PORT" 2>/dev/null || true
sleep 2

nohup python3 "$SCRIPT_DIR/server.py" $PORT >> "$LOG" 2>&1 &

# Wait until /status responds (up to 15 seconds)
echo "[$TIMESTAMP]   Waiting for server..." >> "$LOG"
for i in $(seq 1 15); do
    if curl -s "http://localhost:$PORT/status" 2>/dev/null | grep -q '"ok"'; then
        echo "[$TIMESTAMP]   Server ready after ${i}s" >> "$LOG"
        break
    fi
    sleep 1
done

# Verify it actually started — abort if not
if ! curl -s "http://localhost:$PORT/status" 2>/dev/null | grep -q '"ok"'; then
    echo "[$TIMESTAMP]   ERROR: Server failed to start. Aborting deploy." >> "$LOG"
    exit 1
fi

# 2. Run predictions (updates public/index.html as a side effect)
echo "[$TIMESTAMP] Running predictions..." >> "$LOG"
curl -s "http://localhost:$PORT/run?fmt=text" >> "$LOG" 2>&1

# 3. Commit and push public/index.html + history files → triggers Vercel redeploy
if [ -f "$SCRIPT_DIR/public/index.html" ]; then
    git add public/index.html
    git add history/*.json 2>/dev/null || true
    git add performance/factor_accuracy.json 2>/dev/null || true

    if ! git diff --staged --quiet; then
        git commit -m "picks: $DATE"
        git push
        echo "[$TIMESTAMP] Pushed predictions to GitHub — Vercel redeploying..." >> "$LOG"
    else
        echo "[$TIMESTAMP] No changes to deploy." >> "$LOG"
    fi
fi

echo "[$TIMESTAMP] Deploy done." >> "$LOG"
