"""
NBA Prediction Analyzer
========================
Post-game analysis engine. Compares saved predictions to actual results,
explains why the model got each game right or wrong, tracks factor accuracy
over time, and suggests weight adjustments.

Usage (via run_predictions.py):
    python3 run_predictions.py --analyze 2026-03-08
    python3 run_predictions.py --analyze          # defaults to yesterday
"""

import json
import os
from datetime import datetime, timedelta

from config import HISTORY_DIR, PERFORMANCE_DIR, WEIGHTS
from data_manager import fetch_schedule_espn, load_history, save_history, save_data, load_data

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEDGER_PATH = os.path.join(PERFORMANCE_DIR, "factor_accuracy.json")
NEUTRAL_THRESHOLD = 0.02   # margins <= this are treated as neutral (no vote)
MIN_SAMPLE        = 15     # minimum games before a factor's accuracy affects suggestions
MIN_WEIGHT        = 0.03   # floor for any suggested weight
MAX_SHIFT         = 0.05   # maximum weight change per analysis run
FACTOR_NAMES      = list(WEIGHTS.keys())


# ---------------------------------------------------------------------------
# Section 1: Fetch and match actual results
# ---------------------------------------------------------------------------

def load_actual_results(date_str):
    """
    Fetch (or load cached) actual game results for date_str.
    Returns dict keyed by 'HOME_AWAY' abbreviation pair for O(1) lookup.
    Only includes STATUS_FINAL games.
    """
    cache_key = f"results_{date_str}.json"
    raw = load_data(cache_key)

    if not raw:
        raw = fetch_schedule_espn(date_str)
        if raw:
            save_data(cache_key, raw)

    if not raw:
        return {}

    results = {}
    for game in raw:
        h = game.get("home", {})
        a = game.get("away", {})
        status = game.get("status", "")
        key = f"{h.get('abbr', '')}_{a.get('abbr', '')}"
        results[key] = {
            "home_abbr":  h.get("abbr", ""),
            "away_abbr":  a.get("abbr", ""),
            "home_score": h.get("score", 0),
            "away_score": a.get("score", 0),
            "status":     status,
            "final":      status == "STATUS_FINAL",
        }
    return results


# ---------------------------------------------------------------------------
# Section 2: Per-game factor analysis
# ---------------------------------------------------------------------------

def _factor_vote(factor_dict, home_abbr, away_abbr):
    """
    Given a factor's {"home": float, "away": float}, determine which team
    it voted for and whether the vote was decisive enough to count.

    Returns:
        {
            "voted_for": abbr or None,
            "correct":   True/False/None (None = neutral, excluded from accuracy),
            "margin":    float,          (abs difference)
            "home_pct":  float,
            "away_pct":  float,
        }
    """
    h = factor_dict.get("home", 0.5)
    a = factor_dict.get("away", 0.5)
    margin = abs(h - a)

    return {
        "voted_for": home_abbr if h > a else away_abbr if a > h else None,
        "correct":   None,   # filled in by analyze_game once actual winner is known
        "margin":    round(margin, 4),
        "home_pct":  round(h, 4),
        "away_pct":  round(a, 4),
        "neutral":   margin <= NEUTRAL_THRESHOLD,
    }


def _strength_label(margin):
    if margin >= 0.30:  return "strongly favored"
    if margin >= 0.15:  return "favored"
    if margin >= 0.05:  return "slightly favored"
    return "marginally favored"


