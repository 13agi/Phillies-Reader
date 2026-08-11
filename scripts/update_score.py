import json
import os
from datetime import datetime, timezone, timedelta
import requests
# =========================================================
# CONFIG
# =========================================================
TEAM_ID = 143
TEAM_NAME = "Philadelphia Phillies"
TEAM_ABBR = "PHI"
SEASON = 2026
BASE_URL = "https://statsapi.mlb.com/api/v1"
OUTPUT_FILE = "data/score.json"
JST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": "Phillies-Reader/1.0"
}
# =========================================================
# HTTP
# =========================================================
def get_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return response.json()
# =========================================================
# BASIC HELPERS
# =========================================================
def get_player_name(player):
    person = player.get("person") or {}
    return (
        person.get("fullName")
        or player.get("fullName")
        or "-"
    )
def get_player_id(player):
    person = player.get("person") or {}
    return person.get("id")
def get_position(player):
    position = player.get("position") or {}
    return position.get("abbreviation")
# =========================================================
# TIME
# =========================================================
def now_jst():
    return datetime.now(JST)
def parse_game_date(value):
    if not value:
        return None
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )
# =========================================================
# GET TEAM SCHEDULE
#
# Score専用。
# ScheduleページのJSONは使用しない。
# =========================================================
def get_team_games(date_string):
    url = f"{BASE_URL}/schedule"
    params = {
        "sportId": 1,
        "teamId": TEAM_ID,
        "season": SEASON,
        "date": date_string,
        "hydrate": "team,venue"
    }
    data = get_json(url, params)
    games = []
    for date_block in data.get("dates", []):
        games.extend(
            date_block.get("games", [])
        )
    return games
# =========================================================
# FIND LATEST / LIVE GAME
#
# 優先順位
#
# 1. LIVE
# 2. 今日までに開始した最新試合
# 3. 次の試合
#
# Scoreページなので、
# 「現在または直近の試合」を表示する。
# =========================================================
def find_score_game():
    current = now_jst()
    dates = [
        current.date(),
        current.date() - timedelta(days=1),
        current.date() + timedelta(days=1)
    ]
    all_games = {}
    for date_value in dates:
        date_string = date_value.strftime(
            "%Y-%m-%d"
        )
        print(
            f"Fetching schedule: {date_string}"
        )
        try:
            games = get_team_games(
                date_string
            )
        except Exception as error:
            print(
                f"Schedule request failed: {error}"
            )
            continue
        for game in games:
            game_pk = game.get("gamePk")
            if game_pk is not None:
                all_games[game_pk] = game
    candidates = []
    for game in all_games.values():
        game_date = parse_game_date(
            game.get("gameDate")
        )
        if game_date is None:
            continue
        game_jst = game_date.astimezone(JST)
        status = (
            game.get("status")
            or {}
        )
        abstract = status.get(
            "abstractGameState"
        )
        detailed = status.get(
            "detailedState"
        )
        candidates.append({
            "game": game,
            "start": game_jst,
            "abstract": abstract,
            "detailed": detailed
        })
    # =====================================================
    # LIVE
    # =====================================================
    live = [
        item
        for item in candidates
        if item["abstract"] == "Live"
    ]
    if live:
        live.sort(
            key=lambda x: x["start"],
            reverse=True
        )
        print(
            "LIVE GAME:",
            live[0]["game"].get("gamePk")
        )
        return live[0]["game"]
    # =====================================================
    # STARTED / FINAL
    # =====================================================
    started = [
        item
        for item in candidates
        if (
            item["start"] <= current
            and item["abstract"]
            in {
                "Live",
                "Final",
                "Postponed",
                "Cancelled",
                "Suspended"
            }
        )
    ]
    if started:
        started.sort(
            key=lambda x: x["start"],
            reverse=True
        )
        print(
            "LATEST COMPLETED GAME:",
            started[0]["game"].get("gamePk")
        )
        return started[0]["game"]
    # =====================================================
    # FUTURE
    # =====================================================
    future = [
        item
        for item in candidates
        if item["start"] > current
    ]
    if future:
        future.sort(
            key=lambda x: x["start"]
        )
        print(
            "NEXT GAME:",
            future[0]["game"].get("gamePk")
        )
        return future[0]["game"]
    return None
