"""
NBA Prediction Engine
Computes win probabilities using multiple weighted factors.
"""

from config import WEIGHTS, HOME_COURT_BOOST, CONFIDENCE_HIGH, CONFIDENCE_MODERATE, CONFIDENCE_LOW


def _safe_div(a, b, default=0.5):
    return a / b if b != 0 else default


def compute_win_pct_factor(home_standings, away_standings):
    """
    Compare overall season win percentages.
    Uses power scaling to amplify differences between teams.
    Returns (home_edge, away_edge) each in [0, 1].
    """
    h_pct = home_standings.get("win_pct", 0.5)
    a_pct = away_standings.get("win_pct", 0.5)

    # Power scaling: amplify gaps between good and bad teams
    # A .750 team vs .400 team should show a much bigger edge than raw ratio
    POWER = 2.5
    h_score = h_pct ** POWER
    a_score = a_pct ** POWER

    total = h_score + a_score
    if total == 0:
        return 0.5, 0.5
    return h_score / total, a_score / total


def compute_recent_form_factor(home_recent, away_recent, home_standings=None, away_standings=None):
    """
    Analyze last 10 games for each team.
    Falls back to last_10 from standings if game-by-game data unavailable.
    More recent games weighted slightly higher.
    """
    def _form_score(games):
        if not games:
            return None
        weights = []
        results = []
        for i, g in enumerate(games):
            w = 1.0 + (i * 0.15)
            weights.append(w)
            results.append(1.0 if g.get("win") else 0.0)
        total_w = sum(weights)
        return sum(r * w for r, w in zip(results, weights)) / total_w if total_w > 0 else 0.5

    def _parse_last10(standings):
        """Parse '7-3' last 10 format."""
        if not standings:
            return None
        l10 = standings.get("last_10", "")
        if not l10:
            return None
        try:
            parts = l10.split("-")
            w, l = int(parts[0]), int(parts[1])
            return w / (w + l) if (w + l) > 0 else 0.5
        except (ValueError, IndexError):
            return None

    h_score = _form_score(home_recent)
    a_score = _form_score(away_recent)

    # Fallback to standings last_10
    if h_score is None:
        h_score = _parse_last10(home_standings)
    if a_score is None:
        a_score = _parse_last10(away_standings)

    # Default to neutral if still nothing
    if h_score is None:
        h_score = 0.5
    if a_score is None:
        a_score = 0.5

    # Power scale to amplify form differences
    POWER = 1.8
    h_score = h_score ** POWER
    a_score = a_score ** POWER

    total = h_score + a_score
    if total == 0:
        return 0.5, 0.5
    return h_score / total, a_score / total


def compute_home_away_factor(home_standings, away_standings):
    """
    Factor in home/away records + home court advantage.
    """
    def _parse_record(record_str):
        """Parse '25-10' format into win pct."""
        if not record_str:
            return 0.5
        try:
            parts = record_str.split("-")
            w, l = int(parts[0]), int(parts[1])
            return _safe_div(w, w + l)
        except (ValueError, IndexError):
            return 0.5

    h_home_pct = _parse_record(home_standings.get("home_record", ""))
    a_away_pct = _parse_record(away_standings.get("away_record", ""))

    # Apply home court boost
    h_adj = min(h_home_pct + HOME_COURT_BOOST, 1.0)
    a_adj = max(a_away_pct - HOME_COURT_BOOST * 0.5, 0.0)

    # Power scale
    POWER = 2.0
    h_adj = h_adj ** POWER
    a_adj = a_adj ** POWER

    total = h_adj + a_adj
    if total == 0:
        return 0.5, 0.5
    return h_adj / total, a_adj / total


def compute_injury_factor(home_abbr, away_abbr, injuries):
    """
    Assess injury impact. Key players (starters) missing hurts more.
    Returns adjusted factors favoring the healthier team.
    """
    def _injury_penalty(team_injuries):
        """Calculate penalty based on number and severity of injuries."""
        if not team_injuries:
            return 0.0
        penalty = 0.0
        for inj in team_injuries:
            status = inj.get("status", "").lower()
            if "out" in status:
                penalty += 0.06
            elif "doubtful" in status:
                penalty += 0.04
            elif "questionable" in status:
                penalty += 0.02
            elif "probable" in status or "day-to-day" in status:
                penalty += 0.01
        return min(penalty, 0.25)  # Cap the penalty

    h_penalty = _injury_penalty(injuries.get(home_abbr, []))
    a_penalty = _injury_penalty(injuries.get(away_abbr, []))

    # More injuries = lower score
    h_health = 1.0 - h_penalty
    a_health = 1.0 - a_penalty
    total = h_health + a_health
    if total == 0:
        return 0.5, 0.5
    return h_health / total, a_health / total


