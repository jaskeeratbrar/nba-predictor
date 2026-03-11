#!/bin/bash
# =============================================================================
# NBA Predictor — Post-Game Analysis Script
# Called by cron at 1:00 AM daily (games are finished by then).
# Scores yesterday's predictions → updates factor ledger → saves to history/.
# Does NOT push to git — push_morning.sh handles that at 8 AM.
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG="$SCRIPT_DIR/cron.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M")
PORT=6789
YESTERDAY=$(python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(1)).strftime('%Y-%m-%d'))")

echo "" >> "$LOG"
echo "[$TIMESTAMP] ====== ANALYSIS ($YESTERDAY) ======" >> "$LOG"

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
        echo "[$TIMESTAMP]   ERROR: Server failed to start. Analysis aborted." >> "$LOG"
        exit 1
    fi
fi

# Run analysis — saves history/{YESTERDAY}_analysis.json + updates factor ledger
echo "[$TIMESTAMP] Analyzing $YESTERDAY..." >> "$LOG"
RESULT=$(curl -s "http://localhost:$PORT/analyze?date=$YESTERDAY")
echo "[$TIMESTAMP] Result: $RESULT" >> "$LOG"

echo "[$TIMESTAMP] Analysis done. Dashboard will be updated at 8 AM push." >> "$LOG"