# =========================================================
# GAME FEED
# =========================================================
def get_game_feed(game_pk):
    url = (
        f"{BASE_URL}/game/"
        f"{game_pk}/feed/live"
    )
    return get_json(url)
# =========================================================
# BOXSCORE
# =========================================================
def get_boxscore(game_pk):
    url = (
        f"{BASE_URL}/game/"
        f"{game_pk}/boxscore"
    )
    return get_json(url)
# =========================================================
# LINESCORE
#
# 専用APIを使用。
#
# これが今回の重要部分。
# =========================================================
def get_linescore(game_pk, feed):
    url = (
        f"{BASE_URL}/game/"
        f"{game_pk}/linescore"
    )
    try:
        data = get_json(url)
        if data.get("innings") is not None:
            print(
                "Dedicated linescore API: OK"
            )
            return data
    except Exception as error:
        print(
            "Dedicated linescore API failed:",
            error
        )
    # fallback
    live_data = (
        feed.get("liveData")
        or {}
    )
    linescore = (
        live_data.get("linescore")
        or {}
    )
    if linescore.get("innings") is not None:
        print(
            "Live feed linescore fallback: OK"
        )
        return linescore
    return {}
# =========================================================
# DETERMINE HOME / AWAY
# =========================================================
def get_phillies_side(game_data):
    teams = (
        game_data.get("teams")
        or {}
    )
    home = (
        teams.get("home")
        or {}
    )
    away = (
        teams.get("away")
        or {}
    )
    home_team = (
        home.get("team")
        or {}
    )
    away_team = (
        away.get("team")
        or {}
    )
    if home_team.get("id") == TEAM_ID:
        return "home"
    if away_team.get("id") == TEAM_ID:
        return "away"
    return None
# =========================================================
# GAME INFORMATION
# =========================================================
def build_game_info(game_data):
    teams = (
        game_data.get("teams")
        or {}
    )
    home = (
        teams.get("home")
        or {}
    )
    away = (
        teams.get("away")
        or {}
    )
    home_team = (
        home.get("team")
        or {}
    )
    away_team = (
        away.get("team")
        or {}
    )
    status = (
        game_data.get("status")
        or {}
    )
    venue = (
        game_data.get("venue")
        or {}
    )
    return {
        "gamePk":
            game_data.get("gamePk"),
        "gameDate":
            game_data.get("gameDate"),
        "status": {
            "abstract":
                status.get(
                    "abstractGameState"
                ),
            "detailed":
                status.get(
                    "detailedState"
                ),
            "code":
                status.get(
                    "statusCode"
                )
        },
        "home": {
            "id":
                home_team.get("id"),
            "name":
                home_team.get("name"),
            "abbreviation":
                home_team.get(
                    "abbreviation"
                ),
            "score":
                home.get("score"),
            "hits":
                home.get("hits"),
            "errors":
                home.get("errors")
        },
        "away": {
            "id":
                away_team.get("id"),
            "name":
                away_team.get("name"),
            "abbreviation":
                away_team.get(
                    "abbreviation"
                ),
            "score":
                away.get("score"),
            "hits":
                away.get("hits"),
            "errors":
                away.get("errors")
        },
        "venue": {
            "name":
                venue.get("name")
        }
    }
# =========================================================
# INNING SCORES
# =========================================================
def build_inning_scores(linescore):
    innings = (
        linescore.get("innings")
        or []
    )
    result = []
    for inning in innings:
        away = (
            inning.get("away")
            or {}
        )
        home = (
            inning.get("home")
            or {}
        )
        result.append({
            "inning":
                inning.get("num"),
            "away":
                away.get("runs"),
            "home":
                home.get("runs"),
            "awayHits":
                away.get("hits"),
            "homeHits":
                home.get("hits"),
            "awayErrors":
                away.get("errors"),
            "homeErrors":
                home.get("errors"),
            "awayLOB":
                away.get("leftOnBase"),
            "homeLOB":
                home.get("leftOnBase")
        })
    return result
