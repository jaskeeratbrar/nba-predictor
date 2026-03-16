"""
NBA Predictor — SQLite Database Layer
======================================
Single source of truth for all persistent data.
Raw ESPN API responses (boxscores, schedules) remain as JSON cache.
Everything processed/derived goes here.
"""

import sqlite3
import os
from datetime import datetime
from config import BASE_DIR

DB_PATH = os.path.join(BASE_DIR, "nba_predictor.db")

# ---------------------------------------------------------------------------
# Connection & schema
# ---------------------------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA cache_size = -32000")
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


def init_schema():
    conn = get_connection()
    c = conn.cursor()
    c.executescript("""
        -- ----------------------------------------------------------------
        -- games: every scheduled or completed game
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS games (
            id                  INTEGER PRIMARY KEY,
            espn_game_id        TEXT UNIQUE,
            game_date           TEXT NOT NULL,
            game_time_utc       TEXT,
            home_team_abbr      TEXT NOT NULL,
            away_team_abbr      TEXT NOT NULL,
            venue               TEXT,
            status              TEXT NOT NULL DEFAULT 'STATUS_SCHEDULED',
            home_score          REAL,
            away_score          REAL,
            actual_winner_abbr  TEXT,
            fetched_at          TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(game_date, home_team_abbr, away_team_abbr)
        );

        -- ----------------------------------------------------------------
        -- predictions: model output per game
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS predictions (
            id                      INTEGER PRIMARY KEY,
            game_id                 INTEGER NOT NULL REFERENCES games(id),
            predicted_at            TEXT NOT NULL,
            home_win_prob           REAL NOT NULL,
            away_win_prob           REAL NOT NULL,
            predicted_winner_abbr   TEXT NOT NULL,
            confidence              REAL NOT NULL,
            recommendation          TEXT NOT NULL,
            home_record_wins        INTEGER,
            home_record_losses      INTEGER,
            away_record_wins        INTEGER,
            away_record_losses      INTEGER,
            home_injuries_count     INTEGER NOT NULL DEFAULT 0,
            away_injuries_count     INTEGER NOT NULL DEFAULT 0,
            factor_win_pct_home     REAL, factor_win_pct_away     REAL,
            factor_recent_form_home REAL, factor_recent_form_away REAL,
            factor_player_form_home REAL, factor_player_form_away REAL,
            factor_home_away_home   REAL, factor_home_away_away   REAL,
            factor_injuries_home    REAL, factor_injuries_away    REAL,
            factor_rest_days_home   REAL, factor_rest_days_away   REAL,
            factor_streak_home      REAL, factor_streak_away      REAL,
            UNIQUE(game_id)
        );

        -- ----------------------------------------------------------------
        -- game_results: post-game analysis output
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS game_results (
            id                      INTEGER PRIMARY KEY,
            game_id                 INTEGER NOT NULL UNIQUE REFERENCES games(id),
            prediction_id           INTEGER NOT NULL REFERENCES predictions(id),
            analyzed_at             TEXT NOT NULL,
            correct                 INTEGER NOT NULL,
            confidence_at_predict   REAL NOT NULL,
            recommendation          TEXT NOT NULL,
            vote_win_pct            TEXT,  vote_win_pct_correct    INTEGER, vote_win_pct_margin    REAL, vote_win_pct_neutral    INTEGER DEFAULT 0,
            vote_recent_form        TEXT,  vote_recent_form_correct INTEGER, vote_recent_form_margin REAL, vote_recent_form_neutral INTEGER DEFAULT 0,
            vote_player_form        TEXT,  vote_player_form_correct INTEGER, vote_player_form_margin REAL, vote_player_form_neutral INTEGER DEFAULT 0,
            vote_home_away          TEXT,  vote_home_away_correct  INTEGER, vote_home_away_margin  REAL, vote_home_away_neutral  INTEGER DEFAULT 0,
            vote_injuries           TEXT,  vote_injuries_correct   INTEGER, vote_injuries_margin   REAL, vote_injuries_neutral   INTEGER DEFAULT 0,
            vote_rest_days          TEXT,  vote_rest_days_correct  INTEGER, vote_rest_days_margin  REAL, vote_rest_days_neutral  INTEGER DEFAULT 0,
            vote_streak             TEXT,  vote_streak_correct     INTEGER, vote_streak_margin     REAL, vote_streak_neutral     INTEGER DEFAULT 0,
            explanation             TEXT
        );

        -- ----------------------------------------------------------------
        -- daily_summary: pre-aggregated per-date rollup
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS daily_summary (
            id                  INTEGER PRIMARY KEY,
            summary_date        TEXT NOT NULL UNIQUE,
            analyzed_at         TEXT NOT NULL,
            total_games         INTEGER NOT NULL,
            correct_games       INTEGER NOT NULL,
            accuracy            REAL NOT NULL,
            win_pct_correct     INTEGER NOT NULL DEFAULT 0, win_pct_total     INTEGER NOT NULL DEFAULT 0,
            recent_form_correct INTEGER NOT NULL DEFAULT 0, recent_form_total INTEGER NOT NULL DEFAULT 0,
            player_form_correct INTEGER NOT NULL DEFAULT 0, player_form_total INTEGER NOT NULL DEFAULT 0,
            home_away_correct   INTEGER NOT NULL DEFAULT 0, home_away_total   INTEGER NOT NULL DEFAULT 0,
            injuries_correct    INTEGER NOT NULL DEFAULT 0, injuries_total    INTEGER NOT NULL DEFAULT 0,
            rest_days_correct   INTEGER NOT NULL DEFAULT 0, rest_days_total   INTEGER NOT NULL DEFAULT 0,
            streak_correct      INTEGER NOT NULL DEFAULT 0, streak_total      INTEGER NOT NULL DEFAULT 0
        );

        -- ----------------------------------------------------------------
        -- standings_snapshots: daily standings history
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS standings_snapshots (
            id              INTEGER PRIMARY KEY,
            snapshot_date   TEXT NOT NULL,
            team_abbr       TEXT NOT NULL,
            team_name       TEXT NOT NULL,
            conference      TEXT NOT NULL,
            wins            INTEGER NOT NULL,
            losses          INTEGER NOT NULL,
            win_pct         REAL NOT NULL,
            streak          TEXT,
            home_wins       INTEGER, home_losses  INTEGER,
            away_wins       INTEGER, away_losses  INTEGER,
            last_10_wins    INTEGER, last_10_losses INTEGER,
            fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(snapshot_date, team_abbr)
        );

        -- ----------------------------------------------------------------
        -- injuries: point-in-time injury log
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS injuries (
            id              INTEGER PRIMARY KEY,
            snapshot_date   TEXT NOT NULL,
            team_abbr       TEXT NOT NULL,
            player_name     TEXT NOT NULL,
            position        TEXT,
            status          TEXT NOT NULL,
            injury_type     TEXT,
            detail          TEXT,
            fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(snapshot_date, team_abbr, player_name)
        );

        -- ----------------------------------------------------------------
        -- player_game_stats: per player per game from boxscores
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS player_game_stats (
            id              INTEGER PRIMARY KEY,
            espn_game_id    TEXT NOT NULL,
            game_date       TEXT,
            team_abbr       TEXT NOT NULL,
            player_id       TEXT NOT NULL,
            player_name     TEXT NOT NULL,
            starter         INTEGER NOT NULL DEFAULT 0,
            minutes         REAL,
            pts             REAL,
            fg_made         INTEGER, fg_att INTEGER, fg_pct REAL,
            fg3_pct         REAL,
            ft_pct          REAL,
            reb             REAL,
            ast             REAL,
            plus_minus      REAL,
            form_score      REAL,
            UNIQUE(espn_game_id, team_abbr, player_id)
        );

        -- ----------------------------------------------------------------
        -- player_form_snapshots: computed 5-game rolling form per date
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS player_form_snapshots (
            id              INTEGER PRIMARY KEY,
            snapshot_date   TEXT NOT NULL,
            team_abbr       TEXT NOT NULL,
            player_id       TEXT NOT NULL,
            player_name     TEXT NOT NULL,
            starter         INTEGER NOT NULL DEFAULT 0,
            games_played    INTEGER NOT NULL,
            pts_avg         REAL, fg_pct_avg REAL, fg3_pct_avg REAL,
            plus_minus_avg  REAL, minutes_avg REAL, form_score REAL,
            UNIQUE(snapshot_date, team_abbr, player_id)
        );

        -- ----------------------------------------------------------------
        -- team_recent_form: game-by-game W/L record per team
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS team_recent_form (
            id              INTEGER PRIMARY KEY,
            team_abbr       TEXT NOT NULL,
            espn_game_id    TEXT NOT NULL,
            game_date_utc   TEXT NOT NULL,
            home_away       TEXT NOT NULL,
            opp_abbr        TEXT NOT NULL,
            team_score      REAL,
            opp_score       REAL,
            win             INTEGER,
            UNIQUE(team_abbr, espn_game_id)
        );

        -- ----------------------------------------------------------------
        -- weights_history: audit trail of weights active on each prediction date
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS weights_history (
            id                  INTEGER PRIMARY KEY,
            effective_date      TEXT NOT NULL,
            source              TEXT NOT NULL DEFAULT 'config',
            win_pct             REAL,
            recent_form         REAL,
            player_form         REAL,
            home_away           REAL,
            injuries            REAL,
            rest_days           REAL,
            streak              REAL,
            total_games_at_time INTEGER NOT NULL DEFAULT 0,
            recorded_at         TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- ----------------------------------------------------------------
        -- team_efficiency_snapshots: daily ESPN team stat snapshots
        -- ----------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS team_efficiency_snapshots (
            id              INTEGER PRIMARY KEY,
            snapshot_date   TEXT NOT NULL,
            team_abbr       TEXT NOT NULL,
            ppg             REAL,
            fg_pct          REAL,
            fg3_pct         REAL,
            ft_pct          REAL,
            reb_pg          REAL,
            ast_pg          REAL,
            fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(snapshot_date, team_abbr)
        );

        -- ----------------------------------------------------------------
        -- Indices
        -- ----------------------------------------------------------------
        CREATE INDEX IF NOT EXISTS idx_tes_team_date        ON team_efficiency_snapshots(team_abbr, snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_wh_date             ON weights_history(effective_date);
        CREATE INDEX IF NOT EXISTS idx_games_date          ON games(game_date);
        CREATE INDEX IF NOT EXISTS idx_games_home          ON games(home_team_abbr);
        CREATE INDEX IF NOT EXISTS idx_games_away          ON games(away_team_abbr);
        CREATE INDEX IF NOT EXISTS idx_games_status        ON games(status);
        CREATE INDEX IF NOT EXISTS idx_preds_game          ON predictions(game_id);
        CREATE INDEX IF NOT EXISTS idx_preds_conf          ON predictions(confidence);
        CREATE INDEX IF NOT EXISTS idx_preds_rec           ON predictions(recommendation);
        CREATE INDEX IF NOT EXISTS idx_results_game        ON game_results(game_id);
        CREATE INDEX IF NOT EXISTS idx_results_correct     ON game_results(correct);
        CREATE INDEX IF NOT EXISTS idx_daily_date          ON daily_summary(summary_date);
        CREATE INDEX IF NOT EXISTS idx_standings_team      ON standings_snapshots(team_abbr);
        CREATE INDEX IF NOT EXISTS idx_standings_date      ON standings_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_injuries_team_date  ON injuries(team_abbr, snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_pgs_player          ON player_game_stats(player_id);
        CREATE INDEX IF NOT EXISTS idx_pgs_team_game       ON player_game_stats(team_abbr, espn_game_id);
        CREATE INDEX IF NOT EXISTS idx_pfs_player_date     ON player_form_snapshots(player_id, snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_pfs_team_date       ON player_form_snapshots(team_abbr, snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_trf_team_date       ON team_recent_form(team_abbr, game_date_utc);
    """)
    conn.commit()

    # Migrate predictions table: add columns added after initial schema creation.
    # SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we try/except each.
    for _col, _coltype in [("play_type", "TEXT"), ("risk_score", "REAL"), ("edge_score", "REAL")]:
        try:
            conn.execute(f"ALTER TABLE predictions ADD COLUMN {_col} {_coltype}")
        except Exception:
            pass  # column already exists
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