def _build_explanation(pred, factor_votes, actual_winner, home_score, away_score):
    """
    Build a plain-English paragraph explaining the model's decision.
    """
    home_abbr   = pred["home_abbr"]
    away_abbr   = pred["away_abbr"]
    home_name   = pred["home_team"]
    away_name   = pred["away_team"]
    pred_winner = pred["predicted_winner"]
    correct     = pred_winner == actual_winner

    actual_name = home_name if actual_winner == home_abbr else away_name
    pred_name   = home_name if pred_winner == home_abbr else away_name

    lines = []

    # Opening sentence
    score_str = f"{int(away_score)}-{int(home_score)}" if away_score and home_score else "?"
    if correct:
        lines.append(
            f"Correct. The model picked {pred_name} and they won "
            f"({away_abbr} {score_str} {home_abbr})."
        )
    else:
        lines.append(
            f"Incorrect. The model picked {pred_name} but {actual_name} won "
            f"({away_abbr} {score_str} {home_abbr})."
        )

    # Factor breakdown
    supporting     = []   # factors that voted for predicted winner
    contradicting  = []   # factors that voted against predicted winner
    neutral_names  = []

    for fname, fvote in factor_votes.items():
        if fvote["neutral"] or fvote["voted_for"] is None:
            neutral_names.append(fname.replace("_", " "))
            continue
        label = _strength_label(fvote["margin"])
        team  = home_name if fvote["voted_for"] == home_abbr else away_name
        if fvote["voted_for"] == pred_winner:
            supporting.append(f"{fname.replace('_', ' ')} {label} {team}")
        else:
            contradicting.append(f"{fname.replace('_', ' ')} {label} {team}")

    if supporting:
        lines.append("Factors supporting the pick: " + "; ".join(supporting) + ".")
    if contradicting:
        lines.append("Factors pointing the other way: " + "; ".join(contradicting) + ".")
    if neutral_names:
        lines.append("Neutral (no signal): " + ", ".join(neutral_names) + ".")

    # Diagnosis
    if not correct and contradicting:
        lines.append(
            f"The model overweighted the supporting factors and missed the "
            f"contradicting signals — particularly {contradicting[0]}."
        )
    elif correct and contradicting:
        lines.append(
            f"The model held up despite some signals pointing to {actual_name if actual_winner != pred_winner else away_name}."
        )

    return " ".join(lines)


def analyze_game(pred, actual):
    """
    Produce a full forensic analysis for one game.
    pred:   saved prediction dict (includes 'factors')
    actual: actual result dict from load_actual_results()
    """
    home_abbr    = pred["home_abbr"]
    away_abbr    = pred["away_abbr"]
    home_score   = actual.get("home_score", 0)
    away_score   = actual.get("away_score", 0)
    actual_winner = home_abbr if home_score > away_score else away_abbr
    correct       = pred["predicted_winner"] == actual_winner

    factor_votes = {}
    saved_factors = pred.get("factors", {})
    for fname in FACTOR_NAMES:
        if fname not in saved_factors:
            continue
        vote = _factor_vote(saved_factors[fname], home_abbr, away_abbr)
        # Mark correctness (None if neutral)
        if not vote["neutral"]:
            vote["correct"] = (vote["voted_for"] == actual_winner)
        factor_votes[fname] = vote

    explanation = _build_explanation(pred, factor_votes, actual_winner, home_score, away_score)

    return {
        "matchup":          f"{away_abbr} @ {home_abbr}",
        "home_abbr":        home_abbr,
        "away_abbr":        away_abbr,
        "home_team":        pred.get("home_team", home_abbr),
        "away_team":        pred.get("away_team", away_abbr),
        "predicted_winner": pred["predicted_winner"],
        "actual_winner":    actual_winner,
        "correct":          correct,
        "home_score":       home_score,
        "away_score":       away_score,
        "confidence":       pred.get("confidence", 0),
        "recommendation":   pred.get("recommendation", ""),
        "factor_votes":     factor_votes,
        "explanation":      explanation,
    }


# ---------------------------------------------------------------------------
# Section 3: Date-level aggregation
# ---------------------------------------------------------------------------

def aggregate_date_factors(game_analyses):
    """
    For each factor, count non-neutral correct/total votes across all games.
    Returns per-date factor accuracy dict.
    """
    agg = {f: {"correct": 0, "total": 0} for f in FACTOR_NAMES}
    for ga in game_analyses:
        for fname, fvote in ga["factor_votes"].items():
            if fvote.get("neutral") or fvote.get("correct") is None:
                continue
            agg[fname]["total"] += 1
            if fvote["correct"]:
                agg[fname]["correct"] += 1

    result = {}
    for fname, counts in agg.items():
        t = counts["total"]
        c = counts["correct"]
        result[fname] = {
            "correct":  c,
            "total":    t,
            "accuracy": round(c / t, 4) if t > 0 else None,
        }
    return result


# ---------------------------------------------------------------------------
# Section 4: Persistent factor accuracy ledger
# ---------------------------------------------------------------------------

