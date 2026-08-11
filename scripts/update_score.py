import json
import os
import requests

from datetime import datetime, timezone, timedelta


# =========================================================
# Philadelphia Phillies
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
# API REQUEST
# =========================================================

def get_json(
    url,
    params=None
):

    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={
            "User-Agent":
                "Phillies-Reader/1.0"
        }
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# TIME
# =========================================================

def get_now_jst():

    return datetime.now(
        JST
    )


def parse_game_datetime(
    value
):

    if not value:
        return None

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        ).astimezone(
            JST
        )

    except Exception:

        return None


# =========================================================
# SCHEDULE API
#
# Score専用。
#
# ScheduleのJSONは使用しない。
# MLB APIから最新試合を直接取得する。
# =========================================================

def get_games_by_date(
    game_date
):

    url = (
        f"{BASE_URL}/schedule"
    )

    params = {

        "sportId":
            1,

        "teamId":
            TEAM_ID,

        "season":
            SEASON,

        "date":
            game_date,

        "hydrate":
            "team,venue,linescore"

    }

    data = get_json(
        url,
        params
    )

    games = []

    for date_data in data.get(
        "dates",
        []
    ):

        for game in date_data.get(
            "games",
            []
        ):

            games.append(
                game
            )

    return games


# =========================================================
# LATEST GAME
#
# 優先順位
#
# 1. LIVE
# 2. 直近の開始済み試合
# 3. 次の試合
#
# 日付変更機能は持たない。
# Scoreは常に最新の1試合だけを返す。
# =========================================================