def compute_streak_factor(home_standings, away_standings):
    """
    Factor in current win/loss streak.
    Positive streak = winning, negative = losing.
    Larger streaks have more impact.
    """
    def _streak_score(standings):
        streak = standings.get("streak", 0)
        if isinstance(streak, str):
            if streak.startswith("W"):
                try:
                    return int(streak[1:])
                except ValueError:
                    return 0
            elif streak.startswith("L"):
                try:
                    return -int(streak[1:])
                except ValueError:
                    return 0
            return 0
        return float(streak)

    h_streak = _streak_score(home_standings)
    a_streak = _streak_score(away_standings)

    # More aggressive normalization: streaks of 4+ are significant
    h_norm = 0.5 + (h_streak * 0.04)
    a_norm = 0.5 + (a_streak * 0.04)
    h_norm = max(0.2, min(0.8, h_norm))
    a_norm = max(0.2, min(0.8, a_norm))

    total = h_norm + a_norm
    return h_norm / total, a_norm / total


def compute_rest_factor(home_recent, away_recent):
    """
    Rest analysis based on actual game dates.
    Back-to-back (played yesterday) gets a penalty.
    3+ days rest gets a slight boost.
    """
    from datetime import datetime

    def _days_since_last_game(recent_games):
        if not recent_games:
            return 2  # assume neutral rest if no data
        last_date_str = recent_games[-1].get("date", "")
        if not last_date_str:
            return 2
        try:
            game_date = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
            return (datetime.now() - game_date).days
        except ValueError:
            return 2

    def _rest_score(days):
        if days <= 1:    # back-to-back
            return 0.35
        elif days == 2:  # one day rest — neutral
            return 0.50
        else:            # 3+ days rest — slight boost
            return 0.58

    h_score = _rest_score(_days_since_last_game(home_recent))
    a_score = _rest_score(_days_since_last_game(away_recent))
    total = h_score + a_score
    return h_score / total, a_score / total


def compute_player_form_factor(home_player_form, away_player_form):
    """
    Compute team-level form score from individual player performance
    over the last 5 games.

    form_score per player = pts_avg × fg_pct × plus_minus_boost
    Team score = Σ(form_score × minutes_weight) / Σ(minutes_weight)
    Starters get a 1.2× weight multiplier.

    Falls back to neutral (0.5, 0.5) if either team has no data.
    """
    def _team_score(player_form):
        if not player_form:
            return None
        total_weighted = 0.0
        total_weight   = 0.0
        for p in player_form.values():
            if p.get("minutes_avg", 0) < 8:
                continue
            weight = p["minutes_avg"] * (1.2 if p.get("starter") else 1.0)
            total_weighted += p["form_score"] * weight
            total_weight   += weight
        if total_weight == 0:
            return None
        return total_weighted / total_weight

    h_raw = _team_score(home_player_form)
    a_raw = _team_score(away_player_form)

    if h_raw is None and a_raw is None:
        return 0.5, 0.5
    if h_raw is None:
        h_raw = a_raw  # neutral vs known
    if a_raw is None:
        a_raw = h_raw

    total = h_raw + a_raw
    if total == 0:
        return 0.5, 0.5

    # Power scale to amplify meaningful differences
    POWER = 1.5
    h_scaled = h_raw ** POWER
    a_scaled = a_raw ** POWER
    total_scaled = h_scaled + a_scaled
    return h_scaled / total_scaled, a_scaled / total_scaled