# =========================================================
# BATTING
# =========================================================
def build_batting(boxscore, side):
    teams = (
        boxscore.get("teams")
        or {}
    )
    team = (
        teams.get(side)
        or {}
    )
    players = (
        team.get("players")
        or {}
    )
    batting_order = (
        team.get("battingOrder")
        or []
    )
    result = []
    for sequence, player_id in enumerate(
        batting_order,
        start=1
    ):
        player = (
            players.get(
                f"ID{player_id}"
            )
            or {}
        )
        if not player:
            continue
        stats = (
            player.get("stats")
            or {}
        )
        batting = (
            stats.get("batting")
            or {}
        )
        raw_order = (
            player.get("battingOrder")
            or ""
        )
        try:
            order = int(
                str(raw_order)[0]
            )
        except Exception:
            order = None
        result.append({
            "sequence":
                sequence,
            "battingOrder":
                order,
            "battingOrderRaw":
                raw_order,
            "playerId":
                get_player_id(player),
            "name":
                get_player_name(player),
            "position":
                get_position(player),
            "PA":
                batting.get(
                    "plateAppearances"
                ),
            "H":
                batting.get(
                    "hits"
                ),
            "HR":
                batting.get(
                    "homeRuns"
                ),
            "RBI":
                batting.get(
                    "rbi"
                ),
            "BB":
                batting.get(
                    "baseOnBalls"
                ),
            "AB":
                batting.get(
                    "atBats"
                ),
            "R":
                batting.get(
                    "runs"
                ),
            "SO":
                batting.get(
                    "strikeOuts"
                )
        })
    # =====================================================
    # 打順がない場合
    # =====================================================
    if not result:
        fallback = []
        for player in players.values():
            if not isinstance(
                player,
                dict
            ):
                continue
            batting = (
                (
                    player.get("stats")
                    or {}
                ).get("batting")
                or {}
            )
            if (
                batting.get(
                    "plateAppearances"
                )
                is None
            ):
                continue
            fallback.append({
                "sequence":
                    len(fallback) + 1,
                "battingOrder":
                    None,
                "battingOrderRaw":
                    None,
                "playerId":
                    get_player_id(player),
                "name":
                    get_player_name(player),
                "position":
                    get_position(player),
                "PA":
                    batting.get(
                        "plateAppearances"
                    ),
                "H":
                    batting.get("hits"),
                "HR":
                    batting.get(
                        "homeRuns"
                    ),
                "RBI":
                    batting.get("rbi"),
                "BB":
                    batting.get(
                        "baseOnBalls"
                    ),
                "AB":
                    batting.get("atBats"),
                "R":
                    batting.get("runs"),
                "SO":
                    batting.get(
                        "strikeOuts"
                    )
            })
        result = fallback
    result.sort(
        key=lambda player: (
            player["battingOrder"]
            if player["battingOrder"]
            is not None
            else 99,
            player["sequence"]
        )
    )
    return result
# =========================================================
# PITCHING
# =========================================================
def build_pitching(boxscore, side):
    teams = (
        boxscore.get("teams")
        or {}
    )
    team = (
        teams.get(side)
        or {}
    )
    players = (
        team.get("players")
        or {}
    )
    pitcher_ids = (
        team.get("pitchers")
        or []
    )
    result = []
    for sequence, player_id in enumerate(
        pitcher_ids,
        start=1
    ):
        player = (
            players.get(
                f"ID{player_id}"
            )
            or {}
        )
        if not player:
            continue
        stats = (
            player.get("stats")
            or {}
        )
        pitching = (
            stats.get("pitching")
            or {}
        )
        if (
            pitching.get(
                "inningsPitched"
            )
            is None
            and
            pitching.get(
                "pitchesThrown"
            )
            is None
        ):
            continue
        result.append({
            "sequence":
                sequence,
            "playerId":
                get_player_id(player),
            "name":
                get_player_name(player),
            "IP":
                pitching.get(
                    "inningsPitched"
                ),
            "H":
                pitching.get("hits"),
            "K":
                pitching.get(
                    "strikeOuts"
                ),
            "HR":
                pitching.get(
                    "homeRuns"
                ),
            "R":
                pitching.get("runs"),
            "ER":
                pitching.get(
                    "earnedRuns"
                ),
            "BB":
                pitching.get(
                    "baseOnBalls"
                ),
            "pitches":
                pitching.get(
                    "pitchesThrown"
                )
        })
    return result
