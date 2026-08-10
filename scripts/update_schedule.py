import json
import os
import requests
from datetime import datetime, timezone
# =========================================================
# 設定
# =========================================================
TEAM_ID = 143  # Philadelphia Phillies
SEASON = 2026
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
GAME_FEED_URL = (
    "https://statsapi.mlb.com/api/v1.1/game/"
    "{game_pk}/feed/live"
)
OUTPUT_FILE = "data/schedule.json"
# =========================================================
# HTTP
# =========================================================
def get_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()
# =========================================================
# ファーストネームではなく「姓」を取得
# =========================================================
def get_last_name(person):
    if not person:
        return ""
    last_name = person.get("lastName")
    if last_name:
        return last_name
    full_name = person.get("fullName", "")
    parts = full_name.strip().split()
    if parts:
        return parts[-1]
    return ""
# =========================================================
# フィリーズの投手継投を取得
# =========================================================
def get_phillies_pitching(game_pk):
    url = GAME_FEED_URL.format(
        game_pk=game_pk
    )
    data = get_json(url)
    boxscore = (
        data
        .get("liveData", {})
        .get("boxscore", {})
    )
    teams = boxscore.get(
        "teams",
        {}
    )
    phillies = teams.get(
        "away",
        {}
    )
    # PHIがホームの場合
    if (
        phillies.get("team", {})
        .get("id") != TEAM_ID
    ):
        phillies = teams.get(
            "home",
            {}
        )
    pitchers = phillies.get(
        "pitchers",
        []
    )
    players = phillies.get(
        "players",
        {}
    )
    pitching = []
    for pitcher_id in pitchers:
        player = players.get(
            f"ID{pitcher_id}",
            {}
        )
        person = player.get(
            "person",
            {}
        )
        last_name = get_last_name(
            person
        )
        if not last_name:
            continue
        pitching.append({
            "playerId":
                pitcher_id,
            "lastName":
                last_name
        })
    return pitching
# =========================================================
# イニング別スコア
# =========================================================
def get_linescore(feed):
    linescore = (
        feed
        .get("liveData", {})
        .get("linescore", {})
    )
    innings = []
    for inning in linescore.get(
        "innings",
        []
    ):
        number = inning.get(
            "num"
        )
        away = inning.get(
            "away",
            {}
        )
        home = inning.get(
            "home",
            {}
        )
        innings.append({
            "inning":
                number,
            "awayRuns":
                away.get(
                    "runs",
                    0
                ),
            "homeRuns":
                home.get(
                    "runs",
                    0
                )
        })
    return innings
# =========================================================
# Schedule取得
# =========================================================
def get_schedule():
    params = {
        "sportId": 1,
        "teamId":
            TEAM_ID,
        "season":
            SEASON,
        "gameTypes":
            "R,S",
        "hydrate":
            "team"
    }
    data = get_json(
        SCHEDULE_URL,
        params
    )
    return data.get(
        "dates",
        []
    )
# =========================================================
# 試合情報を変換
# =========================================================
def build_game(game):
    game_pk = game.get(
        "gamePk"
    )
    teams = game.get(
        "teams",
        {}
    )
    away = teams.get(
        "away",
        {}
    )
    home = teams.get(
        "home",
        {}
    )
    away_team = away.get(
        "team",
        {}
    )
    home_team = home.get(
        "team",
        {}
    )
    phillies_home = (
        home_team.get("id")
        == TEAM_ID
    )
    if phillies_home:
        phillies_team = home_team
        opponent_team = away_team
        phillies_data = home
        opponent_data = away
        home_away = "HOME"
    else:
        phillies_team = away_team
        opponent_team = home_team
        phillies_data = away
        opponent_data = home
        home_away = "AWAY"
    # -----------------------------------------------------
    # スコア
    # -----------------------------------------------------
    phillies_score = (
        phillies_data.get(
            "score"
        )
    )
    opponent_score = (
        opponent_data.get(
            "score"
        )
    )
    # -----------------------------------------------------
    # 試合状態
    # -----------------------------------------------------
    status = game.get(
        "status",
        {}
    )
    # -----------------------------------------------------
    # 勝敗
    # -----------------------------------------------------
    result = None
    if (
        status.get(
            "abstractGameState"
        )
        == "Final"
        and phillies_score is not None
        and opponent_score is not None
    ):
        if phillies_score > opponent_score:
            result = "W"
        elif phillies_score < opponent_score:
            result = "L"
        else:
            result = "T"
    # -----------------------------------------------------
    # 基本情報
    # -----------------------------------------------------
    game_data = {
        "gamePk":
            game_pk,
        "gameDate":
            game.get(
                "gameDate"
            ),
        "officialDate":
            game.get(
                "officialDate"
            ),
        "gameType":
            game.get(
                "gameType"
            ),
        "homeAway":
            home_away,
        "opponent": {
            "id":
                opponent_team.get(
                    "id"
                ),
            "name":
                opponent_team.get(
                    "name"
                ),
            "abbreviation":
                opponent_team.get(
                    "abbreviation"
                )
        },
        "status": {
            "abstract":
                status.get(
                    "abstractGameState"
                ),
            "coded":
                status.get(
                    "codedGameState"
                ),
            "detailed":
                status.get(
                    "detailedState"
                )
        },
        "philliesScore":
            phillies_score,
        "opponentScore":
            opponent_score,
        "result":
            result,
        "venue": {
            "id":
                game.get(
                    "venue",
                    {}
                ).get(
                    "id"
                ),
            "name":
                game.get(
                    "venue",
                    {}
                ).get(
                    "name"
                )
        },
        "inningScores": [],
        "philliesPitching": []
    }
    # =====================================================
    # 試合詳細
    # =====================================================
    try:
        feed = get_json(
            GAME_FEED_URL.format(
                game_pk=game_pk
            )
        )
        game_data[
            "inningScores"
        ] = get_linescore(
            feed
        )
        game_data[
            "philliesPitching"
        ] = get_phillies_pitching(
            game_pk
        )
    except Exception as e:
        print(
            f"詳細取得失敗 "
            f"{game_pk}: {e}"
        )
    return game_data
# =========================================================
# メイン
# =========================================================
def main():
    print(
        "Fetching Phillies schedule..."
    )
    dates = get_schedule()
    games = []
    for date in dates:
        for game in date.get(
            "games",
            []
        ):
            print(
                "Processing:",
                game.get(
                    "gamePk"
                )
            )
            games.append(
                build_game(
                    game
                )
            )
    # 日付順
    games.sort(
        key=lambda x:
            x.get(
                "gameDate",
                ""
            )
    )
    output = {
        "team": {
            "id":
                TEAM_ID,
            "name":
                "Philadelphia Phillies"
        },
        "season":
            SEASON,
        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "games":
            games
    }
    # ディレクトリ作成
    os.makedirs(
        os.path.dirname(
            OUTPUT_FILE
        ),
        exist_ok=True
    )
    # JSON保存
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )
    print(
        f"Saved {len(games)} games"
    )
    print(
        OUTPUT_FILE
    )
# =========================================================
# ENTRY POINT
# =========================================================
if __name__ == "__main__":
    main()
