# Model Improvement Plan

_Last updated: 2026-03-22_

## Current State

**Season: 101/129 — 78.3% accuracy.** Model stable, weights updated.

| Metric | Value | Notes |
|--------|-------|-------|
| Overall accuracy | 78.3% (101/129) | Across all recommendation tiers |
| STRONG PICK | 90.0% (18/20) | Excellent |
| LEAN | 86.7% (26/30) | Nearly as good as STRONG PICK |
| SKIP | 67.4% (29/43) | Expected — genuine toss-ups |
| Injury factor votes | 79 (post-fix) | Weight bumped to 0.15 ✓ |
| home_away factor | 75.0% | Rebounded from 67.3% concern — stable |

---

## Active — Accumulating Data

### ESPN team efficiency stats pipeline (added 2026-03-16)
**Status:** Fetching ppg, fg_pct, fg3_pct, ft_pct, reb_pg, ast_pg for every team playing
today. Stored in `team_efficiency_snapshots` DB table. `efficiency_edge` (scoring margin
delta normalized to [-1,1]) shown on dashboard and in API response.

**Not used in model confidence yet.** Needs 2-3 weeks of snapshots to evaluate correlation
with outcomes. Target: early April, cross-reference efficiency_edge with game results to
decide whether to add as a weighted factor.

**How to check correlation when ready (~2026-04-05):**
```bash
python3 -c "
import db, json; conn = db.get_connection()
rows = conn.execute('''
    SELECT p.predicted_winner_abbr, gr.correct, g.game_date
    FROM predictions p
    JOIN game_results gr ON gr.game_id = p.game_id
    JOIN games g ON g.id = p.game_id
    WHERE g.game_date >= \"2026-03-16\"
''').fetchall()
print(f'{len(rows)} games with efficiency data since 2026-03-16')
conn.close()
"
```

---

### Calibrate.py — run weekly starting now
**Status:** Built (2026-03-22). Has 79+ clean games (well past the 30-game threshold).
Run every Monday: `python3 calibrate.py`. Output goes to `performance/calibrated_weights.json`
and is automatically picked up by `run_predictions.py` on next run.

**How it works:** Bayesian accuracy with shrinkage (shrinkage_n=20 per factor). Correlation
damping prevents win_pct + recent_form from both inflating simultaneously. rest_days
permanently frozen at 0.0.

---

## Waiting

### Logistic regression (target: ~Oct 2026, next season)
**Status:** Not started. Needs 200+ clean games to produce reliable coefficients.
At ~1,200 regular season games/year and assuming nightly cron, expect 200+ by
mid-November 2026.

**Why it's worth doing:** Current heuristic (`suggest_weights()`) scales weights by
accuracy independently — ignores feature interactions. LR would learn joint contribution
of all 7 factors simultaneously.

**Migration path:**
1. calibrate.py (Bayesian, built Mar 22) bridges us through the season
2. End of 2025-26 season: evaluate sample size
3. LR replaces `suggest_weights()` — same output format, better algorithm

**What NOT to build:** XGBoost, random forests, neural nets. 7 binary features + binary
outcome = logistic regression is the correct tool.

---

### Opponent quality / SOS adjustment (target: next season)
**Status:** Not started. Recent_form currently treats a win vs lottery team the same as
a win vs playoff team. An SOS multiplier on form_score would improve signal quality.

**Not building yet.** Would require fetching opponent records at time of game (historical
standings). Complex and low-ROI mid-season. Revisit as a 2026-27 preseason improvement.

---

### Kalshi / prediction markets integration (future project)
**Status:** Not started. User trades on Kalshi informed by model output. A dedicated
integration would pull Kalshi market prices, compare with model confidence, and flag
divergences (model says 75%, market says 55% = potential edge).

**Not building yet.** Revisit when model has 200+ games and calibrate.py is running.

---

## Completed