def get_latest_game():

    now = get_now_jst()

    today = now.date()

    dates = [

        today - timedelta(
            days=1
        ),

        today,

        today + timedelta(
            days=1
        )

    ]

    all_games = {}

    for date_value in dates:

        date_string = (
            date_value.strftime(
                "%Y-%m-%d"
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

        except Exception as error:

            print(
                "Schedule API error:",
                date_string,
                error
            )

            continue

        for game in games:

            game_pk = game.get(
                "gamePk"
            )

            if game_pk is not None:

                all_games[
                    game_pk
                ] = game


    candidates = []

    for game in all_games.values():

        game_datetime = parse_game_datetime(
            game.get(
                "gameDate"
            )
        )

        if game_datetime is None:
            continue

        status = game.get(
            "status",
            {}
        ) or {}

        candidates.append({

            "game":
                game,

            "datetime":
                game_datetime,

            "status":
                status.get(
                    "abstractGameState",
                    ""
                ),

            "detailed":
                status.get(
                    "detailedState",
                    ""
                )

        })


    # =====================================================
    # LIVE
    # =====================================================

    live_games = [

        item

        for item in candidates

        if item["status"] == "Live"

    ]

    if live_games:

        live_games.sort(

            key=lambda item:
                item["datetime"],

            reverse=True

        )

        selected = (
            live_games[0]
        )

        print(
            "LIVE GAME:",
            selected["game"].get(
                "gamePk"
            )
        )

        return selected["game"]


    # =====================================================
    # STARTED / FINAL
    # =====================================================

    started_games = [

        item

        for item in candidates

        if (

            item["datetime"] <= now

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
                item["datetime"],

            reverse=True

        )

        selected = (
            started_games[0]
        )

        print(
            "LATEST GAME:",
            selected["game"].get(
                "gamePk"
            )
        )

        return selected["game"]


    # =====================================================
    # FUTURE
    # =====================================================

    future_games = [

        item

        for item in candidates

        if item["datetime"] > now

    ]

    if future_games:

        future_games.sort(

            key=lambda item:
                item["datetime"]

        )

        selected = (
            future_games[0]
        )

        print(
            "NEXT GAME:",
            selected["game"].get(
                "gamePk"
            )
        )

        return selected["game"]


    print(
        "NO GAME FOUND"
    )

    return None


# =========================================================
# LIVE FEED
# =========================================================

def get_live_feed(
    game_pk
):

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

def get_boxscore(
    game_pk
):

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
# PHILLIES SIDE
# =========================================================

def get_phillies_side(
    game
):

    teams = game.get(
        "teams",
        {}
    ) or {}

    home = teams.get(
        "home",
        {}
    ) or {}

    away = teams.get(
        "away",
        {}
    ) or {}

    home_team = home.get(
        "team",
        {}
    ) or {}

    away_team = away.get(
        "team",
        {}
    ) or {}

    if home_team.get(
        "id"
    ) == TEAM_ID:

        return "home"

    if away_team.get(
        "id"
    ) == TEAM_ID:

        return "away"

    return None


# =========================================================
# TEAM INFO
# =========================================================

def get_team_info(
    team
):

    team = team or {}

    return {

        "id":
            team.get(
                "id"
            ),

        "name":
            team.get(
                "name",
                ""
            ),

        "abbreviation":
            team.get(
                "abbreviation",
                ""
            )

    }


# =========================================================
# GAME INFORMATION
# =========================================================

def build_game_info(
    game
):

    teams = game.get(
        "teams",
        {}
    ) or {}

    home = teams.get(
        "home",
        {}
    ) or {}

    away = teams.get(
        "away",
        {}
    ) or {}

    home_team = get_team_info(
        home.get(
            "team",
            {}
        )
    )

    away_team = get_team_info(
        away.get(
            "team",
            {}
        )
    )

    status = game.get(
        "status",
        {}
    ) or {}

    venue = game.get(
        "venue",
        {}
    ) or {}

    return {

        "gamePk":
            game.get(
                "gamePk"
            ),

        "gameDate":
            game.get(
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
                    "name",
                    ""
                )

        }

    }


# =========================================================
# INNING SCORES
#
# Schedule APIのhydrate=linescoreから取得。
#
# これが現在のscore.jsonで空になっている部分。
# =========================================================

def get_inning_scores(
    game
):

    linescore = game.get(
        "linescore",
        {}
    ) or {}

    innings = linescore.get(
        "innings",
        []
    ) or []

    result = []

    for inning in innings:

        away = inning.get(
            "away",
            {}
        ) or {}

        home = inning.get(
            "home",
            {}
        ) or {}

        result.append({

            "inning":
                inning.get(
                    "num"
                ),

            "away":
                away.get(
                    "runs",
                    0
                ),

            "home":
                home.get(
                    "runs",
                    0
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
# BATTING
# =========================================================

def get_phillies_batting(
    boxscore,
    side
):

    teams = boxscore.get(
        "teams",
        {}
    ) or {}

    team = teams.get(
        side,
        {}
    ) or {}

    players = team.get(
        "players",
        {}
    ) or {}

    batting_order = team.get(
        "battingOrder",
        []
    ) or []

    result = []

    for sequence, player_id in enumerate(
        batting_order,
        start=1
    ):

        player = players.get(
            f"ID{player_id}",
            {}
        ) or {}

        if not player:
            continue

        stats = player.get(
            "stats",
            {}
        ) or {}

        batting = stats.get(
            "batting",
            {}
        ) or {}

        person = player.get(
            "person",
            {}
        ) or {}

        position = player.get(
            "position",
            {}
        ) or {}

        raw_order = player.get(
            "battingOrder",
            ""
        ) or ""

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
                person.get(
                    "id",
                    player_id
                ),

            "name":
                person.get(
                    "fullName",
                    ""
                ),

            "position":
                position.get(
                    "abbreviation"
                ),

            "PA":
                batting.get(
                    "plateAppearances",
                    0
                ),

            "H":
                batting.get(
                    "hits",
                    0
                ),

            "HR":
                batting.get(
                    "homeRuns",
                    0
                ),

            "RBI":
                batting.get(
                    "rbi",
                    0
                ),

            "BB":
                batting.get(
                    "baseOnBalls",
                    0
                ),

            "AB":
                batting.get(
                    "atBats",
                    0
                ),

            "R":
                batting.get(
                    "runs",
                    0
                ),

            "SO":
                batting.get(
                    "strikeOuts",
                    0
                )

        })

    return result


# =========================================================
# PITCHING
# =========================================================

def get_phillies_pitching(
    boxscore,
    side
):

    teams = boxscore.get(
        "teams",
        {}
    ) or {}

    team = teams.get(
        side,
        {}
    ) or {}

    players = team.get(
        "players",
        {}
    ) or {}

    pitcher_ids = team.get(
        "pitchers",
        []
    ) or []

    result = []

    for sequence, player_id in enumerate(
        pitcher_ids,
        start=1
    ):

        player = players.get(
            f"ID{player_id}",
            {}
        ) or {}

        if not player:
            continue

        stats = player.get(
            "stats",
            {}
        ) or {}

        pitching = stats.get(
            "pitching",
            {}
        ) or {}

        person = player.get(
            "person",
            {}
        ) or {}

        result.append({

            "sequence":
                sequence,

            "playerId":
                person.get(
                    "id",
                    player_id
                ),

            "name":
                person.get(
                    "fullName",
                    ""
                ),

            "IP":
                pitching.get(
                    "inningsPitched"
                ),

            "H":
                pitching.get(
                    "hits"
                ),

            "K":
                pitching.get(
                    "strikeOuts"
                ),

            "HR":
                pitching.get(
                    "homeRuns"
                ),

            "R":
                pitching.get(
                    "runs"
                ),

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
# CURRENT GAME
#
# LIVE中のみ詳細を入れる。
# Finalならavailable=False。
# =========================================================

def get_current_game(
    feed,
    side
):

    live_data = feed.get(
        "liveData",
        {}
    ) or {}

    plays = live_data.get(
        "plays",
        {}
    ) or {}

    linescore = live_data.get(
        "linescore",
        {}
    ) or {}

    current_play = plays.get(
        "currentPlay"
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


    about = current_play.get(
        "about",
        {}
    ) or {}

    count = current_play.get(
        "count",
        {}
    ) or {}

    matchup = current_play.get(
        "matchup",
        {}
    ) or {}

    pitcher = matchup.get(
        "pitcher",
        {}
    ) or {}

    batter = matchup.get(
        "batter",
        {}
    ) or {}

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


    offense = linescore.get(
        "offense",
        {}
    ) or {}

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


    # =====================================================
    # LAST PITCH
    # =====================================================

    last_pitch = None

    play_events = current_play.get(
        "playEvents",
        []
    ) or []

    for event in reversed(
        play_events
    ):

        if not event.get(
            "isPitch"
        ):

            continue

        pitch_data = event.get(
            "pitchData",
            {}
        ) or {}

        details = event.get(
            "details",
            {}
        ) or {}

        pitch_type = details.get(
            "type",
            {}
        ) or {}

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
                )

        },

        "lastPitch":
            last_pitch,

        "runners":
            runners

    }


# =========================================================
# GAME CONVERSION
# =========================================================

def build_game(
    game
):

    game_pk = game.get(
        "gamePk"
    )

    side = get_phillies_side(
        game
    )

    if side is None:

        raise ValueError(
            "Phillies side could not be determined."
        )


    # -----------------------------------------------------
    # Boxscore
    # -----------------------------------------------------

    boxscore = get_boxscore(
        game_pk
    )


    # -----------------------------------------------------
    # Live Feed
    # -----------------------------------------------------

    feed = get_live_feed(
        game_pk
    )


    # -----------------------------------------------------
    # Basic
    # -----------------------------------------------------

    game_info = build_game_info(
        game
    )


    # -----------------------------------------------------
    # Inning
    # -----------------------------------------------------

    inning_scores = get_inning_scores(
        game
    )


    # -----------------------------------------------------
    # Batting
    # -----------------------------------------------------

    batting = get_phillies_batting(
        boxscore,
        side
    )


    # -----------------------------------------------------
    # Pitching
    # -----------------------------------------------------

    pitching = get_phillies_pitching(
        boxscore,
        side
    )


    # -----------------------------------------------------
    # Current game
    # -----------------------------------------------------

    current_game = get_current_game(
        feed,
        side
    )


    # -----------------------------------------------------
    # Scores
    # -----------------------------------------------------

    teams = game.get(
        "teams",
        {}
    ) or {}

    home = teams.get(
        "home",
        {}
    ) or {}

    away = teams.get(
        "away",
        {}
    ) or {}


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
            inning_scores,

        "philliesBatting":
            batting,

        "philliesPitching":
            pitching,

        "currentGame":
            current_game

    }


# =========================================================
# OUTPUT
# =========================================================

def save_json(
    game
):

    os.makedirs(
        "data",
        exist_ok=True
    )

    now = get_now_jst()

    if game is None:

        games = []

    else:

        games = [
            game
        ]


    output = {

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
            now.strftime(
                "%Y-%m-%d"
            ),

        "updated":
            now.isoformat(),

        "gameCount":
            len(games),

        "games":
            games

    }


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )


    return output


# =========================================================
# MAIN
# =========================================================

def main():

    print("")
    print(
        "========================================"
    )
    print(
        "PHILLIES SCORE UPDATE"
    )
    print(
        "========================================"
    )

    print(
        "Getting latest Phillies game..."
    )

    game = get_latest_game()

    if game is None:

        print(
            "No relevant game found."
        )

        output = save_json(
            None
        )

        print(
            "Saved:",
            OUTPUT_FILE
        )

        print(
            "Game count:",
            output["gameCount"]
        )

        return


    print(
        "Selected game:",
        game.get(
            "gamePk"
        )
    )

    print(
        "Building Score data..."
    )


    try:

        converted = build_game(
            game
        )

    except Exception as error:

        print(
            "Score conversion error:",
            error
        )

        raise


    output = save_json(
        converted
    )


    print("")
    print(
        "========================================"
    )

    print(
        "Saved:",
        OUTPUT_FILE
    )

    print(
        "Game count:",
        output["gameCount"]
    )

    if output["games"]:

        score_game = (
            output["games"][0]
        )

        print(
            "GamePk:",
            score_game[
                "game"
            ].get(
                "gamePk"
            )
        )

        print(
            "Status:",
            score_game[
                "game"
            ].get(
                "status",
                {}
            ).get(
                "abstract"
            )
        )

        print(
            "Innings:",
            len(
                score_game.get(
                    "inningScores",
                    []
                )
            )
        )

        print(
            "Batters:",
            len(
                score_game.get(
                    "philliesBatting",
                    []
                )
            )
        )

        print(
            "Pitchers:",
            len(
                score_game.get(
                    "philliesPitching",
                    []
                )
            )
        )

    print(
        "========================================"
    )

    print("")


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
