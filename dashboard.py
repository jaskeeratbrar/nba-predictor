"""
NBA Prediction Dashboard Generator
Creates an HTML report with predictions, confidence bars, and factor breakdowns.
Automatically loads the previous day's analysis and renders it as a Results section
above today's predictions so every dashboard push includes yesterday's outcomes.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from config import REPORTS_DIR, HISTORY_DIR

_ET = timezone(timedelta(hours=-4))  # EDT (Mar–Nov); update to -5 in Nov for EST


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


def _play_type_badge(play_type):
    """Return styled badge HTML for play type classification."""
    styles = {
        "LOCK":           ("#22c55e", "#052e16"),
        "VALUE PLAY":     ("#3b82f6", "#172554"),
        "RISKY — WORTH IT": ("#f59e0b", "#451a03"),
        "RISKY — AVOID":  ("#ef4444", "#450a0a"),
        "SKIP":           ("#475569", "#0f172a"),
    }
    bg, text = styles.get(play_type, ("#6b7280", "#1f2937"))
    return f'<span style="background:{bg};color:{text};padding:3px 10px;border-radius:12px;font-weight:700;font-size:0.75em;letter-spacing:0.5px">{play_type}</span>'


def _risk_edge_bars(risk_score, edge_score, risk_components=None, edge_components=None):
    """Two thin bars showing risk level and edge strength, with subcomponent breakdown."""
    risk_pct = round(risk_score * 100, 1)
    edge_pct = round(edge_score * 100, 1)
    risk_color = "#ef4444" if risk_score >= 0.55 else "#f59e0b" if risk_score >= 0.30 else "#22c55e"
    edge_color = "#22c55e" if edge_score >= 0.40 else "#3b82f6" if edge_score >= 0.20 else "#64748b"

    # Risk subcomponent label: factor disagreement vs injury uncertainty
    risk_sub = ""
    if risk_components:
        fd  = risk_components.get("factor_disagreement", 0)
        iu  = risk_components.get("injury_uncertainty", 0)
        total = fd + iu
        if total > 0:
            fd_pct = round(fd / total * 100)
            iu_pct = 100 - fd_pct
            risk_sub = (
                f'<div style="font-size:0.63em;color:#334155;margin-top:2px;margin-bottom:6px">'
                f'factor split {fd_pct}% · injury uncertainty {iu_pct}%</div>'
            )

    # Edge subcomponent label: health / momentum / rest
    edge_sub = ""
    if edge_components:
        he  = edge_components.get("health_edge", 0)
        me  = edge_components.get("momentum_edge", 0)
        re_ = edge_components.get("rest_edge", 0)
        total = he + me + re_
        if total > 0:
            he_pct = round(he / total * 100)
            me_pct = round(me / total * 100)
            re_pct = 100 - he_pct - me_pct
            edge_sub = (
                f'<div style="font-size:0.63em;color:#334155;margin-top:2px">'
                f'health {he_pct}% · momentum {me_pct}% · rest {re_pct}%</div>'
            )

    return f"""
    <div style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;font-size:0.72em;color:#64748b;margin-bottom:3px">
            <span>Risk</span><span style="color:{risk_color};font-weight:700">{risk_pct}%</span>
        </div>
        <div style="height:5px;background:#1e293b;border-radius:3px;overflow:hidden">
            <div style="height:100%;width:{risk_pct}%;background:{risk_color};border-radius:3px"></div>
        </div>
        {risk_sub}
        <div style="display:flex;justify-content:space-between;font-size:0.72em;color:#64748b;margin-bottom:3px">
            <span>Edge</span><span style="color:{edge_color};font-weight:700">{edge_pct}%</span>
        </div>
        <div style="height:5px;background:#1e293b;border-radius:3px;overflow:hidden">
            <div style="height:100%;width:{edge_pct}%;background:{edge_color};border-radius:3px"></div>
        </div>
        {edge_sub}
    </div>"""


def _injury_detail_html(injury_detail, total_count):
    """
    Render a compact injury list showing star/starter players by name.
    Falls back to a plain count for bench/role players.
    """
    if not injury_detail and total_count == 0:
        return ""

    named = [p for p in injury_detail if p.get("impact") in ("star", "starter")]
    others = total_count - len(named)

    lines = []
    for p in named:
        icon   = "⭐" if p.get("impact") == "star" else "🏥"
        status = p.get("status", "")
        pts    = p.get("pts_avg", 0)
        pts_str = f" {pts}pts" if pts else ""
        lines.append(
            f'<div style="font-size:0.68em;color:#f87171;white-space:nowrap">'
            f'{icon} {p["name"]} ({status}){pts_str}</div>'
        )
    if others > 0 and others != total_count:
        lines.append(
            f'<div style="font-size:0.65em;color:#475569">+{others} more</div>'
        )
    elif not named and total_count > 0:
        lines.append(
            f'<div style="font-size:0.68em;color:#f87171">🏥 {total_count} injured</div>'
        )

    return "".join(lines)


def _factor_bar(home_val, away_val, label, home_abbr="HOME", away_abbr="AWAY"):
    """Create a horizontal comparison bar for a factor."""
    h_pct = round(home_val * 100, 1)
    a_pct = round(away_val * 100, 1)
    return f"""
    <div style="margin:4px 0">
        <div style="display:flex;justify-content:space-between;font-size:0.75em;color:#94a3b8;margin-bottom:2px">
            <span style="color:#60a5fa;font-weight:600">{home_abbr} {h_pct}%</span>
            <span style="font-weight:600;color:#64748b">{label}</span>
            <span style="color:#fb923c;font-weight:600">{a_pct}% {away_abbr}</span>
        </div>
        <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;background:#1e293b">
            <div style="width:{h_pct}%;background:linear-gradient(90deg,#3b82f6,#60a5fa)"></div>
            <div style="width:{a_pct}%;background:linear-gradient(90deg,#f97316,#fb923c)"></div>
        </div>
    </div>"""


def load_latest_analysis(for_date_str):
    """
    Load the analysis file for the day before for_date_str.
    Returns the analysis dict or None if not available.
    """
    try:
        prev = (datetime.strptime(for_date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        path = os.path.join(HISTORY_DIR, f"{prev}_analysis.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return None


def generate_results_section(analysis_data):
    """Render yesterday's game results as an HTML section."""
    if not analysis_data:
        return ""

    date_str = analysis_data.get("date", "")
    summary  = analysis_data.get("summary", {})
    games    = analysis_data.get("games", [])

    correct  = summary.get("correct", 0)
    total    = summary.get("total", 0)
    accuracy = summary.get("accuracy", 0)

    try:
        date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
    except Exception:
        date_display = date_str

    acc_color = "#22c55e" if accuracy >= 0.65 else "#eab308" if accuracy >= 0.50 else "#ef4444"

    game_cards = ""
    for g in games:
        icon        = "✅" if g["correct"] else "❌"
        away        = g["away_abbr"]
        home        = g["home_abbr"]
        away_score  = int(g.get("away_score", 0))
        home_score  = int(g.get("home_score", 0))
        score       = f"{away_score}-{home_score}" if away_score or home_score else "?"
        pred        = g["predicted_winner"]
        actual      = g["actual_winner"]
        conf        = g.get("confidence", 0)
        rec         = g.get("recommendation", "")
        explanation = g.get("explanation", "")

        # Factor vote rows (non-neutral only)
        factor_rows = ""
        for fname, fv in g.get("factor_votes", {}).items():
            if fv.get("neutral"):
                continue
            voted  = fv.get("voted_for", "?")
            margin = f"{fv['margin']*100:.0f}%"
            chk_color = "#22c55e" if fv.get("correct") else "#ef4444"
            chk = "✓" if fv.get("correct") else "✗"
            factor_rows += (
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:0.72em;color:#94a3b8;padding:2px 0">'
                f'<span style="min-width:90px;color:#64748b">{fname.replace("_"," ")}</span>'
                f'<span style="color:#cbd5e1;min-width:40px">{voted}</span>'
                f'<span style="color:#475569;min-width:32px;text-align:right">{margin}</span>'
                f'<span style="color:{chk_color};font-weight:700;margin-left:8px">{chk}</span>'
                f'</div>'
            )

        factors_html = ""
        if factor_rows:
            factors_html = (
                f'<details style="margin-top:6px;cursor:pointer">'
                f'<summary style="font-size:0.72em;color:#334155;user-select:none;letter-spacing:0.5px">FACTOR VOTES</summary>'
                f'<div style="margin-top:4px">{factor_rows}</div>'
                f'</details>'
            )

        expl_html = ""
        if explanation:
            expl_html = (
                f'<div style="font-size:0.75em;color:#64748b;margin-top:6px;line-height:1.5">'
                f'{explanation}</div>'
            )

        card_bg     = "#071220" if g["correct"] else "#150808"
        border_col  = "#14311e" if g["correct"] else "#351010"
        actual_col  = "#22c55e" if g["correct"] else "#ef4444"

        game_cards += f"""
        <div style="background:{card_bg};border:1px solid {border_col};border-radius:8px;padding:12px;margin:8px 0">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
                <span style="font-size:1em;font-weight:700">{icon} {away} @ {home}</span>
                <span style="font-size:0.73em;color:#475569">{rec} · {conf*100:.0f}%</span>
            </div>
            <div style="font-size:0.82em;color:#94a3b8;margin-bottom:2px">
                Final: <span style="color:#e2e8f0;font-weight:600">{score}</span>
                &nbsp;·&nbsp; Picked: <span style="color:#60a5fa;font-weight:600">{pred}</span>
                &nbsp;·&nbsp; Won: <span style="color:{actual_col};font-weight:600">{actual}</span>
            </div>
            {factors_html}
            {expl_html}
        </div>"""

    return f"""
    <div style="margin-bottom:28px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
            <h2 style="font-size:0.85em;font-weight:700;color:#475569;letter-spacing:1px;text-transform:uppercase">
                Results — {date_display}
            </h2>
            <span style="font-size:1.2em;font-weight:800;color:{acc_color}">{correct}/{total}
                <span style="font-size:0.65em;color:#475569;font-weight:500">correct</span>
            </span>
        </div>
        {game_cards}
    </div>
    <div style="border-top:1px solid #1e293b;margin:0 0 28px 0"></div>"""


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

    # Build factor bars (player_form was previously missing — head_to_head key was wrong)
    factor_labels = {
        "win_pct":     "Win %",
        "recent_form": "Recent Form",
        "player_form": "Player Form",
        "home_away":   "Home/Away",
        "injuries":    "Health",
        "net_rating":  "Net Rating",
        "defense":     "Defense",
        "streak":      "Streak",
        "rest_days":   "Rest",
    }
    factor_bars = ""
    for key, label in factor_labels.items():
        if key in factors:
            factor_bars += _factor_bar(factors[key]["home"], factors[key]["away"], label, h_abbr, a_abbr)

    conf_color = _confidence_color(conf)
    badge = _recommendation_badge(rec)
    h_injuries = pred.get("home_injuries", 0)
    a_injuries = pred.get("away_injuries", 0)
    play_type   = pred.get("play_type", "")
    risk_score  = pred.get("risk_score", 0.0)
    edge_score  = pred.get("edge_score", 0.0)
    explanation = pred.get("play_explanation", "")

    eff_edge = pred.get("efficiency_edge")
    winner_side = "HOME" if pred["predicted_winner"] == h_abbr else "AWAY"

    play_badge = _play_type_badge(play_type) if play_type else ""
    risk_edge_html = (
        _risk_edge_bars(
            risk_score, edge_score,
            pred.get("risk_components"), pred.get("edge_components"),
        )
        if play_type else ""
    )
    explanation_html = (
        f'<div style="font-size:0.75em;color:#64748b;font-style:italic;margin-bottom:12px">{explanation}</div>'
        if explanation else ""
    )

    # Game time in ET
    game_time_str = ""
    raw_game_time = pred.get("game_time", "")
    if raw_game_time:
        try:
            gt = datetime.fromisoformat(raw_game_time.replace("Z", "+00:00")).astimezone(_ET)
            game_time_str = gt.strftime("%-I:%M %p ET")
        except Exception:
            pass

    # Injury detail: named players for star/starter, count for rest
    h_inj_html = _injury_detail_html(pred.get("home_injury_detail", []), h_injuries)
    a_inj_html = _injury_detail_html(pred.get("away_injury_detail", []), a_injuries)

    # Efficiency edge indicator (scoring margin delta, informational only)
    eff_html = ""
    if eff_edge is not None:
        eff_abs  = abs(eff_edge)
        eff_team = h_abbr if eff_edge > 0 else a_abbr
        eff_color = "#22c55e" if eff_abs >= 0.3 else "#64748b"
        eff_label = f"{eff_team} +{eff_abs:.2f}" if eff_abs >= 0.05 else "Even"
        eff_html = (
            f'<div style="text-align:center;font-size:0.72em;color:{eff_color};margin-bottom:8px">'
            f'Efficiency Edge: <span style="font-weight:700">{eff_label}</span>'
            f'</div>'
        )

    venue_time = venue
    if game_time_str:
        venue_time = f"{venue} · {game_time_str}" if venue else game_time_str

    return f"""
    <div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:24px;margin:16px 0;box-shadow:0 4px 12px rgba(0,0,0,0.3)">
        <!-- Header -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
            <div style="font-size:0.8em;color:#64748b">{venue_time}</div>
            <div style="display:flex;gap:8px;align-items:center">
                {play_badge}
                {badge}
            </div>
        </div>

        <!-- Teams -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
            <div style="text-align:center;flex:1">
                <div style="font-size:1.4em;font-weight:800;color:{'#60a5fa' if winner_side == 'AWAY' else '#cbd5e1'}">{a_abbr}</div>
                <div style="font-size:0.85em;color:#94a3b8">{away}</div>
                <div style="font-size:0.8em;color:#64748b">{a_rec}</div>
                <div style="font-size:1.6em;font-weight:800;color:{'#60a5fa' if winner_side == 'AWAY' else '#475569'};margin-top:4px">{round(a_prob*100)}%</div>
                {a_inj_html}
            </div>
            <div style="font-size:1.2em;color:#334155;font-weight:700;padding:0 16px">@</div>
            <div style="text-align:center;flex:1">
                <div style="font-size:1.4em;font-weight:800;color:{'#60a5fa' if winner_side == 'HOME' else '#cbd5e1'}">{h_abbr}</div>
                <div style="font-size:0.85em;color:#94a3b8">{home}</div>
                <div style="font-size:0.8em;color:#64748b">{h_rec}</div>
                <div style="font-size:1.6em;font-weight:800;color:{'#60a5fa' if winner_side == 'HOME' else '#475569'};margin-top:4px">{round(h_prob*100)}%</div>
                {h_inj_html}
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

        <!-- Risk / Edge Bars -->
        {risk_edge_html}

        <!-- Prediction -->
        <div style="text-align:center;padding:12px;background:#1e293b;border-radius:8px;margin-bottom:12px">
            <span style="color:#94a3b8;font-size:0.85em">Predicted Winner: </span>
            <span style="color:#f0f9ff;font-weight:800;font-size:1.05em">{winner}</span>
        </div>

        {eff_html}

        <!-- Play Explanation -->
        {explanation_html}

        <!-- Factor Breakdown -->
        <details style="cursor:pointer">
            <summary style="color:#64748b;font-size:0.8em;font-weight:600;letter-spacing:0.5px;user-select:none">FACTOR BREAKDOWN</summary>
            <div style="margin-top:8px">
                {factor_bars}
            </div>
        </details>
    </div>"""


