#!/bin/bash
# =============================================================================
# NBA Predictor — Morning Push Script
# Called by cron at 8:00 AM daily.
# Re-runs predictions with fresh morning data (injury reports update overnight)
# and pushes to GitHub. By this point, run_analysis.sh has already saved
# yesterday's analysis to history/ — so the regenerated dashboard includes
# the Results tab automatically.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG="$SCRIPT_DIR/cron.log"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date "+%Y-%m-%d %H:%M")
PORT=6789

echo "" >> "$LOG"
echo "[$TIMESTAMP] ====== MORNING PUSH ($DATE) ======" >> "$LOG"

# Ensure server is running — restart if not
if ! curl -s "http://localhost:$PORT/status" 2>/dev/null | grep -q '"ok"'; then
    echo "[$TIMESTAMP] Server not responding — restarting..." >> "$LOG"

    if [ -f "$SCRIPT_DIR/server.pid" ]; then
        OLD_PID=$(cat "$SCRIPT_DIR/server.pid")
        kill "$OLD_PID" 2>/dev/null || true
        rm -f "$SCRIPT_DIR/server.pid"
    fi
    pkill -f "server.py $PORT" 2>/dev/null || true
    sleep 2

    nohup python3 "$SCRIPT_DIR/server.py" $PORT >> "$LOG" 2>&1 &

    for i in $(seq 1 15); do
        if curl -s "http://localhost:$PORT/status" 2>/dev/null | grep -q '"ok"'; then
            echo "[$TIMESTAMP]   Server ready after ${i}s" >> "$LOG"
            break
        fi
        sleep 1
    done

    if ! curl -s "http://localhost:$PORT/status" 2>/dev/null | grep -q '"ok"'; then
        echo "[$TIMESTAMP]   ERROR: Server failed to start. Morning push aborted." >> "$LOG"
        exit 1
    fi
fi

# Re-run predictions with fresh morning data.
# generate_dashboard() auto-loads yesterday's _analysis.json, so the
# Results tab will appear in the pushed HTML automatically.
echo "[$TIMESTAMP] Re-running predictions (fresh morning data)..." >> "$LOG"
curl -s "http://localhost:$PORT/run?fmt=text" >> "$LOG" 2>&1

# Commit and push — this is the push you wake up to
if [ -f "$SCRIPT_DIR/public/index.html" ]; then
    git add public/index.html
    git add history/*.json 2>/dev/null || true
    git add performance/factor_accuracy.json 2>/dev/null || true

    if ! git diff --staged --quiet; then
        git commit -m "morning: $DATE (predictions + results tab)"
        git push
        echo "[$TIMESTAMP] Pushed to GitHub — Vercel redeploying with results tab..." >> "$LOG"
    else
        echo "[$TIMESTAMP] No changes to push." >> "$LOG"
    fi
fi

echo "[$TIMESTAMP] Morning push done." >> "$LOG"
