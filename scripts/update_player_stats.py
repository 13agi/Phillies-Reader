import json
import os
import requests
from datetime import datetime, timezone


# =========================================================
# CONFIG
# =========================================================

TEAM_ID = 143
SEASON = 2026

API_BASE = "https://statsapi.mlb.com/api/v1"

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "player_stats.json"
)


# =========================================================
# API
# =========================================================

def api_get(url, params=None):

    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={
            "User-Agent": "Phillies-Reader"
        }
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# PHILLIES 40-MAN ROSTER
# =========================================================

def get_roster():

    url = (
        f"{API_BASE}/teams/"
        f"{TEAM_ID}/roster"
    )

    params = {
        "rosterType": "40Man",
        "hydrate": "person"
    }

    data = api_get(
        url,
        params
    )

    return data.get(
        "roster",
        []
    )


# =========================================================
# PLAYER SEASON STATS
# =========================================================

def get_stats(
    player_id,
    group
):

    url = (
        f"{API_BASE}/people/"
        f"{player_id}/stats"
    )

    params = {
        "stats": "season",
        "group": group,
        "season": str(SEASON)
    }

    data = api_get(
        url,
        params
    )

    stats = data.get(
        "stats",
        []
    )

    if not stats:
        return {}

    # season stats
    splits = stats[0].get(
        "splits",
        []
    )

    if not splits:
        return {}

    # 通常season=2026の1件
    for split in splits:

        if str(
            split.get("season", "")
        ) == str(SEASON):

            return split.get(
                "stat",
                {}
            )

    return splits[0].get(
        "stat",
        {}
    )


# =========================================================
# SAFE VALUE
# =========================================================

def value(
    data,
    key
):

    return data.get(
        key
    )


# =========================================================
# BATTING DATA
#
# APIから取得した通常シーズン打撃成績
# =========================================================

def build_batting(
    batting
):

    return {

        # 基本
        "games":
            value(
                batting,
                "gamesPlayed"
            ),

        "plateAppearances":
            value(
                batting,
                "plateAppearances"
            ),

        "atBats":
            value(
                batting,
                "atBats"
            ),

        "hits":
            value(
                batting,
                "hits"
            ),

        "runs":
            value(
                batting,
                "runs"
            ),

        # 長打
        "doubles":
            value(
                batting,
                "doubles"
            ),

        "triples":
            value(
                batting,
                "triples"
            ),

        "homeRuns":
            value(
                batting,
                "homeRuns"
            ),

        "totalBases":
            value(
                batting,
                "totalBases"
            ),

        # 得点・走塁
        "rbi":
            value(
                batting,
                "rbi"
            ),

        "stolenBases":
            value(
                batting,
                "stolenBases"
            ),

        "caughtStealing":
            value(
                batting,
                "caughtStealing"
            ),

        # 四死球・三振
        "walks":
            value(
                batting,
                "baseOnBalls"
            ),

        "intentionalWalks":
            value(
                batting,
                "intentionalWalks"
            ),

        "hitByPitch":
            value(
                batting,
                "hitByPitch"
            ),

        "strikeouts":
            value(
                batting,
                "strikeOuts"
            ),

        # 犠打・犠飛
        "sacBunts":
            value(
                batting,
                "sacBunts"
            ),

        "sacFlies":
            value(
                batting,
                "sacFlies"
            ),

        # 併殺
        "groundIntoDoublePlay":
            value(
                batting,
                "groundIntoDoublePlay"
            ),

        # 打撃率
        "avg":
            value(
                batting,
                "avg"
            ),

        "obp":
            value(
                batting,
                "obp"
            ),

        "slg":
            value(
                batting,
                "slg"
            ),

        "ops":
            value(
                batting,
                "ops"
            ),

        # BABIP等
        "babip":
            value(
                batting,
                "babip"
            ),

        "groundOuts":
            value(
                batting,
                "groundOuts"
            ),

        "airOuts":
            value(
                batting,
                "airOuts"
            ),

        "leftOnBase":
            value(
                batting,
                "leftOnBase"
            ),

        "numberOfPitches":
            value(
                batting,
                "numberOfPitches"
            )

    }


# =========================================================
# PITCHING DATA
#
# BFを含め、成績カードに必要な値を保存
# =========================================================

