"""
NBA Data Manager
Handles loading, saving, and fetching NBA data from multiple sources.
Falls back gracefully when APIs are unavailable.
"""

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from config import DATA_DIR, HISTORY_DIR, TEAMS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(url, headers=None, timeout=12):
    """Simple HTTP GET with optional headers."""
    if headers is None:
        headers = {"User-Agent": "Mozilla/5.0 (NBAPredictor/1.0)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _safe_float(val, default=0.0):
    if isinstance(val, dict):
        val = val.get("value", default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# ESPN-based fetchers (primary)
# ---------------------------------------------------------------------------

_ABBR_NORMALIZE = {
    "NY": "NYK", "SA": "SAS", "NO": "NOP", "WSH": "WAS",
    "GS": "GSW", "UTAH": "UTA",
}

# ESPN uses non-standard slugs for some teams in the team schedule URL
_ESPN_URL_SLUG = {
    "NOP": "no",
    "UTA": "utah",
}

def fetch_schedule_espn(date_str):
    """
    Fetch NBA schedule for a given date from ESPN API.
    date_str: 'YYYY-MM-DD'
    Returns list of game dicts.
    """
    dt = date_str.replace("-", "")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={dt}"
    data = _get(url)
    if not data or "events" not in data:
        return None

    games = []
    for event in data["events"]:
        comps = event.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        if len(competitors) < 2:
            continue

        home = away = None
        for c in competitors:
            team_info = c.get("team", {})
            abbr = _ABBR_NORMALIZE.get(team_info.get("abbreviation", ""), team_info.get("abbreviation", ""))
            record_items = c.get("records", [{}])
            record_str = record_items[0].get("summary", "0-0") if record_items else "0-0"
            parts = record_str.split("-")
            wins = int(parts[0]) if len(parts) == 2 else 0
            losses = int(parts[1]) if len(parts) == 2 else 0

            entry = {
                "abbr": abbr,
                "name": team_info.get("displayName", abbr),
                "wins": wins,
                "losses": losses,
                "score": _safe_float(c.get("score", 0)),
            }
            if c.get("homeAway") == "home":
                home = entry
            else:
                away = entry

        if home and away:
            status = event.get("status", {}).get("type", {})
            games.append({
                "home": home,
                "away": away,
                "date": date_str,
                "time": event.get("date", ""),
                "status": status.get("name", "STATUS_SCHEDULED"),
                "venue": comps.get("venue", {}).get("fullName", ""),
            })

    return games if games else None


def fetch_standings_espn():
    """Fetch current NBA standings from ESPN API."""
    url = "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
    data = _get(url)
    if not data:
        return None

    standings = {}
    for child in data.get("children", []):
        conf = child.get("abbreviation", "")
        for entry in child.get("standings", {}).get("entries", []):
            team = entry.get("team", {})
            abbr = team.get("abbreviation", "")
            # Build stats dict by abbreviation for numeric values only
            stats = {s["abbreviation"]: s["value"] for s in entry.get("stats", []) if "abbreviation" in s and "value" in s}
            # Record strings (Home, Road, L10) are stored in "summary" keyed by name
            records = {s["name"]: s.get("summary", "") for s in entry.get("stats", []) if "summary" in s}
            wins = int(stats.get("W", stats.get("wins", 0)))
            losses = int(stats.get("L", stats.get("losses", 0)))
            total = wins + losses
            standings[abbr] = {
                "name": team.get("displayName", abbr),
                "abbr": abbr,
                "conference": "East" if "east" in conf.lower() else "West",
                "wins": wins,
                "losses": losses,
                "win_pct": wins / total if total > 0 else 0.5,
                "streak": stats.get("STRK", stats.get("streak", 0)),
                "home_record": records.get("Home", ""),
                "away_record": records.get("Road", ""),
                "last_10": records.get("Last Ten Games", ""),
            }
    return standings if standings else None


def fetch_injuries_espn():
    """
    Fetch current NBA injuries. ESPN doesn't have a clean public API for this,
    so we try the team-level endpoint.
    """
    # ESPN API now uses displayName (full team name) at top level — map to abbreviation
    _NAME_TO_ABBR = {
        "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
        "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
        "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
        "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
        "LA Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
        "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
        "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
        "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
        "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
        "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
    }
    injuries = {}
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    data = _get(url)
    if data and "injuries" in data:
        for team_entry in data["injuries"]:
            display_name = team_entry.get("displayName", "")
            abbr = _NAME_TO_ABBR.get(display_name) or team_entry.get("team", {}).get("abbreviation", "")
            if not abbr:
                continue
            players = []
            for inj in team_entry.get("injuries", []):
                athlete = inj.get("athlete", {})
                players.append({
                    "name": athlete.get("displayName", "Unknown"),
                    "position": athlete.get("position", {}).get("abbreviation", ""),
                    "status": inj.get("status", ""),
                    "injury": inj.get("type", {}).get("description", "Unknown"),
                    "detail": inj.get("longComment", ""),
                })
            if players:
                injuries[abbr] = players
    return injuries if injuries else None


def fetch_recent_games_espn(team_abbr, count=10):
    """Fetch recent game results for a specific team."""
    slug = _ESPN_URL_SLUG.get(team_abbr.upper(), team_abbr.lower())
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{slug}/schedule?season=2026&seasontype=2"
    data = _get(url)
    if not data or "events" not in data:
        return None

    completed = []
    for event in data["events"]:
        status = event.get("competitions", [{}])[0].get("status", {}).get("type", {})
        if status.get("completed", False):
            comps = event["competitions"][0]
            competitors = comps.get("competitors", [])
            result = {}
            for c in competitors:
                t = _ABBR_NORMALIZE.get(c.get("team", {}).get("abbreviation", ""), c.get("team", {}).get("abbreviation", ""))
                s = _safe_float(c.get("score", 0))
                ha = c.get("homeAway", "")
                if t.upper() == team_abbr.upper():
                    result["team_score"] = s
                    result["home_away"] = ha
                else:
                    result["opp_abbr"] = t
                    result["opp_score"] = s
            if "team_score" in result and "opp_score" in result:
                result["win"] = result["team_score"] > result["opp_score"]
                result["date"] = event.get("date", "")
                result["game_id"] = event.get("id", "")
                completed.append(result)

    # Return the most recent `count` games
    return completed[-count:] if completed else None


# ---------------------------------------------------------------------------
# Player form fetchers
# ---------------------------------------------------------------------------

def _parse_fg(fg_str):
    """Parse '7-14' into (made, attempted, pct). Returns (0,0,0) on failure."""
    try:
        parts = str(fg_str).split("-")
        made, att = int(parts[0]), int(parts[1])
        return made, att, made / att if att > 0 else 0.0
    except (ValueError, IndexError):
        return 0, 0, 0.0


def fetch_boxscore_players(game_id):
    """
    Fetch player stats from a single game boxscore.
    Returns {team_abbr: [player_stat_dicts]} for both teams.
    Caches by game_id so shared games between two teams only fetch once.
    """
    cache_file = f"boxscore_{game_id}.json"
    cached = load_data(cache_file)
    if cached:
        return cached

    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    data = _get(url)
    if not data or "boxscore" not in data:
        return {}

    result = {}
    for team_block in data["boxscore"].get("players", []):
        team_abbr = _ABBR_NORMALIZE.get(
            team_block.get("team", {}).get("abbreviation", ""),
            team_block.get("team", {}).get("abbreviation", "")
        )
        stat_cat = team_block.get("statistics", [{}])[0]
        labels = stat_cat.get("labels", [])

        # Build index map for stat positions
        idx = {label: i for i, label in enumerate(labels)}
        players = []

        for entry in stat_cat.get("athletes", []):
            if entry.get("didNotPlay"):
                continue
            ath   = entry.get("athlete", {})
            stats = entry.get("stats", [])

            def _stat(name, default=0):
                i = idx.get(name)
                return stats[i] if i is not None and i < len(stats) else default

            # Parse minutes (e.g. "32:14" → 32.2)
            min_str = _stat("MIN", "0")
            try:
                min_parts = str(min_str).split(":")
                minutes = int(min_parts[0]) + (int(min_parts[1]) / 60 if len(min_parts) > 1 else 0)
            except (ValueError, IndexError):
                minutes = 0.0

            if minutes < 5:
                continue  # skip garbage time

            fg_made, fg_att, fg_pct     = _parse_fg(_stat("FG", "0-0"))
            _, _, fg3_pct               = _parse_fg(_stat("3PT", "0-0"))
            ft_made, ft_att, ft_pct     = _parse_fg(_stat("FT", "0-0"))

            players.append({
                "name":       ath.get("displayName", "Unknown"),
                "id":         ath.get("id", ""),
                "starter":    entry.get("starter", False),
                "minutes":    round(minutes, 1),
                "pts":        _safe_float(_stat("PTS", 0)),
                "fg_made":    fg_made,
                "fg_att":     fg_att,
                "fg_pct":     round(fg_pct, 4),
                "fg3_pct":    round(fg3_pct, 4),
                "ft_made":    ft_made,
                "ft_att":     ft_att,
                "ft_pct":     round(ft_pct, 4),
                "reb":        _safe_float(_stat("REB", 0)),
                "ast":        _safe_float(_stat("AST", 0)),
                "plus_minus": _safe_float(_stat("+/-", 0)),
            })

        if players:
            result[team_abbr] = players

    if result:
        save_data(cache_file, result)
    return result


def fetch_player_form(team_abbr, recent_games, count=5):
    """
    Aggregate player stats across the last `count` completed games.
    recent_games: list of game dicts from fetch_recent_games_espn (includes game_id).
    Returns {player_id: {name, games_played, pts_avg, fg_pct_avg, plus_minus_avg,
                          minutes_avg, starter, form_score}}
    """
    games_to_use = [g for g in recent_games if g.get("game_id")][-count:]
    if not games_to_use:
        return {}

    # Accumulate stats per player across games
    player_totals = {}  # player_id → running totals

    for game in games_to_use:
        gid = game["game_id"]
        boxscores = fetch_boxscore_players(gid)
        team_players = boxscores.get(team_abbr.upper(), [])

        for p in team_players:
            pid = p["id"] or p["name"]
            if pid not in player_totals:
                player_totals[pid] = {
                    "name":         p["name"],
                    "starter":      p["starter"],
                    "games":        0,
                    "pts":          0.0,
                    "fg_made":      0,
                    "fg_att":       0,
                    "ft_att":       0,
                    "plus_minus":   0.0,
                    "minutes":      0.0,
                    "fg3_pct_sum":  0.0,
                }
            t = player_totals[pid]
            t["games"]       += 1
            t["pts"]         += p["pts"]
            t["fg_made"]     += p["fg_made"]
            t["fg_att"]      += p["fg_att"]
            t["ft_att"]      += p.get("ft_att", 0)
            t["plus_minus"]  += p["plus_minus"]
            t["minutes"]     += p["minutes"]
            t["fg3_pct_sum"] += p["fg3_pct"]
            if p["starter"]:
                t["starter"] = True  # mark as starter if started any of these games

    # Compute averages and form score
    result = {}
    for pid, t in player_totals.items():
        g = t["games"]
        if g == 0:
            continue
        pts_avg      = t["pts"] / g
        fg_pct_avg   = t["fg_made"] / t["fg_att"] if t["fg_att"] > 0 else 0.0
        pm_avg       = t["plus_minus"] / g
        min_avg      = t["minutes"] / g
        fg3_pct_avg  = t["fg3_pct_sum"] / g

        # True Shooting %: more position-neutral than raw FG%
        # TS% = pts / (2 * (fg_att + 0.44 * ft_att))
        ts_denom   = 2.0 * (t["fg_att"] + 0.44 * t["ft_att"])
        ts_pct     = t["pts"] / ts_denom if ts_denom > 0 else fg_pct_avg

        pm_boost   = max(0.5, min(1.5, 1.0 + pm_avg / 30.0))
        form_score = pts_avg * max(ts_pct, 0.1) * pm_boost

        result[pid] = {
            "name":           t["name"],
            "starter":        t["starter"],
            "games_played":   g,
            "pts_avg":        round(pts_avg, 2),
            "fg_pct_avg":     round(fg_pct_avg, 4),
            "ts_pct":         round(ts_pct, 4),
            "fg3_pct_avg":    round(fg3_pct_avg, 4),
            "plus_minus_avg": round(pm_avg, 2),
            "minutes_avg":    round(min_avg, 1),
            "form_score":     round(form_score, 4),
        }

    return result


# ---------------------------------------------------------------------------
# Local data persistence
# ---------------------------------------------------------------------------

def save_data(filename, data):
    """Save data to a JSON file in the data directory (atomic write)."""
    filepath = os.path.join(DATA_DIR, filename)
    tmp = filepath + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, filepath)
    return filepath


def load_data(filename):
    """Load data from a JSON file in the data directory."""
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath) as f:
                return json.load(f)
        except json.JSONDecodeError:
            os.remove(filepath)  # purge corrupted file
    return None


