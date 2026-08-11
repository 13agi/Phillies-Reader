import json
import os
import requests
from datetime import datetime, timezone
# =========================================================
# CONFIG
# =========================================================
TEAM_ID = 143
SEASON = 2026
BASE_URL = "https://statsapi.mlb.com/api/v1"
OUTPUT_FILE = "data/roster.json"
HEADERS = {
    "User-Agent": "Phillies-Reader/1.0"
}
# =========================================================
# HTTP
# =========================================================
def get_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()
    return response.json()
# =========================================================
# MLB ROSTER API
# =========================================================
def get_roster(roster_type):
    url = (
        f"{BASE_URL}/teams/"
        f"{TEAM_ID}/roster"
    )
    params = {
        "rosterType": roster_type,
        "season": SEASON,
        "hydrate": "person"
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
# MAP
# =========================================================
def make_map(roster):
    result = {}
    for entry in roster:
        person = entry.get(
            "person",
            {}
        )
        if not isinstance(
            person,
            dict
        ):
            continue
        player_id = person.get(
            "id"
        )
        if player_id:
            result[player_id] = entry
    return result
# =========================================================
# TEXT NORMALIZATION
# =========================================================
def normalized(value):
    if value is None:
        return ""
    return str(
        value
    ).strip().upper()
# =========================================================
# IL DETECTION
#
# MLB APIのROSTER ENTRYを使用する。
#
# fullRosterには負傷者を含むため、
# そのentryのstatus / designation等を確認する。
#
# 文字列を推測して選手を新規作成することはしない。
# =========================================================
def roster_entry_is_il(entry):
    if not entry:
        return False
    # -----------------------------------------------------
    # 直接的なフィールド
    # -----------------------------------------------------
    candidates = [
        entry.get(
            "status"
        ),
        entry.get(
            "designation"
        ),
        entry.get(
            "rosterType"
        )
    ]
    # -----------------------------------------------------
    # status / designationがオブジェクトの場合
    # -----------------------------------------------------
    for key in (
        "status",
        "designation"
    ):
        value = entry.get(
            key
        )
        if isinstance(
            value,
            dict
        ):
            candidates.extend([
                value.get(
                    "code"
                ),
                value.get(
                    "description"
                ),
                value.get(
                    "name"
                )
            ])
    # -----------------------------------------------------
    # 判定
    # -----------------------------------------------------
    for value in candidates:
        text = normalized(
            value
        )
        if not text:
            continue
        # 代表的なMLB IL表記
        if text == "IL":
            return True
        if "INJURED LIST" in text:
            return True
        if "INJURED" in text:
            return True
        if "DISABLED LIST" in text:
            return True
    return False
# =========================================================
# STATUS
# =========================================================
def determine_roster_status(
    player_id,
    active_map,
    full_map,
    forty_map
):
    # -----------------------------------------------------
    # MLB API active roster
    # -----------------------------------------------------
    if player_id in active_map:
        return "26MAN"
    # -----------------------------------------------------
    # MLB API full roster
    #
    # ActiveではないがFullRosterに存在する選手について
    # APIのRoster Entryを確認。
    # -----------------------------------------------------
    full_entry = full_map.get(
        player_id
    )
    if roster_entry_is_il(
        full_entry
    ):
        return "IL"
    # -----------------------------------------------------
    # 40MAN
    # -----------------------------------------------------
    if player_id in forty_map:
        return "40MAN"
    # -----------------------------------------------------
    # 判定不能
    # -----------------------------------------------------
    return None
# =========================================================
# PLAYER
# =========================================================
def build_player(
    forty_entry,
    active_map,
    full_map,
    forty_map
):
    person = forty_entry.get(
        "person",
        {}
    )
    if not isinstance(
        person,
        dict
    ):
        return None
    player_id = person.get(
        "id"
    )
    if not player_id:
        return None
    # -----------------------------------------------------
    # FULL ROSTER ENTRY
    # -----------------------------------------------------
    full_entry = full_map.get(
        player_id,
        {}
    )
    # -----------------------------------------------------
    # ACTIVE ENTRY
    # -----------------------------------------------------
    active_entry = active_map.get(
        player_id,
        {}
    )
    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------
    roster_status = (
        determine_roster_status(
            player_id,
            active_map,
            full_map,
            forty_map
        )
    )
    # 判定不能な選手は登録しない
    if roster_status is None:
        print(
            "Skipping unknown roster status:",
            player_id,
            person.get(
                "fullName"
            )
        )
        return None
    # -----------------------------------------------------
    # POSITION
    # -----------------------------------------------------
    position = (
        active_entry.get(
            "position"
        )
        or
        full_entry.get(
            "position"
        )
        or
        forty_entry.get(
            "position"
        )
        or
        {}
    )
    # -----------------------------------------------------
    # BAT / PITCH
    # -----------------------------------------------------
    bat_side = (
        person.get(
            "batSide"
        )
        or
        {}
    )
    pitch_hand = (
        person.get(
            "pitchHand"
        )
        or
        {}
    )
    # -----------------------------------------------------
    # CURRENT TEAM
    # -----------------------------------------------------
    current_team = (
        person.get(
            "currentTeam"
        )
        or
        {}
    )
    # -----------------------------------------------------
    # RETURN
    # -----------------------------------------------------
    return {
        "id":
            player_id,
        "name":
            person.get(
                "fullName"
            ),
        "firstName":
            person.get(
                "firstName"
            ),
        "lastName":
            person.get(
                "lastName"
            ),
        "number":
            (
                active_entry.get(
                    "jerseyNumber"
                )
                or
                full_entry.get(
                    "jerseyNumber"
                )
                or
                forty_entry.get(
                    "jerseyNumber"
                )
            ),
        "position":
            position.get(
                "abbreviation"
            ),
        "positionName":
            position.get(
                "name"
            ),
        "bt":
            (
                f"{bat_side.get('code', '')}/"
                f"{pitch_hand.get('code', '')}"
            ).strip("/"),
        "batSide":
            bat_side.get(
                "code"
            ),
        "pitchHand":
            pitch_hand.get(
                "code"
            ),
        # -------------------------------------------------
        # FINAL ROSTER STATUS
        # -------------------------------------------------
        "rosterStatus":
            roster_status,
        "fortyMan":
            player_id in forty_map,
        "activeRoster":
            player_id in active_map,
        "il":
            roster_status == "IL",
        # -------------------------------------------------
        # TEAM
        # -------------------------------------------------
        "currentTeam":
            {
                "id":
                    current_team.get(
                        "id"
                    ),
                "name":
                    current_team.get(
                        "name"
                    )
            },
        # -------------------------------------------------
        # BASIC MLB INFORMATION
        # -------------------------------------------------
        "birthDate":
            person.get(
                "birthDate"
            ),
        "birthCity":
            person.get(
                "birthCity"
            ),
        "birthStateProvince":
            person.get(
                "birthStateProvince"
            ),
        "birthCountry":
            person.get(
                "birthCountry"
            ),
        "height":
            person.get(
                "height"
            ),
        "weight":
            person.get(
                "weight"
            ),
        "mlbDebutDate":
            person.get(
                "mlbDebutDate"
            ),
        "active":
            person.get(
                "active"
            )
    }
# =========================================================
# MAIN
# =========================================================
def main():
    print("")
    print("=" * 60)
    print("PHILLIES ROSTER UPDATE")
    print("=" * 60)
    print(
        "Season:",
        SEASON
    )
    print("")
    # =====================================================
    # 40-MAN
    # =====================================================
    print(
        "Fetching 40-man roster..."
    )
    roster_40 = get_roster(
        "40Man"
    )
    forty_map = make_map(
        roster_40
    )
    print(
        "40-man:",
        len(forty_map)
    )
    # =====================================================
    # ACTIVE
    # =====================================================
    print(
        "Fetching active roster..."
    )
    active_roster = get_roster(
        "active"
    )
    active_map = make_map(
        active_roster
    )
    print(
        "Active:",
        len(active_map)
    )
    # =====================================================
    # FULL ROSTER
    # =====================================================
    print(
        "Fetching full roster..."
    )
    full_roster = get_roster(
        "fullRoster"
    )
    full_map = make_map(
        full_roster
    )
    print(
        "Full roster:",
        len(full_map)
    )
    # =====================================================
    # BUILD
    #
    # 40-manを母集団とする。
    # MLB APIに存在しない選手は作らない。
    # =====================================================
    players = []
    for entry in roster_40:
        player = build_player(
            entry,
            active_map,
            full_map,
            forty_map
        )
        if player:
            players.append(
                player
            )
    # =====================================================
    # SORT
    # =====================================================
    status_order = {
        "26MAN": 0,
        "IL": 1,
        "40MAN": 2
    }
    players.sort(
        key=lambda player: (
            status_order.get(
                player.get(
                    "rosterStatus"
                ),
                99
            ),
            player.get(
                "name"
            )
            or ""
        )
    )
    # =====================================================
    # OUTPUT
    # =====================================================
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
                timezone.utc
            ).isoformat(),
        "count":
            len(players),
        "players":
            players
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
            output,
            file,
            ensure_ascii=False,
            indent=2
        )
    # =====================================================
    # SUMMARY
    # =====================================================
    counts = {
        "26MAN": 0,
        "IL": 0,
        "40MAN": 0
    }
    for player in players:
        status = player.get(
            "rosterStatus"
        )
        if status in counts:
            counts[status] += 1
    print("")
    print("=" * 60)
    print(
        "Saved:",
        OUTPUT_FILE
    )
    print(
        "Players:",
        len(players)
    )
    print(
        "26MAN:",
        counts["26MAN"]
    )
    print(
        "IL:",
        counts["IL"]
    )
    print(
        "40MAN:",
        counts["40MAN"]
    )
    print("=" * 60)
    print("")
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