def predict_game(game, standings, injuries, recent_form, player_form=None):
    """
    Generate a prediction for a single game.

    Returns dict with:
        - predicted_winner (abbr)
        - home_win_prob
        - away_win_prob
        - confidence
        - recommendation ('PICK', 'LEAN', 'SKIP')
        - factors (detailed breakdown)
    """
    if player_form is None:
        player_form = {}

    home_abbr = game["home"]["abbr"]
    away_abbr = game["away"]["abbr"]

    home_standings = standings.get(home_abbr, {})
    away_standings = standings.get(away_abbr, {})
    home_recent = recent_form.get(home_abbr, [])
    away_recent = recent_form.get(away_abbr, [])

    # If no standings data, use the records from the schedule
    if not home_standings:
        hw = game["home"].get("wins", 0)
        hl = game["home"].get("losses", 0)
        home_standings = {
            "win_pct": _safe_div(hw, hw + hl),
            "wins": hw, "losses": hl,
            "home_record": "", "away_record": "",
            "streak": 0, "last_10": "",
        }
    if not away_standings:
        aw = game["away"].get("wins", 0)
        al = game["away"].get("losses", 0)
        away_standings = {
            "win_pct": _safe_div(aw, aw + al),
            "wins": aw, "losses": al,
            "home_record": "", "away_record": "",
            "streak": 0, "last_10": "",
        }

    # Compute all factors
    factors = {}

    h_wp, a_wp = compute_win_pct_factor(home_standings, away_standings)
    factors["win_pct"] = {"home": h_wp, "away": a_wp}

    h_rf, a_rf = compute_recent_form_factor(home_recent, away_recent, home_standings, away_standings)
    factors["recent_form"] = {"home": h_rf, "away": a_rf}

    h_ha, a_ha = compute_home_away_factor(home_standings, away_standings)
    factors["home_away"] = {"home": h_ha, "away": a_ha}

    h_inj, a_inj = compute_injury_factor(home_abbr, away_abbr, injuries)
    factors["injuries"] = {"home": h_inj, "away": a_inj}

    h_st, a_st = compute_streak_factor(home_standings, away_standings)
    factors["streak"] = {"home": h_st, "away": a_st}

    h_rest, a_rest = compute_rest_factor(home_recent, away_recent)
    factors["rest_days"] = {"home": h_rest, "away": a_rest}

    h_pf, a_pf = compute_player_form_factor(
        player_form.get(home_abbr, {}),
        player_form.get(away_abbr, {})
    )
    factors["player_form"] = {"home": h_pf, "away": a_pf}

    # Weighted combination
    home_score = 0.0
    away_score = 0.0
    for factor_name, weight in WEIGHTS.items():
        f = factors.get(factor_name, {"home": 0.5, "away": 0.5})
        home_score += f["home"] * weight
        away_score += f["away"] * weight

    # Normalize to probabilities
    total = home_score + away_score
    home_prob = home_score / total if total > 0 else 0.5
    away_prob = away_score / total if total > 0 else 0.5

    # Determine winner and confidence
    confidence = max(home_prob, away_prob)
    predicted_winner = home_abbr if home_prob >= away_prob else away_abbr

    # Recommendation
    if confidence >= CONFIDENCE_HIGH:
        recommendation = "STRONG PICK"
    elif confidence >= CONFIDENCE_MODERATE:
        recommendation = "LEAN"
    elif confidence >= CONFIDENCE_LOW:
        recommendation = "SLIGHT LEAN"
    else:
        recommendation = "SKIP"

    return {
        "home_team": game["home"]["name"],
        "home_abbr": home_abbr,
        "away_team": game["away"]["name"],
        "away_abbr": away_abbr,
        "home_record": f"{home_standings.get('wins', game['home'].get('wins', '?'))}-{home_standings.get('losses', game['home'].get('losses', '?'))}",
        "away_record": f"{away_standings.get('wins', game['away'].get('wins', '?'))}-{away_standings.get('losses', game['away'].get('losses', '?'))}",
        "home_win_prob": round(home_prob, 4),
        "away_win_prob": round(away_prob, 4),
        "predicted_winner": predicted_winner,
        "predicted_winner_name": game["home"]["name"] if predicted_winner == home_abbr else game["away"]["name"],
        "confidence": round(confidence, 4),
        "recommendation": recommendation,
        "venue": game.get("venue", ""),
        "game_time": game.get("time", ""),
        "factors": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in factors.items()},
        "home_injuries": len(injuries.get(home_abbr, [])),
        "away_injuries": len(injuries.get(away_abbr, [])),
    }


def predict_all_games(schedule, standings, injuries, recent_form, player_form=None):
    """Generate predictions for all games in the schedule."""
    if player_form is None:
        player_form = {}
    predictions = []
    for game in schedule:
        pred = predict_game(game, standings, injuries, recent_form, player_form)
        predictions.append(pred)

    # Sort by confidence (highest first)
    predictions.sort(key=lambda p: p["confidence"], reverse=True)
    return predictions
