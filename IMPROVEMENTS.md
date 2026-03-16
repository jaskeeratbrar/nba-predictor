# Model Improvement Plan

_Last updated: 2026-03-15_

## Context
Opus-level reflection after Mar 9 results (2/5, 40%). The model is 75% backward-looking
and only 11% real-time. On injury-heavy slates it fails systematically because win%,
player_form, and recent_form all describe a team that may not exist tonight.

Season record: 33/42 (78.6%) — likely inflated by healthy-roster games masking
poor performance on injury-heavy slates. March is when this gets worse (teams
managing rosters for playoffs).

---

## Priority 1 — Calibrate injury factor (WAITING — ~2026-03-25)
**Status:** Accumulating votes. 8 clean votes as of 2026-03-15 (post API fix 2026-03-09).
Need 15+ before drawing weight conclusions. Current weight: 12%. Target 15-20% once calibrated.

**What to do:** After 2026-03-20, check injury factor accuracy in `--analyze` output.
If accuracy is stable at 70%+, increase weight toward 0.15-0.20 in config.py.

---

## Priority 2 — Injuries should modulate other factors, not just vote ✅ DONE 2026-03-15
**Status:** Implemented. `_dynamic_weights()` now reduces win_pct and player_form when
injury load exceeds threshold (2.0), redistributing to injuries (70%) and streak (30%).
Max adjustment: 6pp per factor at load=5.0. See DEBUG.md for full detail.

**Next:** Monitor accuracy on injury-heavy slates (March–April) to validate the thresholds
are well-tuned. Adjust INJURY_MAX_LOAD and MAX_ADJUST in `_dynamic_weights()` if needed.

---

## Priority 3 — Player form should only count active players ✅ IN PROGRESS
**Status:** Partially addressed. Lookback extended from 5→10 games (catches recently
injured players). Position-based fallback added for long-term injured stars.

**Remaining gap:** Player form score still reflects contributions from players who are
NOW on the injury list. A team's form computed from 10 games with Ja Morant is
misleading when Morant is out tonight. Need to filter: when computing a team's
aggregate player_form score in predict_game(), exclude players who appear on
tonight's injury list as Out/Doubtful.

**Effort:** Medium. Changes prediction_engine.py compute_player_form_factor().

---

## Priority 4 — Both-teams-decimated → lower confidence, not neutral (NOT STARTED)
**Status:** Not started. When both teams have significant injury loads, the injury
factor returns ~0.5 (neutral) and the model makes a confident prediction based
entirely on backward-looking factors — which are both unreliable. Wrong behavior.

**The idea:** Detect when total injury penalty across both teams exceeds a threshold.
In that scenario, compress overall confidence toward 50% (i.e. push toward SKIP)
rather than letting stale factors decide with false confidence.

**Effort:** Small. Changes predict_game() confidence calculation.

---

## Priority 5 — Severe injuries → auto SKIP (NOT STARTED)
**Status:** Not started. A team missing 5+ rotation players should mechanically push
toward SKIP regardless of what other factors say, because all backward-looking signals
for that team are unreliable.

**The idea:** Count "Out" players weighted by impact (star=2, starter=1, role=0.5).
If either team's weighted absence score exceeds a threshold, cap confidence at SKIP
level (below 60%) regardless of model output.

**Effort:** Small. Can be added as a post-prediction override in predict_game().

---

## Priority 6 — Build calibrate.py from SQLite data (WAITING — ~2026-03-31)
**Status:** Design complete (see Opus plan below). Do NOT build yet.

**Why waiting:** All 42 games of history have a broken injury factor (fixed 2026-03-09).
Calibrating weights from that window produces weights for a 6-factor model, not 7.
Need ~30 games of clean data (injury factor working) before calibration is meaningful.
Target: around 2026-03-31, check if 30+ post-fix games exist before starting.

**How to check when ready:**
```bash
python3 -c "
import db, json
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute(\"\"\"
    SELECT COUNT(*) FROM predictions p
    JOIN game_results gr ON p.game_date = gr.game_date
        AND p.home_abbr = gr.home_abbr
    WHERE p.game_date >= '2026-03-09'
\"\"\")
print('Clean games available:', cursor.fetchone()[0])
conn.close()
"
```
If result >= 30, proceed with building calibrate.py using the Opus design below.