def save_history(date_str, data):
    """Save daily predictions or analysis to history (atomic write)."""
    filepath = os.path.join(HISTORY_DIR, f"{date_str}.json")
    tmp = filepath + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, filepath)
    return filepath


def load_history(date_str):
    """Load historical predictions for a given date."""
    filepath = os.path.join(HISTORY_DIR, f"{date_str}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath) as f:
                return json.load(f)
        except json.JSONDecodeError:
            os.remove(filepath)
    return None


def get_all_history_dates():
    """Return sorted list of all dates that have prediction history."""
    dates = []
    for f in os.listdir(HISTORY_DIR):
        if f.endswith(".json"):
            dates.append(f.replace(".json", ""))
    return sorted(dates)


# ---------------------------------------------------------------------------
# Main data refresh
# ---------------------------------------------------------------------------

def refresh_all_data(target_date):
    """
    Fetch and cache all data needed for predictions.
    Returns a dict with schedule, standings, injuries, and recent form.
    """
    print(f"  Fetching schedule for {target_date}...")
    schedule = fetch_schedule_espn(target_date)
    if schedule:
        save_data(f"schedule_{target_date}.json", schedule)
        print(f"    Found {len(schedule)} games")
    else:
        # Try loading cached
        schedule = load_data(f"schedule_{target_date}.json")
        if schedule:
            print(f"    Using cached schedule ({len(schedule)} games)")
        else:
            print("    WARNING: Could not fetch schedule")

    print("  Fetching standings...")
    standings = fetch_standings_espn()
    if standings:
        save_data("standings_current.json", standings)
        print(f"    Got standings for {len(standings)} teams")
    else:
        standings = load_data("standings_current.json")
        if standings:
            print(f"    Using cached standings ({len(standings)} teams)")
        else:
            print("    WARNING: Could not fetch standings")

    print("  Fetching injuries...")
    injuries = fetch_injuries_espn()
    if injuries:
        save_data("injuries_current.json", injuries)
        teams_with_injuries = len(injuries)
        total_injured = sum(len(v) for v in injuries.values())
        print(f"    {total_injured} injuries across {teams_with_injuries} teams")
    else:
        injuries = load_data("injuries_current.json")
        if injuries:
            print("    Using cached injury data")
        else:
            injuries = {}
            print("    No injury data available")

    # Fetch recent form for teams playing today
    recent_form = {}
    if schedule:
        teams_playing = set()
        for game in schedule:
            teams_playing.add(game["home"]["abbr"])
            teams_playing.add(game["away"]["abbr"])

        print(f"  Fetching recent form for {len(teams_playing)} teams...")
        for abbr in teams_playing:
            recent = fetch_recent_games_espn(abbr)
            if recent:
                recent_form[abbr] = recent
                wins = sum(1 for g in recent if g.get("win"))
                print(f"    {abbr}: {wins}-{len(recent)-wins} last {len(recent)}")
            else:
                print(f"    {abbr}: No recent data")

        if recent_form:
            save_data("recent_form.json", recent_form)
    else:
        recent_form = load_data("recent_form.json") or {}

    # Fetch player form for teams playing today
    player_form = {}
    if schedule:
        print(f"  Fetching player form (last 5 games per team)...")
        for abbr in teams_playing:
            team_recent = recent_form.get(abbr, [])
            form = fetch_player_form(abbr, team_recent, count=5)
            if form:
                player_form[abbr] = form
                hot = sum(1 for p in form.values() if p["form_score"] > 7.0 and p["minutes_avg"] >= 15)
                top = sorted(form.values(), key=lambda p: p["form_score"], reverse=True)
                leader = top[0] if top else None
                leader_str = f"  (best: {leader['name']} {leader['pts_avg']}pts {leader['fg_pct_avg']*100:.0f}%FG)" if leader else ""
                print(f"    {abbr}: {len(form)} players tracked, {hot} hot{leader_str}")
            else:
                print(f"    {abbr}: No player data")

        if player_form:
            save_data("player_form.json", player_form)
    else:
        player_form = load_data("player_form.json") or {}

    # Persist to SQLite (non-critical — errors never crash predictions)
    try:
        import db as _db
        _db.init_schema()
        _conn = _db.get_connection()
        if standings:
            _db.upsert_standings_snapshot(_conn, target_date, standings)
        if injuries:
            _db.upsert_injuries_snapshot(_conn, target_date, injuries)
        for _abbr, _games in recent_form.items():
            _db.upsert_team_recent_form(_conn, _abbr, _games)
        for _abbr, _form in player_form.items():
            _db.upsert_player_form_snapshot(_conn, target_date, _abbr, _form)
        _conn.commit()
        _conn.close()
    except Exception as _db_err:
        print(f"  [DB] Data write skipped: {_db_err}")

    return {
        "schedule": schedule or [],
        "standings": standings or {},
        "injuries": injuries or {},
        "recent_form": recent_form,
        "player_form": player_form,
    }
