import json
import os
from datetime import datetime, timezone
import requests
# =========================================================
# 設定
# =========================================================
BASE_URL = "https://statsapi.mlb.com/api/v1"
TEAM_ID = 143
SEASON = 2026
OUTPUT_FILE = "data/players.json"
# =========================================================
# HTTP
# =========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Phillies-Reader/1.0"
})
def get_json(url, params=None):
    response = session.get(
        url,
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()
# =========================================================
# ROSTER取得
# =========================================================
def get_roster(roster_type):
    url = f"{BASE_URL}/teams/{TEAM_ID}/roster"
    params = {
        "rosterType": roster_type,
        "season": SEASON
    }
    data = get_json(
        url,
        params
    )
    return data.get(
        "roster",
        []
    )
# =========================================================
# 選手プロフィール
# =========================================================
def get_person(player_id):
    url = (
        f"{BASE_URL}/people/"
        f"{player_id}"
    )
    data = get_json(url)
    people = data.get(
        "people",
        []
    )
    if not people:
        return {}
    return people[0]
# =========================================================
# ポジション
# =========================================================
VALID_POSITIONS = {
    "P",
    "C",
    "1B",
    "2B",
    "3B",
    "SS",
    "LF",
    "CF",
    "RF",
    "DH"
}
def get_position(roster_item, person):
    roster_position = roster_item.get(
        "position",
        {}
    )
    abbreviation = roster_position.get(
        "abbreviation"
    )
    if abbreviation in VALID_POSITIONS:
        return {
            "code": abbreviation,
            "name": roster_position.get(
                "name"
            )
        }
    primary_position = person.get(
        "primaryPosition",
        {}
    )
    abbreviation = primary_position.get(
        "abbreviation"
    )
    if abbreviation in VALID_POSITIONS:
        return {
            "code": abbreviation,
            "name": primary_position.get(
                "name"
            )
        }
    return {
        "code": None,
        "name": None
    }
# =========================================================
# B/T
# =========================================================
def get_bt(person):
    bat_side = (
        person
        .get(
            "batSide",
            {}
        )
        .get(
            "code"
        )
    )
    pitch_hand = (
        person
        .get(
            "pitchHand",
            {}
        )
        .get(
            "code"
        )
    )
    if bat_side and pitch_hand:
        return {
            "bat": bat_side,
            "throw": pitch_hand,
            "display": (
                f"{bat_side}/{pitch_hand}"
            )
        }
    return {
        "bat": None,
        "throw": None,
        "display": None
    }
# =========================================================
# 選手データ生成
# =========================================================
def build_player(
    roster_item,
    roster_status
):
    person = roster_item.get(
        "person",
        {}
    )
    player_id = person.get(
        "id"
    )
    # -----------------------------------------------------
    # プロフィール
    # -----------------------------------------------------
    if player_id:
        profile = get_person(
            player_id
        )
    else:
        profile = {}
    # rosterのpersonを優先し、
    # profileに不足があれば補完
    if not profile:
        profile = person
    position = get_position(
        roster_item,
        profile
    )
    bt = get_bt(
        profile
    )
    player = {
        "id": player_id,
        "name": profile.get(
            "fullName"
        ),
        "firstName": profile.get(
            "firstName"
        ),
        "lastName": profile.get(
            "lastName"
        ),
        "jerseyNumber":
            roster_item.get(
                "jerseyNumber"
            ),
        "bt": bt,
        "position": position,
        "rosterStatus":
            roster_status
    }
    return player
# =========================================================
# ロスター統合
# =========================================================
def main():
    print(
        "===================================="
    )
    print(
        "Phillies Roster Collector"
    )
    print(
        f"Season: {SEASON}"
    )
    print(
        "===================================="
    )
    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------
    print(
        "\n40-MAN roster..."
    )
    roster_40 = get_roster(
        "40Man"
    )
    print(
        f"40-MAN: {len(roster_40)}"
    )
    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------
    print(
        "\nACTIVE roster..."
    )
    roster_active = get_roster(
        "active"
    )
    print(
        f"ACTIVE: {len(roster_active)}"
    )
    # -----------------------------------------------------
    # FULL ROSTER
    # -----------------------------------------------------
    print(
        "\nFULL roster..."
    )
    roster_full = get_roster(
        "fullRoster"
    )
    print(
        f"FULL: {len(roster_full)}"
    )
    # -----------------------------------------------------
    # 選手を統合
    # -----------------------------------------------------
    players = {}
    # -----------------------------------------------------
    # FULL
    # -----------------------------------------------------
    for item in roster_full:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if not player_id:
            continue
        players[player_id] = {
            "item": item,
            "status": "40-MAN"
        }
    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------
    for item in roster_40:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if not player_id:
            continue
        players[player_id] = {
            "item": item,
            "status": "40-MAN"
        }
    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------
    for item in roster_active:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if not player_id:
            continue
        players[player_id] = {
            "item": item,
            "status": "ACTIVE"
        }
    # -----------------------------------------------------
    # PLAYER BUILD
    # -----------------------------------------------------
    result = []
    total = len(players)
    for index, (
        player_id,
        entry
    ) in enumerate(
        players.items(),
        start=1
    ):
        print(
            f"[{index}/{total}] "
            f"{player_id}"
        )
        try:
            player = build_player(
                entry["item"],
                entry["status"]
            )
            result.append(
                player
            )
        except Exception as error:
            print(
                f"ERROR: {error}"
            )
    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------
    status_order = {
        "ACTIVE": 0,
        "IL": 1,
        "40-MAN": 2
    }
    result.sort(
        key=lambda player: (
            status_order.get(
                player.get(
                    "rosterStatus"
                ),
                99
            ),
            player.get(
                "name"
            ) or ""
        )
    )
    # -----------------------------------------------------
    # COUNTS
    # -----------------------------------------------------
    counts = {
        "players": len(result),
        "active": sum(
            1
            for p in result
            if p.get(
                "rosterStatus"
            ) == "ACTIVE"
        ),
        "il": sum(
            1
            for p in result
            if p.get(
                "rosterStatus"
            ) == "IL"
        ),
        "fortyMan": sum(
            1
            for p in result
            if p.get(
                "rosterStatus"
            ) == "40-MAN"
        )
    }
    # -----------------------------------------------------
    # OUTPUT
    # -----------------------------------------------------
    output = {
        "team": {
            "id": TEAM_ID,
            "name":
                "Philadelphia Phillies",
            "abbreviation":
                "PHI"
        },
        "season":
            SEASON,
        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "counts":
            counts,
        "players":
            result
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
            output,
            file,
            ensure_ascii=False,
            indent=2
        )
    print(
        "\n===================================="
    )
    print(
        "Roster update completed"
    )
    print(
        f"Players: {len(result)}"
    )
    print(
        f"Active: {counts['active']}"
    )
    print(
        f"IL: {counts['il']}"
    )
    print(
        f"40-Man: {counts['fortyMan']}"
    )
    print(
        "===================================="
    )
if __name__ == "__main__":
    main()
