import json
import os
import requests

from datetime import datetime, timezone, timedelta


# =========================================================
# CONFIG
# =========================================================

TEAM_ID = 143
TEAM_NAME = "Philadelphia Phillies"
TEAM_ABBR = "PHI"
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

def player_name(player):

    person = (
        player.get("person")
        or {}
    )

    return (
        person.get("fullName")
        or player.get("fullName")
        or "-"
    )


def player_id(player):

    person = (
        player.get("person")
        or {}
    )

    return person.get("id")


def batting_stat(stats, key):

    return stats.get(key)


def pitching_stat(stats, key):

    return stats.get(key)


# =========================================================
# TIME
# =========================================================

def get_now_jst():

    return datetime.now(JST)


def get_date_string(date_value):

    return date_value.strftime(
        "%Y-%m-%d"
    )


# =========================================================
# SCHEDULE
# =========================================================

def get_games_by_date(game_date):

    url = (
        f"{BASE_URL}/schedule"
    )

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
# SELECT RELEVANT GAME
#
# 優先順位
#
# 1. LIVE
# 2. 最新の開始済み試合
# 3. 次の試合
#
# 日本時間を基準にする。
# =========================================================

def get_relevant_games():

    now = get_now_jst()

    today = now.date()

    dates = [
        today - timedelta(days=1),
        today,
        today + timedelta(days=1)
    ]

    all_games = []


    for date_value in dates:

        date_string = (
            get_date_string(
                date_value
            )
        )

        print(
            "Fetching schedule:",
            date_string
        )

        try:

            games = get_games_by_date(
                date_string
            )

            all_games.extend(
                games
            )

        except Exception as error:

            print(
                "Schedule error:",
                date_string,
                error
            )


    # -----------------------------------------------------
    # 重複除去
    # -----------------------------------------------------

    unique_games = {}

    for game in all_games:

        game_pk = game.get(
            "gamePk"
        )

        if game_pk is not None:

            unique_games[
                game_pk
            ] = game


    all_games = list(
        unique_games.values()
    )


    print(
        "Total candidate games:",
        len(all_games)
    )


    # -----------------------------------------------------
    # 候補作成
    # -----------------------------------------------------

    candidates = []


    for game in all_games:

        game_date_raw = game.get(
            "gameDate"
        )

        if not game_date_raw:
            continue


        try:

            game_dt_utc = (
                datetime.fromisoformat(
                    game_date_raw.replace(
                        "Z",
                        "+00:00"
                    )
                )
            )

            game_dt_jst = (
                game_dt_utc.astimezone(
                    JST
                )
            )

        except Exception as error:

            print(
                "Date conversion error:",
                error
            )

            continue


        status = (
            game.get(
                "status",
                {}
            )
            or {}
        )


        abstract = status.get(
            "abstractGameState"
        )

        detailed = status.get(
            "detailedState"
        )


        print(
            "Candidate:",
            game.get("gamePk"),
            "UTC:",
            game_date_raw,
            "JST:",
            game_dt_jst.isoformat(),
            "status:",
            abstract,
            detailed
        )


        candidates.append({

            "game":
                game,

            "start":
                game_dt_jst,

            "status":
                abstract,

            "detailed":
                detailed

        })


    # =====================================================
    # 1. LIVE
    # =====================================================

    live_games = [

        item

        for item in candidates

        if item["status"] == "Live"

    ]


    if live_games:

        live_games.sort(
            key=lambda item:
                item["start"],
            reverse=True
        )


        selected = live_games[0]


        print(
            "LIVE GAME FOUND:",
            selected["game"].get(
                "gamePk"
            )
        )


        return [
            selected["game"]
        ]


    # =====================================================
    # 2. STARTED / FINAL
    # =====================================================

    started_games = [

        item

        for item in candidates

        if (
            item["start"] <= now
            and
            item["status"]
            in (
                "Live",
                "Final",
                "Postponed",
                "Cancelled",
                "Suspended"
            )
        )

    ]


    if started_games:

        started_games.sort(
            key=lambda item:
                item["start"],
            reverse=True
        )


        selected = (
            started_games[0]
        )


        print(
            "SELECTED STARTED GAME:",
            selected["game"].get(
                "gamePk"
            )
        )


        return [
            selected["game"]
        ]


    # =====================================================
    # 3. FUTURE
    # =====================================================

    future_games = [

        item

        for item in candidates

        if item["start"] > now

    ]


    if future_games:

        future_games.sort(
            key=lambda item:
                item["start"]
        )


        selected = (
            future_games[0]
        )


        print(
            "NEXT FUTURE GAME:",
            selected["game"].get(
                "gamePk"
            )
        )


        return [
            selected["game"]
        ]


    print(
        "NO RELEVANT GAME FOUND"
    )


    return []


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
# LINESCORE
#
# 今回追加した重要部分
#
# 専用 Linescore API を最優先する。
#
# /game/{gamePk}/linescore
#
# 取得できなかった場合は
# feed/live の linescore を使用。
# =========================================================

