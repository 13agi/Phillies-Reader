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
# SELECT RELEVANT GAME
#
# MLB APIのgameDateはUTC。
#
# 日本時間の日付をまたぐ試合を正しく扱う。
#
# 優先順位
#
# 1. LIVE中の試合
# 2. すでに開始した試合
# 3. 次に開始する未来の試合
#
# これにより、日本時間8/11になっていても、
# 8/10の試合がLIVEなら8/10の試合を取得する。
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

    # -----------------------------------------------------
    # 昨日・今日・明日の試合を取得
    # -----------------------------------------------------

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
    # 時刻情報を作成
    # -----------------------------------------------------

    candidates = []

    for game in all_games:

        game_date_raw = game.get(
            "gameDate"
        )

        if not game_date_raw:

            continue

        try:

            # MLB APIのgameDateはUTC

            game_dt_utc = (
                datetime.fromisoformat(
                    game_date_raw.replace(
                        "Z",
                        "+00:00"
                    )
                )
            )

            # JSTへ変換

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
    # 1. LIVE GAME
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

        print(
            "========================================"
        )

        print(
            "LIVE GAME FOUND"
        )

        print(
            "Game:",
            live_games[0]["game"].get(
                "gamePk"
            )
        )

        print(
            "Start JST:",
            live_games[0]["start"].isoformat()
        )

        print(
            "========================================"
        )

        return [

            item["game"]

            for item in live_games

        ]

    # =====================================================
    # 2. ALREADY STARTED GAME
    #
    # Final / Postponedなど。
    #
    # まだ始まっていないPreviewはここに入らない。
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
                "Postponed"
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
            "========================================"
        )

        print(
            "SELECTED STARTED GAME"
        )

        print(
            "Game:",
            selected["game"].get(
                "gamePk"
            )
        )

        print(
            "Start JST:",
            selected["start"].isoformat()
        )

        print(
            "Status:",
            selected["status"]
        )

        print(
            "========================================"
        )

        return [

            selected["game"]

        ]

    # =====================================================
    # 3. FUTURE GAME
    #
    # まだ試合が始まっていない場合のみ、
    # 次に開始する試合を返す。
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
            "========================================"
        )

        print(
            "NEXT FUTURE GAME"
        )

        print(
            "Game:",
            selected["game"].get(
                "gamePk"
            )
        )

        print(
            "Start JST:",
            selected["start"].isoformat()
        )

        print(
            "========================================"
        )

        return [

            selected["game"]

        ]

    # =====================================================
    # 4. NOTHING
    # =====================================================

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
    # battingOrderが存在しない場合
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
    # 打順順
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
    # Phillies攻撃中
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
    # -----------------------------------------------------

    boxscore = get_boxscore(
        game_pk
    )

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
    # Game info
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

    now = get_now_jst()

    game_date = now.strftime(
        "%Y-%m-%d"
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
        "Display Date:",
        game_date
    )

    print(
        "========================================"
    )

    # =====================================================
    # 重要
    #
    # 「今日」だけではなく、
    # 昨日・今日・明日から実際の対象試合を選ぶ。
    # =====================================================

    games = get_relevant_games()

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
