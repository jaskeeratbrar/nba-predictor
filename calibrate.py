#!/usr/bin/env python3
"""
calibrate.py — Bayesian weight calibrator for the NBA predictor.

Reads all history/*_analysis.json files, computes per-factor Bayesian accuracy
with shrinkage, and writes suggested weights to performance/calibrated_weights.json.

Only writes output if any weight shifts by more than 1%.
Run manually, weekly (e.g. Mondays), after enough clean data has accumulated.

Usage:
    python3 calibrate.py            # compute + write if changes > 1%
    python3 calibrate.py --dry-run  # compute + print, no write
"""

import json
import os
import sys
from datetime import datetime

from config import WEIGHTS, PERFORMANCE_DIR, HISTORY_DIR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_PATH      = os.path.join(PERFORMANCE_DIR, "calibrated_weights.json")
INJURY_FIX_DATE  = "2026-03-09"   # injury API fix — exclude prior injury votes
REST_DAYS_FACTOR = "rest_days"    # permanently frozen at weight 0.0
MIN_UPDATE_DELTA = 0.01           # only write if any weight shifts > 1%
MAX_SHIFT        = 0.05           # max change per factor per run
MIN_WEIGHT       = 0.03           # floor for any active factor
SHRINKAGE_N      = 20             # at N votes, shrinkage = 0 (full trust in observed)
CORR_FACTORS     = ("win_pct", "recent_form")  # correlated — damp if both want to increase

FACTOR_NAMES = list(WEIGHTS.keys())


# ---------------------------------------------------------------------------
# Step 1: Collect factor votes from analysis files
# ---------------------------------------------------------------------------

def collect_factor_votes():
    """
    Walk all history/*_analysis.json files.
    For each factor, accumulate non-neutral correct/total votes.
    Injury factor: exclude votes from before INJURY_FIX_DATE.
    Returns dict: {factor: {"correct": int, "total": int}}
    """
    votes = {f: {"correct": 0, "total": 0} for f in FACTOR_NAMES}

    if not os.path.exists(HISTORY_DIR):
        return votes

    for fname in sorted(os.listdir(HISTORY_DIR)):
        if not fname.endswith("_analysis.json"):
            continue
        date_str = fname.replace("_analysis.json", "")
        fpath = os.path.join(HISTORY_DIR, fname)
        try:
            with open(fpath) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        for game in data.get("games", []):
            for factor, fvote in game.get("factor_votes", {}).items():
                if factor not in votes:
                    continue
                if fvote.get("neutral", False):
                    continue
                # Injury factor: skip tainted pre-fix data
                if factor == "injuries" and date_str < INJURY_FIX_DATE:
                    continue
                votes[factor]["total"] += 1
                if fvote.get("correct", False):
                    votes[factor]["correct"] += 1

    return votes


# ---------------------------------------------------------------------------
# Step 2: Bayesian shrinkage accuracy
# ---------------------------------------------------------------------------

def bayesian_accuracy(correct, total, prior=0.5, shrinkage_n=SHRINKAGE_N):
    """
    Blend observed accuracy with a prior using shrinkage.
      - At total=0:              return prior (no data, full shrinkage)
      - At total>=shrinkage_n:   return observed accuracy (no shrinkage)
      - In between:              linear blend toward prior
    """
    if total == 0:
        return prior
    shrinkage = max(0.0, 1.0 - total / shrinkage_n)
    observed = correct / total
    return shrinkage * prior + (1.0 - shrinkage) * observed


# ---------------------------------------------------------------------------
# Step 3: Compute new weights
# ---------------------------------------------------------------------------

def compute_weights(votes):
    """
    Given factor vote counts, compute calibrated weights using Bayesian accuracy.

    Pipeline:
      1. Bayesian accuracy per factor (shrinkage-blended)
      2. Raw weight = bayes_acc * current_weight (performance-proportional)
      3. Normalize to sum = 1.0 (excluding rest_days)
      4. Correlation damping: if both win_pct + recent_form want to increase,
         cap both at MAX_SHIFT/2 (prevents double-loading correlated factors)
      5. MAX_SHIFT cap per factor
      6. MIN_WEIGHT floor (rest_days stays 0.0)
      7. Renormalize + absorb rounding residual
    """
    current = dict(WEIGHTS)

    # Bayesian accuracy per factor
    bayes_acc = {}
    for factor in FACTOR_NAMES:
        if factor == REST_DAYS_FACTOR:
            bayes_acc[factor] = 0.0
            continue
        v = votes[factor]
        bayes_acc[factor] = bayesian_accuracy(v["correct"], v["total"])

    # Raw weight = bayes_accuracy * current_weight
    raw = {}
    for f in FACTOR_NAMES:
        raw[f] = 0.0 if f == REST_DAYS_FACTOR else bayes_acc[f] * current[f]

    # Normalize (rest_days excluded from denominator)
    total_raw = sum(v for f, v in raw.items() if f != REST_DAYS_FACTOR)
    if total_raw == 0:
        return dict(current)

    normalized = {}
    for f in FACTOR_NAMES:
        normalized[f] = 0.0 if f == REST_DAYS_FACTOR else raw[f] / total_raw

    # Correlation damping: if win_pct AND recent_form both want to increase,
    # cap both at MAX_SHIFT/2 to prevent overloading two correlated signals.
    corr_deltas = {f: normalized[f] - current[f] for f in CORR_FACTORS}
    both_increasing = all(corr_deltas[f] > 0 for f in CORR_FACTORS)

    # MAX_SHIFT cap (with correlation damping applied to CORR_FACTORS)
    capped = {}
    for f in FACTOR_NAMES:
        if f == REST_DAYS_FACTOR:
            capped[f] = 0.0
            continue
        delta = normalized[f] - current[f]
        limit = MAX_SHIFT / 2 if (both_increasing and f in CORR_FACTORS) else MAX_SHIFT
        if abs(delta) > limit:
            capped[f] = current[f] + limit * (1 if delta > 0 else -1)
        else:
            capped[f] = normalized[f]

    # MIN_WEIGHT floor
    for f in FACTOR_NAMES:
        if f != REST_DAYS_FACTOR:
            capped[f] = max(capped[f], MIN_WEIGHT)

    # Renormalize
    total_capped = sum(v for f, v in capped.items() if f != REST_DAYS_FACTOR)
    final = {}
    for f in FACTOR_NAMES:
        final[f] = 0.0 if f == REST_DAYS_FACTOR else round(capped[f] / total_capped, 4)

    # Absorb rounding residual into highest-weight active factor
    residual = round(1.0 - sum(final.values()), 4)
    if residual != 0:
        top = max((f for f in final if f != REST_DAYS_FACTOR), key=lambda x: final[x])
        final[top] = round(final[top] + residual, 4)

    return final


