import json
import os
import requests
from datetime import datetime, timezone, timedelta
# =========================================================
# Phillies
# =========================================================
TEAM_ID = 143
SEASON = 2026
BASE_URL = (
    "https://statsapi.mlb.com/api/v1"
)
OUTPUT_FILE = (
    "data/score.json"
)
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
# TODAY
#
# 日本時間の日付を使用
# =========================================================
def get_today():
    return datetime.now(
        JST
    ).strftime(
        "%Y-%m-%d"
    )
# =========================================================
# TODAY'S SCHEDULE
# =========================================================
def get_today_schedule(
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
    return get_json(
        url,
        params
    )
# =========================================================
# LIVE FEED
#
# 試合中の詳細情報
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
            "Live feed取得失敗:",
            game_pk,
            error
        )
        return {}
# =========================================================
# TEAM INFO
# =========================================================
def get_team_info(
    team
):
    if not team:
        return {
            "id": None,
            "name": None,
            "abbreviation": None
        }
    return {
        "id":
            team.get(
                "id"
            ),
        "name":
            team.get(
                "name"
            ),
        "abbreviation":
            team.get(
                "abbreviation"
            )
    }
# =========================================================
# MATCHUP
# =========================================================
def get_matchup(
    game
):
    teams = (
        game
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
    if (
        home_team["id"]
        ==
        TEAM_ID
    ):
        return {
            "location":
                "HOME",
            "phillies":
                home,
            "opponent":
                away,
            "philliesTeam":
                home_team,
            "opponentTeam":
                away_team
        }
    return {
        "location":
            "AWAY",
        "phillies":
            away,
        "opponent":
            home,
        "philliesTeam":
            away_team,
        "opponentTeam":
            home_team
    }
# =========================================================
# GAME STATUS
# =========================================================
def get_game_status(
    game
):
    status = (
        game
        .get(
            "status",
            {}
        )
    )
    return {
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
    }
# =========================================================
# GAME INFO
# =========================================================
def get_game_info(
    game,
    matchup
):
    venue = (
        game
        .get(
            "venue",
            {}
        )
    )
    location = (
        venue
        .get(
            "location",
            {}
        )
    )
    return {
        "gamePk":
            game.get(
                "gamePk"
            ),
        "gameDate":
            game.get(
                "gameDate"
            ),
        "status":
            get_game_status(
                game
            ),
        "location":
            matchup.get(
                "location"
            ),
        "phillies":
            matchup.get(
                "philliesTeam"
            ),
        "opponent":
            matchup.get(
                "opponentTeam"
            ),
        "venue": {
            "name":
                venue.get(
                    "name"
                ),
            "city":
                location.get(
                    "city"
                ),
            "state":
                location.get(
                    "state"
                )
        }
    }
# =========================================================
# SCORE
# =========================================================
def get_score(
    game
):
    teams = (
        game
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
    return {
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
    }
# =========================================================
# INNING SCORE
# =========================================================
def get_inning_scores(
    game
):
    linescore = (
        game
        .get(
            "linescore",
            {}
        )
    )
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
        )
        home = (
            inning
            .get(
                "home",
                {}
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
                )
        })
    return result
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
            "Boxscore取得失敗:",
            game_pk,
            error
        )
        return {}
# =========================================================
# PLAYER NAME
# =========================================================
def get_player_name(
    player
):
    person = (
        player
        .get(
            "person",
            {}
        )
    )
    return (
        person.get(
            "fullName"
        )
    )