def upsert_game(conn, game: dict) -> int:
    """Insert or ignore a game row. Returns the game's id."""
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO games
            (espn_game_id, game_date, game_time_utc, home_team_abbr, away_team_abbr,
             venue, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        game.get("espn_game_id"),
        game["game_date"],
        game.get("game_time_utc"),
        game["home_team_abbr"],
        game["away_team_abbr"],
        game.get("venue"),
        game.get("status", "STATUS_SCHEDULED"),
    ))
    c.execute("""
        SELECT id FROM games
        WHERE game_date = ? AND home_team_abbr = ? AND away_team_abbr = ?
    """, (game["game_date"], game["home_team_abbr"], game["away_team_abbr"]))
    row = c.fetchone()
    return row["id"] if row else None


def finalize_game(conn, game_date: str, home_abbr: str, away_abbr: str,
                  home_score: float, away_score: float, status: str = "STATUS_FINAL"):
    actual_winner = home_abbr if home_score > away_score else away_abbr
    conn.execute("""
        UPDATE games SET home_score=?, away_score=?, actual_winner_abbr=?, status=?
        WHERE game_date=? AND home_team_abbr=? AND away_team_abbr=?
    """, (home_score, away_score, actual_winner, status, game_date, home_abbr, away_abbr))


def get_game_id(conn, game_date: str, home_abbr: str, away_abbr: str):
    c = conn.execute("""
        SELECT id FROM games WHERE game_date=? AND home_team_abbr=? AND away_team_abbr=?
    """, (game_date, home_abbr, away_abbr))
    row = c.fetchone()
    return row["id"] if row else None


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

