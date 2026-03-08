#!/usr/bin/env python3
"""
NBA Daily Prediction Runner
============================
Run this script daily to generate predictions for today's or tomorrow's NBA games.

Usage:
    python run_predictions.py                  # Predict today's games
    python run_predictions.py tomorrow         # Predict tomorrow's games
    python run_predictions.py 2026-03-15       # Predict a specific date
    python run_predictions.py --verify 2026-03-08  # Verify past predictions
"""

import sys
import os
import json
from datetime import datetime, timedelta

# Ensure we're running from the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import HISTORY_DIR, REPORTS_DIR
from data_manager import refresh_all_data, save_history, load_history, fetch_schedule_espn, save_data, load_data
from prediction_engine import predict_all_games
from dashboard import generate_dashboard


def print_header():
    print()
    print("=" * 60)
    print("        NBA PREDICTOR  -  Daily Prediction Engine")
    print("=" * 60)
    print()


def print_prediction(pred, idx):
    """Pretty-print a single prediction to console."""
    rec = pred["recommendation"]
    conf = pred["confidence"]
    winner = pred["predicted_winner_name"]
    w_abbr = pred["predicted_winner"]

    # Color codes for terminal
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    if rec == "STRONG PICK":
        color = GREEN
        icon = "✅"
    elif rec in ("LEAN", "SLIGHT LEAN"):
        color = YELLOW
        icon = "⚠️"
    else:
        color = RED
        icon = "🚫"

    print(f"\n  {BOLD}Game {idx}{RESET}")
    print(f"  {'─' * 50}")
    print(f"  {pred['away_team']} ({pred['away_record']})")
    print(f"     @  {pred['home_team']} ({pred['home_record']})")
    if pred.get("venue"):
        print(f"  📍 {pred['venue']}")

    print()
    print(f"  {BLUE}Win Probability:{RESET}")
    h_bar = "█" * int(pred["home_win_prob"] * 30)
    a_bar = "█" * int(pred["away_win_prob"] * 30)
    print(f"    {pred['home_abbr']:>4} {h_bar} {pred['home_win_prob']*100:.1f}%")
    print(f"    {pred['away_abbr']:>4} {a_bar} {pred['away_win_prob']*100:.1f}%")

    print()
    print(f"  {icon} {color}{BOLD}{rec}{RESET}  →  Pick: {BOLD}{winner}{RESET}  ({conf*100:.1f}% confidence)")

    # Injury notes
    h_inj = pred.get("home_injuries", 0)
    a_inj = pred.get("away_injuries", 0)
    if h_inj > 0 or a_inj > 0:
        notes = []
        if h_inj > 0:
            notes.append(f"{pred['home_abbr']}: {h_inj} injured")
        if a_inj > 0:
            notes.append(f"{pred['away_abbr']}: {a_inj} injured")
        print(f"  🏥 {', '.join(notes)}")

    print(f"  {'─' * 50}")


def verify_predictions(date_str):
    """
    Verify past predictions against actual results.
    Fetches the results for that date and compares.
    """
    history = load_history(date_str)
    if not history:
        print(f"\n  No predictions found for {date_str}")
        return None

    # Try to fetch actual results
    actual = fetch_schedule_espn(date_str)
    if not actual:
        actual_data = load_data(f"results_{date_str}.json")
        if actual_data:
            actual = actual_data
        else:
            print(f"\n  Could not fetch results for {date_str}")
            return None

    # Save actual results
    save_data(f"results_{date_str}.json", actual)

    results = []
    correct = 0
    total = 0

    for pred in history.get("predictions", []):
        # Find matching game in actual results
        h_abbr = pred["home_abbr"]
        a_abbr = pred["away_abbr"]

        for game in actual:
            if game["home"]["abbr"] == h_abbr and game["away"]["abbr"] == a_abbr:
                if game.get("status") == "STATUS_FINAL":
                    h_score = game["home"].get("score", 0)
                    a_score = game["away"].get("score", 0)
                    actual_winner = h_abbr if h_score > a_score else a_abbr

                    is_correct = pred["predicted_winner"] == actual_winner
                    if is_correct:
                        correct += 1
                    total += 1

                    results.append({
                        **pred,
                        "actual_winner": actual_winner,
                        "home_score": h_score,
                        "away_score": a_score,
                        "correct": is_correct,
                    })
                break

    if total > 0:
        accuracy = (correct / total) * 100
        print(f"\n  📊 Results for {date_str}:")
        print(f"     Correct: {correct}/{total} ({accuracy:.1f}%)")

        for r in results:
            icon = "✅" if r["correct"] else "❌"
            print(f"     {icon} {r['away_abbr']} @ {r['home_abbr']}: "
                  f"Predicted {r['predicted_winner']}, "
                  f"Actual {r['actual_winner']} "
                  f"({r.get('away_score', '?')}-{r.get('home_score', '?')})")

        # Save verified results
        save_history(f"{date_str}_verified", {
            "date": date_str,
            "correct": correct,
            "total": total,
            "accuracy": accuracy,
            "results": results,
        })
        return {"correct": correct, "total": total, "accuracy": accuracy}

    print(f"\n  Games for {date_str} may not be final yet.")
    return None


