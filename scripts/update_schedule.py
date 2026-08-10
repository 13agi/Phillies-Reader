import json
import os
import requests
from datetime import datetime, timezone, timedelta
# =========================================================
# Philadelphia Phillies
# =========================================================
TEAM_ID = 143
SEASON = 2026
BASE_URL = "https://statsapi.mlb.com/api/v1"
OUTPUT_FILE = "data/update-schedule.json"
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
# SCHEDULE API
#
# 2026年シーズンのフィリーズ全試合
# =========================================================
def get_schedule():
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
        "startDate":
            f"{SEASON}-03-01",
        "endDate":
            f"{SEASON}-11-01",
        "hydrate":
            "team,venue,linescore"
    }
    data = get_json(
        url,
        params
    )
    return data
# =========================================================
# BOX SCORE API
#
# 終了・進行中の試合について
# フィリーズの継投を取得する
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
# TEAM INFO
# =========================================================
def get_team_info(
    team_data
):
    if not team_data:
        return {
            "id":
                None,
            "name":
                "",
            "abbreviation":
                ""
        }
    return {
        "id":
            team_data.get(
                "id"
            ),
        "name":
            team_data.get(
                "name",
                ""
            ),
        "abbreviation":
            team_data.get(
                "abbreviation",
                ""
            )
    }
