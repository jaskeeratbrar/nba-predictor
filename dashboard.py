"""
NBA Prediction Dashboard Generator
Creates an HTML report with predictions, confidence bars, and factor breakdowns.
"""

import os
from datetime import datetime
from config import REPORTS_DIR


def _confidence_color(confidence):
    """Return a CSS color based on confidence level."""
    if confidence >= 0.70:
        return "#22c55e"  # Green
    elif confidence >= 0.60:
        return "#eab308"  # Yellow
    elif confidence >= 0.55:
        return "#f97316"  # Orange
    else:
        return "#ef4444"  # Red


def _recommendation_badge(rec):
    """Return styled badge HTML."""
    colors = {
        "STRONG PICK": ("#22c55e", "#052e16"),
        "LEAN": ("#eab308", "#422006"),
        "SLIGHT LEAN": ("#f97316", "#431407"),
        "SKIP": ("#ef4444", "#450a0a"),
    }
    bg, text = colors.get(rec, ("#6b7280", "#1f2937"))
    return f'<span style="background:{bg};color:{text};padding:3px 10px;border-radius:12px;font-weight:700;font-size:0.8em;letter-spacing:0.5px">{rec}</span>'


def _factor_bar(home_val, away_val, label):
    """Create a horizontal comparison bar for a factor."""
    h_pct = round(home_val * 100, 1)
    a_pct = round(away_val * 100, 1)
    return f"""
    <div style="margin:4px 0">
        <div style="display:flex;justify-content:space-between;font-size:0.75em;color:#94a3b8;margin-bottom:2px">
            <span>{h_pct}%</span>
            <span style="font-weight:600">{label}</span>
            <span>{a_pct}%</span>
        </div>
        <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;background:#1e293b">
            <div style="width:{h_pct}%;background:linear-gradient(90deg,#3b82f6,#60a5fa)"></div>
            <div style="width:{a_pct}%;background:linear-gradient(90deg,#f97316,#fb923c)"></div>
        </div>
    </div>"""


def generate_game_card(pred):
    """Generate HTML for a single game prediction card."""
    home = pred["home_team"]
    away = pred["away_team"]
    h_abbr = pred["home_abbr"]
    a_abbr = pred["away_abbr"]
    h_rec = pred["home_record"]
    a_rec = pred["away_record"]
    h_prob = pred["home_win_prob"]
    a_prob = pred["away_win_prob"]
    conf = pred["confidence"]
    winner = pred["predicted_winner_name"]
    rec = pred["recommendation"]
    venue = pred.get("venue", "")
    factors = pred.get("factors", {})

    # Build factor bars
    factor_labels = {
        "win_pct": "Win %",
        "recent_form": "Recent Form",
        "home_away": "Home/Away",
        "injuries": "Health",
        "streak": "Streak",
        "rest_days": "Rest",
        "head_to_head": "H2H",
    }
    factor_bars = ""
    for key, label in factor_labels.items():
        if key in factors:
            factor_bars += _factor_bar(factors[key]["home"], factors[key]["away"], label)

    conf_color = _confidence_color(conf)
    badge = _recommendation_badge(rec)
    h_injuries = pred.get("home_injuries", 0)
    a_injuries = pred.get("away_injuries", 0)

    winner_side = "HOME" if pred["predicted_winner"] == h_abbr else "AWAY"

    return f"""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:24px;margin:16px 0;box-shadow:0 4px 12px rgba(0,0,0,0.3)">
        <!-- Header -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <div style="font-size:0.8em;color:#64748b">{venue}</div>
            {badge}
        </div>

        <!-- Teams -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
            <div style="text-align:center;flex:1">
                <div style="font-size:1.4em;font-weight:800;color:{'#60a5fa' if winner_side == 'AWAY' else '#cbd5e1'}">{a_abbr}</div>
                <div style="font-size:0.85em;color:#94a3b8">{away}</div>
                <div style="font-size:0.8em;color:#64748b">{a_rec}</div>
                <div style="font-size:1.6em;font-weight:800;color:{'#60a5fa' if winner_side == 'AWAY' else '#475569'};margin-top:4px">{round(a_prob*100)}%</div>
                {'<div style="font-size:0.7em;color:#f87171">🏥 ' + str(a_injuries) + ' injured</div>' if a_injuries > 0 else ''}
            </div>
            <div style="font-size:1.2em;color:#334155;font-weight:700;padding:0 16px">@</div>
            <div style="text-align:center;flex:1">
                <div style="font-size:1.4em;font-weight:800;color:{'#60a5fa' if winner_side == 'HOME' else '#cbd5e1'}">{h_abbr}</div>
                <div style="font-size:0.85em;color:#94a3b8">{home}</div>
                <div style="font-size:0.8em;color:#64748b">{h_rec}</div>
                <div style="font-size:1.6em;font-weight:800;color:{'#60a5fa' if winner_side == 'HOME' else '#475569'};margin-top:4px">{round(h_prob*100)}%</div>
                {'<div style="font-size:0.7em;color:#f87171">🏥 ' + str(h_injuries) + ' injured</div>' if h_injuries > 0 else ''}
            </div>
        </div>

        <!-- Confidence Bar -->
        <div style="margin-bottom:16px">
            <div style="display:flex;justify-content:space-between;font-size:0.75em;color:#64748b;margin-bottom:4px">
                <span>Model Confidence</span>
                <span style="color:{conf_color};font-weight:700">{round(conf*100, 1)}%</span>
            </div>
            <div style="height:8px;background:#1e293b;border-radius:4px;overflow:hidden">
                <div style="height:100%;width:{conf*100}%;background:{conf_color};border-radius:4px;transition:width 0.5s"></div>
            </div>
        </div>

        <!-- Prediction -->
        <div style="text-align:center;padding:12px;background:#1e293b;border-radius:8px;margin-bottom:12px">
            <span style="color:#94a3b8;font-size:0.85em">Predicted Winner: </span>
            <span style="color:#f0f9ff;font-weight:800;font-size:1.05em">{winner}</span>
        </div>

        <!-- Factor Breakdown -->
        <details style="cursor:pointer">
            <summary style="color:#64748b;font-size:0.8em;font-weight:600;letter-spacing:0.5px;user-select:none">FACTOR BREAKDOWN</summary>
            <div style="margin-top:8px">
                {factor_bars}
            </div>
        </details>
    </div>"""


