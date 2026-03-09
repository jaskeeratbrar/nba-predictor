#!/usr/bin/env python3
"""
NBA Predictor — Simple HTTP API Server
=======================================
Zero dependencies (stdlib only). Run once, ping anytime.

Start:
    python3 server.py              # default port 6789
    python3 server.py 8080         # custom port

Endpoints:
    GET /run                       # run today's predictions
    GET /run?date=2026-03-08       # run for a specific date
    GET /analyze?date=2026-03-07   # post-game analysis for a past date
    GET /status                    # quick health check
"""

import json
import os
import sys
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

os.chdir(os.path.dirname(os.path.abspath(__file__)))

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 6789


def _run_predictions(date_str):
    """Run the full prediction pipeline and return structured results."""
    from data_manager import refresh_all_data
    from prediction_engine import predict_all_games
    from dashboard import generate_dashboard
    from data_manager import save_history, load_history
    from config import HISTORY_DIR, REPORTS_DIR

    data = refresh_all_data(date_str)
    if not data["schedule"]:
        return {"error": f"No games found for {date_str}"}

    predictions = predict_all_games(
        data["schedule"],
        data["standings"],
        data["injuries"],
        data["recent_form"],
        data.get("player_form", {}),
    )

    history_entry = {
        "date": date_str,
        "generated_at": datetime.now().isoformat(),
        "num_games": len(predictions),
        "predictions": predictions,
    }
    save_history(date_str, history_entry)

    try:
        import db as _db
        _conn = _db.get_connection()
        _db.upsert_predictions(_conn, date_str, predictions)
        _conn.commit()
        _conn.close()
    except Exception as _e:
        pass  # DB write is non-critical

    # Generate dashboard and update public/index.html for Vercel
    try:
        import shutil
        dashboard_path = generate_dashboard(predictions, date_str, None)
        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
        os.makedirs(public_dir, exist_ok=True)
        shutil.copy(dashboard_path, os.path.join(public_dir, "index.html"))
    except Exception:
        pass

    # Build clean summary
    strong  = [p for p in predictions if p["recommendation"] == "STRONG PICK"]
    leans   = [p for p in predictions if p["recommendation"] in ("LEAN", "SLIGHT LEAN")]
    skips   = [p for p in predictions if p["recommendation"] == "SKIP"]

    def _fmt(p):
        pf = p.get("player_form_leader", "")
        return {
            "matchup":     f"{p['away_abbr']} @ {p['home_abbr']}",
            "pick":        p["predicted_winner_name"],
            "confidence":  f"{p['confidence']*100:.1f}%",
            "away_record": p["away_record"],
            "home_record": p["home_record"],
        }

    return {
        "date":       date_str,
        "total_games": len(predictions),
        "strong_picks": [_fmt(p) for p in strong],
        "leans":        [_fmt(p) for p in leans],
        "skips":        [f"{p['away_abbr']} @ {p['home_abbr']}" for p in skips],
        "all_predictions": predictions,
    }


def _format_text(result):
    """Format results as clean plain text for notifications."""
    if "error" in result:
        return f"ERROR: {result['error']}"

    lines = []
    lines.append(f"NBA PICKS — {result['date']}  ({result['total_games']} games)")
    lines.append("=" * 45)

    if result["strong_picks"]:
        lines.append(f"\nSTRONG PICKS ({len(result['strong_picks'])}):")
        for p in result["strong_picks"]:
            lines.append(f"  ✓ {p['pick']} ({p['confidence']})  {p['matchup']}")

    if result["leans"]:
        lines.append(f"\nLEANS ({len(result['leans'])}):")
        for p in result["leans"]:
            lines.append(f"  → {p['pick']} ({p['confidence']})  {p['matchup']}")

    if result["skips"]:
        lines.append(f"\nSKIP ({len(result['skips'])}) — too close:")
        for s in result["skips"]:
            lines.append(f"  – {s}")

    lines.append("\n" + "=" * 45)
    return "\n".join(lines)


def _run_analysis(date_str):
    """Run post-game analysis for a past date."""
    from analyzer import analyze_date
    result = analyze_date(date_str)
    if not result:
        return {"error": f"No data or results not final for {date_str}"}
    return {
        "date":     result["date"],
        "correct":  result["summary"]["correct"],
        "total":    result["summary"]["total"],
        "accuracy": f"{result['summary']['accuracy']*100:.1f}%",
        "games": [
            {
                "matchup":   g["matchup"],
                "predicted": g["predicted_winner"],
                "actual":    g["actual_winner"],
                "correct":   g["correct"],
                "score":     f"{int(g['away_score'])}-{int(g['home_score'])}",
            }
            for g in result["games"]
        ],
    }


class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {args[0]} {args[1]} {args[2]}")

    def _respond(self, data, status=200, fmt="json"):
        if fmt == "text":
            body = data.encode() if isinstance(data, str) else data
            ct = "text/plain; charset=utf-8"
        else:
            body = json.dumps(data, indent=2, default=str).encode()
            ct = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path   = parsed.path.rstrip("/")

        try:
            if path == "/status":
                self._respond({"status": "ok", "time": datetime.now().isoformat()})

            elif path == "/run":
                date_str = params.get("date", [datetime.now().strftime("%Y-%m-%d")])[0]
                fmt      = params.get("fmt", ["json"])[0]
                print(f"  Running predictions for {date_str}...")
                result = _run_predictions(date_str)
                if fmt == "text":
                    self._respond(_format_text(result), fmt="text")
                else:
                    self._respond(result)

            elif path == "/analyze":
                date_str = params.get("date", [None])[0]
                if not date_str:
                    self._respond({"error": "date param required, e.g. /analyze?date=2026-03-07"}, 400)
                    return
                print(f"  Running analysis for {date_str}...")
                result = _run_analysis(date_str)
                self._respond(result)

            else:
                self._respond({
                    "endpoints": {
                        "GET /status":                   "health check",
                        "GET /run":                      "today's predictions (JSON)",
                        "GET /run?date=YYYY-MM-DD":      "specific date predictions",
                        "GET /run?fmt=text":             "plain text output (for notifications)",
                        "GET /analyze?date=YYYY-MM-DD":  "post-game analysis",
                    }
                }, 404)

        except Exception:
            tb = traceback.format_exc()
            print(tb)
            self._respond({"error": "Internal error", "detail": tb}, 500)


if __name__ == "__main__":
    # Apply learned weights at startup if enough games analyzed
    try:
        from analyzer import load_factor_ledger
        from prediction_engine import set_weights
        _ledger = load_factor_ledger()
        if _ledger.get("total_games_analyzed", 0) >= 50:
            _suggestions = _ledger.get("weight_suggestions", {})
            if _suggestions:
                set_weights(_suggestions)
                print(f"  Learned weights active ({_ledger['total_games_analyzed']} analyzed games)")
    except Exception:
        pass

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"NBA Predictor server running on http://localhost:{PORT}")
    print(f"  GET http://localhost:{PORT}/run")
    print(f"  GET http://localhost:{PORT}/run?fmt=text")
    print(f"  GET http://localhost:{PORT}/analyze?date=2026-03-07")
    print(f"  GET http://localhost:{PORT}/status")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