def load_factor_ledger():
    if os.path.exists(LEDGER_PATH):
        with open(LEDGER_PATH) as f:
            return json.load(f)
    # Initialize blank ledger
    return {
        "last_updated":          None,
        "total_games_analyzed":  0,
        "total_correct":         0,
        "overall_accuracy":      None,
        "factors":               {f: {"correct_votes": 0, "total_votes": 0,
                                       "accuracy": None, "current_weight": WEIGHTS[f],
                                       "suggested_weight": WEIGHTS[f]}
                                   for f in FACTOR_NAMES},
        "dates_analyzed":        [],
        "weight_suggestions":    dict(WEIGHTS),
    }


def save_factor_ledger(ledger):
    os.makedirs(PERFORMANCE_DIR, exist_ok=True)
    tmp = LEDGER_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(ledger, f, indent=2)
    os.replace(tmp, LEDGER_PATH)


def merge_into_ledger(ledger, date_str, date_factor_acc, date_summary):
    """
    Merge one date's results into the persistent ledger.
    Safe to re-run — skips if date already recorded.
    """
    if date_str in ledger.get("dates_analyzed", []):
        return ledger  # already counted

    ledger["dates_analyzed"].append(date_str)
    ledger["last_updated"]         = date_str
    ledger["total_games_analyzed"] += date_summary["total"]
    ledger["total_correct"]        += date_summary["correct"]

    total = ledger["total_games_analyzed"]
    ledger["overall_accuracy"] = round(ledger["total_correct"] / total, 4) if total > 0 else None

    for fname, counts in date_factor_acc.items():
        if fname not in ledger["factors"]:
            continue
        ledger["factors"][fname]["correct_votes"] += counts["correct"]
        ledger["factors"][fname]["total_votes"]   += counts["total"]
        tv = ledger["factors"][fname]["total_votes"]
        cv = ledger["factors"][fname]["correct_votes"]
        ledger["factors"][fname]["accuracy"] = round(cv / tv, 4) if tv > 0 else None
        ledger["factors"][fname]["current_weight"] = WEIGHTS.get(fname, 0)

    # Recompute weight suggestions with updated data
    suggestions = suggest_weights(ledger["factors"])
    ledger["weight_suggestions"] = suggestions
    for fname in FACTOR_NAMES:
        if fname in ledger["factors"]:
            ledger["factors"][fname]["suggested_weight"] = suggestions.get(fname, WEIGHTS.get(fname))

    return ledger


# ---------------------------------------------------------------------------
# Section 5: Weight suggestion algorithm
# ---------------------------------------------------------------------------

def suggest_weights(factor_data):
    """
    Suggest new weights based on factor accuracy vs current weights.
    - Factors below MIN_SAMPLE games keep their current weight unchanged.
    - Uses performance-weighted scaling: raw[f] = accuracy * current_weight
    - Applies damping (MAX_SHIFT cap) and a minimum weight floor (MIN_WEIGHT).
    """
    current = {f: WEIGHTS.get(f, 0) for f in FACTOR_NAMES}
    raw = {}

    for fname in FACTOR_NAMES:
        fd = factor_data.get(fname, {})
        total  = fd.get("total_votes", 0)
        acc    = fd.get("accuracy")

        if acc is None or total < MIN_SAMPLE:
            raw[fname] = current[fname]   # not enough data — hold current
        else:
            raw[fname] = acc * current[fname]

    # Normalize raw weights to sum to 1.0
    total_raw = sum(raw.values())
    if total_raw == 0:
        return dict(current)
    normalized = {f: raw[f] / total_raw for f in FACTOR_NAMES}

    # Apply damping: cap change at MAX_SHIFT
    capped = {}
    for fname in FACTOR_NAMES:
        delta = normalized[fname] - current[fname]
        if abs(delta) > MAX_SHIFT:
            capped[fname] = current[fname] + MAX_SHIFT * (1 if delta > 0 else -1)
        else:
            capped[fname] = normalized[fname]

    # Apply minimum weight floor
    capped = {f: max(v, MIN_WEIGHT) for f, v in capped.items()}

    # Re-normalize after clamping/flooring
    total_capped = sum(capped.values())
    final = {f: round(v / total_capped, 4) for f, v in capped.items()}

    # Absorb rounding residual into the highest-weight factor
    residual = round(1.0 - sum(final.values()), 4)
    if residual != 0:
        top = max(final, key=final.get)
        final[top] = round(final[top] + residual, 4)

    return final