**Opus design summary (full detail in conversation history 2026-03-10):**
- Read from SQLite: join `predictions` + `game_results`, use stored factor scores
- Method: Bayesian weighted accuracy with shrinkage (not logistic regression — too few samples)
- Shrinkage formula: `shrinkage = max(0, 1 - effective_n / 20)` per factor
- Injury factor: exclude all pre-2026-03-09 rows, freeze if < 20 non-neutral votes
- Rest days: effectively frozen (timing bug means near-zero margins stored in DB)
- Output: `performance/calibrated_weights.json` — model reads this at startup
- Guard: only update if any weight changes by > 1%, otherwise skip
- Correlation damping: if win_pct AND recent_form both want to increase, cap both at half MAX_SHIFT
- Run: manually (not cron), weekly on Mondays, `python3 calibrate.py [--dry-run]`

**Key files to read before implementing:**
- `db.py` — schema, `save_weights_snapshot()`
- `analyzer.py` — existing DB read patterns
- `config.py` — WEIGHTS, MIN_WEIGHT, PERFORMANCE_DIR
- `run_predictions.py` lines 31-45 — startup weight loading block to update

---

## Priority 7 — Logistic regression weight learning (WAITING — next season)
**Status:** Not started. Do NOT build until a full season of clean data exists.

**Why waiting:** Logistic regression needs ~200+ games per feature to produce reliable
coefficients. With 7 factors that means ~1,400+ factor votes minimum. We have ~53 games
total (11 with injury factor clean). This is a next-season project (~Oct 2026).

**Why it's worth doing eventually:** The current heuristic (`suggest_weights()` in
analyzer.py) scales weights by accuracy independently — it ignores feature interactions.
Logistic regression would learn the joint contribution of all 7 factors simultaneously,
handling correlations like win_pct + recent_form moving together.

**Migration path:**
1. `calibrate.py` (Priority 6, ~Mar 31) — Bayesian shrinkage, bridges us to end of season
2. End of 2025-26 season — evaluate: do we have 200+ clean games? If yes, build LR.
3. Logistic regression replaces `suggest_weights()` in analyzer.py. Same output format
   (`weight_suggestions` dict), same auto-apply mechanism — just a better algorithm inside.

**What NOT to build:** XGBoost, random forests, neural nets. 7 binary features + binary
outcome = logistic regression is the correct tool. Tree models need 500+ samples and
become black boxes that can't tell you which factors actually matter.

**How to check when ready (~Oct 2026):**
```bash
python3 -c "
import db
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute('''
    SELECT COUNT(*) FROM predictions p
    JOIN game_results gr ON p.game_date = gr.game_date
        AND p.home_abbr = gr.home_abbr
    WHERE p.game_date >= '2026-03-09'
''')
print('Clean games available:', cursor.fetchone()[0])
conn.close()
"
```
Target: 200+ before building. At ~1,200 regular season games/year, expect ~200 clean
games by mid-November 2026 (assuming cron runs nightly).

---

## Priority 6b — SQLite is write-only, nothing reads from it (NOT STARTED)
**Status:** Not started. The DB has 43 predictions, 42 game results, 418 player form
snapshots, 290 team recent form rows — but zero of this is used for analysis or learning.
Everything reads from JSON files. The DB is an audit trail that nobody consults.

**What's possible:** analyzer.py could query `predictions` + `game_results` joined
directly from the DB instead of scanning JSON files. Factor accuracy ledger could
be stored and queried from DB. Player form snapshots could power richer historical
analysis (e.g. true season averages, not just last 10 games).

**Not urgent** — JSON files work and are now in git. But long-term the DB is the
right data layer, especially as history grows beyond a season.

---

## Completed
- [x] Injury-conditional weighting (Priority 2) — win_pct/player_form suppressed on high-injury slates — 2026-03-15
- [x] Fixed learned weights override — config zero-weights now enforced before set_weights() — 2026-03-15
- [x] Play type accuracy tracking — LOCK/VALUE/RISKY etc. tracked in ledger + report — 2026-03-15
- [x] Effective win% — blend 60% season win% + 40% last-10 win% in compute_win_pct_factor() — 2026-03-11
- [x] Playoff position pressure — teams within 2-3 games of play-in/playoff cut get urgency boost in predict_game() — 2026-03-11
- [x] Fix ESPN injury API (team name structure changed, all injuries were silently dropped) — 2026-03-09
- [x] Star player detection: reb/blk/stl now in form_score, not just pts — 2026-03-10
- [x] Position-based fallback for long-term injured players (Steph, Ja etc.) — 2026-03-10
- [x] Player form lookback extended 5→10 games — 2026-03-10
- [x] History files tracked in git across machines — 2026-03-09
- [x] Power scaling reduced (win_pct 2.5→1.8, recent_form 1.8→1.3) — earlier
- [x] Season-progress dynamic weights — earlier
- [x] Point differential in recent_form — earlier
- [x] Atomic JSON writes — earlier
- [x] True Shooting % in player form — earlier