def _parse_record(record_str):
    """'42-21' → (42, 21)"""
    try:
        w, l = record_str.split("-")
        return int(w), int(l)
    except Exception:
        return None, None


def upsert_predictions(conn, date_str: str, predictions: list):
    """Save all predictions for a date. Idempotent — replaces on re-run."""
    predicted_at = datetime.now().isoformat()
    for pred in predictions:
        home_abbr = pred["home_abbr"]
        away_abbr = pred["away_abbr"]

        game_id = upsert_game(conn, {
            "game_date":     date_str,
            "home_team_abbr": home_abbr,
            "away_team_abbr": away_abbr,
            "venue":         pred.get("venue"),
            "game_time_utc": pred.get("game_time"),
            "status":        "STATUS_SCHEDULED",
        })
        if not game_id:
            continue

        hw, hl = _parse_record(pred.get("home_record", ""))
        aw, al = _parse_record(pred.get("away_record", ""))
        factors = pred.get("factors", {})

        def fv(factor, side):
            return factors.get(factor, {}).get(side)

        conn.execute("""
            INSERT OR REPLACE INTO predictions (
                game_id, predicted_at,
                home_win_prob, away_win_prob,
                predicted_winner_abbr, confidence, recommendation,
                home_record_wins, home_record_losses,
                away_record_wins, away_record_losses,
                home_injuries_count, away_injuries_count,
                factor_win_pct_home,     factor_win_pct_away,
                factor_recent_form_home, factor_recent_form_away,
                factor_player_form_home, factor_player_form_away,
                factor_home_away_home,   factor_home_away_away,
                factor_injuries_home,    factor_injuries_away,
                factor_rest_days_home,   factor_rest_days_away,
                factor_streak_home,      factor_streak_away,
                play_type, risk_score, edge_score
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            game_id, predicted_at,
            pred.get("home_win_prob"), pred.get("away_win_prob"),
            pred.get("predicted_winner"), pred.get("confidence"),
            pred.get("recommendation"),
            hw, hl, aw, al,
            pred.get("home_injuries", 0), pred.get("away_injuries", 0),
            fv("win_pct","home"),     fv("win_pct","away"),
            fv("recent_form","home"), fv("recent_form","away"),
            fv("player_form","home"), fv("player_form","away"),
            fv("home_away","home"),   fv("home_away","away"),
            fv("injuries","home"),    fv("injuries","away"),
            fv("rest_days","home"),   fv("rest_days","away"),
            fv("streak","home"),      fv("streak","away"),
            pred.get("play_type"), pred.get("risk_score"), pred.get("edge_score"),
        ))


def load_predictions(conn, date_str: str) -> list:
    """Load predictions for a date, joined with game info."""
    rows = conn.execute("""
        SELECT p.*, g.home_team_abbr, g.away_team_abbr, g.venue, g.game_time_utc,
               g.home_score, g.away_score, g.actual_winner_abbr, g.status
        FROM predictions p
        JOIN games g ON g.id = p.game_id
        WHERE g.game_date = ?
        ORDER BY p.confidence DESC
    """, (date_str,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Game results (post-game analysis)
# ---------------------------------------------------------------------------

def upsert_game_result(conn, game_date: str, analysis: dict):
    """Save post-game analysis for one game."""
    home_abbr = analysis["home_abbr"]
    away_abbr = analysis["away_abbr"]

    game_id = get_game_id(conn, game_date, home_abbr, away_abbr)
    if not game_id:
        return

    # Finalize game scores
    finalize_game(conn, game_date, home_abbr, away_abbr,
                  analysis.get("home_score", 0), analysis.get("away_score", 0))

    pred_row = conn.execute(
        "SELECT id FROM predictions WHERE game_id=?", (game_id,)
    ).fetchone()
    if not pred_row:
        return
    pred_id = pred_row["id"]

    analyzed_at = datetime.now().isoformat()
    fv = analysis.get("factor_votes", {})

    def _col(factor, key):
        fdata = fv.get(factor, {})
        if key == "correct":
            v = fdata.get("correct")
            return int(v) if v is not None else None
        if key == "neutral":
            return int(fdata.get("neutral", False))
        return fdata.get(key)

    conn.execute("""
        INSERT OR REPLACE INTO game_results (
            game_id, prediction_id, analyzed_at, correct,
            confidence_at_predict, recommendation,
            vote_win_pct,      vote_win_pct_correct,      vote_win_pct_margin,      vote_win_pct_neutral,
            vote_recent_form,  vote_recent_form_correct,  vote_recent_form_margin,  vote_recent_form_neutral,
            vote_player_form,  vote_player_form_correct,  vote_player_form_margin,  vote_player_form_neutral,
            vote_home_away,    vote_home_away_correct,    vote_home_away_margin,    vote_home_away_neutral,
            vote_injuries,     vote_injuries_correct,     vote_injuries_margin,     vote_injuries_neutral,
            vote_rest_days,    vote_rest_days_correct,    vote_rest_days_margin,    vote_rest_days_neutral,
            vote_streak,       vote_streak_correct,       vote_streak_margin,       vote_streak_neutral,
            explanation
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        game_id, pred_id, analyzed_at, int(analysis.get("correct", 0)),
        analysis.get("confidence"), analysis.get("recommendation"),
        _col("win_pct","voted_for"),     _col("win_pct","correct"),     _col("win_pct","margin"),     _col("win_pct","neutral"),
        _col("recent_form","voted_for"), _col("recent_form","correct"), _col("recent_form","margin"), _col("recent_form","neutral"),
        _col("player_form","voted_for"), _col("player_form","correct"), _col("player_form","margin"), _col("player_form","neutral"),
        _col("home_away","voted_for"),   _col("home_away","correct"),   _col("home_away","margin"),   _col("home_away","neutral"),
        _col("injuries","voted_for"),    _col("injuries","correct"),    _col("injuries","margin"),    _col("injuries","neutral"),
        _col("rest_days","voted_for"),   _col("rest_days","correct"),   _col("rest_days","margin"),   _col("rest_days","neutral"),
        _col("streak","voted_for"),      _col("streak","correct"),      _col("streak","margin"),      _col("streak","neutral"),
        analysis.get("explanation"),
    ))