# ---------------------------------------------------------------------------
# Section 6: Console report printer
# ---------------------------------------------------------------------------

def print_report(date_str, game_analyses, date_summary, ledger):
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
    DIM    = "\033[2m"

    total    = date_summary["total"]
    correct  = date_summary["correct"]
    accuracy = date_summary["accuracy"]

    print()
    print("=" * 60)
    print(f"        POST-GAME ANALYSIS  —  {date_str}")
    print("=" * 60)
    print()
    acc_color = GREEN if accuracy >= 0.65 else YELLOW if accuracy >= 0.50 else RED
    print(f"  {BOLD}Result:{RESET} {acc_color}{correct}/{total} correct ({accuracy*100:.1f}%){RESET}")
    print()

    # Per-game blocks
    print("━" * 60)
    print("  GAME BREAKDOWN")
    print("━" * 60)

    for ga in game_analyses:
        icon = f"{GREEN}✅{RESET}" if ga["correct"] else f"{RED}❌{RESET}"
        score_str = f"{int(ga['away_score'])}-{int(ga['home_score'])}" if ga['home_score'] or ga['away_score'] else "?"
        print(f"\n  {icon} {BOLD}{ga['away_abbr']} @ {ga['home_abbr']}{RESET}  |  Final: {score_str}")
        print(f"     Predicted: {ga['predicted_winner']}  |  Actual: {ga['actual_winner']}  |  Confidence: {ga['confidence']*100:.1f}%")

        # Factor vote table
        print(f"     {DIM}{'Factor':<14} {'Voted for':<8} {'Margin':>7}  {'✓/✗'}{RESET}")
        for fname in FACTOR_NAMES:
            if fname not in ga["factor_votes"]:
                continue
            fv = ga["factor_votes"][fname]
            if fv.get("neutral"):
                vote_str   = "neutral"
                margin_str = "—"
                check      = DIM + "–" + RESET
            else:
                vote_str   = fv.get("voted_for", "?")
                margin_str = f"{fv['margin']*100:.1f}%"
                if fv.get("correct"):
                    check = GREEN + "✓" + RESET
                elif fv.get("correct") is False:
                    check = RED + "✗" + RESET
                else:
                    check = "?"
            print(f"     {fname:<14} {vote_str:<8} {margin_str:>7}  {check}")

        print(f"\n     {BLUE}Analysis:{RESET} {ga['explanation']}")
        print(f"  {'─' * 56}")

    # Factor accuracy table (cross-date)
    print()
    print("━" * 60)
    print("  FACTOR ACCURACY  (all-time)")
    print("━" * 60)
    print()
    print(f"  {'Factor':<16} {'Accuracy':>8}  {'Votes':>6}  {'Curr Wt':>8}  {'Sugg Wt':>8}  {'Change':>8}")
    print(f"  {'-'*16} {'-'*8}  {'-'*6}  {'-'*8}  {'-'*8}  {'-'*8}")

    suggestions = ledger.get("weight_suggestions", {})
    for fname in FACTOR_NAMES:
        fd  = ledger["factors"].get(fname, {})
        acc = fd.get("accuracy")
        tv  = fd.get("total_votes", 0)
        cw  = WEIGHTS.get(fname, 0)
        sw  = suggestions.get(fname, cw)
        delta = sw - cw

        acc_str   = f"{acc*100:.1f}%" if acc is not None else "n/a"
        delta_str = f"+{delta*100:.1f}%" if delta > 0.001 else f"{delta*100:.1f}%" if delta < -0.001 else "  —"

        acc_color = ""
        if acc is not None:
            acc_color = GREEN if acc >= 0.65 else YELLOW if acc >= 0.50 else RED
        delta_color = GREEN if delta > 0.005 else RED if delta < -0.005 else DIM

        print(f"  {fname:<16} {acc_color}{acc_str:>8}{RESET}  {tv:>6}  {cw*100:>7.1f}%  {sw*100:>7.1f}%  {delta_color}{delta_str:>8}{RESET}")

    # Weight suggestions block
    print()
    print("━" * 60)
    print("  SUGGESTED WEIGHT ADJUSTMENTS")
    print("━" * 60)
    print()

    any_suggestion = False
    for fname in FACTOR_NAMES:
        fd    = ledger["factors"].get(fname, {})
        tv    = fd.get("total_votes", 0)
        cw    = WEIGHTS.get(fname, 0)
        sw    = suggestions.get(fname, cw)
        delta = sw - cw

        if tv < MIN_SAMPLE:
            print(f"  {fname:<16}  {DIM}Not enough data yet ({tv}/{MIN_SAMPLE} games){RESET}")
            continue

        any_suggestion = True
        if abs(delta) < 0.005:
            print(f"  {fname:<16}  Keep at {cw*100:.1f}%  (performing as expected)")
        elif delta > 0:
            print(f"  {fname:<16}  {GREEN}Increase {cw*100:.1f}% → {sw*100:.1f}%{RESET}  (above-average accuracy)")
        else:
            print(f"  {fname:<16}  {RED}Decrease {cw*100:.1f}% → {sw*100:.1f}%{RESET}  (below-average accuracy)")

    if not any_suggestion:
        print(f"  {DIM}Run analysis on more dates to unlock weight suggestions (need {MIN_SAMPLE}+ games per factor).{RESET}")

    # Season record
    overall_acc   = ledger.get("overall_accuracy")
    total_analyzed = ledger.get("total_games_analyzed", 0)
    total_correct  = ledger.get("total_correct", 0)
    if overall_acc is not None:
        print()
        print("━" * 60)
        oa_color = GREEN if overall_acc >= 0.65 else YELLOW if overall_acc >= 0.50 else RED
        print(f"  {BOLD}Season record:{RESET} {oa_color}{total_correct}/{total_analyzed} ({overall_acc*100:.1f}%){RESET}")

    print()
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# Section 7: Public entry point
# ---------------------------------------------------------------------------

