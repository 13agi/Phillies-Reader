import json
import os
import requests
from datetime import datetime, timezone, timedelta
# =========================================================
# CONFIG
# =========================================================
TEAM_ID = 143
SEASON = 2026
BASE_URL = "https://statsapi.mlb.com/api/v1"
OUTPUT_FILE = "data/score.json"
JST = timezone(
    timedelta(hours=9)
)
# =========================================================
# HTTP
# =========================================================
def get_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={
            "User-Agent": "Phillies-Reader/1.0"
        }
    )
    response.raise_for_status()
    return response.json()
# =========================================================
# HELPERS
# =========================================================
def value_or_none(value):
    if value is None:
        return None
    return value
def player_name(player):
    person = player.get("person") or {}
    return (
        person.get("fullName")
        or player.get("fullName")
        or "-"
    )
def player_id(player):
    person = player.get("person") or {}
    return person.get("id")
def batting_stat(stats, key):
    value = stats.get(key)
    if value is None:
        return None
    return value
def pitching_stat(stats, key):
    value = stats.get(key)
    if value is None:
        return None
    return value
# =========================================================
# TODAY
# =========================================================
def get_today():
    return datetime.now(
        JST
    ).strftime(
        "%Y-%m-%d"
    )
# =========================================================
# SCHEDULE
# =========================================================
def get_today_games(game_date):
    url = f"{BASE_URL}/schedule"
    params = {
        "sportId": 1,
        "teamId": TEAM_ID,
        "season": SEASON,
        "date": game_date,
        "hydrate": "team,venue"
    }
    data = get_json(
        url,
        params
    )
    games = []
    for date_block in data.get(
        "dates",
        []
    ):
        for game in date_block.get(
            "games",
            []
        ):
            games.append(
                game
            )
    return games
# =========================================================
# LIVE FEED
# =========================================================
def get_live_feed(game_pk):
    url = (
        f"{BASE_URL}/game/"
        f"{game_pk}/feed/live"
    )
    try:
        return get_json(
            url
        )
    except Exception as error:
        print(
            "Live feed error:",
            error
        )
        return {}
# =========================================================
# BOXSCORE
# =========================================================
def get_boxscore(game_pk):
    url = (
        f"{BASE_URL}/game/"
        f"{game_pk}/boxscore"
    )
    try:
        return get_json(
            url
        )
    except Exception as error:
        print(
            "Boxscore error:",
            error
        )
        return {}
# =========================================================
# DETERMINE PHILLIES SIDE
# =========================================================
def get_phillies_side(
    game_data
):
    teams = (
        game_data
        .get(
            "teams",
            {}
        )
    )
    home = (
        teams
        .get(
            "home",
            {}
        )
    )
    away = (
        teams
        .get(
            "away",
            {}
        )
    )
    home_team = (
        home
        .get(
            "team",
            {}
        )
    )
    away_team = (
        away
        .get(
            "team",
            {}
        )
    )
    if (
        home_team.get("id")
        == TEAM_ID
    ):
        return "home"
    if (
        away_team.get("id")
        == TEAM_ID
    ):
        return "away"
    return None
# =========================================================
# GAME INFORMATION
# =========================================================
def build_game_info(
    game_data
):
    teams = (
        game_data
        .get(
            "teams",
            {}
        )
    )
    home = (
        teams
        .get(
            "home",
            {}
        )
    )
    away = (
        teams
        .get(
            "away",
            {}
        )
    )
    home_team = (
        home
        .get(
            "team",
            {}
        )
        or {}
    )
    away_team = (
        away
        .get(
            "team",
            {}
        )
        or {}
    )
    venue = (
        game_data
        .get(
            "venue",
            {}
        )
        or {}
    )
    status = (
        game_data
        .get(
            "status",
            {}
        )
        or {}
    )
    return {
        "gamePk":
            game_data.get(
                "gamePk"
            ),
        "gameDate":
            game_data.get(
                "gameDate"
            ),
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
                home_team.get(
                    "id"
                ),
            "name":
                home_team.get(
                    "name"
                ),
            "abbreviation":
                home_team.get(
                    "abbreviation"
                ),
            "score":
                home.get(
                    "score"
                ),
            "hits":
                home.get(
                    "hits"
                ),
            "errors":
                home.get(
                    "errors"
                )
        },
        "away": {
            "id":
                away_team.get(
                    "id"
                ),
            "name":
                away_team.get(
                    "name"
                ),
            "abbreviation":
                away_team.get(
                    "abbreviation"
                ),
            "score":
                away.get(
                    "score"
                ),
            "hits":
                away.get(
                    "hits"
                ),
            "errors":
                away.get(
                    "errors"
                )
        },
        "venue": {
            "name":
                venue.get(
                    "name"
                )
        }
    }
