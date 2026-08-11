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
# TIME
# =========================================================

def get_now_jst():

    return datetime.now(JST)


def get_date_string(date_value):

    return date_value.strftime(
        "%Y-%m-%d"
    )


# =========================================================
# SAFE HELPERS
# =========================================================

def safe_dict(value):

    if isinstance(value, dict):
        return value

    return {}


def safe_list(value):

    if isinstance(value, list):
        return value

    return []


def player_name(player):

    player = safe_dict(player)

    person = safe_dict(
        player.get("person")
    )

    return (
        person.get("fullName")
        or player.get("fullName")
        or "-"
    )


def player_id(player):

    player = safe_dict(player)

    person = safe_dict(
        player.get("person")
    )

    return person.get("id")


def stat(stats, key):

    stats = safe_dict(stats)

    return stats.get(key)


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

    for date_block in safe_list(
        data.get("dates")
    ):

        for game in safe_list(
            date_block.get("games")
        ):

            games.append(game)

    return games


# =========================================================
# SELECT LATEST / CURRENT GAME
#
# 優先順位
#
# 1. LIVE
# 2. 今日/昨日の終了済み試合
# 3. 次の試合
#
# 日本時間を基準にする。
# =========================================================

def get_relevant_game():

    now = get_now_jst()

    today = now.date()

    dates = [
        today - timedelta(days=2),
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


    if not all_games:

        return None


    candidates = []


    # -----------------------------------------------------
    # 時刻変換
    # -----------------------------------------------------

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

        except Exception:

            continue


        status = safe_dict(
            game.get("status")
        )

        abstract = status.get(
            "abstractGameState"
        )

        detailed = status.get(
            "detailedState"
        )


        candidates.append({

            "game": game,

            "start": game_dt_jst,

            "abstract": abstract,

            "detailed": detailed

        })


    # =====================================================
    # 1. LIVE
    # =====================================================

    live_games = [

        item

        for item in candidates

        if item["abstract"]
        in (
            "Live",
            "In Progress"
        )

    ]


    if live_games:

        live_games.sort(
            key=lambda x:
                x["start"],
            reverse=True
        )

        selected = live_games[0]

        print(
            "LIVE GAME:",
            selected["game"].get(
                "gamePk"
            )
        )

        return selected["game"]


    # =====================================================
    # 2. COMPLETED / STARTED
    #
    # 最新の終了済み試合を選ぶ
    # =====================================================

    started_games = [

        item

        for item in candidates

        if (
            item["start"] <= now
            and
            item["abstract"]
            in (
                "Final",
                "Postponed",
                "Cancelled",
                "Suspended"
            )
        )

    ]


    if started_games:

        started_games.sort(
            key=lambda x:
                x["start"],
            reverse=True
        )

        selected = started_games[0]

        print(
            "LATEST COMPLETED GAME:",
            selected["game"].get(
                "gamePk"
            )
        )

        return selected["game"]


    # =====================================================
    # 3. 次の試合
    # =====================================================

    future_games = [

        item

        for item in candidates

        if item["start"] > now

    ]


    if future_games:

        future_games.sort(
            key=lambda x:
                x["start"]
        )

        selected = future_games[0]

        print(
            "NEXT GAME:",
            selected["game"].get(
                "gamePk"
            )
        )

        return selected["game"]


    return None


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
# ここが今回の重要部分。
#
# 1. 専用 /linescore
# 2. feed/live の linescore
#
# の順で取得。
# =========================================================

def get_linescore(game_pk, live_feed):

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

        if safe_list(
            data.get("innings")
        ):

            print(
                "Linescore endpoint: OK"
            )

            return data

    except Exception as error:

        print(
            "Linescore endpoint error:",
            error
        )


    # -----------------------------------------------------
    # ② Live Feed
    # -----------------------------------------------------

    live_data = safe_dict(
        live_feed.get(
            "liveData"
        )
    )

    linescore = safe_dict(
        live_data.get(
            "linescore"
        )
    )


    if safe_list(
        linescore.get("innings")
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

    teams = safe_dict(
        game_data.get(
            "teams"
        )
    )

    home = safe_dict(
        teams.get("home")
    )

    away = safe_dict(
        teams.get("away")
    )

    home_team = safe_dict(
        home.get("team")
    )

    away_team = safe_dict(
        away.get("team")
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
# GAME INFO
# =========================================================

def build_game_info(
    game_data
):

    teams = safe_dict(
        game_data.get(
            "teams"
        )
    )

    home = safe_dict(
        teams.get("home")
    )

    away = safe_dict(
        teams.get("away")
    )

    home_team = safe_dict(
        home.get("team")
    )

    away_team = safe_dict(
        away.get("team")
    )

    venue = safe_dict(
        game_data.get(
            "venue"
        )
    )

    status = safe_dict(
        game_data.get(
            "status"
        )
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

    linescore = safe_dict(
        linescore
    )

    innings = safe_list(
        linescore.get(
            "innings"
        )
    )

    result = []


    for inning in innings:

        inning = safe_dict(
            inning
        )

        away = safe_dict(
            inning.get(
                "away"
            )
        )

        home = safe_dict(
            inning.get(
                "home"
            )
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
# BATTING
# =========================================================

def build_phillies_batting(
    boxscore,
    side
):

    teams = safe_dict(
        boxscore.get(
            "teams"
        )
    )

    team = safe_dict(
        teams.get(
            side
        )
    )

    players = safe_dict(
        team.get(
            "players"
        )
    )

    batting_order = safe_list(
        team.get(
            "battingOrder"
        )
    )


    result = []


    # -----------------------------------------------------
    # battingOrderを使う
    # -----------------------------------------------------

    for sequence, pid in enumerate(
        batting_order,
        start=1
    ):

        player = safe_dict(
            players.get(
                f"ID{pid}"
            )
        )

        if not player:
            continue


        stats = safe_dict(
            player.get(
                "stats"
            )
        )

        batting = safe_dict(
            stats.get(
                "batting"
            )
        )

        position = safe_dict(
            player.get(
                "position"
            )
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
                stat(
                    batting,
                    "plateAppearances"
                ),

            "H":
                stat(
                    batting,
                    "hits"
                ),

            "HR":
                stat(
                    batting,
                    "homeRuns"
                ),

            "RBI":
                stat(
                    batting,
                    "rbi"
                ),

            "BB":
                stat(
                    batting,
                    "baseOnBalls"
                ),

            "AB":
                stat(
                    batting,
                    "atBats"
                ),

            "R":
                stat(
                    batting,
                    "runs"
                ),

            "SO":
                stat(
                    batting,
                    "strikeOuts"
                )

        })


    # -----------------------------------------------------
    # 念のためplayersからも回収
    # -----------------------------------------------------

    if not result:

        for key, player in players.items():

            player = safe_dict(
                player
            )

            stats = safe_dict(
                player.get(
                    "stats"
                )
            )

            batting = safe_dict(
                stats.get(
                    "batting"
                )
            )

            pa = batting.get(
                "plateAppearances"
            )

            if pa is None:
                continue


            position = safe_dict(
                player.get(
                    "position"
                )
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
# PITCHING
# =========================================================

def build_phillies_pitching(
    boxscore,
    side
):

    teams = safe_dict(
        boxscore.get(
            "teams"
        )
    )

    team = safe_dict(
        teams.get(
            side
        )
    )

    players = safe_dict(
        team.get(
            "players"
        )
    )

    pitcher_ids = safe_list(
        team.get(
            "pitchers"
        )
    )


    result = []


    for sequence, pid in enumerate(
        pitcher_ids,
        start=1
    ):

        player = safe_dict(
            players.get(
                f"ID{pid}"
            )
        )

        if not player:
            continue


        stats = safe_dict(
            player.get(
                "stats"
            )
        )

        pitching = safe_dict(
            stats.get(
                "pitching"
            )
        )


        ip = pitching.get(
            "inningsPitched"
        )

        pitches = pitching.get(
            "pitchesThrown"
        )


        if (
            ip is None
            and
            pitches is None
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
                stat(
                    pitching,
                    "inningsPitched"
                ),

            "H":
                stat(
                    pitching,
                    "hits"
                ),

            "K":
                stat(
                    pitching,
                    "strikeOuts"
                ),

            "HR":
                stat(
                    pitching,
                    "homeRuns"
                ),

            "R":
                stat(
                    pitching,
                    "runs"
                ),

            "ER":
                stat(
                    pitching,
                    "earnedRuns"
                ),

            "BB":
                stat(
                    pitching,
                    "baseOnBalls"
                ),

            "pitches":
                stat(
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

    live_data = safe_dict(
        live_feed.get(
            "liveData"
        )
    )

    plays = safe_dict(
        live_data.get(
            "plays"
        )
    )

    linescore = safe_dict(
        live_data.get(
            "linescore"
        )
    )

    current_play = (
        plays.get(
            "currentPlay"
        )
    )


    empty = {

        "available": False,

        "isPhilliesBatting": None,

        "inning": None,

        "half": None,

        "outs": None,

        "balls": None,

        "strikes": None,

        "pitcher": None,

        "batter": None,

        "lastPitch": None,

        "runners": {

            "first": False,

            "second": False,

            "third": False

        }

    }


    if not current_play:

        return empty


    about = safe_dict(
        current_play.get(
            "about"
        )
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


    count = safe_dict(
        current_play.get(
            "count"
        )
    )


    matchup = safe_dict(
        current_play.get(
            "matchup"
        )
    )

    pitcher = safe_dict(
        matchup.get(
            "pitcher"
        )
    )

    batter = safe_dict(
        matchup.get(
            "batter"
        )
    )

    pitch_hand = safe_dict(
        matchup.get(
            "pitchHand"
        )
    )

    bat_side = safe_dict(
        matchup.get(
            "batSide"
        )
    )


    # -----------------------------------------------------
    # runners
    # -----------------------------------------------------

    offense = safe_dict(
        linescore.get(
            "offense"
        )
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
    # last pitch
    # -----------------------------------------------------

    last_pitch = {

        "speed": None,

        "type": None

    }


    play_events = safe_list(
        current_play.get(
            "playEvents"
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


        pitch_data = safe_dict(
            event.get(
                "pitchData"
            )
        )

        details = safe_dict(
            event.get(
                "details"
            )
        )

        pitch_type = safe_dict(
            details.get(
                "type"
            )
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

        "available": True,

        "isPhilliesBatting":
            is_phillies_batting,

        "inning":
            inning,

        "half":
            half,

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
    # live feed
    # -----------------------------------------------------

    live_feed = get_live_feed(
        game_pk
    )


    live_game_data = safe_dict(
        live_feed.get(
            "gameData"
        )
    )

    live_data = safe_dict(
        live_feed.get(
            "liveData"
        )
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
    # boxscore
    # -----------------------------------------------------

    boxscore = get_boxscore(
        game_pk
    )


    if not boxscore:

        boxscore = safe_dict(
            live_data.get(
                "boxscore"
            )
        )


    # -----------------------------------------------------
    # LINESCORE
    #
    # 専用endpointを最優先。
    # これでFinal試合でもinningScoresを取得する。
    # -----------------------------------------------------

    linescore = get_linescore(
        game_pk,
        live_feed
    )


    # -----------------------------------------------------
    # game info
    # -----------------------------------------------------

    game_info = build_game_info(
        game_data
    )


    # -----------------------------------------------------
    # batting
    # -----------------------------------------------------

    batting = build_phillies_batting(
        boxscore,
        side
    )


    # -----------------------------------------------------
    # pitching
    # -----------------------------------------------------

    pitching = build_phillies_pitching(
        boxscore,
        side
    )


    # -----------------------------------------------------
    # current game
    # -----------------------------------------------------

    current_game = build_current_game(
        live_feed,
        side
    )


    # -----------------------------------------------------
    # score
    # -----------------------------------------------------

    teams = safe_dict(
        game_data.get(
            "teams"
        )
    )

    away = safe_dict(
        teams.get(
            "away"
        )
    )

    home = safe_dict(
        teams.get(
            "home"
        )
    )


    return {

        "game": game_info,

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
# EMPTY DATA
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
    # 最新/現在の試合
    # -----------------------------------------------------

    game = get_relevant_game()


    # -----------------------------------------------------
    # no game
    # -----------------------------------------------------

    if game is None:

        data = empty_data(
            game_date
        )


    else:

        result = None


        try:

            result = build_game(
                game
            )

        except Exception as error:

            print(
                "BUILD ERROR:",
                error
            )


        if result is None:

            data = empty_data(
                game_date
            )

        else:

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
                    1,

                "games": [

                    result

                ]

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


    if data.get("games"):

        game_data = (
            data["games"][0]
        )

        print(
            "GamePk:",
            game_data
            .get("game", {})
            .get("gamePk")
        )

        print(
            "Status:",
            game_data
            .get("game", {})
            .get("status", {})
            .get("abstract")
        )

        print(
            "Innings:",
            len(
                game_data.get(
                    "inningScores",
                    []
                )
            )
        )

        print(
            "Batters:",
            len(
                game_data.get(
                    "philliesBatting",
                    []
                )
            )
        )

        print(
            "Pitchers:",
            len(
                game_data.get(
                    "philliesPitching",
                    []
                )
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