def analyze_date(date_str):
    """
    Full post-game analysis pipeline for date_str.
    Loads saved predictions, fetches actual results, runs analysis,
    updates the persistent ledger, prints the report, and saves output.
    """
    print()
    print("=" * 60)
    print(f"  LOADING ANALYSIS FOR {date_str}")
    print("=" * 60)

    history = load_history(date_str)
    if not history:
        print(f"\n  No predictions found for {date_str}.")
        print("  Run predictions first:  python3 run_predictions.py {date_str}")
        return None

    print(f"  Fetching actual results for {date_str}...")
    actuals = load_actual_results(date_str)
    if not actuals:
        print(f"  Could not fetch results. Games may not be final yet.")
        return None

    game_analyses = []
    skipped = 0
    for pred in history.get("predictions", []):
        key = f"{pred['home_abbr']}_{pred['away_abbr']}"
        if key not in actuals:
            skipped += 1
            continue
        actual = actuals[key]
        if not actual.get("final"):
            skipped += 1
            continue
        game_analyses.append(analyze_game(pred, actual))

    if not game_analyses:
        print(f"  No finalized games found for {date_str}. Try again after games are complete.")
        return None

    if skipped:
        print(f"  Note: {skipped} game(s) not yet final, excluded from analysis.")

    correct = sum(1 for g in game_analyses if g["correct"])
    total   = len(game_analyses)
    date_summary = {
        "correct":  correct,
        "total":    total,
        "accuracy": round(correct / total, 4) if total > 0 else 0,
    }

    date_factor_acc = aggregate_date_factors(game_analyses)

    # Save per-date analysis file
    analysis_output = {
        "date":                      date_str,
        "analyzed_at":               datetime.now().isoformat(),
        "summary":                   date_summary,
        "games":                     game_analyses,
        "factor_accuracy_this_date": date_factor_acc,
    }
    save_history(f"{date_str}_analysis", analysis_output)

    # Update persistent ledger
    ledger = load_factor_ledger()
    ledger = merge_into_ledger(ledger, date_str, date_factor_acc, date_summary)
    save_factor_ledger(ledger)

    # Persist to DB
    try:
        import db as _db
        _conn = _db.get_connection()
        for _ga in game_analyses:
            _db.upsert_game_result(_conn, date_str, _ga)
        _db.upsert_daily_summary(_conn, date_str, date_summary, date_factor_acc)
        _conn.commit()
        _conn.close()
    except Exception as _db_err:
        print(f"  [DB] Analysis write skipped: {_db_err}")

    print_report(date_str, game_analyses, date_summary, ledger)
    print(f"  Analysis saved to history/{date_str}_analysis.json")
    print(f"  Ledger updated at performance/factor_accuracy.json")
    print()

    return analysis_output