# =========================================================
# INNING SCORES
# =========================================================
def build_inning_scores(
    linescore
):
    innings = (
        linescore
        .get(
            "innings",
            []
        )
    )
    result = []
    for inning in innings:
        away = (
            inning
            .get(
                "away",
                {}
            )
            or {}
        )
        home = (
            inning
            .get(
                "home",
                {}
            )
            or {}
        )
        result.append({
            "inning":
                inning.get(
                    "num"
                ),
            "away":
                away.get(
                    "runs"
                ),
            "home":
                home.get(
                    "runs"
                ),
            "awayHits":
                away.get(
                    "hits"
                ),
            "homeHits":
                home.get(
                    "hits"
                ),
            "awayErrors":
                away.get(
                    "errors"
                ),
            "homeErrors":
                home.get(
                    "errors"
                )
        })
    return result
# =========================================================
# PHILLIES BATTING
#
# battingOrder:
# 100 = 1番
# 200 = 2番
# ...
#
# 同じ打順に複数選手が存在する場合は
# 代打・交代選手として保持する。
# =========================================================
def build_phillies_batting(
    boxscore,
    side
):
    teams = (
        boxscore
        .get(
            "teams",
            {}
        )
    )
    team = (
        teams
        .get(
            side,
            {}
        )
        or {}
    )
    players = (
        team
        .get(
            "players",
            {}
        )
    )
    batting_order = (
        team
        .get(
            "battingOrder",
            []
        )
    )
    result = []
    # -----------------------------------------------------
    # battingOrderに登録された選手を順番に処理
    # -----------------------------------------------------
    for sequence, pid in enumerate(
        batting_order,
        start=1
    ):
        key = f"ID{pid}"
        player = (
            players
            .get(
                key,
                {}
            )
        )
        if not player:
            continue
        stats_container = (
            player
            .get(
                "stats",
                {}
            )
            or {}
        )
        batting = (
            stats_container
            .get(
                "batting",
                {}
            )
            or {}
        )
        # MLB APIの battingOrder は文字列の場合がある
        order_raw = (
            player.get(
                "battingOrder"
            )
            or ""
        )
        try:
            if order_raw:
                order_number = int(
                    str(
                        order_raw
                    )[:1]
                )
            else:
                order_number = None
        except Exception:
            order_number = None
        result.append({
            "sequence":
                sequence,
            "battingOrder":
                order_number,
            "battingOrderRaw":
                order_raw,
            "playerId":
                player_id(
                    player
                ),
            "name":
                player_name(
                    player
                ),
            "position":
                (
                    player
                    .get(
                        "position",
                        {}
                    )
                    or {}
                )
                .get(
                    "abbreviation"
                ),
            "PA":
                batting_stat(
                    batting,
                    "plateAppearances"
                ),
            "H":
                batting_stat(
                    batting,
                    "hits"
                ),
            "HR":
                batting_stat(
                    batting,
                    "homeRuns"
                ),
            "RBI":
                batting_stat(
                    batting,
                    "rbi"
                ),
            "BB":
                batting_stat(
                    batting,
                    "baseOnBalls"
                ),
            "AB":
                batting_stat(
                    batting,
                    "atBats"
                ),
            "R":
                batting_stat(
                    batting,
                    "runs"
                ),
            "SO":
                batting_stat(
                    batting,
                    "strikeOuts"
                )
        })
    # -----------------------------------------------------
    # battingOrderが存在しない場合の保険
    # -----------------------------------------------------
    if not result:
        for key, player in players.items():
            if not isinstance(
                player,
                dict
            ):
                continue
            stats_container = (
                player
                .get(
                    "stats",
                    {}
                )
                or {}
            )
            batting = (
                stats_container
                .get(
                    "batting",
                    {}
                )
                or {}
            )
            if not batting:
                continue
            pa = batting.get(
                "plateAppearances"
            )
            if pa is None:
                continue
            result.append({
                "sequence":
                    len(result) + 1,
                "battingOrder":
                    None,
                "battingOrderRaw":
                    None,
                "playerId":
                    player_id(
                        player
                    ),
                "name":
                    player_name(
                        player
                    ),
                "position":
                    (
                        player
                        .get(
                            "position",
                            {}
                        )
                        or {}
                    )
                    .get(
                        "abbreviation"
                    ),
                "PA":
                    pa,
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
    # -----------------------------------------------------
    # 打順順に並べる
    # -----------------------------------------------------
    result.sort(
        key=lambda x: (
            x["battingOrder"]
            if x["battingOrder"]
            is not None
            else 99,
            x["sequence"]
        )
    )
    return result
# =========================================================
# PHILLIES PITCHING
#
# pitchers配列は登板順
# =========================================================
def build_phillies_pitching(
    boxscore,
    side
):
    teams = (
        boxscore
        .get(
            "teams",
            {}
        )
    )
    team = (
        teams
        .get(
            side,
            {}
        )
        or {}
    )
    players = (
        team
        .get(
            "players",
            {}
        )
    )
    pitcher_ids = (
        team
        .get(
            "pitchers",
            []
        )
    )
    result = []
    for sequence, pid in enumerate(
        pitcher_ids,
        start=1
    ):
        player = (
            players
            .get(
                f"ID{pid}",
                {}
            )
        )
        if not player:
            continue
        stats_container = (
            player
            .get(
                "stats",
                {}
            )
            or {}
        )
        pitching = (
            stats_container
            .get(
                "pitching",
                {}
            )
            or {}
        )
        # 登板していない選手を除外
        # inningsPitchedが無い場合でも、
        # pitchesThrownがあれば保持
        ip = pitching.get(
            "inningsPitched"
        )
        pitches = pitching.get(
            "pitchesThrown"
        )
        if (
            ip is None
            and pitches is None
        ):
            continue
        result.append({
            "sequence":
                sequence,
            "playerId":
                player_id(
                    player
                ),
            "name":
                player_name(
                    player
                ),
            "IP":
                pitching_stat(
                    pitching,
                    "inningsPitched"
                ),
            "H":
                pitching_stat(
                    pitching,
                    "hits"
                ),
            "K":
                pitching_stat(
                    pitching,
                    "strikeOuts"
                ),
            "HR":
                pitching_stat(
                    pitching,
                    "homeRuns"
                ),
            "R":
                pitching_stat(
                    pitching,
                    "runs"
                ),
            "ER":
                pitching_stat(
                    pitching,
                    "earnedRuns"
                ),
            "BB":
                pitching_stat(
                    pitching,
                    "baseOnBalls"
                ),
            "pitches":
                pitching_stat(
                    pitching,
                    "pitchesThrown"
                )
        })
    return result
# =========================================================
# CURRENT GAME
# =========================================================
def build_current_game(
    live_feed,
    side
):
    live_data = (
        live_feed
        .get(
            "liveData",
            {}
        )
    )
    game_data = (
        live_feed
        .get(
            "gameData",
            {}
        )
    )
    plays = (
        live_data
        .get(
            "plays",
            {}
        )
    )
    linescore = (
        live_data
        .get(
            "linescore",
            {}
        )
    )
    current_play = (
        plays
        .get(
            "currentPlay"
        )
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
        current_play
        .get(
            "about",
            {}
        )
        or {}
    )
    half = about.get(
        "halfInning"
    )
    inning = about.get(
        "inning"
    )
    # -----------------------------------------------------
    # Phillies攻撃中か
    # -----------------------------------------------------
    if side == "home":
        is_phillies_batting = (
            half == "bottom"
        )
    else:
        is_phillies_batting = (
            half == "top"
        )
    # -----------------------------------------------------
    # COUNT
    # -----------------------------------------------------
    count = (
        current_play
        .get(
            "count",
            {}
        )
        or {}
    )
    # -----------------------------------------------------
    # MATCHUP
    # -----------------------------------------------------
    matchup = (
        current_play
        .get(
            "matchup",
            {}
        )
        or {}
    )
    pitcher = (
        matchup
        .get(
            "pitcher",
            {}
        )
        or {}
    )
    batter = (
        matchup
        .get(
            "batter",
            {}
        )
        or {}
    )
    pitch_hand = (
        matchup
        .get(
            "pitchHand",
            {}
        )
        or {}
    )
    bat_side = (
        matchup
        .get(
            "batSide",
            {}
        )
        or {}
    )
    # -----------------------------------------------------
    # RUNNERS
    #
    # linescore.offense を使用
    # -----------------------------------------------------
    offense = (
        linescore
        .get(
            "offense",
            {}
        )
        or {}
    )
    runners = {
        "first":
            offense.get(
                "first"
            )
            is not None,
        "second":
            offense.get(
                "second"
            )
            is not None,
        "third":
            offense.get(
                "third"
            )
            is not None
    }
    # -----------------------------------------------------
    # LAST PITCH
    #
    # currentPlayの最後のisPitch=trueだけ
    # -----------------------------------------------------
    last_pitch = {
        "speed":
            None,
        "type":
            None
    }
    play_events = (
        current_play
        .get(
            "playEvents",
            []
        )
    )
    for event in reversed(
        play_events
    ):
        if (
            event.get(
                "isPitch"
            )
            is not True
        ):
            continue
        pitch_data = (
            event
            .get(
                "pitchData",
                {}
            )
            or {}
        )
        details = (
            event
            .get(
                "details",
                {}
            )
            or {}
        )
        pitch_type = (
            details
            .get(
                "type",
                {}
            )
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
    # -----------------------------------------------------
    # RETURN
    # -----------------------------------------------------
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
                f"{str(half).upper()} "
                f"{inning}"
                if half and inning
                else None
            ),
        "outs":
            count.get(
                "outs"
            ),
        "balls":
            count.get(
                "balls"
            ),
        "strikes":
            count.get(
                "strikes"
            ),
        "pitcher": {
            "id":
                pitcher.get(
                    "id"
                ),
            "name":
                pitcher.get(
                    "fullName"
                ),
            "hand":
                pitch_hand.get(
                    "code"
                )
        },
        "batter": {
            "id":
                batter.get(
                    "id"
                ),
            "name":
                batter.get(
                    "fullName"
                ),
            "hand":
                bat_side.get(
                    "code"
                )
        },
        "lastPitch":
            last_pitch,
        "runners":
            runners
    }
# =========================================================
# BUILD GAME
# =========================================================
def build_game(
    scheduled_game
):
    game_pk = scheduled_game.get(
        "gamePk"
    )
    print(
        "Processing game:",
        game_pk
    )
    # -----------------------------------------------------
    # Live Feed
    # -----------------------------------------------------
    live_feed = get_live_feed(
        game_pk
    )
    live_game_data = (
        live_feed
        .get(
            "gameData",
            {}
        )
    )
    live_data = (
        live_feed
        .get(
            "liveData",
            {}
        )
    )
    # -----------------------------------------------------
    # game data
    # -----------------------------------------------------
    if live_game_data:
        game_data = (
            live_game_data
        )
    else:
        game_data = (
            scheduled_game
        )
    # -----------------------------------------------------
    # side
    # -----------------------------------------------------
    side = get_phillies_side(
        game_data
    )
    if side is None:
        print(
            "Phillies side could not be determined."
        )
        return None
    # -----------------------------------------------------
    # Boxscore
    #
    # 試合前でも取得を試みる
    # 試合中・試合後はここが重要
    # -----------------------------------------------------
    boxscore = get_boxscore(
        game_pk
    )
    # -----------------------------------------------------
    # Live Feedにboxscoreが含まれている場合
    # Boxscore endpointを優先
    # -----------------------------------------------------
    if not boxscore:
        boxscore = (
            live_data
            .get(
                "boxscore",
                {}
            )
        )
    # -----------------------------------------------------
    # Linescore
    # -----------------------------------------------------
    linescore = (
        live_data
        .get(
            "linescore",
            {}
        )
    )
    # -----------------------------------------------------
    # game info
    # -----------------------------------------------------
    game_info = build_game_info(
        game_data
    )
    # -----------------------------------------------------
    # Phillies batting
    # -----------------------------------------------------
    batting = build_phillies_batting(
        boxscore,
        side
    )
    # -----------------------------------------------------
    # Phillies pitching
    # -----------------------------------------------------
    pitching = build_phillies_pitching(
        boxscore,
        side
    )
    # -----------------------------------------------------
    # Current
    # -----------------------------------------------------
    current_game = build_current_game(
        live_feed,
        side
    )
    # -----------------------------------------------------
    # RETURN
    # -----------------------------------------------------
    return {
        "game":
            game_info,
        "location":
            (
                "HOME"
                if side == "home"
                else "AWAY"
            ),
        "score": {
            "away": {
                "runs":
                    game_data
                    .get(
                        "teams",
                        {}
                    )
                    .get(
                        "away",
                        {}
                    )
                    .get(
                        "score"
                    ),
                "hits":
                    game_data
                    .get(
                        "teams",
                        {}
                    )
                    .get(
                        "away",
                        {}
                    )
                    .get(
                        "hits"
                    ),
                "errors":
                    game_data
                    .get(
                        "teams",
                        {}
                    )
                    .get(
                        "away",
                        {}
                    )
                    .get(
                        "errors"
                    )
            },
            "home": {
                "runs":
                    game_data
                    .get(
                        "teams",
                        {}
                    )
                    .get(
                        "home",
                        {}
                    )
                    .get(
                        "score"
                    ),
                "hits":
                    game_data
                    .get(
                        "teams",
                        {}
                    )
                    .get(
                        "home",
                        {}
                    )
                    .get(
                        "hits"
                    ),
                "errors":
                    game_data
                    .get(
                        "teams",
                        {}
                    )
                    .get(
                        "home",
                        {}
                    )
                    .get(
                        "errors"
                    )
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
# EMPTY
# =========================================================
def empty_data(
    game_date
):
    return {
        "team": {
            "id":
                TEAM_ID,
            "name":
                "Philadelphia Phillies",
            "abbreviation":
                "PHI"
        },
        "season":
            SEASON,
        "date":
            game_date,
        "updated":
            datetime.now(
                JST
            ).isoformat(),
        "gameCount":
            0,
        "games":
            []
    }
# =========================================================
# MAIN
# =========================================================
def main():
    game_date = get_today()
    print(
        "========================================"
    )
    print(
        "PHILLIES SCORE UPDATE"
    )
    print(
        "Date:",
        game_date
    )
    print(
        "========================================"
    )
    games = get_today_games(
        game_date
    )
    # -----------------------------------------------------
    # No game
    # -----------------------------------------------------
    if not games:
        data = empty_data(
            game_date
        )
    else:
        result_games = []
        for scheduled_game in games:
            try:
                result = build_game(
                    scheduled_game
                )
                if result is not None:
                    result_games.append(
                        result
                    )
            except Exception as error:
                print(
                    "ERROR:",
                    scheduled_game.get(
                        "gamePk"
                    ),
                    error
                )
        data = {
            "team": {
                "id":
                    TEAM_ID,
                "name":
                    "Philadelphia Phillies",
                "abbreviation":
                    "PHI"
            },
            "season":
                SEASON,
            "date":
                game_date,
            "updated":
                datetime.now(
                    JST
                ).isoformat(),
            "gameCount":
                len(
                    result_games
                ),
            "games":
                result_games
        }
    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------
    os.makedirs(
        "data",
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
    print(
        "========================================"
    )
    print(
        "Saved:",
        OUTPUT_FILE
    )
    print(
        "Games:",
        data.get(
            "gameCount"
        )
    )
    print(
        "Updated:",
        data.get(
            "updated"
        )
    )
    print(
        "========================================"
    )
# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    main()
