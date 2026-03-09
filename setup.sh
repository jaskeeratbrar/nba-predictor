#!/bin/bash
# =============================================================================
# NBA Predictor — Setup Script
# Run once on a new machine after cloning the repo.
# Supports macOS and Linux.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(which python3)
PORT=6789
LOG="$SCRIPT_DIR/server.log"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }

echo ""
echo "================================================"
echo "  NBA Predictor — Setup"
echo "================================================"
echo ""

# --- 1. Check Python --------------------------------------------------------
command -v python3 &>/dev/null || fail "python3 not found. Install Python 3.8+ first."
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
[[ ${PY_VER%%.*} -ge 3 && ${PY_VER##*.} -ge 8 ]] || fail "Python 3.8+ required. Found $PY_VER"
ok "Python $PY_VER"

# --- 2. Create directories --------------------------------------------------
mkdir -p "$SCRIPT_DIR/data" \
         "$SCRIPT_DIR/history" \
         "$SCRIPT_DIR/performance" \
         "$SCRIPT_DIR/reports" \
         "$SCRIPT_DIR/backups"
ok "Directories ready"

# --- 3. Initialize DB and migrate existing data -----------------------------
echo ""
echo "--- Initializing database ---"
cd "$SCRIPT_DIR"
$PYTHON migrate.py
ok "Database ready"

# --- 4. Start server as a persistent background service --------------------
echo ""
echo "--- Setting up server ---"
OS=$(uname -s)

if [ "$OS" = "Linux" ]; then
    SERVICE_FILE="/etc/systemd/system/nba-predictor.service"
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=NBA Predictor HTTP Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON $SCRIPT_DIR/server.py $PORT
Restart=always
RestartSec=10
StandardOutput=append:$LOG
StandardError=append:$LOG

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable nba-predictor
    sudo systemctl restart nba-predictor
    ok "systemd service installed (nba-predictor)"
    echo "     Status:  sudo systemctl status nba-predictor"
    echo "     Logs:    sudo journalctl -u nba-predictor -f"

elif [ "$OS" = "Darwin" ]; then
    PLIST="$HOME/Library/LaunchAgents/com.nbapredictor.server.plist"
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nbapredictor.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT_DIR/server.py</string>
        <string>$PORT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
</dict>
</plist>
EOF
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    ok "launchd service installed"
    echo "     Logs:  tail -f $LOG"

else
    warn "Unknown OS. Starting server manually in background."
    nohup $PYTHON "$SCRIPT_DIR/server.py" $PORT >> "$LOG" 2>&1 &
    echo $! > "$SCRIPT_DIR/server.pid"
    ok "Server started (PID $(cat $SCRIPT_DIR/server.pid))"
    warn "Add this to your @reboot cron to auto-start on reboot:"
    echo "     @reboot $PYTHON $SCRIPT_DIR/server.py $PORT >> $LOG 2>&1"
fi

# --- 5. Git identity (needed for cron commits) ------------------------------
echo ""
echo "--- Configuring git ---"
if [ -z "$(git config user.email)" ]; then
    read -p "  Git email for cron commits: " GIT_EMAIL
    read -p "  Git name: " GIT_NAME
    git config user.email "$GIT_EMAIL"
    git config user.name "$GIT_NAME"
    ok "Git identity set"
else
    ok "Git identity already set ($(git config user.email))"
fi

# Verify we can push (SSH key or token must already be configured)
echo "  Testing git push access..."
if git ls-remote origin &>/dev/null; then
    ok "Git push access confirmed"
else
    warn "Cannot reach git remote. Make sure SSH key or token is set up before cron runs."
    echo "  SSH setup: https://docs.github.com/en/authentication/connecting-to-github-with-ssh"
fi

# --- 6. Install cron jobs ---------------------------------------------------
echo ""
echo "--- Installing cron jobs ---"

# Make scripts executable
chmod +x "$SCRIPT_DIR/deploy.sh"

# Helper script for post-game analysis (handles macOS/Linux date differences)
cat > "$SCRIPT_DIR/run_analysis.sh" <<'EOF'
#!/bin/bash
YESTERDAY=$(python3 -c "from datetime import date, timedelta; print((date.today()-timedelta(1)).strftime('%Y-%m-%d'))")
curl -s "http://localhost:6789/analyze?date=$YESTERDAY"
EOF
chmod +x "$SCRIPT_DIR/run_analysis.sh"

# Remove any existing nba-predictor cron lines
(crontab -l 2>/dev/null | grep -v "# nba-predictor") | crontab -

# Install the three jobs
(crontab -l 2>/dev/null; cat <<EOF

# nba-predictor: predictions at 6 PM ET → commit → push → Vercel redeploys
0 18 * * * "$SCRIPT_DIR/deploy.sh" # nba-predictor

# nba-predictor: post-game analysis at 9 AM (updates learning ledger)
0 9  * * * "$SCRIPT_DIR/run_analysis.sh" >> "$SCRIPT_DIR/cron.log" 2>&1 # nba-predictor

# nba-predictor: daily DB backup at 10 AM
0 10 * * * cp "$SCRIPT_DIR/nba_predictor.db" "$SCRIPT_DIR/backups/nba_\$(date +\%Y\%m\%d).db" # nba-predictor

EOF
) | crontab -

ok "Cron jobs installed"
echo "     Installed jobs:"
crontab -l | grep "# nba-predictor" | sed 's/^/     /'

# --- 6. Smoke test ----------------------------------------------------------
echo ""
echo "--- Testing server ---"
sleep 3
if curl -s "http://localhost:$PORT/status" 2>/dev/null | grep -q '"ok"'; then
    ok "Server responding at http://localhost:$PORT"
else
    warn "Server not responding yet — may still be starting. Check: curl http://localhost:$PORT/status"
fi

# --- Done -------------------------------------------------------------------
echo ""
echo "================================================"
echo "  Setup complete"
echo "================================================"
echo ""
echo "  Quick test:"
echo "    curl http://localhost:$PORT/status"
echo "    curl http://localhost:$PORT/run?fmt=text"
echo ""
echo "  Cron runs at:"
echo "    6:00 PM  — predictions (adjust if not in ET timezone)"
echo "    9:00 AM  — post-game analysis + model learning"
echo "    10:00 AM — database backup"
echo ""
echo "  Logs:"
echo "    Server:  tail -f $LOG"
echo "    Cron:    tail -f $SCRIPT_DIR/cron.log"
echo ""