def generate_dashboard(predictions, date_str, history_stats=None):
    """
    Generate complete HTML dashboard.
    Automatically loads yesterday's analysis (if available) and renders it
    as a Results section above today's predictions.
    """
    total_games  = len(predictions)
    strong_picks = sum(1 for p in predictions if p["recommendation"] == "STRONG PICK")
    leans        = sum(1 for p in predictions if p["recommendation"] in ("LEAN", "SLIGHT LEAN"))
    skips        = sum(1 for p in predictions if p["recommendation"] == "SKIP")

    locks         = sum(1 for p in predictions if p.get("play_type") == "LOCK")
    value_plays   = sum(1 for p in predictions if p.get("play_type") == "VALUE PLAY")
    risky_worth   = sum(1 for p in predictions if p.get("play_type") == "RISKY — WORTH IT")
    risky_avoid   = sum(1 for p in predictions if p.get("play_type") == "RISKY — AVOID")

    # History stats
    history_html = ""
    if history_stats:
        acc       = history_stats.get("accuracy", 0)
        total_hist = history_stats.get("total_predictions", 0)
        correct   = history_stats.get("correct", 0)
        acc_color = "#22c55e" if acc >= 70 else "#eab308" if acc >= 60 else "#ef4444"

        # Tier accuracy pills
        def _tier_pill(label, c, t, color):
            if t == 0:
                return ""
            pct = c / t * 100
            return (
                f'<div style="text-align:center;padding:6px 10px;background:#0f172a;'
                f'border-radius:6px;min-width:72px">'
                f'<div style="font-size:1em;font-weight:800;color:{color}">{pct:.0f}%</div>'
                f'<div style="font-size:0.62em;color:#475569;margin-top:1px">{label} ({c}/{t})</div>'
                f'</div>'
            )

        sp_pill = _tier_pill(
            "STRONG", history_stats.get("strong_pick_correct", 0),
            history_stats.get("strong_pick_total", 0), "#22c55e"
        )
        ln_pill = _tier_pill(
            "LEAN", history_stats.get("lean_correct", 0),
            history_stats.get("lean_total", 0), "#eab308"
        )
        sk_pill = _tier_pill(
            "SKIP", history_stats.get("skip_correct", 0),
            history_stats.get("skip_total", 0), "#64748b"
        )

        history_html = f"""
        <div style="background:#1e293b;border-radius:8px;padding:16px;margin-bottom:24px">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
                <div>
                    <span style="font-size:1.9em;font-weight:800;color:{acc_color}">{acc:.1f}%</span>
                    <span style="font-size:0.75em;color:#64748b;margin-left:6px">season accuracy</span>
                </div>
                <div style="font-size:0.85em;color:#60a5fa;font-weight:700">{correct}/{total_hist}</div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
                {sp_pill}{ln_pill}{sk_pill}
            </div>
        </div>"""

    # Auto-load yesterday's analysis for the results section
    yesterday_analysis = load_latest_analysis(date_str)
    results_html = generate_results_section(yesterday_analysis)

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
        <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap">
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
        <!-- Play Type Breakdown -->
        <div style="display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap">
            <div style="flex:1;min-width:100px;background:#0a1f0f;border:1px solid #14311e;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:1.5em;font-weight:800;color:#22c55e">{locks}</div>
                <div style="font-size:0.65em;color:#64748b;margin-top:2px">Locks</div>
            </div>
            <div style="flex:1;min-width:100px;background:#0a0f1f;border:1px solid #172554;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:1.5em;font-weight:800;color:#3b82f6">{value_plays}</div>
                <div style="font-size:0.65em;color:#64748b;margin-top:2px">Value Plays</div>
            </div>
            <div style="flex:1;min-width:100px;background:#1a1000;border:1px solid #451a03;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:1.5em;font-weight:800;color:#f59e0b">{risky_worth}</div>
                <div style="font-size:0.65em;color:#64748b;margin-top:2px">Risky Worth It</div>
            </div>
            <div style="flex:1;min-width:100px;background:#150808;border:1px solid #450a0a;border-radius:8px;padding:12px;text-align:center">
                <div style="font-size:1.5em;font-weight:800;color:#ef4444">{risky_avoid}</div>
                <div style="font-size:0.65em;color:#64748b;margin-top:2px">Risky Avoid</div>
            </div>
        </div>

        {history_html}

        <!-- Yesterday's Results -->
        {results_html}

        <!-- Today's Predictions -->
        <div style="font-size:0.85em;font-weight:700;color:#475569;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">
            Predictions — {date_str}
        </div>
        {game_cards}

    </div>
</body>
</html>"""

    # Save
    filepath = os.path.join(REPORTS_DIR, f"predictions_{date_str}.html")
    with open(filepath, "w") as f:
        f.write(html)

    return filepath