def upsert_daily_summary(conn, date_str: str, summary: dict, factor_acc: dict):
    analyzed_at = datetime.now().isoformat()

    def _c(f): return factor_acc.get(f, {}).get("correct", 0)
    def _t(f): return factor_acc.get(f, {}).get("total", 0)

    conn.execute("""
        INSERT OR REPLACE INTO daily_summary (
            summary_date, analyzed_at, total_games, correct_games, accuracy,
            win_pct_correct, win_pct_total,
            recent_form_correct, recent_form_total,
            player_form_correct, player_form_total,
            home_away_correct, home_away_total,
            injuries_correct, injuries_total,
            rest_days_correct, rest_days_total,
            streak_correct, streak_total
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        date_str, analyzed_at,
        summary.get("total", 0), summary.get("correct", 0), summary.get("accuracy", 0),
        _c("win_pct"),     _t("win_pct"),
        _c("recent_form"), _t("recent_form"),
        _c("player_form"), _t("player_form"),
        _c("home_away"),   _t("home_away"),
        _c("injuries"),    _t("injuries"),
        _c("rest_days"),   _t("rest_days"),
        _c("streak"),      _t("streak"),
    ))


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def upsert_standings_snapshot(conn, date_str: str, standings: dict):
    def _parse_rec(s):
        try:
            w, l = s.split("-"); return int(w), int(l)
        except Exception:
            return None, None

    rows = []
    for abbr, s in standings.items():
        hw, hl = _parse_rec(s.get("home_record", ""))
        aw, al = _parse_rec(s.get("away_record", ""))
        l10w, l10l = _parse_rec(s.get("last_10", ""))
        rows.append((
            date_str, abbr, s.get("name", abbr), s.get("conference", ""),
            s.get("wins", 0), s.get("losses", 0), s.get("win_pct", 0.5),
            str(s.get("streak", "")),
            hw, hl, aw, al, l10w, l10l,
        ))

    conn.executemany("""
        INSERT OR REPLACE INTO standings_snapshots
            (snapshot_date, team_abbr, team_name, conference,
             wins, losses, win_pct, streak,
             home_wins, home_losses, away_wins, away_losses,
             last_10_wins, last_10_losses)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)


