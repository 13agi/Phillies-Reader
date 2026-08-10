import json
import os
import time
import requests
from datetime import datetime, timezone
# =========================================================
# Philadelphia Phillies
# =========================================================
TEAM_ID = 143
SEASON = 2026
API_BASE = "https://statsapi.mlb.com/api/v1"
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "player_stats.json"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
REQUEST_INTERVAL = 0.15
# =========================================================
# API REQUEST
# =========================================================
def get_json(
    url,
    params=None
):
    last_error = None
    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={
                    "User-Agent":
                        "Phillies-Reader/1.0"
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as error:
            last_error = error
            print(
                f"API error "
                f"{attempt}/{MAX_RETRIES}: "
                f"{error}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(2)
    raise RuntimeError(
        f"MLB API request failed: "
        f"{last_error}"
    )
# =========================================================
# 40-MAN ROSTER
# =========================================================
def get_roster():
    url = (
        f"{API_BASE}/teams/"
        f"{TEAM_ID}/roster"
    )
    params = {
        "rosterType": "40Man",
        "season": SEASON,
        "hydrate": "person"
    }
    data = get_json(
        url,
        params
    )
    roster = data.get(
        "roster",
        []
    )
    if not roster:
        raise RuntimeError(
            "MLB API returned an empty 40-man roster."
        )
    return roster
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
        "season": SEASON
    }
    data = get_json(
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
    # -----------------------------------------------------
    # 2026年のsplitを明示的に探す
    # -----------------------------------------------------
    for split in splits:
        if str(
            split.get(
                "season",
                ""
            )
        ) == str(SEASON):
            return split.get(
                "stat",
                {}
            )
    return {}
# =========================================================
# SAFE VALUE
# =========================================================
def safe_number(value):
    if value is None:
        return None
    return value
# =========================================================
# PERCENTAGE
#
# K%  = K / BF × 100
# BB% = BB / BF × 100
# =========================================================
def calculate_percent(
    numerator,
    denominator
):
    if (
        numerator is None
        or
        denominator is None
    ):
        return None
    try:
        denominator = float(
            denominator
        )
        numerator = float(
            numerator
        )
        if denominator <= 0:
            return None
        return round(
            numerator /
            denominator *
            100,
            1
        )
    except (
        ValueError,
        TypeError
    ):
        return None
# =========================================================
# MAIN
# =========================================================
def main():
    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )
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
    # 最新40-manをMLB APIから取得
    # =====================================================
    roster = get_roster()
    print(
        f"40-man players: {len(roster)}"
    )
    players = {}
    # =====================================================
    # 全40-man選手
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
            f"{name} "
            f"(ID: {player_id})"
        )
        # =================================================
        # HITTING
        # =================================================
        batting = get_stats(
            player_id,
            "hitting"
        )
        time.sleep(
            REQUEST_INTERVAL
        )
        # =================================================
        # PITCHING
        # =================================================
        pitching = get_stats(
            player_id,
            "pitching"
        )
        time.sleep(
            REQUEST_INTERVAL
        )
        # =================================================
        # 投手K / BB / BF
        # =================================================
        strikeouts = safe_number(
            pitching.get(
                "strikeOuts"
            )
        )
        walks = safe_number(
            pitching.get(
                "baseOnBalls"
            )
        )
        batters_faced = safe_number(
            pitching.get(
                "battersFaced"
            )
        )
        k_percent = calculate_percent(
            strikeouts,
            batters_faced
        )
        bb_percent = calculate_percent(
            walks,
            batters_faced
        )
        # =================================================
        # SAVE
        # =================================================
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
            # =============================================
            # BATTING
            # =============================================
            "batting": {
                "games":
                    safe_number(
                        batting.get(
                            "gamesPlayed"
                        )
                    ),
                "plateAppearances":
                    safe_number(
                        batting.get(
                            "plateAppearances"
                        )
                    ),
                "atBats":
                    safe_number(
                        batting.get(
                            "atBats"
                        )
                    ),
                "hits":
                    safe_number(
                        batting.get(
                            "hits"
                        )
                    ),
                "runs":
                    safe_number(
                        batting.get(
                            "runs"
                        )
                    ),
                "doubles":
                    safe_number(
                        batting.get(
                            "doubles"
                        )
                    ),
                "triples":
                    safe_number(
                        batting.get(
                            "triples"
                        )
                    ),
                "homeRuns":
                    safe_number(
                        batting.get(
                            "homeRuns"
                        )
                    ),
                "rbi":
                    safe_number(
                        batting.get(
                            "rbi"
                        )
                    ),
                "walks":
                    safe_number(
                        batting.get(
                            "baseOnBalls"
                        )
                    ),
                "hitByPitch":
                    safe_number(
                        batting.get(
                            "hitByPitch"
                        )
                    ),
                "strikeouts":
                    safe_number(
                        batting.get(
                            "strikeOuts"
                        )
                    ),
                "stolenBases":
                    safe_number(
                        batting.get(
                            "stolenBases"
                        )
                    ),
                "caughtStealing":
                    safe_number(
                        batting.get(
                            "caughtStealing"
                        )
                    ),
                "sacBunts":
                    safe_number(
                        batting.get(
                            "sacBunts"
                        )
                    ),
                "sacFlies":
                    safe_number(
                        batting.get(
                            "sacFlies"
                        )
                    ),
                "avg":
                    safe_number(
                        batting.get(
                            "avg"
                        )
                    ),
                "obp":
                    safe_number(
                        batting.get(
                            "obp"
                        )
                    ),
                "slg":
                    safe_number(
                        batting.get(
                            "slg"
                        )
                    ),
                "ops":
                    safe_number(
                        batting.get(
                            "ops"
                        )
                    ),
                # ★ 今回追加
                "babip":
                    safe_number(
                        batting.get(
                            "babip"
                        )
                    )
            },
            # =============================================
            # PITCHING
            # =============================================
            "pitching": {
                "games":
                    safe_number(
                        pitching.get(
                            "gamesPlayed"
                        )
                    ),
                "gamesStarted":
                    safe_number(
                        pitching.get(
                            "gamesStarted"
                        )
                    ),
                "inningsPitched":
                    safe_number(
                        pitching.get(
                            "inningsPitched"
                        )
                    ),
                "wins":
                    safe_number(
                        pitching.get(
                            "wins"
                        )
                    ),
                "losses":
                    safe_number(
                        pitching.get(
                            "losses"
                        )
                    ),
                "saves":
                    safe_number(
                        pitching.get(
                            "saves"
                        )
                    ),
                "holds":
                    safe_number(
                        pitching.get(
                            "holds"
                        )
                    ),
                "era":
                    safe_number(
                        pitching.get(
                            "era"
                        )
                    ),
                "whip":
                    safe_number(
                        pitching.get(
                            "whip"
                        )
                    ),
                "hits":
                    safe_number(
                        pitching.get(
                            "hits"
                        )
                    ),
                "earnedRuns":
                    safe_number(
                        pitching.get(
                            "earnedRuns"
                        )
                    ),
                "homeRuns":
                    safe_number(
                        pitching.get(
                            "homeRuns"
                        )
                    ),
                "walks":
                    safe_number(
                        pitching.get(
                            "baseOnBalls"
                        )
                    ),
                "strikeouts":
                    safe_number(
                        pitching.get(
                            "strikeOuts"
                        )
                    ),
                # ★ 対戦打者数
                "battersFaced":
                    batters_faced,
                # ★ K%
                "kPercent":
                    k_percent,
                # ★ BB%
                "bbPercent":
                    bb_percent,
                # APIから取得
                "k9":
                    safe_number(
                        pitching.get(
                            "strikeoutsPer9"
                        )
                    ),
                "bb9":
                    safe_number(
                        pitching.get(
                            "walksPer9"
                        )
                    )
            }
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
    # =====================================================
    # JSON SAVE
    # =====================================================
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
    # CHECK
    # =====================================================
    pitching_count = 0
    bf_count = 0
    k_percent_count = 0
    bb_percent_count = 0
    babip_count = 0
    for player in players.values():
        pitching = player.get(
            "pitching",
            {}
        )
        batting = player.get(
            "batting",
            {}
        )
        if pitching.get(
            "games"
        ) is not None:
            pitching_count += 1
        if pitching.get(
            "battersFaced"
        ) is not None:
            bf_count += 1
        if pitching.get(
            "kPercent"
        ) is not None:
            k_percent_count += 1
        if pitching.get(
            "bbPercent"
        ) is not None:
            bb_percent_count += 1
        if batting.get(
            "babip"
        ) is not None:
            babip_count += 1
    print("")
    print(
        "=========================================="
    )
    print(
        f"Players updated : {len(players)}"
    )
    print(
        f"Pitchers        : {pitching_count}"
    )
    print(
        f"BF available    : {bf_count}"
    )
    print(
        f"K% available    : {k_percent_count}"
    )
    print(
        f"BB% available   : {bb_percent_count}"
    )
    print(
        f"BABIP available : {babip_count}"
    )
    print(
        f"Output          : {OUTPUT_FILE}"
    )
    print(
        "=========================================="
    )
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
