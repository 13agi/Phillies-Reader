import json
import os
import time
import requests
from datetime import datetime, timezone
# =========================================================
# CONFIG
# =========================================================
TEAM_ID = 143
SEASON = 2026
API_BASE = "https://statsapi.mlb.com/api/v1"
OUTPUT_FILE = "data/player_stats.json"
REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 0.15
# =========================================================
# API
# =========================================================
def api_get(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent": "Phillies-Reader/1.0"
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as error:
            print(
                f"API error "
                f"(attempt {attempt + 1}/{retries}): "
                f"{error}"
            )
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise
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
        "season": SEASON
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
# PLAYER STATS
# =========================================================
def get_player_stats(
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
        "season": SEASON
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
    splits = stats[0].get(
        "splits",
        []
    )
    if not splits:
        return {}
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
# HELPER
# =========================================================
def get_value(
    data,
    key
):
    return data.get(key)
# =========================================================
# BATTING
# =========================================================
def build_batting(stat):
    return {
        # 基本
        "games":
            get_value(
                stat,
                "gamesPlayed"
            ),
        "plateAppearances":
            get_value(
                stat,
                "plateAppearances"
            ),
        "atBats":
            get_value(
                stat,
                "atBats"
            ),
        "hits":
            get_value(
                stat,
                "hits"
            ),
        "runs":
            get_value(
                stat,
                "runs"
            ),
        # 長打
        "doubles":
            get_value(
                stat,
                "doubles"
            ),
        "triples":
            get_value(
                stat,
                "triples"
            ),
        "homeRuns":
            get_value(
                stat,
                "homeRuns"
            ),
        "totalBases":
            get_value(
                stat,
                "totalBases"
            ),
        # 打点
        "rbi":
            get_value(
                stat,
                "rbi"
            ),
        # 走塁
        "stolenBases":
            get_value(
                stat,
                "stolenBases"
            ),
        "caughtStealing":
            get_value(
                stat,
                "caughtStealing"
            ),
        # 四死球
        "walks":
            get_value(
                stat,
                "baseOnBalls"
            ),
        "intentionalWalks":
            get_value(
                stat,
                "intentionalWalks"
            ),
        "hitByPitch":
            get_value(
                stat,
                "hitByPitch"
            ),
        # 三振
        "strikeouts":
            get_value(
                stat,
                "strikeOuts"
            ),
        # 犠打
        "sacBunts":
            get_value(
                stat,
                "sacBunts"
            ),
        "sacFlies":
            get_value(
                stat,
                "sacFlies"
            ),
        # 併殺
        "groundIntoDoublePlay":
            get_value(
                stat,
                "groundIntoDoublePlay"
            ),
        # 打撃率
        "avg":
            get_value(
                stat,
                "avg"
            ),
        "obp":
            get_value(
                stat,
                "obp"
            ),
        "slg":
            get_value(
                stat,
                "slg"
            ),
        "ops":
            get_value(
                stat,
                "ops"
            ),
        # その他
        "babip":
            get_value(
                stat,
                "babip"
            ),
        "groundOuts":
            get_value(
                stat,
                "groundOuts"
            ),
        "airOuts":
            get_value(
                stat,
                "airOuts"
            ),
        "leftOnBase":
            get_value(
                stat,
                "leftOnBase"
            ),
        "numberOfPitches":
            get_value(
                stat,
                "numberOfPitches"
            )
    }
# =========================================================
# PITCHING
# =========================================================
def build_pitching(stat):
    return {
        # 登板
        "games":
            get_value(
                stat,
                "gamesPlayed"
            ),
        "gamesStarted":
            get_value(
                stat,
                "gamesStarted"
            ),
        # 勝敗
        "wins":
            get_value(
                stat,
                "wins"
            ),
        "losses":
            get_value(
                stat,
                "losses"
            ),
        # セーブ・リリーフ
        "saves":
            get_value(
                stat,
                "saves"
            ),
        "saveOpportunities":
            get_value(
                stat,
                "saveOpportunities"
            ),
        "holds":
            get_value(
                stat,
                "holds"
            ),
        "blownSaves":
            get_value(
                stat,
                "blownSaves"
            ),
        # イニング
        "inningsPitched":
            get_value(
                stat,
                "inningsPitched"
            ),
        # 被安打・失点
        "hits":
            get_value(
                stat,
                "hits"
            ),
        "runs":
            get_value(
                stat,
                "runs"
            ),
        "earnedRuns":
            get_value(
                stat,
                "earnedRuns"
            ),
        "homeRuns":
            get_value(
                stat,
                "homeRuns"
            ),
        # 四死球
        "walks":
            get_value(
                stat,
                "baseOnBalls"
            ),
        "intentionalWalks":
            get_value(
                stat,
                "intentionalWalks"
            ),
        "hitByPitch":
            get_value(
                stat,
                "hitByPitch"
            ),
        # 三振
        "strikeouts":
            get_value(
                stat,
                "strikeOuts"
            ),
        # ★ 対戦打者数
        "battersFaced":
            get_value(
                stat,
                "battersFaced"
            ),
        # 基本指標
        "era":
            get_value(
                stat,
                "era"
            ),
        "whip":
            get_value(
                stat,
                "whip"
            ),
        # 完投・完封
        "completeGames":
            get_value(
                stat,
                "completeGames"
            ),
        "shutouts":
            get_value(
                stat,
                "shutouts"
            ),
        # その他
        "wildPitches":
            get_value(
                stat,
                "wildPitches"
            ),
        "balks":
            get_value(
                stat,
                "balks"
            ),
        "pickoffs":
            get_value(
                stat,
                "pickoffs"
            ),
        # 比率
        "k9":
            get_value(
                stat,
                "strikeoutsPer9"
            ),
        "bb9":
            get_value(
                stat,
                "walksPer9"
            ),
        "h9":
            get_value(
                stat,
                "hitsPer9"
            ),
        "kbb":
            get_value(
                stat,
                "strikeoutWalkRatio"
            )
    }
# =========================================================
# MAIN
# =========================================================
def main():
    print("")
    print(
        "=========================================="
    )
    print(
        "PHILLIES PLAYER STATS UPDATE"
    )
    print(
        f"SEASON: {SEASON}"
    )
    print(
        "=========================================="
    )
    # =====================================================
    # 最新40-manを毎回MLB APIから取得
    # =====================================================
    roster = get_roster()
    if not roster:
        raise RuntimeError(
            "MLB API returned an empty roster."
        )
    print(
        f"40-man players: {len(roster)}"
    )
    players = {}
    # =====================================================
    # 各選手の最新シーズン成績を取得
    # =====================================================
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
            f"{name}"
        )
        # -------------------------------------------------
        # 最新 batting
        # -------------------------------------------------
        try:
            batting_raw = get_player_stats(
                player_id,
                "hitting"
            )
        except Exception as error:
            print(
                f"  batting error: {error}"
            )
            batting_raw = {}
        time.sleep(
            REQUEST_INTERVAL
        )
        # -------------------------------------------------
        # 最新 pitching
        # -------------------------------------------------
        try:
            pitching_raw = get_player_stats(
                player_id,
                "pitching"
            )
        except Exception as error:
            print(
                f"  pitching error: {error}"
            )
            pitching_raw = {}
        # -------------------------------------------------
        # 保存
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
        time.sleep(
            REQUEST_INTERVAL
        )
    # =====================================================
    # JSON
    #
    # 「前回に加算」ではなく、
    # MLB APIから取得した最新累計値で完全更新
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
    # =====================================================
    # 保存
    # =====================================================
    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )
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
    # =====================================================
    # BF確認
    # =====================================================
    pitching_count = 0
    bf_count = 0
    for player in players.values():
        pitching = player.get(
            "pitching",
            {}
        )
        if pitching:
            pitching_count += 1
            if (
                pitching.get(
                    "battersFaced"
                ) is not None
            ):
                bf_count += 1
    print("")
    print(
        "=========================================="
    )
    print(
        f"Players updated : {len(players)}"
    )
    print(
        f"Pitching data   : {pitching_count}"
    )
    print(
        f"BF available    : {bf_count}"
    )
    print(
        f"Output          : {OUTPUT_FILE}"
    )
    print(
        "=========================================="
    )
# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    main()