- [x] **net_rating factor** — avg point differential last 10 games (0.05 weight); no new API calls — 2026-03-22
- [x] **defense factor** — avg opponent PPG allowed last 10 games (0.07 weight); fills the only missing signal class — 2026-03-22
- [x] **calibrate.py** — Bayesian weight calibrator, runs weekly — 2026-03-22
- [x] **Injury weight bump** — injuries 0.12→0.15, win_pct 0.27→0.24 (79 votes @ 73.4%) — 2026-03-22
- [x] **calibrated_weights.json wired into run_predictions.py** — takes priority over ledger suggestions — 2026-03-22
- [x] **SQLite analytics endpoints** — /stats, /history, /misses expose DB data remotely — 2026-03-16
- [x] **ESPN team efficiency stats** — fetch_team_stats_espn(), efficiency_edge on dashboard — 2026-03-16
- [x] **DB schema: play_type/risk_score/edge_score** — ALTER TABLE migration + upsert — 2026-03-16
- [x] **Server weight bug fixed** — startup exclusion logic mirrored from run_predictions.py — 2026-03-16
- [x] **Server weights snapshot** — /run now records active weights in weights_history — 2026-03-16
- [x] **Injury-conditional weighting** (P2) — win_pct/player_form suppressed on high-injury slates — 2026-03-15
- [x] **Both-teams-decimated confidence compression** (P4) — compress toward 0.5 when both teams individually decimated (load > 3.0) — 2026-03-15
- [x] **Severe injury auto-cap** (P5) — model picks more-injured team → cap confidence at 0.57 — 2026-03-15
- [x] **Active roster filter** (P3) — Out/Doubtful players excluded from player_form before scoring — 2026-03-10
- [x] **Learned weights exclusion fix** — config zero-weights enforced before set_weights() — 2026-03-15
- [x] **Play type classification** — LOCK/VALUE/RISKY tracked in ledger + dashboard — 2026-03-15
- [x] **rest_days excluded** — zeroed (33.3% accuracy), weight redistributed — 2026-03-15
- [x] **Effective win%** — blend 60% season + 40% last-10 in win_pct factor — 2026-03-11
- [x] **Playoff pressure** — play-in/playoff race urgency boost — 2026-03-11
- [x] **ESPN injury API fix** — response structure changed, silently dropping all injuries — 2026-03-09
- [x] **Star player detection** — reb/blk/stl in form_score — 2026-03-10
- [x] **Position-based fallback** — long-term injured stars get impact estimate — 2026-03-10
- [x] **Player form lookback 5 → 10 games** — 2026-03-10
- [x] **Power scaling reduced** — win_pct 2.5→1.8, recent_form 1.8→1.3 — earlier
- [x] **Season-progress dynamic weights** — earlier
- [x] **Point differential in recent_form** — earlier
- [x] **Atomic JSON writes** — earlier
- [x] **True Shooting % in player form** — earlier

---

### ESPN team efficiency stats pipeline (added 2026-03-16)
**Status:** Fetching ppg, fg_pct, fg3_pct, ft_pct, reb_pg, ast_pg for every team playing
today. Stored in `team_efficiency_snapshots` DB table. `efficiency_edge` (scoring margin
delta normalized to [-1,1]) shown on dashboard and in API response.

**Not used in model confidence yet.** Needs 2-3 weeks of snapshots to evaluate correlation
with outcomes. Target: early April, cross-reference efficiency_edge with game results to
decide whether to add as a weighted factor.

**How to check correlation when ready (~2026-04-05):**
```bash
python3 -c "
import db, json; conn = db.get_connection()
# Load predictions that have efficiency_edge and a result
rows = conn.execute('''
    SELECT p.predicted_winner_abbr, gr.correct, g.game_date
    FROM predictions p
    JOIN game_results gr ON gr.game_id = p.game_id
    JOIN games g ON g.id = p.game_id
    WHERE g.game_date >= \"2026-03-16\"
''').fetchall()
print(f'{len(rows)} games with efficiency data since 2026-03-16')
conn.close()
"
```

---

### home_away factor under watch
**Status:** 67.3% accuracy — weakest active factor. Not broken (NBA home court advantage
is genuinely shrinking in the modern era), but if it drops below 65% by end of March,
consider reducing weight from 0.12 to 0.08 and redistributing to recent_form.

---

## Waiting

### Build calibrate.py (target: ~2026-03-31)
**Status:** Design complete. DO NOT build until 30+ clean post-fix games exist.

**Why waiting:** All pre-2026-03-09 games have a broken injury factor. Calibrating from
that data would produce weights for a 6-factor model. Need clean 7-factor data.