def get_linescore(
    game_pk,
    live_feed
):

    # -----------------------------------------------------
    # ① 専用 Linescore API
    # -----------------------------------------------------

    url = (
        f"{BASE_URL}/game/"
        f"{game_pk}/linescore"
    )


    try:

        data = get_json(
            url
        )


        if data.get(
            "innings"
        ):

            print(
                "Linescore API: OK"
            )

            return data


    except Exception as error:

        print(
            "Linescore API error:",
            error
        )


    # -----------------------------------------------------
    # ② feed/live fallback
    # -----------------------------------------------------

    live_data = (
        live_feed.get(
            "liveData",
            {}
        )
        or {}
    )


    linescore = (
        live_data.get(
            "linescore",
            {}
        )
        or {}
    )


    if linescore.get(
        "innings"
    ):

        print(
            "Linescore from live feed: OK"
        )

        return linescore


    print(
        "Linescore unavailable"
    )


    return {}


# =========================================================
# PHILLIES SIDE
# =========================================================

def get_phillies_side(
    game_data
):

    teams = (
        game_data.get(
            "teams",
            {}
        )
        or {}
    )


    home = (
        teams.get(
            "home",
            {}
        )
        or {}
    )


    away = (
        teams.get(
            "away",
            {}
        )
        or {}
    )


    home_team = (
        home.get(
            "team",
            {}
        )
        or {}
    )


    away_team = (
        away.get(
            "team",
            {}
        )
        or {}
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
        game_data.get(
            "teams",
            {}
        )
        or {}
    )


    home = (
        teams.get(
            "home",
            {}
        )
        or {}
    )


    away = (
        teams.get(
            "away",
            {}
        )
        or {}
    )


    home_team = (
        home.get(
            "team",
            {}
        )
        or {}
    )


    away_team = (
        away.get(
            "team",
            {}
        )
        or {}
    )


    venue = (
        game_data.get(
            "venue",
            {}
        )
        or {}
    )


    status = (
        game_data.get(
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
        linescore.get(
            "innings",
            []
        )
        or []
    )


    result = []


    for inning in innings:

        away = (
            inning.get(
                "away",
                {}
            )
            or {}
        )


        home = (
            inning.get(
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
                ),

            "awayLOB":
                away.get(
                    "leftOnBase"
                ),

            "homeLOB":
                home.get(
                    "leftOnBase"
                )

        })


    return result


# =========================================================
# PHILLIES BATTING
# =========================================================

