# API Reference — NBA Predictor

_Last verified: 2026-03-11_

All external data comes from ESPN's public (unauthenticated) APIs.
No API key required. User-Agent header is set to `Mozilla/5.0 (NBAPredictor/1.0)`.
Timeout: 12 seconds per request. All failures return `None` and fall back to cached JSON.

---

## External APIs (ESPN)

### 1. Schedule
**URL:** `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`

**Used by:** `fetch_schedule_espn(date_str)`

**Response path:** `data["events"]` → list of game objects

**Key fields extracted per game:**
```
event
  competitions[0]
    competitors[]          — two entries, one per team
      homeAway             — "home" or "away"
      team.abbreviation    — e.g. "BOS" (may need _ABBR_NORMALIZE: NY→NYK, SA→SAS, GS→GSW, etc.)
      team.displayName     — full name
      records[0].summary   — "35-30" (season W-L)
      score                — current/final score (float)
    venue.fullName         — arena name
  status.type.name         — "STATUS_SCHEDULED" | "STATUS_IN_PROGRESS" | "STATUS_FINAL"
  date                     — ISO timestamp of tip-off
```

**Output dict per game:**
```python
{
  "home": {"abbr", "name", "wins", "losses", "score"},
  "away": {"abbr", "name", "wins", "losses", "score"},
  "date": "YYYY-MM-DD",
  "time": "<ISO timestamp>",
  "status": "STATUS_SCHEDULED",
  "venue": "TD Garden"
}
```

**Quirks:**
- Date format in URL is `YYYYMMDD` (no dashes), not `YYYY-MM-DD`
- Some abbreviations differ: `NY`→`NYK`, `SA`→`SAS`, `GS`→`GSW`, `NO`→`NOP`, `WSH`→`WAS`, `UTAH`→`UTA` — handled by `_ABBR_NORMALIZE`
- Returns `None` (not empty list) when no games exist for that date

---

### 2. Standings
**URL:** `https://site.api.espn.com/apis/v2/sports/basketball/nba/standings`

**Used by:** `fetch_standings_espn()`

**Response path:** `data["children"]` → list of conferences → `standings.entries[]`

**Key fields extracted per team:**
```
child.abbreviation       — conference key (contains "east" or "west")
entry.team.abbreviation  — team abbr
entry.team.displayName   — full name
entry.stats[]
  — numeric stats keyed by "abbreviation": W, L, STRK
  — record strings keyed by "name" with "summary" field:
      "Home"            → e.g. "22-8"
      "Road"            → e.g. "13-17"
      "Last Ten Games"  → e.g. "7-3"
```

**Output dict per team (keyed by abbr):**
```python
{
  "name": "Boston Celtics",
  "abbr": "BOS",
  "conference": "East",          # or "West"
  "wins": 48,
  "losses": 17,
  "win_pct": 0.738,
  "streak": 3,                   # positive = win streak, negative = losing streak
  "home_record": "28-7",
  "away_record": "20-10",
  "last_10": "8-2"               # CRITICAL: used by effective win% blend (60/40)
}
```

**Quirks:**
- `last_10` field is present and populated for all 30 teams throughout the season
- `streak` comes from stat abbreviation `STRK` — value is numeric (positive=W, negative=L)
- No `games_back` or conference rank field — rank must be computed by sorting wins
- Cached to `data/standings_current.json` on each successful fetch

---

### 3. Injuries
**URL:** `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries`

**Used by:** `fetch_injuries_espn()`

**Response path:** `data["injuries"]` → list of team injury blocks

**Key fields extracted per player:**
```
team_entry.displayName        — full team name (e.g. "Boston Celtics") — used for abbr lookup
  injuries[]
    athlete.displayName       — player name
    athlete.position.abbreviation — "PG", "SG", "SF", "PF", "C", "G", "F"
    status                    — "Out" | "Doubtful" | "Questionable" | "Day-To-Day" | "Probable"
    type.description          — injury type (e.g. "Knee", "Ankle")
    longComment               — detail string (e.g. "Out for season")
```

**Output dict (keyed by team abbr):**
```python
{
  "BOS": [
    {
      "name": "Kristaps Porzingis",
      "position": "C",
      "status": "Out",
      "injury": "Leg",
      "detail": "Out indefinitely"
    },
    ...
  ]
}
```

**Quirks:**
- ESPN switched from `team.abbreviation` to `displayName` at the top level (broke in 2026-03 season) — fixed by `_NAME_TO_ABBR` lookup dict
- Only teams WITH injuries appear in the response — healthy teams are absent (normal)
- Typically 25-29 teams returned (1-5 teams fully healthy on any given day)
- The model uses `status in ("Out", "Doubtful")` as the active injury threshold
- Cached to `data/injuries_current.json`