# =========================================================
# CURRENT LIVE GAME
# =========================================================
def build_current_game(feed, side):
    live_data = (
        feed.get("liveData")
        or {}
    )
    plays = (
        live_data.get("plays")
        or {}
    )
    linescore = (
        live_data.get("linescore")
        or {}
    )
    current_play = (
        plays.get("currentPlay")
    )
    if not current_play:
        return {
            "available":
                False,
            "isPhilliesBatting":
                None,
            "inning":
                None,
            "half":
                None,
            "outs":
                None,
            "balls":
                None,
            "strikes":
                None,
            "pitcher":
                None,
            "batter":
                None,
            "lastPitch":
                None,
            "runners": {
                "first":
                    False,
                "second":
                    False,
                "third":
                    False
            }
        }
    about = (
        current_play.get("about")
        or {}
    )
    half = about.get(
        "halfInning"
    )
    inning = about.get(
        "inning"
    )
    if side == "home":
        is_phillies_batting = (
            half == "bottom"
        )
    else:
        is_phillies_batting = (
            half == "top"
        )
    count = (
        current_play.get("count")
        or {}
    )
    matchup = (
        current_play.get("matchup")
        or {}
    )
    pitcher = (
        matchup.get("pitcher")
        or {}
    )
    batter = (
        matchup.get("batter")
        or {}
    )
    pitch_hand = (
        matchup.get("pitchHand")
        or {}
    )
    bat_side = (
        matchup.get("batSide")
        or {}
    )
    offense = (
        linescore.get("offense")
        or {}
    )
    runners = {
        "first":
            offense.get("first")
            is not None,
        "second":
            offense.get("second")
            is not None,
        "third":
            offense.get("third")
            is not None
    }
    # =====================================================
    # LAST PITCH
    # =====================================================
    last_pitch = {
        "speed": None,
        "type": None
    }
    events = (
        current_play.get(
            "playEvents"
        )
        or []
    )
    for event in reversed(events):
        if event.get("isPitch") is not True:
            continue
        pitch_data = (
            event.get("pitchData")
            or {}
        )
        details = (
            event.get("details")
            or {}
        )
        pitch_type = (
            details.get("type")
            or {}
        )
        last_pitch = {
            "speed":
                pitch_data.get(
                    "startSpeed"
                ),
            "type":
                pitch_type.get(
                    "description"
                )
        }
        break
    return {
        "available":
            True,
        "isPhilliesBatting":
            is_phillies_batting,
        "inning":
            inning,
        "half":
            half,
        "inningLabel":
            (
                f"{half.upper()} {inning}"
                if half and inning
                else None
            ),
        "outs":
            count.get("outs"),
        "balls":
            count.get("balls"),
        "strikes":
            count.get("strikes"),
        "pitcher": {
            "id":
                pitcher.get("id"),
            "name":
                pitcher.get("fullName"),
            "hand":
                pitch_hand.get("code")
        },
        "batter": {
            "id":
                batter.get("id"),
            "name":
                batter.get("fullName"),
            "hand":
                bat_side.get("code")
        },
        "lastPitch":
            last_pitch,
        "runners":
            runners
    }
