# Model Improvement Plan

_Last updated: 2026-03-10_

## Context
Opus-level reflection after Mar 9 results (2/5, 40%). The model is 75% backward-looking
and only 11% real-time. On injury-heavy slates it fails systematically because win%,
player_form, and recent_form all describe a team that may not exist tonight.

Season record: 33/42 (78.6%) — likely inflated by healthy-roster games masking
poor performance on injury-heavy slates. March is when this gets worse (teams
managing rosters for playoffs).

---

## Priority 1 — Calibrate injury factor (WAITING — ~2 weeks)
**Status:** Waiting for data. Injury factor was broken all season (ESPN API structure
changed, all injuries silently dropped). Fixed 2026-03-09. Now accumulating votes.

**What to do:** After 15+ injury-factor votes in the ledger, check its standalone
accuracy. Until then, do not change its weight — you have no evidence for what's right.
Current weight: 11%. May need to go to 20-25% once calibrated.

**Watch for:** Factor accuracy table in the daily `--analyze` output. Currently shows
`n/a (0/15 games)`. Target: 15 votes before drawing conclusions.

---

## Priority 2 — Injuries should modulate other factors, not just vote (NOT STARTED)
**Status:** Architectural change needed. Currently injuries cast one vote among seven.
They should suppress the weight of win% and player_form when injury load is high.

**The idea:** When a team's injury penalty exceeds a threshold (e.g. 2+ stars out),
dynamically reduce that team's win_pct and player_form contribution in the final
score calculation. The more decimated the roster, the less historical signals matter.

**Blocked by:** Priority 1 — need calibrated injury data before tuning this interaction.

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

## Completed
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
