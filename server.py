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
    GET /stats                     # season accuracy + factor breakdown (DB)
    GET /history?team=LAL          # last N predictions for a team (DB)
    GET /misses?conf=0.70          # high-confidence wrong predictions (DB)
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
        data.get("team_stats", {}),
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
        import shutil, json, os as _os
        # Compute season accuracy from verified history files
        _season_stats = None
        try:
            _total_correct, _total = 0, 0
            for _f in _os.listdir(HISTORY_DIR):
                if _f.endswith("_verified.json"):
                    with open(_os.path.join(HISTORY_DIR, _f)) as _fh:
                        _d = json.load(_fh)
                        _total_correct += _d.get("correct", 0)
                        _total += _d.get("total", 0)
            if _total > 0:
                _season_stats = {"correct": _total_correct, "total_predictions": _total, "accuracy": (_total_correct / _total) * 100}
        except Exception:
            pass
        dashboard_path = generate_dashboard(predictions, date_str, _season_stats)
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
        d = {
            "matchup":        f"{p['away_abbr']} @ {p['home_abbr']}",
            "pick":           p["predicted_winner_name"],
            "confidence":     f"{p['confidence']*100:.1f}%",
            "play_type":      p.get("play_type", ""),
            "away_record":    p["away_record"],
            "home_record":    p["home_record"],
        }
        if p.get("efficiency_edge") is not None:
            d["efficiency_edge"] = p["efficiency_edge"]
        return d

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
            pt = f"  [{p['play_type']}]" if p.get("play_type") else ""
            lines.append(f"  ✓ {p['pick']} ({p['confidence']}){pt}  {p['matchup']}")

    if result["leans"]:
        lines.append(f"\nLEANS ({len(result['leans'])}):")
        for p in result["leans"]:
            pt = f"  [{p['play_type']}]" if p.get("play_type") else ""
            lines.append(f"  → {p['pick']} ({p['confidence']}){pt}  {p['matchup']}")

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

            elif path == "/stats":
                import db as _db
                _conn = _db.get_connection()
                summary   = _db.get_model_accuracy_summary(_conn)
                by_tier   = _db.get_accuracy_by_confidence_tier(_conn)
                by_factor = _db.get_cumulative_factor_accuracy(_conn)
                _conn.close()

                factor_out = {}
                for col in ("win_pct", "recent_form", "player_form",
                            "home_away", "injuries", "rest_days", "streak"):
                    acc   = by_factor.get(col)
                    votes = by_factor.get(f"{col}_votes")
                    if acc is not None:
                        factor_out[col] = {
                            "accuracy": f"{acc*100:.1f}%",
                            "votes":    int(votes) if votes else 0,
                        }

                total   = summary.get("total", 0) or 0
                correct = summary.get("correct", 0) or 0
                acc     = summary.get("accuracy")
                self._respond({
                    "season": {
                        "total":    total,
                        "correct":  correct,
                        "accuracy": f"{acc*100:.1f}%" if acc is not None else "n/a",
                    },
                    "by_recommendation": [
                        {
                            "recommendation": r["recommendation"],
                            "total":          r["total"],
                            "correct":        r["correct"],
                            "accuracy":       f"{r['accuracy']*100:.1f}%" if r.get("accuracy") else "n/a",
                            "avg_confidence": f"{r['avg_confidence']*100:.1f}%" if r.get("avg_confidence") else "n/a",
                        }
                        for r in by_tier
                    ],
                    "factor_accuracy": factor_out,
                })

            elif path == "/history":
                team = params.get("team", [None])[0]
                if not team:
                    self._respond({"error": "team param required, e.g. /history?team=LAL"}, 400)
                    return
                limit = int(params.get("limit", [20])[0])
                import db as _db
                _conn = _db.get_connection()
                rows = _db.get_team_prediction_history(_conn, team.upper(), limit)
                _conn.close()
                self._respond({"team": team.upper(), "limit": limit, "games": rows})

            elif path == "/misses":
                min_conf = float(params.get("conf", [0.70])[0])
                import db as _db
                _conn = _db.get_connection()
                rows = _db.get_high_confidence_misses(_conn, min_conf)
                _conn.close()
                self._respond({"min_confidence": min_conf, "misses": rows})

            else:
                self._respond({
                    "endpoints": {
                        "GET /status":                   "health check",
                        "GET /run":                      "today's predictions (JSON)",
                        "GET /run?date=YYYY-MM-DD":      "specific date predictions",
                        "GET /run?fmt=text":             "plain text output (for notifications)",
                        "GET /analyze?date=YYYY-MM-DD":  "post-game analysis",
                        "GET /stats":                    "season accuracy + factor breakdown",
                        "GET /history?team=LAL":         "last N predictions for a team",
                        "GET /misses?conf=0.70":         "high-confidence wrong predictions",
                    }
                }, 404)

        except Exception:
            tb = traceback.format_exc()
            print(tb)
            self._respond({"error": "Internal error", "detail": tb}, 500)


if __name__ == "__main__":
    # Apply learned weights at startup if enough games analyzed.
    # Mirror the exclusion fix from run_predictions.py: zero out config-excluded
    # factors before calling set_weights() so rest_days=0.0 is never overridden.
    try:
        from analyzer import load_factor_ledger
        from prediction_engine import set_weights
        from config import WEIGHTS as _CONFIG_WEIGHTS
        _ledger = load_factor_ledger()
        if _ledger.get("total_games_analyzed", 0) >= 50:
            _suggestions = _ledger.get("weight_suggestions", {})
            if _suggestions:
                _excluded = {f for f, w in _CONFIG_WEIGHTS.items() if w == 0.0}
                if _excluded:
                    _suggestions = dict(_suggestions)
                    for _f in _excluded:
                        _suggestions[_f] = 0.0
                    _total = sum(_suggestions.values())
                    if _total > 0:
                        _suggestions = {f: round(v / _total, 4) for f, v in _suggestions.items()}
                set_weights(_suggestions)
                print(f"  Learned weights active ({_ledger['total_games_analyzed']} analyzed games)")
    except Exception:
        pass

    # Write PID file so deploy/restart scripts can kill us reliably
    pid_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.pid")
    with open(pid_path, "w") as _pf:
        _pf.write(str(os.getpid()))

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"NBA Predictor server running on http://localhost:{PORT}  (PID {os.getpid()})")
    print(f"  GET http://localhost:{PORT}/run")
    print(f"  GET http://localhost:{PORT}/run?fmt=text")
    print(f"  GET http://localhost:{PORT}/analyze?date=2026-03-07")
    print(f"  GET http://localhost:{PORT}/status")
    print(f"  GET http://localhost:{PORT}/stats")
    print(f"  GET http://localhost:{PORT}/history?team=LAL")
    print(f"  GET http://localhost:{PORT}/misses?conf=0.70")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        try:
            os.remove(pid_path)
        except OSError:
            pass