# =========================================================
# BUILD ONE GAME
# =========================================================
def build_game(scheduled_game):
    game_pk = scheduled_game.get(
        "gamePk"
    )
    print(
        f"Processing game: {game_pk}"
    )
    # =====================================================
    # FEED
    # =====================================================
    feed = get_game_feed(
        game_pk
    )
    game_data = (
        feed.get("gameData")
        or scheduled_game
    )
    live_data = (
        feed.get("liveData")
        or {}
    )
    # =====================================================
    # SIDE
    # =====================================================
    side = get_phillies_side(
        game_data
    )
    if side is None:
        raise RuntimeError(
            "Could not determine Phillies HOME/AWAY side."
        )
    # =====================================================
    # BOXSCORE
    # =====================================================
    boxscore = get_boxscore(
        game_pk
    )
    # =====================================================
    # LINESCORE
    # =====================================================
    linescore = get_linescore(
        game_pk,
        feed
    )
    # =====================================================
    # INFORMATION
    # =====================================================
    game_info = build_game_info(
        game_data
    )
    # =====================================================
    # BATTING
    # =====================================================
    batting = build_batting(
        boxscore,
        side
    )
    # =====================================================
    # PITCHING
    # =====================================================
    pitching = build_pitching(
        boxscore,
        side
    )
    # =====================================================
    # CURRENT GAME
    # =====================================================
    current_game = build_current_game(
        feed,
        side
    )
    teams = (
        game_data.get("teams")
        or {}
    )
    away = (
        teams.get("away")
        or {}
    )
    home = (
        teams.get("home")
        or {}
    )
    return {
        "game": game_info,
        "location":
            "HOME"
            if side == "home"
            else "AWAY",
        "score": {
            "away": {
                "runs":
                    away.get("score"),
                "hits":
                    away.get("hits"),
                "errors":
                    away.get("errors")
            },
            "home": {
                "runs":
                    home.get("score"),
                "hits":
                    home.get("hits"),
                "errors":
                    home.get("errors")
            }
        },
        "inningScores":
            build_inning_scores(
                linescore
            ),
        "philliesBatting":
            batting,
        "philliesPitching":
            pitching,
        "currentGame":
            current_game
    }
# =========================================================
# MAIN
# =========================================================
def main():
    current = now_jst()
    print(
        "========================================"
    )
    print(
        "PHILLIES SCORE UPDATE"
    )
    print(
        "JST:",
        current.isoformat()
    )
    print(
        "========================================"
    )
    scheduled_game = find_score_game()
    if scheduled_game is None:
        data = {
            "team": {
                "id":
                    TEAM_ID,
                "name":
                    TEAM_NAME,
                "abbreviation":
                    TEAM_ABBR
            },
            "season":
                SEASON,
            "date":
                current.strftime(
                    "%Y-%m-%d"
                ),
            "updated":
                current.isoformat(),
            "gameCount":
                0,
            "games":
                []
        }
    else:
        try:
            game = build_game(
                scheduled_game
            )
            games = (
                [game]
                if game is not None
                else []
            )
        except Exception as error:
            print(
                "========================================"
            )
            print(
                "SCORE UPDATE FAILED"
            )
            print(
                repr(error)
            )
            print(
                "========================================"
            )
            raise
        data = {
            "team": {
                "id":
                    TEAM_ID,
                "name":
                    TEAM_NAME,
                "abbreviation":
                    TEAM_ABBR
            },
            "season":
                SEASON,
            "date":
                current.strftime(
                    "%Y-%m-%d"
                ),
            "updated":
                current.isoformat(),
            "gameCount":
                len(games),
            "games":
                games
        }
    # =====================================================
    # SAVE
    # =====================================================
    os.makedirs(
        os.path.dirname(
            OUTPUT_FILE
        ),
        exist_ok=True
    )
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )
    # =====================================================
    # VALIDATION
    # =====================================================
    print(
        "========================================"
    )
    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print(
        f"gameCount: {data['gameCount']}"
    )
    if data["games"]:
        game = data["games"][0]
        info = game["game"]
        print(
            f"gamePk: {info.get('gamePk')}"
        )
        print(
            f"status: {info.get('status', {}).get('abstract')}"
        )
        print(
            "inningScores:",
            len(
                game.get(
                    "inningScores",
                    []
                )
            )
        )
        print(
            "batters:",
            len(
                game.get(
                    "philliesBatting",
                    []
                )
            )
        print(
            "pitchers:",
            len(
                game.get(
                    "philliesPitching",
                    []
                )
            )
        current_game = game.get(
            "currentGame",
            {}
        )
        print(
            "live available:",
            current_game.get(
                "available"
            )
        )
    print(
        "========================================"
    )
if __name__ == "__main__":
    main()