def load_latest_standings(conn) -> dict:
    rows = conn.execute("""
        SELECT * FROM standings_snapshots
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM standings_snapshots)
    """).fetchall()
    return {r["team_abbr"]: dict(r) for r in rows}


# ---------------------------------------------------------------------------
# Injuries
# ---------------------------------------------------------------------------

def upsert_injuries_snapshot(conn, date_str: str, injuries: dict):
    rows = []
    for team_abbr, players in injuries.items():
        for p in players:
            rows.append((
                date_str, team_abbr,
                p.get("name", "Unknown"), p.get("position"),
                p.get("status", ""), p.get("injury", ""), p.get("detail", ""),
            ))
    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO injuries
                (snapshot_date, team_abbr, player_name, position,
                 status, injury_type, detail)
            VALUES (?,?,?,?,?,?,?)
        """, rows)


# ---------------------------------------------------------------------------
# Player game stats
# ---------------------------------------------------------------------------

def upsert_player_game_stats(conn, espn_game_id: str, game_date: str,
                              team_players: dict):
    """
    team_players: {team_abbr: [player_dicts]} from fetch_boxscore_players()
    """
    rows = []
    for team_abbr, players in team_players.items():
        for p in players:
            rows.append((
                espn_game_id, game_date, team_abbr,
                p.get("id", p.get("name")), p.get("name"),
                int(p.get("starter", False)),
                p.get("minutes"), p.get("pts"),
                p.get("fg_made"), p.get("fg_att"), p.get("fg_pct"),
                p.get("fg3_pct"), p.get("ft_pct"),
                p.get("reb"), p.get("ast"), p.get("plus_minus"),
                p.get("form_score"),
            ))
    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO player_game_stats
                (espn_game_id, game_date, team_abbr, player_id, player_name,
                 starter, minutes, pts, fg_made, fg_att, fg_pct,
                 fg3_pct, ft_pct, reb, ast, plus_minus, form_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)


def player_stats_exist(conn, espn_game_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM player_game_stats WHERE espn_game_id=? LIMIT 1",
        (espn_game_id,)
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Player form snapshots
# ---------------------------------------------------------------------------

def upsert_player_form_snapshot(conn, date_str: str, team_abbr: str, form: dict):
    rows = []
    for pid, p in form.items():
        rows.append((
            date_str, team_abbr, pid, p.get("name"),
            int(p.get("starter", False)), p.get("games_played", 0),
            p.get("pts_avg"), p.get("fg_pct_avg"), p.get("fg3_pct_avg"),
            p.get("plus_minus_avg"), p.get("minutes_avg"), p.get("form_score"),
        ))
    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO player_form_snapshots
                (snapshot_date, team_abbr, player_id, player_name,
                 starter, games_played, pts_avg, fg_pct_avg, fg3_pct_avg,
                 plus_minus_avg, minutes_avg, form_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)


# ---------------------------------------------------------------------------
# Team recent form
# ---------------------------------------------------------------------------

def upsert_team_recent_form(conn, team_abbr: str, games: list):
    rows = []
    for g in games:
        if not g.get("game_id"):
            continue
        rows.append((
            team_abbr, g["game_id"], g.get("date", ""),
            g.get("home_away", ""), g.get("opp_abbr", ""),
            g.get("team_score"), g.get("opp_score"),
            int(g.get("win", False)) if g.get("win") is not None else None,
        ))
    if rows:
        conn.executemany("""
            INSERT OR IGNORE INTO team_recent_form
                (team_abbr, espn_game_id, game_date_utc, home_away,
                 opp_abbr, team_score, opp_score, win)
            VALUES (?,?,?,?,?,?,?,?)
        """, rows)


# ---------------------------------------------------------------------------
# Analytics queries
# ---------------------------------------------------------------------------

def get_cumulative_factor_accuracy(conn, last_n_days: int = None) -> dict:
    """Return accuracy per factor, optionally limited to last N days."""
    where = ""
    params = ()
    if last_n_days:
        where = f"WHERE summary_date >= date('now', '-{last_n_days} days')"

    row = conn.execute(f"""
        SELECT
            SUM(win_pct_correct)     * 1.0 / NULLIF(SUM(win_pct_total), 0)     AS win_pct,
            SUM(recent_form_correct) * 1.0 / NULLIF(SUM(recent_form_total), 0) AS recent_form,
            SUM(player_form_correct) * 1.0 / NULLIF(SUM(player_form_total), 0) AS player_form,
            SUM(home_away_correct)   * 1.0 / NULLIF(SUM(home_away_total), 0)   AS home_away,
            SUM(injuries_correct)    * 1.0 / NULLIF(SUM(injuries_total), 0)    AS injuries,
            SUM(rest_days_correct)   * 1.0 / NULLIF(SUM(rest_days_total), 0)   AS rest_days,
            SUM(streak_correct)      * 1.0 / NULLIF(SUM(streak_total), 0)      AS streak,
            SUM(correct_games)       * 1.0 / NULLIF(SUM(total_games), 0)       AS overall,
            SUM(total_games) AS total_games, SUM(correct_games) AS total_correct,
            SUM(win_pct_total) AS win_pct_votes, SUM(recent_form_total) AS recent_form_votes,
            SUM(player_form_total) AS player_form_votes, SUM(home_away_total) AS home_away_votes,
            SUM(injuries_total) AS injuries_votes, SUM(rest_days_total) AS rest_days_votes,
            SUM(streak_total) AS streak_votes
        FROM daily_summary {where}
    """, params).fetchone()
    return dict(row) if row else {}


def get_accuracy_by_confidence_tier(conn) -> list:
    rows = conn.execute("""
        SELECT
            p.recommendation,
            COUNT(*) AS total,
            SUM(gr.correct) AS correct,
            ROUND(SUM(gr.correct) * 1.0 / COUNT(*), 4) AS accuracy,
            ROUND(AVG(p.confidence), 4) AS avg_confidence
        FROM game_results gr
        JOIN predictions p ON gr.prediction_id = p.id
        GROUP BY p.recommendation
        ORDER BY avg_confidence DESC
    """).fetchall()
    return [dict(r) for r in rows]


def get_model_accuracy_summary(conn) -> dict:
    row = conn.execute("""
        SELECT COUNT(*) AS total, SUM(correct) AS correct,
               ROUND(SUM(correct) * 1.0 / COUNT(*), 4) AS accuracy
        FROM game_results
    """).fetchone()
    return dict(row) if row else {}


def get_team_prediction_history(conn, team_abbr: str, limit: int = 20) -> list:
    rows = conn.execute("""
        SELECT g.game_date, g.home_team_abbr, g.away_team_abbr,
               p.predicted_winner_abbr, g.actual_winner_abbr,
               p.confidence, p.recommendation,
               gr.correct, g.home_score, g.away_score
        FROM games g
        JOIN predictions p ON p.game_id = g.id
        LEFT JOIN game_results gr ON gr.game_id = g.id
        WHERE g.home_team_abbr = ? OR g.away_team_abbr = ?
        ORDER BY g.game_date DESC
        LIMIT ?
    """, (team_abbr, team_abbr, limit)).fetchall()
    return [dict(r) for r in rows]


def get_player_form_trend(conn, player_id: str, last_n: int = 10) -> list:
    rows = conn.execute("""
        SELECT snapshot_date, player_name, team_abbr,
               pts_avg, fg_pct_avg, plus_minus_avg, form_score, games_played
        FROM player_form_snapshots
        WHERE player_id = ?
        ORDER BY snapshot_date DESC
        LIMIT ?
    """, (player_id, last_n)).fetchall()
    return [dict(r) for r in rows]


def save_weights_snapshot(conn, date_str: str, weights: dict,
                          source: str = "config", total_games: int = 0):
    """Record which weights were active for predictions on a given date."""
    conn.execute("""
        INSERT INTO weights_history
            (effective_date, source, win_pct, recent_form, player_form,
             home_away, injuries, rest_days, streak, total_games_at_time)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        date_str, source,
        weights.get("win_pct"), weights.get("recent_form"), weights.get("player_form"),
        weights.get("home_away"), weights.get("injuries"), weights.get("rest_days"),
        weights.get("streak"), total_games,
    ))


def upsert_team_efficiency_snapshot(conn, date_str: str, team_abbr: str, stats: dict):
    """Store daily team efficiency snapshot from ESPN."""
    conn.execute("""
        INSERT OR REPLACE INTO team_efficiency_snapshots
            (snapshot_date, team_abbr, ppg, fg_pct, fg3_pct, ft_pct, reb_pg, ast_pg)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        date_str, team_abbr,
        stats.get("ppg"), stats.get("fg_pct"), stats.get("fg3_pct"),
        stats.get("ft_pct"), stats.get("reb_pg"), stats.get("ast_pg"),
    ))


def get_high_confidence_misses(conn, min_confidence: float = 0.70) -> list:
    rows = conn.execute("""
        SELECT g.game_date, g.home_team_abbr, g.away_team_abbr,
               p.confidence, p.recommendation,
               p.predicted_winner_abbr, g.actual_winner_abbr,
               gr.explanation
        FROM game_results gr
        JOIN predictions p ON gr.prediction_id = p.id
        JOIN games g ON g.id = gr.game_id
        WHERE gr.correct = 0 AND p.confidence >= ?
        ORDER BY p.confidence DESC
    """, (min_confidence,)).fetchall()
    return [dict(r) for r in rows]