---

### 4. Recent Games (Team Schedule)
**URL:** `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{slug}/schedule?season=2026&seasontype=2`

**Used by:** `fetch_recent_games_espn(team_abbr, count=10)`

**Slug note:** Most teams use lowercase abbr (e.g. `bos`, `lal`). Exceptions handled by `_ESPN_URL_SLUG`:
- `NOP` → `no`
- `UTA` → `utah`

**Response path:** `data["events"]` → filters to `competitions[0].status.type.completed == True`

**Output list per game:**
```python
{
  "team_score": 112.0,
  "opp_score": 105.0,
  "opp_abbr": "MIA",
  "home_away": "home",     # or "away"
  "win": True,
  "date": "<ISO timestamp>",
  "game_id": "401705123"   # used for boxscore lookup
}
```

**Returns:** Last `count` completed games (default 10). Used by `recent_form_factor` and as input to `fetch_player_form`.

---

### 5. Boxscore / Player Stats
**URL:** `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}`

**Used by:** `fetch_boxscore_players(game_id)`

**Response path:** `data["boxscore"]["players"]` → two team blocks

**Key fields extracted per player:**
```
statistics[0].labels[]    — column names: MIN, PTS, FG, 3PT, FT, REB, AST, BLK, STL, +/-
statistics[0].athletes[]
  athlete.displayName
  athlete.id
  starter                 — bool
  didNotPlay              — bool (skip these)
  stats[]                 — values aligned to labels[]
```

**Output per player (after aggregation in `fetch_player_form`):**
```python
{
  "name": "Jayson Tatum",
  "starter": True,
  "games_played": 5,
  "pts_avg": 26.4,
  "reb_avg": 8.1,
  "ast_avg": 4.9,
  "blk_avg": 0.6,
  "stl_avg": 1.1,
  "fg_pct_avg": 0.4612,
  "ts_pct": 0.5831,        # True Shooting % — pts / (2 * (fga + 0.44*fta))
  "fg3_pct_avg": 0.3750,
  "plus_minus_avg": 8.2,
  "minutes_avg": 36.5,
  "form_score": 18.43      # composite impact score used by player_form_factor
}
```

**form_score formula:**
```
impact = pts + reb*1.1 + ast*1.2 + blk*2.5 + stl*2.0
pm_boost = clamp(1.0 + plus_minus/30, 0.5, 1.5)
form_score = impact * max(ts_pct, 0.1) * pm_boost
```

**Quirks:**
- Minutes parsed from `"32:14"` string format
- Players with < 5 minutes excluded (garbage time filter)
- Results cached by `game_id` to `data/boxscore_{game_id}.json` — shared across teams
- Uses last 10 games for form (was 5 before 2026-03-10 change)

---

## Local Server Endpoints

Server runs on `http://localhost:6789`. Started by `server.py 6789`.

### GET /status
Health check. Returns:
```json
{"status": "ok", "time": "2026-03-11T00:10:51.069408"}
```

### GET /run?fmt=text
Runs full prediction pipeline for today's games.
- Calls `refresh_all_data()` → fetches all 5 external APIs above
- Runs `predict_game()` for each game
- Saves `public/index.html` (Vercel dashboard)
- Saves `history/YYYY-MM-DD.json`

`fmt=text` returns human-readable picks. Without `fmt`, returns JSON.

### GET /analyze?date=YYYY-MM-DD
Scores yesterday's predictions against actual results.
- Fetches final scores from ESPN scoreboard for that date
- Joins against stored predictions in `history/YYYY-MM-DD.json`
- Updates `performance/factor_accuracy.json` (learning ledger)
- Persists results to SQLite `game_results` table

Returns JSON with `correct`, `total`, `games_analyzed`, per-game breakdown.

---

## Fallback Behavior

All fetchers follow the same pattern:
1. Try live ESPN API
2. On failure → load from `data/*.json` cache
3. If cache also missing → return `None` / empty dict
4. Predictions still run with degraded data (missing factors default to 0.5 neutral)

Cache files:
- `data/schedule_YYYY-MM-DD.json`
- `data/standings_current.json`
- `data/injuries_current.json`
- `data/recent_form.json`
- `data/player_form.json`
- `data/boxscore_{game_id}.json` (per-game, persistent)

---

## Known Historical Issues

| Date | Issue | Status |
|------|-------|--------|
| All of 2025-26 until 2026-03-09 | ESPN injury API changed structure — `displayName` moved to top level, all injuries silently dropped | Fixed 2026-03-09 via `_NAME_TO_ABBR` lookup |
| Ongoing | REST days factor reads near-zero margins from DB due to timing bug | Not fixed — factor effectively frozen at neutral |
