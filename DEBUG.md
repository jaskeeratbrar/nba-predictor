# NBA Predictor — Debug & Status Log

Quick lookup for known issues, fixes, and runtime health checks.
Update this file whenever you hit and resolve something non-obvious.

---

## Quick Health Check

```bash
# Verify predictions run and produce expected fields
python3 -c "
import json
with open('history/$(date +%Y-%m-%d).json') as f:
    d = json.load(f)
p = d['predictions'][0]
required = ['confidence','recommendation','play_type','risk_score','edge_score','play_explanation','factors']
missing = [k for k in required if k not in p]
print('MISSING FIELDS:', missing or 'none')
print('play_type sample:', p.get('play_type'))
print('explanation sample:', p.get('play_explanation'))
"
```

```bash
# Check factor accuracy ledger
python3 -c "
import json
with open('performance/factor_accuracy.json') as f:
    d = json.load(f)
print(f\"Games analyzed: {d.get('total_games_analyzed',0)}\")
print(f\"Overall accuracy: {d.get('overall_accuracy',0)*100:.1f}%\")
for k,v in d.get('factors',{}).items():
    print(f\"  {k}: {v.get('accuracy',0)*100:.1f}% | weight={v.get('current_weight',0):.3f} | suggested={v.get('suggested_weight',0):.3f}\")
"
```

---

## Known Issues & Fixes

### [2026-03-16] ESPN team efficiency stats pipeline added
**What changed:** `fetch_team_stats_espn()` in data_manager.py pulls ppg/fg_pct/fg3_pct/ft_pct/reb_pg/ast_pg
per team. Stored in `team_efficiency_snapshots` DB table daily. `efficiency_edge` (scoring margin delta from
recent games, normalized [-1,1]) added to prediction output and dashboard.
**Not in model yet.** Informational only — needs 2-3 weeks of snapshots before correlation check.

### [2026-03-16] SQLite analytics endpoints added
**Endpoints:** GET /stats, /history?team=X, /misses?conf=0.7. Read-only, query existing DB analytics functions.
**DB schema migrated:** predictions table gained play_type, risk_score, edge_score columns (ALTER TABLE with try/except).
**Server weight fix:** server.py startup now mirrors run_predictions.py exclusion logic. /run now saves weights_history.

### [2026-03-15] Injury-conditional weighting added (Priority 2)
**What changed:** `_dynamic_weights()` in `prediction_engine.py` now accepts `home_injury_load`
and `away_injury_load`. When `max(h_load, a_load) > 2.0`, backward-looking weights (win_pct,
player_form) are reduced and the freed weight shifts to injuries (70%) and streak (30%).
Max reduction: 6pp per factor at load=5.0 (≈ 3+ starters out).
**Effect:** On heavy-injury slates (late March), the model now relies less on a team's season
record and more on who is actually available tonight.

### [2026-03-15] rest_days factor broken (33.3% accuracy)
**Symptom:** rest_days was contributing noise to confidence scores.
**Root cause:** ESPN doesn't expose pre-game rest data — the computed margins are near-zero, making votes essentially random.
**Fix:** Zeroed out rest_days weight in `config.py` (was 0.08, now 0.00). Redistributed to reliable factors:
- win_pct: 0.25 → 0.27
- recent_form: 0.20 → 0.22
- player_form: 0.20 → 0.22
- home_away: 0.11 → 0.12
- injuries: 0.11 → 0.12
**Note:** rest_days is still computed and used as a raw edge signal in `classify_play()` for the `RISKY — WORTH IT` classification.

### [2026-03-15] Risk/Reward classification added
**New fields on every prediction:** `play_type`, `risk_score`, `edge_score`, `risk_components`, `edge_components`, `play_explanation`
**Play types:** LOCK | VALUE PLAY | RISKY — WORTH IT | RISKY — AVOID | SKIP
**Key rule:** if `confidence >= CONFIDENCE_HIGH (0.70)` → always LOCK, regardless of risk score.
**Files changed:** `config.py`, `prediction_engine.py`, `dashboard.py`, `server.py`

### [2026-03-09] Injury factor broken (ESPN API structure change)
**Symptom:** Injuries silently dropped — factor returning 0.5 (neutral) for every game.
**Root cause:** ESPN changed the injuries API response structure.
**Fix:** Updated `data_manager.py` to handle new response shape.
**Impact:** Only ~8 clean injury votes collected before fix. Injury suggested weight (0.139) is unreliable until ~30 more clean games accumulate.

### [2026-03-09] Player form including injured players
**Symptom:** Form scores inflated when stars are out — e.g., Ja Morant in 10 recent games but out tonight.
**Fix:** `predict_game()` filters out tonight's Out/Doubtful players from player_form before scoring via `_active_form()` (added ~2026-03-09).

---

## Learned Weights: When They Apply

Learned weights from `performance/factor_accuracy.json` override `config.py` WEIGHTS when:
- `total_games_analyzed >= 50` AND
- `weight_suggestions` dict has same number of keys as WEIGHTS

**Current state (2026-03-16):** 53 games analyzed → learned weights ARE active.

**Fixed (2026-03-15):** Startup block in `run_predictions.py` now enforces config exclusions
before calling `set_weights()`. Any factor with `weight == 0.0` in `config.py` is zeroed in
the learned suggestions and the remainder renormalized. This prevents tainted learned weights
(e.g. rest_days at 0.101) from silently overriding intentional exclusions.

To force config weights entirely (bypass learned): comment out `set_weights(_suggestions)` call in `run_predictions.py` temporarily.

---

## Confidence vs Play Type Mapping (expected)

| conf | recommendation | expected play_type |
|------|---------------|-------------------|
| ≥0.70 | STRONG PICK | LOCK |
| 0.65–0.69 | LEAN | LOCK or VALUE PLAY (if risk < 0.30) |
| 0.60–0.64 | LEAN | VALUE PLAY or RISKY — AVOID/WORTH IT |
| 0.55–0.59 | SLIGHT LEAN | VALUE PLAY or RISKY — * |
| <0.55 | SKIP | SKIP |

---

## Factor Accuracy Status (as of 2026-03-16)

| Factor | Accuracy | Weight (config) | Status |
|--------|----------|----------------|--------|
| recent_form | 80.8% | 0.22 | reliable |
| streak | 77.5% | 0.05 | reliable |
| injuries | 75.0% | 0.12 | only 8 clean votes — accumulating (target: 15+ by 2026-03-25) |
| player_form | 72.4% | 0.22 | reliable |
| win_pct | 72.0% | 0.27 | reliable |
| home_away | 67.3% | 0.12 | weakest — under watch, reduce if drops below 65% |
| rest_days | 33.3% | 0.00 | excluded (broken data source, used only for edge scoring) |

---

## Thresholds Quick Reference

```python
# config.py
CONFIDENCE_HIGH     = 0.70  # STRONG PICK
CONFIDENCE_MODERATE = 0.60  # LEAN
CONFIDENCE_LOW      = 0.55  # SLIGHT LEAN / skip boundary
RISK_HIGH           = 0.55  # risk_score >= this → HIGH RISK
RISK_MODERATE       = 0.30  # risk_score >= this → MODERATE RISK
EDGE_STRONG         = 0.40  # edge_score >= this → STRONG EDGE
EDGE_MODERATE       = 0.20
```
