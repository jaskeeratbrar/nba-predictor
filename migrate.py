#!/usr/bin/env python3
"""
migrate.py — One-time import of JSON history files into SQLite.

Run once (safe to re-run — all writes are idempotent):
    python3 migrate.py
"""

import json
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

import db
from config import HISTORY_DIR

db.init_schema()


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"  [SKIP] {path}: {e}")
        return None


def migrate_predictions():
    """Import prediction JSON files (history/YYYY-MM-DD.json)."""
    files = sorted(
        f for f in os.listdir(HISTORY_DIR)
        if f.endswith(".json")
        and not f.endswith("_analysis.json")
        and not f.endswith("_verified.json")
        and len(f) == len("YYYY-MM-DD.json")
    )
    print(f"\n--- Migrating {len(files)} prediction files ---")
    conn = db.get_connection()
    imported = 0
    for fname in files:
        date_str = fname.replace(".json", "")
        data = _load_json(os.path.join(HISTORY_DIR, fname))
        if not data or "predictions" not in data:
            continue
        preds = data["predictions"]
        if not preds:
            continue
        try:
            db.upsert_predictions(conn, date_str, preds)
            conn.commit()
            imported += 1
            print(f"  {date_str}: {len(preds)} predictions")
        except Exception as e:
            print(f"  [ERR] {date_str}: {e}")
    conn.close()
    print(f"  Done: {imported}/{len(files)} dates imported.")


def migrate_analyses():
    """Import analysis JSON files (history/YYYY-MM-DD_analysis.json)."""
    files = sorted(
        f for f in os.listdir(HISTORY_DIR)
        if f.endswith("_analysis.json")
    )
    print(f"\n--- Migrating {len(files)} analysis files ---")
    conn = db.get_connection()
    imported = 0
    for fname in files:
        date_str = fname.replace("_analysis.json", "")
        data = _load_json(os.path.join(HISTORY_DIR, fname))
        if not data:
            continue
        games      = data.get("games", [])
        summary    = data.get("summary", {})
        factor_acc = data.get("factor_accuracy_this_date", {})
        try:
            for ga in games:
                db.upsert_game_result(conn, date_str, ga)
            if summary:
                db.upsert_daily_summary(conn, date_str, summary, factor_acc)
            conn.commit()
            imported += 1
            print(f"  {date_str}: {len(games)} games analyzed")
        except Exception as e:
            print(f"  [ERR] {date_str}: {e}")
    conn.close()
    print(f"  Done: {imported}/{len(files)} dates imported.")


def report():
    """Print a quick summary of what's now in the DB."""
    conn = db.get_connection()
    counts = {}
    for table in ["games", "predictions", "game_results", "daily_summary",
                  "standings_snapshots", "injuries", "player_form_snapshots",
                  "team_recent_form"]:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        counts[table] = row["n"]
    conn.close()

    print("\n--- DB summary ---")
    for t, n in counts.items():
        print(f"  {t:<28} {n:>6} rows")

    # Factor accuracy from DB
    conn = db.get_connection()
    acc = db.get_cumulative_factor_accuracy(conn)
    conn.close()
    if acc.get("total_games"):
        overall = acc.get("overall", 0) or 0
        print(f"\n  Overall accuracy: {acc['total_correct']}/{acc['total_games']} ({overall*100:.1f}%)")


if __name__ == "__main__":
    migrate_predictions()
    migrate_analyses()
    report()
    print("\nMigration complete. DB is at nba_predictor.db\n")