def build_pitching(
    pitching
):

    return {

        # 登板
        "games":
            value(
                pitching,
                "gamesPlayed"
            ),

        "gamesStarted":
            value(
                pitching,
                "gamesStarted"
            ),

        # 勝敗
        "wins":
            value(
                pitching,
                "wins"
            ),

        "losses":
            value(
                pitching,
                "losses"
            ),

        # セーブ関連
        "saves":
            value(
                pitching,
                "saves"
            ),

        "saveOpportunities":
            value(
                pitching,
                "saveOpportunities"
            ),

        "holds":
            value(
                pitching,
                "holds"
            ),

        "blownSaves":
            value(
                pitching,
                "blownSaves"
            ),

        # イニング
        "inningsPitched":
            value(
                pitching,
                "inningsPitched"
            ),

        # 被打撃
        "hits":
            value(
                pitching,
                "hits"
            ),

        "runs":
            value(
                pitching,
                "runs"
            ),

        "earnedRuns":
            value(
                pitching,
                "earnedRuns"
            ),

        "homeRuns":
            value(
                pitching,
                "homeRuns"
            ),

        # 四死球
        "walks":
            value(
                pitching,
                "baseOnBalls"
            ),

        "intentionalWalks":
            value(
                pitching,
                "intentionalWalks"
            ),

        "hitByPitch":
            value(
                pitching,
                "hitByPitch"
            ),

        # 三振
        "strikeouts":
            value(
                pitching,
                "strikeOuts"
            ),

        # ★ 対戦打者数
        "battersFaced":
            value(
                pitching,
                "battersFaced"
            ),

        # 基本指標
        "era":
            value(
                pitching,
                "era"
            ),

        "whip":
            value(
                pitching,
                "whip"
            ),

        # その他
        "completeGames":
            value(
                pitching,
                "completeGames"
            ),

        "shutouts":
            value(
                pitching,
                "shutouts"
            ),

        "wildPitches":
            value(
                pitching,
                "wildPitches"
            ),

        "balks":
            value(
                pitching,
                "balks"
            ),

        "pickoffs":
            value(
                pitching,
                "pickoffs"
            ),

        # /9系
        "k9":
            value(
                pitching,
                "strikeoutsPer9"
            ),

        "bb9":
            value(
                pitching,
                "walksPer9"
            ),

        "h9":
            value(
                pitching,
                "hitsPer9"
            ),

        "kbb":
            value(
                pitching,
                "strikeoutWalkRatio"
            )

    }


# =========================================================
# MAIN
# =========================================================

def main():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    print(
        "========================================"
    )

    print(
        "PHILLIES PLAYER STATS UPDATE"
    )

    print(
        f"Season: {SEASON}"
    )

    print(
        "========================================"
    )


    # -----------------------------------------------------
    # roster
    # -----------------------------------------------------

    roster = get_roster()

    print(
        f"Roster players: {len(roster)}"
    )


    players = {}


    # -----------------------------------------------------
    # players
    # -----------------------------------------------------

    for index, entry in enumerate(
        roster,
        start=1
    ):

        person = entry.get(
            "person",
            {}
        )

        player_id = person.get(
            "id"
        )

        if not player_id:
            continue


        name = person.get(
            "fullName",
            "Unknown"
        )


        position = (
            entry
            .get(
                "position",
                {}
            )
            .get(
                "abbreviation",
                ""
            )
        )


        print(
            f"[{index}/{len(roster)}] "
            f"{name} ({position})"
        )


        batting_raw = {}

        pitching_raw = {}


        # -------------------------------------------------
        # hitting
        # -------------------------------------------------

        try:

            batting_raw = get_stats(
                player_id,
                "hitting"
            )

        except Exception as error:

            print(
                f"  Hitting error: {error}"
            )


        # -------------------------------------------------
        # pitching
        # -------------------------------------------------

        try:

            pitching_raw = get_stats(
                player_id,
                "pitching"
            )

        except Exception as error:

            print(
                f"  Pitching error: {error}"
            )


        # -------------------------------------------------
        # save
        # -------------------------------------------------

        players[
            str(player_id)
        ] = {

            "playerId":
                player_id,

            "name":
                name,

            "position":
                position,

            "season":
                SEASON,

            "batting":
                build_batting(
                    batting_raw
                ),

            "pitching":
                build_pitching(
                    pitching_raw
                )

        }


    # =====================================================
    # OUTPUT
    # =====================================================

    output = {

        "team":
            "Philadelphia Phillies",

        "teamId":
            TEAM_ID,

        "season":
            SEASON,

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "players":
            players

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


    print("")
    print(
        "========================================"
    )

    print(
        f"Saved {len(players)} players"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )

    print(
        "========================================"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