**How to check when ready:**
```bash
python3 -c "
import db; conn = db.get_connection()
r = conn.execute('''
    SELECT COUNT(*) FROM game_results gr
    JOIN games g ON g.id = gr.game_id
    WHERE g.game_date >= \"2026-03-09\"
''').fetchone()
print(f'Clean games: {r[0]} (need 30+)')
conn.close()
"
```

**Design:** Bayesian weighted accuracy with shrinkage. See conversation history 2026-03-10
for full Opus-level design. Key points:
- Shrinkage: `max(0, 1 - effective_n / 20)` per factor
- Injury factor: exclude pre-2026-03-09 rows, freeze if < 20 non-neutral votes
- Rest days: permanently frozen (data source broken)
- Output: `performance/calibrated_weights.json`
- Guard: only update if any weight changes by > 1%
- Correlation damping: win_pct + recent_form both wanting increase → cap both at half MAX_SHIFT
- Run: manually, weekly on Mondays, `python3 calibrate.py [--dry-run]`

---

### Logistic regression (target: ~Oct 2026, next season)
**Status:** Not started. Needs 200+ clean games to produce reliable coefficients.
At ~1,200 regular season games/year and assuming nightly cron, expect 200+ by
mid-November 2026.

**Why it's worth doing:** Current heuristic (`suggest_weights()`) scales weights by
accuracy independently — ignores feature interactions. LR would learn joint contribution
of all 7 factors simultaneously.

**Migration path:**
1. calibrate.py (Bayesian, ~Mar 31) bridges us through the season
2. End of 2025-26 season: evaluate sample size
3. LR replaces `suggest_weights()` — same output format, better algorithm

**What NOT to build:** XGBoost, random forests, neural nets. 7 binary features + binary
outcome = logistic regression is the correct tool.

---

### Kalshi / prediction markets integration (future project)
**Status:** Not started. User trades on Kalshi informed by model output. A dedicated
integration would pull Kalshi market prices, compare with model confidence, and flag
divergences (model says 75%, market says 55% = potential edge).

**Not building yet.** This is a separate project. Current model needs to prove its
accuracy through a full season first. Revisit when model has 200+ games and calibrate.py
is running.

---

## Completed

- [x] **SQLite analytics endpoints** — /stats, /history, /misses expose DB data remotely — 2026-03-16
- [x] **ESPN team efficiency stats** — fetch_team_stats_espn(), efficiency_edge on dashboard — 2026-03-16
- [x] **DB schema: play_type/risk_score/edge_score** — ALTER TABLE migration + upsert — 2026-03-16
- [x] **Server weight bug fixed** — startup exclusion logic mirrored from run_predictions.py — 2026-03-16
- [x] **Server weights snapshot** — /run now records active weights in weights_history — 2026-03-16
- [x] **Injury-conditional weighting** (P2) — win_pct/player_form suppressed on high-injury slates — 2026-03-15
- [x] **Both-teams-decimated confidence compression** (P4) — compress toward 0.5 when both teams individually decimated (load > 3.0) — 2026-03-15
- [x] **Severe injury auto-cap** (P5) — model picks more-injured team → cap confidence at 0.57 — 2026-03-15
- [x] **Active roster filter** (P3) — Out/Doubtful players excluded from player_form before scoring — 2026-03-10
- [x] **Learned weights exclusion fix** — config zero-weights enforced before set_weights() — 2026-03-15
- [x] **Play type classification** — LOCK/VALUE/RISKY tracked in ledger + dashboard — 2026-03-15
- [x] **rest_days excluded** — zeroed (33.3% accuracy), weight redistributed — 2026-03-15
- [x] **Effective win%** — blend 60% season + 40% last-10 in win_pct factor — 2026-03-11
- [x] **Playoff pressure** — play-in/playoff race urgency boost — 2026-03-11
- [x] **ESPN injury API fix** — response structure changed, silently dropping all injuries — 2026-03-09
- [x] **Star player detection** — reb/blk/stl in form_score — 2026-03-10
- [x] **Position-based fallback** — long-term injured stars get impact estimate — 2026-03-10
- [x] **Player form lookback 5 → 10 games** — 2026-03-10
- [x] **Power scaling reduced** — win_pct 2.5→1.8, recent_form 1.8→1.3 — earlier
- [x] **Season-progress dynamic weights** — earlier
- [x] **Point differential in recent_form** — earlier
- [x] **Atomic JSON writes** — earlier
- [x] **True Shooting % in player form** — earlier