def get_season_accuracy():
    """Calculate overall season prediction accuracy."""
    total_correct = 0
    total_predictions = 0

    for f in os.listdir(HISTORY_DIR):
        if f.endswith("_verified.json"):
            filepath = os.path.join(HISTORY_DIR, f)
            with open(filepath) as fh:
                data = json.load(fh)
                total_correct += data.get("correct", 0)
                total_predictions += data.get("total", 0)

    if total_predictions > 0:
        return {
            "correct": total_correct,
            "total_predictions": total_predictions,
            "accuracy": (total_correct / total_predictions) * 100,
        }
    return None


def main():
    print_header()

    # Parse arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--analyze":
            from analyzer import analyze_date
            date = sys.argv[2] if len(sys.argv) > 2 else (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            analyze_date(date)
            return
        elif arg == "--verify" and len(sys.argv) > 2:
            verify_predictions(sys.argv[2])
            return
        elif arg == "tomorrow":
            target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            target_date = arg
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print(f"  🎯 Target date: {target_date}")
    print(f"  📁 Project dir: {os.path.dirname(os.path.abspath(__file__))}")
    print()

    # Step 1: Fetch data
    print("━" * 60)
    print("  STEP 1: Fetching Data")
    print("━" * 60)
    data = refresh_all_data(target_date)

    if not data["schedule"]:
        print("\n  ⚠️  No games found for this date.")
        print("     This could mean:")
        print("     - No games are scheduled")
        print("     - The API is temporarily unavailable")
        print("     - The date format might be wrong (use YYYY-MM-DD)")
        return

    # Step 2: Generate predictions
    print()
    print("━" * 60)
    print("  STEP 2: Generating Predictions")
    print("━" * 60)

    predictions = predict_all_games(
        data["schedule"],
        data["standings"],
        data["injuries"],
        data["recent_form"],
        data.get("player_form", {}),
    )

    # Step 3: Display predictions
    print()
    print("━" * 60)
    print(f"  PREDICTIONS FOR {target_date}")
    print("━" * 60)

    for i, pred in enumerate(predictions, 1):
        print_prediction(pred, i)

    # Summary
    print()
    print("━" * 60)
    print("  SUMMARY")
    print("━" * 60)
    strong = [p for p in predictions if p["recommendation"] == "STRONG PICK"]
    leans = [p for p in predictions if p["recommendation"] in ("LEAN", "SLIGHT LEAN")]
    skips = [p for p in predictions if p["recommendation"] == "SKIP"]

    if strong:
        print(f"\n  ✅ STRONG PICKS ({len(strong)}):")
        for p in strong:
            print(f"     → {p['predicted_winner_name']} ({p['confidence']*100:.1f}%)")

    if leans:
        print(f"\n  ⚠️  LEANS ({len(leans)}):")
        for p in leans:
            print(f"     → {p['predicted_winner_name']} ({p['confidence']*100:.1f}%)")

    if skips:
        print(f"\n  🚫 SKIP ({len(skips)}):")
        for p in skips:
            print(f"     → {p['home_abbr']} vs {p['away_abbr']} - too close to call")

    # Step 4: Save history
    history_entry = {
        "date": target_date,
        "generated_at": datetime.now().isoformat(),
        "num_games": len(predictions),
        "predictions": predictions,
    }
    save_history(target_date, history_entry)
    print(f"\n  💾 Predictions saved to history/{target_date}.json")

    # Step 5: Generate HTML dashboard
    season_stats = get_season_accuracy()
    dashboard_path = generate_dashboard(predictions, target_date, season_stats)
    print(f"  📊 Dashboard saved to {os.path.relpath(dashboard_path)}")

    # Step 6: Auto-verify yesterday's predictions
    yesterday = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_history = load_history(yesterday)
    if yesterday_history and not os.path.exists(os.path.join(HISTORY_DIR, f"{yesterday}_verified.json")):
        print()
        print("━" * 60)
        print(f"  AUTO-VERIFYING YESTERDAY ({yesterday})")
        print("━" * 60)
        verify_predictions(yesterday)

    if season_stats:
        print(f"\n  📈 Season Record: {season_stats['correct']}/{season_stats['total_predictions']} "
              f"({season_stats['accuracy']:.1f}%)")

    print()
    print("=" * 60)
    print("  Done! Check the HTML report for the visual dashboard.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