# ---------------------------------------------------------------------------
# Step 4: Guard + write
# ---------------------------------------------------------------------------

def any_meaningful_change(current, proposed):
    """Return True if any weight shifts by more than MIN_UPDATE_DELTA."""
    for f in FACTOR_NAMES:
        if abs(proposed.get(f, 0) - current.get(f, 0)) > MIN_UPDATE_DELTA:
            return True
    return False


def run(dry_run=False):
    print()
    print("=" * 58)
    print("  NBA PREDICTOR — BAYESIAN WEIGHT CALIBRATION")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 58)

    current = dict(WEIGHTS)
    votes = collect_factor_votes()

    print()
    print(f"  {'Factor':<16} {'Votes':>6}  {'Raw Acc':>8}  {'Bayes Acc':>10}")
    print(f"  {'-'*16} {'-'*6}  {'-'*8}  {'-'*10}")
    for f in FACTOR_NAMES:
        v = votes[f]
        t, c = v["total"], v["correct"]
        if f == REST_DAYS_FACTOR:
            print(f"  {f:<16} {t:>6}  {'FROZEN':>8}  {'FROZEN':>10}")
        else:
            raw_acc  = f"{c/t*100:.1f}%" if t > 0 else "n/a"
            bacc     = bayesian_accuracy(c, t)
            bacc_str = f"{bacc*100:.1f}%"
            shrink   = max(0.0, 1.0 - t / SHRINKAGE_N)
            note     = f"  (shrinkage={shrink:.0%})" if shrink > 0 else ""
            print(f"  {f:<16} {t:>6}  {raw_acc:>8}  {bacc_str:>10}{note}")

    proposed = compute_weights(votes)

    print()
    print(f"  {'Factor':<16} {'Current':>8}  {'Proposed':>9}  {'Delta':>8}")
    print(f"  {'-'*16} {'-'*8}  {'-'*9}  {'-'*8}")
    for f in FACTOR_NAMES:
        cur  = current[f]
        prop = proposed.get(f, cur)
        delta = prop - cur
        delta_str = f"+{delta*100:.1f}%" if delta > 0.0005 else f"{delta*100:.1f}%" if delta < -0.0005 else "—"
        flag = "  ◄ change" if abs(delta) > MIN_UPDATE_DELTA else ""
        print(f"  {f:<16} {cur*100:>7.1f}%  {prop*100:>8.1f}%  {delta_str:>8}{flag}")

    print()

    if not any_meaningful_change(current, proposed):
        print("  No meaningful changes (all deltas < 1%). Weights are well-calibrated.")
        print("  Check again next Monday.")
        return proposed

    if dry_run:
        print("  [DRY RUN] Would write calibrated weights. Not writing.")
        print()
        print("  To apply: python3 calibrate.py")
        return proposed

    output = {
        "generated_at":  datetime.now().isoformat(),
        "weights":        proposed,
        "vote_counts":    {f: votes[f] for f in FACTOR_NAMES},
        "notes": {
            "injury_fix_date": INJURY_FIX_DATE,
            "rest_days":       "permanently frozen — data source unreliable",
            "shrinkage_n":     SHRINKAGE_N,
            "max_shift":       MAX_SHIFT,
        },
    }

    os.makedirs(PERFORMANCE_DIR, exist_ok=True)
    tmp = OUTPUT_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(output, f, indent=2)
    os.replace(tmp, OUTPUT_PATH)

    print(f"  Calibrated weights written → performance/calibrated_weights.json")
    print()
    print("  These weights will be picked up automatically by run_predictions.py")
    print("  on the next prediction run (no manual config.py edit needed).")
    print()

    return proposed


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run(dry_run=dry_run)