# =========================================================
# PHILLIES BATTING
#
# 打順
# PA
# H
# HR
# RBI
# BB
# =========================================================
def get_phillies_batting(
    boxscore,
    location
):
    teams = (
        boxscore
        .get(
            "teams",
            {}
        )
    )
    side = (
        "home"
        if location == "HOME"
        else "away"
    )
    team = (
        teams
        .get(
            side,
            {}
        )
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
    for order_index, player_id in enumerate(
        batting_order,
        start=1
    ):
        player = (
            players
            .get(
                f"ID{player_id}",
                {}
            )
        )
        stats = (
            player
            .get(
                "stats",
                {}
            )
            .get(
                "batting",
                {}
            )
        )
        name = get_player_name(
            player
        )
        if not name:
            continue
        result.append({
            "battingOrder":
                order_index,
            "playerId":
                player
                .get(
                    "person",
                    {}
                )
                .get(
                    "id"
                ),
            "name":
                name,
            "PA":
                stats.get(
                    "plateAppearances"
                ),
            "H":
                stats.get(
                    "hits"
                ),
            "HR":
                stats.get(
                    "homeRuns"
                ),
            "RBI":
                stats.get(
                    "rbi"
                ),
            "BB":
                stats.get(
                    "baseOnBalls"
                )
        })
    return result
# =========================================================
# PHILLIES PITCHING
#
# IP
# H
# K
# HR
# R
# =========================================================
def get_phillies_pitching(
    boxscore,
    location
):
    teams = (
        boxscore
        .get(
            "teams",
            {}
        )
    )
    side = (
        "home"
        if location == "HOME"
        else "away"
    )
    team = (
        teams
        .get(
            side,
            {}
        )
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
    for order_index, player_id in enumerate(
        pitcher_ids,
        start=1
    ):
        player = (
            players
            .get(
                f"ID{player_id}",
                {}
            )
        )
        stats = (
            player
            .get(
                "stats",
                {}
            )
            .get(
                "pitching",
                {}
            )
        )
        name = get_player_name(
            player
        )
        if not name:
            continue
        result.append({
            "order":
                order_index,
            "playerId":
                player
                .get(
                    "person",
                    {}
                )
                .get(
                    "id"
                ),
            "name":
                name,
            "IP":
                stats.get(
                    "inningsPitched"
                ),
            "H":
                stats.get(
                    "hits"
                ),
            "K":
                stats.get(
                    "strikeOuts"
                ),
            "HR":
                stats.get(
                    "homeRuns"
                ),
            "R":
                stats.get(
                    "runs"
                )
        })
    return result
# =========================================================
# CURRENT GAME
# =========================================================
def get_current_game(
    live_feed,
    location
):
    live_data = (
        live_feed
        .get(
            "liveData",
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
    current_play = (
        plays
        .get(
            "currentPlay"
        )
    )
    linescore = (
        live_data
        .get(
            "linescore",
            {}
        )
    )
    # -----------------------------------------------------
    # 試合中でない
    # -----------------------------------------------------
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
    # -----------------------------------------------------
    # ABOUT
    # -----------------------------------------------------
    about = (
        current_play
        .get(
            "about",
            {}
        )
    )
    half = (
        about
        .get(
            "halfInning"
        )
    )
    inning = (
        about
        .get(
            "inning"
        )
    )
    # -----------------------------------------------------
    # PHILLIES ATTACK / DEFENSE
    # -----------------------------------------------------
    if location == "HOME":
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
    )
    pitcher = (
        matchup
        .get(
            "pitcher",
            {}
        )
    )
    batter = (
        matchup
        .get(
            "batter",
            {}
        )
    )
    pitcher_hand = (
        matchup
        .get(
            "pitchHand",
            {}
        )
        .get(
            "code"
        )
    )
    batter_hand = (
        matchup
        .get(
            "batSide",
            {}
        )
        .get(
            "code"
        )
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
    # 直前の1球だけ
    # -----------------------------------------------------
    last_pitch = {
        "speed":
            None,
        "type":
            None
    }
    events = (
        current_play
        .get(
            "playEvents",
            []
        )
    )
    for event in reversed(
        events
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
        )
        details = (
            event
            .get(
                "details",
                {}
            )
        )
        pitch_type = (
            details
            .get(
                "type",
                {}
            )
            .get(
                "description"
            )
        )
        speed = (
            pitch_data
            .get(
                "startSpeed"
            )
        )
        last_pitch = {
            "speed":
                speed,
            "type":
                pitch_type
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
                pitcher_hand
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
                batter_hand
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
    game_pk = (
        scheduled_game
        .get(
            "gamePk"
        )
    )
    # -----------------------------------------------------
    # schedule情報
    # -----------------------------------------------------
    matchup = get_matchup(
        scheduled_game
    )
    game_info = get_game_info(
        scheduled_game,
        matchup
    )
    # -----------------------------------------------------
    # live feed
    # -----------------------------------------------------
    live_feed = get_live_feed(
        game_pk
    )
    # -----------------------------------------------------
    # live game data
    # -----------------------------------------------------
    live_game = (
        live_feed
        .get(
            "gameData",
            {}
        )
    )
    live_live_data = (
        live_feed
        .get(
            "liveData",
            {}
        )
    )
    # live feedに情報がある場合はこちらを優先
    if live_game:
        game_info = get_game_info(
            live_game,
            get_matchup(
                live_game
            )
        )
    # -----------------------------------------------------
    # boxscore
    # -----------------------------------------------------
    boxscore = get_boxscore(
        game_pk
    )
    # -----------------------------------------------------
    # score
    # -----------------------------------------------------
    score_source = (
        live_game
        if live_game
        else scheduled_game
    )
    # live linescoreが存在する場合
    if live_live_data:
        score_source_for_linescore = (
            live_live_data
        )
        score = get_score(
            live_live_data
        )
        inning_scores = (
            get_inning_scores(
                live_live_data
            )
        )
    else:
        score = get_score(
            score_source
        )
        inning_scores = (
            get_inning_scores(
                score_source
            )
        )
    # -----------------------------------------------------
    # Phillies location
    # -----------------------------------------------------
    location = (
        matchup
        .get(
            "location"
        )
    )
    # live game側で再判定
    if live_game:
        live_matchup = get_matchup(
            live_game
        )
        location = (
            live_matchup
            .get(
                "location"
            )
        )
    # -----------------------------------------------------
    # Return
    # -----------------------------------------------------
    return {
        "game": game_info,
        "score":
            score,
        "inningScores":
            inning_scores,
        "philliesBatting":
            get_phillies_batting(
                boxscore,
                location
            ),
        "philliesPitching":
            get_phillies_pitching(
                boxscore,
                location
            ),
        "currentGame":
            get_current_game(
                live_feed,
                location
            )
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
    # -----------------------------------------------------
    # 今日の試合だけ取得
    # -----------------------------------------------------
    schedule = get_today_schedule(
        game_date
    )
    scheduled_games = []
    for date_data in (
        schedule.get(
            "dates",
            []
        )
    ):
        for game in (
            date_data.get(
                "games",
                []
            )
        ):
            scheduled_games.append(
                game
            )
    # -----------------------------------------------------
    # 試合なし
    # -----------------------------------------------------
    if not scheduled_games:
        data = empty_data(
            game_date
        )
    else:
        games = []
        for game in scheduled_games:
            try:
                print(
                    "Updating game:",
                    game.get(
                        "gamePk"
                    )
                )
                games.append(
                    build_game(
                        game
                    )
                )
            except Exception as error:
                print(
                    "Game error:",
                    game.get(
                        "gamePk"
                    ),
                    error
                )
                # 試合自体の情報だけ残す
                matchup = get_matchup(
                    game
                )
                games.append({
                    "game":
                        get_game_info(
                            game,
                            matchup
                        ),
                    "score": {
                        "away": {
                            "runs": None,
                            "hits": None,
                            "errors": None
                        },
                        "home": {
                            "runs": None,
                            "hits": None,
                            "errors": None
                        }
                    },
                    "inningScores":
                        [],
                    "philliesBatting":
                        [],
                    "philliesPitching":
                        [],
                    "currentGame": {
                        "available":
                            False
                    }
                })
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
                len(games),
            "games":
                games
        }
    # -----------------------------------------------------
    # SAVE
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
        "Saved:",
        OUTPUT_FILE
    )
    print(
        "Games:",
        data["gameCount"]
    )
    print(
        "Updated:",
        data["updated"]
    )
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