def generate_dashboard(predictions, date_str, history_stats=None):
    """Generate complete HTML dashboard."""
    total_games = len(predictions)
    strong_picks = sum(1 for p in predictions if p["recommendation"] == "STRONG PICK")
    leans = sum(1 for p in predictions if p["recommendation"] in ("LEAN", "SLIGHT LEAN"))
    skips = sum(1 for p in predictions if p["recommendation"] == "SKIP")

    # History stats
    history_html = ""
    if history_stats:
        acc = history_stats.get("accuracy", 0)
        total_hist = history_stats.get("total_predictions", 0)
        correct = history_stats.get("correct", 0)
        history_html = f"""
        <div style="display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap">
            <div style="flex:1;min-width:140px;background:#1e293b;border-radius:8px;padding:16px;text-align:center">
                <div style="font-size:2em;font-weight:800;color:{'#22c55e' if acc >= 60 else '#eab308'}">{acc:.1f}%</div>
                <div style="font-size:0.75em;color:#64748b;margin-top:4px">Season Accuracy</div>
            </div>
            <div style="flex:1;min-width:140px;background:#1e293b;border-radius:8px;padding:16px;text-align:center">
                <div style="font-size:2em;font-weight:800;color:#60a5fa">{correct}/{total_hist}</div>
                <div style="font-size:0.75em;color:#64748b;margin-top:4px">Correct Picks</div>
            </div>
        </div>"""

    game_cards = "\n".join(generate_game_card(p) for p in predictions)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NBA Predictions - {date_str}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #020617;
            color: #e2e8f0;
            min-height: 100vh;
            padding: 24px;
        }}
        .container {{ max-width: 720px; margin: 0 auto; }}
        details > summary {{ list-style: none; }}
        details > summary::-webkit-details-marker {{ display: none; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div style="text-align:center;margin-bottom:32px">
            <h1 style="font-size:2.2em;font-weight:900;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px">
                NBA PREDICTOR
            </h1>
            <div style="color:#64748b;font-size:0.9em">Predictions for {date_str}</div>
            <div style="color:#475569;font-size:0.75em;margin-top:2px">Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>

        <!-- Summary Stats -->
        <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap">
            <div style="flex:1;min-width:100px;background:#1e293b;border-radius:8px;padding:14px;text-align:center">
                <div style="font-size:1.8em;font-weight:800;color:#60a5fa">{total_games}</div>
                <div style="font-size:0.7em;color:#64748b;margin-top:2px">Games</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1e293b;border-radius:8px;padding:14px;text-align:center">
                <div style="font-size:1.8em;font-weight:800;color:#22c55e">{strong_picks}</div>
                <div style="font-size:0.7em;color:#64748b;margin-top:2px">Strong Picks</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1e293b;border-radius:8px;padding:14px;text-align:center">
                <div style="font-size:1.8em;font-weight:800;color:#eab308">{leans}</div>
                <div style="font-size:0.7em;color:#64748b;margin-top:2px">Leans</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1e293b;border-radius:8px;padding:14px;text-align:center">
                <div style="font-size:1.8em;font-weight:800;color:#ef4444">{skips}</div>
                <div style="font-size:0.7em;color:#64748b;margin-top:2px">Skips</div>
            </div>
        </div>

        {history_html}

        <!-- Game Predictions -->
        {game_cards}

    </div>
</body>
</html>"""

    # Save
    filepath = os.path.join(REPORTS_DIR, f"predictions_{date_str}.html")
    with open(filepath, "w") as f:
        f.write(html)

    return filepath