def build_phillies_batting(
    boxscore,
    side
):

    teams = (
        boxscore.get(
            "teams",
            {}
        )
        or {}
    )


    team = (
        teams.get(
            side,
            {}
        )
        or {}
    )


    players = (
        team.get(
            "players",
            {}
        )
        or {}
    )


    batting_order = (
        team.get(
            "battingOrder",
            []
        )
        or []
    )


    result = []


    # -----------------------------------------------------
    # battingOrder
    # -----------------------------------------------------

    for sequence, pid in enumerate(
        batting_order,
        start=1
    ):

        player = (
            players.get(
                f"ID{pid}",
                {}
            )
            or {}
        )


        if not player:
            continue


        stats_container = (
            player.get(
                "stats",
                {}
            )
            or {}
        )


        batting = (
            stats_container.get(
                "batting",
                {}
            )
            or {}
        )


        order_raw = (
            player.get(
                "battingOrder"
            )
            or ""
        )


        try:

            order_number = int(
                str(
                    order_raw
                )[:1]
            )

        except Exception:

            order_number = None


        position = (
            player.get(
                "position",
                {}
            )
            or {}
        )


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
                position.get(
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
    # fallback
    # -----------------------------------------------------

    if not result:

        for player in players.values():

            if not isinstance(
                player,
                dict
            ):
                continue


            stats_container = (
                player.get(
                    "stats",
                    {}
                )
                or {}
            )


            batting = (
                stats_container.get(
                    "batting",
                    {}
                )
                or {}
            )


            if not batting:
                continue


            if (
                batting.get(
                    "plateAppearances"
                )
                is None
            ):
                continue


            position = (
                player.get(
                    "position",
                    {}
                )
                or {}
            )


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
                    position.get(
                        "abbreviation"
                    ),

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
# =========================================================

def build_phillies_pitching(
    boxscore,
    side
):

    teams = (
        boxscore.get(
            "teams",
            {}
        )
        or {}
    )


    team = (
        teams.get(
            side,
            {}
        )
        or {}
    )


    players = (
        team.get(
            "players",
            {}
        )
        or {}
    )


    pitcher_ids = (
        team.get(
            "pitchers",
            []
        )
        or []
    )


    result = []


    for sequence, pid in enumerate(
        pitcher_ids,
        start=1
    ):

        player = (
            players.get(
                f"ID{pid}",
                {}
            )
            or {}
        )


        if not player:
            continue


        stats_container = (
            player.get(
                "stats",
                {}
            )
            or {}
        )


        pitching = (
            stats_container.get(
                "pitching",
                {}
            )
            or {}
        )


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
        live_feed.get(
            "liveData",
            {}
        )
        or {}
    )


    plays = (
        live_data.get(
            "plays",
            {}
        )
        or {}
    )


    linescore = (
        live_data.get(
            "linescore",
            {}
        )
        or {}
    )


    current_play = (
        plays.get(
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
        current_play.get(
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


    if side == "home":

        is_phillies_batting = (
            half == "bottom"
        )

    else:

        is_phillies_batting = (
            half == "top"
        )


    count = (
        current_play.get(
            "count",
            {}
        )
        or {}
    )


    matchup = (
        current_play.get(
            "matchup",
            {}
        )
        or {}
    )


    pitcher = (
        matchup.get(
            "pitcher",
            {}
        )
        or {}
    )


    batter = (
        matchup.get(
            "batter",
            {}
        )
        or {}
    )


    pitch_hand = (
        matchup.get(
            "pitchHand",
            {}
        )
        or {}
    )


    bat_side = (
        matchup.get(
            "batSide",
            {}
        )
        or {}
    )


    # -----------------------------------------------------
    # runners
    # -----------------------------------------------------

    offense = (
        linescore.get(
            "offense",
            {}
        )
        or {}
    )


    runners = {

        "first":
            offense.get(
                "first"
            ) is not None,

        "second":
            offense.get(
                "second"
            ) is not None,

        "third":
            offense.get(
                "third"
            ) is not None

    }


    # -----------------------------------------------------
    # last pitch
    # -----------------------------------------------------

    last_pitch = {

        "speed":
            None,

        "type":
            None

    }


    play_events = (
        current_play.get(
            "playEvents",
            []
        )
        or []
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
            event.get(
                "pitchData",
                {}
            )
            or {}
        )


        details = (
            event.get(
                "details",
                {}
            )
            or {}
        )


        pitch_type = (
            details.get(
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
    # LIVE FEED
    # -----------------------------------------------------

    live_feed = get_live_feed(
        game_pk
    )


    live_game_data = (
        live_feed.get(
            "gameData",
            {}
        )
        or {}
    )


    live_data = (
        live_feed.get(
            "liveData",
            {}
        )
        or {}
    )


    if live_game_data:

        game_data = (
            live_game_data
        )

    else:

        game_data = (
            scheduled_game
        )


    # -----------------------------------------------------
    # Phillies side
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
    # BOXSCORE
    # -----------------------------------------------------

    boxscore = get_boxscore(
        game_pk
    )


    if not boxscore:

        boxscore = (
            live_data.get(
                "boxscore",
                {}
            )
            or {}
        )


    # -----------------------------------------------------
    # LINESCORE
    #
    # ★今回の追加点
    #
    # 専用APIを取得するのでFinal試合でも
    # inningScoresが空になりにくい。
    # -----------------------------------------------------

    linescore = get_linescore(
        game_pk,
        live_feed
    )


    # -----------------------------------------------------
    # GAME INFO
    # -----------------------------------------------------

    game_info = build_game_info(
        game_data
    )


    # -----------------------------------------------------
    # BATTING
    # -----------------------------------------------------

    batting = build_phillies_batting(
        boxscore,
        side
    )


    # -----------------------------------------------------
    # PITCHING
    # -----------------------------------------------------

    pitching = build_phillies_pitching(
        boxscore,
        side
    )


    # -----------------------------------------------------
    # CURRENT GAME
    # -----------------------------------------------------

    current_game = build_current_game(
        live_feed,
        side
    )


    teams = (
        game_data.get(
            "teams",
            {}
        )
        or {}
    )


    away = (
        teams.get(
            "away",
            {}
        )
        or {}
    )


    home = (
        teams.get(
            "home",
            {}
        )
        or {}
    )


    # =====================================================
    # RETURN
    # =====================================================

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

            "home": {

                "runs":
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
                TEAM_NAME,

            "abbreviation":
                TEAM_ABBR

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

    now = get_now_jst()

    game_date = (
        now.strftime(
            "%Y-%m-%d"
        )
    )


    print(
        "========================================"
    )

    print(
        "PHILLIES SCORE UPDATE"
    )

    print(
        "JST:",
        now.isoformat()
    )

    print(
        "========================================"
    )


    # -----------------------------------------------------
    # 最新の対象試合を取得
    # -----------------------------------------------------

    games = get_relevant_games()


    # -----------------------------------------------------
    # 試合なし
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
                    TEAM_NAME,

                "abbreviation":
                    TEAM_ABBR

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


    # =====================================================
    # SAVE
    # =====================================================

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


    # =====================================================
    # LOG
    # =====================================================

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


    if data.get(
        "games"
    ):

        game = (
            data["games"][0]
        )


        print(
            "GamePk:",
            game
            .get(
                "game",
                {}
            )
            .get(
                "gamePk"
            )
        )


        print(
            "Status:",
            game
            .get(
                "game",
                {}
            )
            .get(
                "status",
                {}
            )
            .get(
                "abstract"
            )
        )


        print(
            "Innings:",
            len(
                game.get(
                    "inningScores",
                    []
                )
            )
        )


        print(
            "Batters:",
            len(
                game.get(
                    "philliesBatting",
                    []
                )
            )
        )


        print(
            "Pitchers:",
            len(
                game.get(
                    "philliesPitching",
                    []
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