# =========================================================
# PHILLIES / OPPONENT
# =========================================================
def determine_matchup(
    game
):
    teams = game.get(
        "teams",
        {}
    )
    home = teams.get(
        "home",
        {}
    )
    away = teams.get(
        "away",
        {}
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
# RESULT
# =========================================================
def get_result(
    status,
    phillies_score,
    opponent_score
):
    abstract_state = status.get(
        "abstractGameState",
        ""
    )
    if (
        abstract_state
        !=
        "Final"
    ):
        return None
    if (
        phillies_score
        is None
        or
        opponent_score
        is None
    ):
        return None
    if (
        phillies_score
        >
        opponent_score
    ):
        return "W"
    if (
        phillies_score
        <
        opponent_score
    ):
        return "L"
    return "T"
# =========================================================
# INNING SCORES
# =========================================================
def get_inning_scores(
    game
):
    linescore = game.get(
        "linescore",
        {}
    )
    innings = linescore.get(
        "innings",
        []
    )
    result = []
    for inning in innings:
        away_data = inning.get(
            "away",
            {}
        )
        home_data = inning.get(
            "home",
            {}
        )
        result.append({
            "inning":
                inning.get(
                    "num"
                ),
            "away":
                away_data.get(
                    "runs",
                    0
                ),
            "home":
                home_data.get(
                    "runs",
                    0
                )
        })
    return result
# =========================================================
# PITCHING
#
# フィリーズ側だけ
# 登板順
# 姓だけ
# =========================================================
def get_phillies_pitchers(
    game_pk,
    location
):
    boxscore = get_boxscore(
        game_pk
    )
    if not boxscore:
        return []
    teams = boxscore.get(
        "teams",
        {}
    )
    phillies_side = (
        "home"
        if location == "HOME"
        else "away"
    )
    phillies = teams.get(
        phillies_side,
        {}
    )
    pitcher_ids = phillies.get(
        "pitchers",
        []
    )
    players = phillies.get(
        "players",
        {}
    )
    result = []
    for pitcher_id in pitcher_ids:
        player_key = (
            f"ID{pitcher_id}"
        )
        player = players.get(
            player_key,
            {}
        )
        person = player.get(
            "person",
            {}
        )
        last_name = person.get(
            "lastName",
            ""
        )
        if not last_name:
            full_name = person.get(
                "fullName",
                ""
            )
            if full_name:
                parts = (
                    full_name.split()
                )
                last_name = parts[-1]
        if not last_name:
            continue
        result.append({
            "id":
                pitcher_id,
            "name":
                last_name
        })
    return result
# =========================================================
# VENUE
# =========================================================
def get_venue(
    game
):
    venue = game.get(
        "venue",
        {}
    )
    location = venue.get(
        "location",
        {}
    )
    return {
        "id":
            venue.get(
                "id"
            ),
        "name":
            venue.get(
                "name",
                ""
            ),
        "city":
            location.get(
                "city",
                ""
            ),
        "state":
            location.get(
                "state",
                ""
            ),
        "stateAbbrev":
            location.get(
                "stateAbbrev",
                ""
            )
    }
# =========================================================
# GAME CONVERSION
# =========================================================
def build_game(
    date_data,
    game
):
    matchup = determine_matchup(
        game
    )
    phillies = matchup[
        "phillies"
    ]
    opponent = matchup[
        "opponent"
    ]
    phillies_team = matchup[
        "philliesTeam"
    ]
    opponent_team = matchup[
        "opponentTeam"
    ]
    status = game.get(
        "status",
        {}
    )
    phillies_score = phillies.get(
        "score"
    )
    opponent_score = opponent.get(
        "score"
    )
    game_pk = game.get(
        "gamePk"
    )
    location = matchup[
        "location"
    ]
    abstract_state = status.get(
        "abstractGameState",
        ""
    )
    detailed_state = status.get(
        "detailedState",
        ""
    )
    result = get_result(
        status,
        phillies_score,
        opponent_score
    )
    # -----------------------------------------------------
    # 継投
    #
    # Final / Live の試合のみ取得
    # -----------------------------------------------------
    pitchers = []
    if abstract_state in {
        "Live",
        "Final"
    }:
        pitchers = (
            get_phillies_pitchers(
                game_pk,
                location
            )
        )
    # -----------------------------------------------------
    # 基本データ
    # -----------------------------------------------------
    return {
        "gamePk":
            game_pk,
        "date":
            date_data.get(
                "date",
                ""
            ),
        "gameDate":
            game.get(
                "gameDate",
                ""
            ),
        "status":
            abstract_state,
        "statusCode":
            status.get(
                "statusCode",
                ""
            ),
        "detailedState":
            detailed_state,
        "location":
            location,
        "phillies": {
            "id":
                phillies_team.get(
                    "id"
                ),
            "name":
                phillies_team.get(
                    "name",
                    "Philadelphia Phillies"
                ),
            "abbreviation":
                phillies_team.get(
                    "abbreviation",
                    "PHI"
                ),
            "score":
                phillies_score
        },
        "opponent": {
            "id":
                opponent_team.get(
                    "id"
                ),
            "name":
                opponent_team.get(
                    "name",
                    ""
                ),
            "abbreviation":
                opponent_team.get(
                    "abbreviation",
                    ""
                ),
            "score":
                opponent_score
        },
        "result":
            result,
        "venue":
            get_venue(
                game
            ),
        "inningScores":
            get_inning_scores(
                game
            ),
        "philliesPitchers":
            pitchers
    }
# =========================================================
# ALL GAMES
# =========================================================
def build_schedule(
    schedule_data
):
    games = []
    dates = schedule_data.get(
        "dates",
        []
    )
    for date_data in dates:
        date_games = date_data.get(
            "games",
            []
        )
        for game in date_games:
            try:
                converted = build_game(
                    date_data,
                    game
                )
                games.append(
                    converted
                )
            except Exception as error:
                print(
                    "試合データ変換エラー:",
                    game.get(
                        "gamePk"
                    ),
                    error
                )
    games.sort(
        key=lambda game:
            game.get(
                "gameDate",
                ""
            )
    )
    return games
# =========================================================
# OUTPUT
# =========================================================
def save_json(
    games
):
    os.makedirs(
        "data",
        exist_ok=True
    )
    output = {
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
        "updated":
            datetime.now(
                JST
            ).isoformat(),
        "count":
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
        "PHILLIES SCHEDULE UPDATE"
    )
    print(
        "========================================"
    )
    print(
        "Getting MLB Schedule API..."
    )
    schedule_data = get_schedule()
    dates = schedule_data.get(
        "dates",
        []
    )
    print(
        "Schedule dates:",
        len(dates)
    )
    games = build_schedule(
        schedule_data
    )
    print(
        "Games:",
        len(games)
    )
    output = save_json(
        games
    )
    print("")
    print(
        "Saved:",
        OUTPUT_FILE
    )
    print(
        "Total games:",
        output["count"]
    )
    print(
        "Updated:",
        output["updated"]
    )
    print("")
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
