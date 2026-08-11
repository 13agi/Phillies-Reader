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
# TEAM ROSTER
# =========================================================
def get_team_roster(roster_type):
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
# PLAYER DETAILS
# =========================================================
def get_player(player_id):
    url = (
        f"{BASE_URL}/people/"
        f"{player_id}"
    )
    params = {
        "hydrate": "currentTeam,transactions"
    }
    data = get_json(
        url,
        params
    )
    people = data.get(
        "people",
        []
    )
    if not people:
        return None
    return people[0]
# =========================================================
# ROSTER MAP
# =========================================================
def make_map(roster):
    result = {}
    for entry in roster:
        person = (
            entry.get("person")
            or {}
        )
        player_id = person.get(
            "id"
        )
        if player_id:
            result[player_id] = entry
    return result
# =========================================================
# VALUE
# =========================================================
def safe_dict(value):
    if isinstance(value, dict):
        return value
    return {}
# =========================================================
# IL DETECTION
#
# IMPORTANT:
#
# fullSeasonをILとはみなさない。
#
# MLB APIのRoster Entry / status / designation
# と選手のtransaction情報を確認する。
# =========================================================
def is_il_from_roster(entry):
    if not entry:
        return False
    status = safe_dict(
        entry.get("status")
    )
    designation = safe_dict(
        entry.get("designation")
    )
    values = [
        str(
            entry.get(
                "status",
                ""
            )
        ).upper(),
        str(
            entry.get(
                "designation",
                ""
            )
        ).upper(),
        str(
            status.get(
                "code",
                ""
            )
        ).upper(),
        str(
            status.get(
                "description",
                ""
            )
        ).upper(),
        str(
            designation.get(
                "code",
                ""
            )
        ).upper(),
        str(
            designation.get(
                "description",
                ""
            )
        ).upper()
    ]
    for value in values:
        if (
            "INJURED LIST"
            in value
            or
            "INJURED_LIST"
            in value
            or
            value in {
                "IL",
                "10-DAY IL",
                "15-DAY IL",
                "60-DAY IL",
                "7-DAY IL"
            }
        ):
            return True
    return False
# =========================================================
# TRANSACTION IL DETECTION
#
# 最新のMLB API transaction情報から
# 現在ILに置かれていることを確認する。
# =========================================================
def is_il_from_transactions(
    person
):
    transactions = (
        person.get(
            "transactions",
            []
        )
        if person
        else []
    )
    if not transactions:
        return False
    current_il = False
    for transaction in transactions:
        description = str(
            transaction.get(
                "description",
                ""
            )
        ).lower()
        effective_date = (
            transaction.get(
                "effectiveDate"
            )
            or
            transaction.get(
                "date"
            )
        )
        if not effective_date:
            continue
        # IL登録
        if (
            "placed"
            in description
            and
            (
                "injured list"
                in description
                or
                "injured" in description
            )
        ):
            current_il = True
        # IL解除
        elif (
            (
                "activated"
                in description
            )
            or
            (
                "reinstated"
                in description
            )
            or
            (
                "returned from"
                in description
            )
        ) and (
            "injured"
            in description
            or
            "injured list"
            in description
        ):
            current_il = False
    return current_il
# =========================================================
# DETERMINE STATUS
# =========================================================
def determine_status(
    player_id,
    active_map,
    roster_40_map,
    person
):
    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------
    if player_id in active_map:
        return "26MAN"
    # -----------------------------------------------------
    # IL
    # -----------------------------------------------------
    roster_entry = (
        roster_40_map.get(
            player_id
        )
    )
    if is_il_from_roster(
        roster_entry
    ):
        return "IL"
    if is_il_from_transactions(
        person
    ):
        return "IL"
    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------
    if player_id in roster_40_map:
        return "40MAN"
    return None
# =========================================================
# BUILD PLAYER
# =========================================================
def build_player(
    entry,
    active_map,
    roster_40_map
):
    person_basic = (
        entry.get(
            "person"
        )
        or {}
    )
    player_id = (
        person_basic.get(
            "id"
        )
    )
    if not player_id:
        return None
    # -----------------------------------------------------
    # PLAYER DETAIL
    # -----------------------------------------------------
    person = get_player(
        player_id
    )
    if not person:
        print(
            "Skipping player without API data:",
            player_id
        )
        return None
    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------
    roster_status = determine_status(
        player_id,
        active_map,
        roster_40_map,
        person
    )
    # 判定不能なら登録しない
    if roster_status is None:
        print(
            "Skipping player with unknown roster status:",
            player_id,
            person.get("fullName")
        )
        return None
    # -----------------------------------------------------
    # POSITION
    # -----------------------------------------------------
    position = (
        entry.get(
            "position"
        )
        or {}
    )
    # -----------------------------------------------------
    # BAT / PITCH
    # -----------------------------------------------------
    bat_side = (
        person.get(
            "batSide"
        )
        or {}
    )
    pitch_hand = (
        person.get(
            "pitchHand"
        )
        or {}
    )
    # -----------------------------------------------------
    # CURRENT TEAM
    # -----------------------------------------------------
    current_team = (
        person.get(
            "currentTeam"
        )
        or {}
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
            entry.get(
                "jerseyNumber"
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
        "rosterStatus":
            roster_status,
        "fortyMan":
            player_id in roster_40_map,
        "activeRoster":
            player_id in active_map,
        "il":
            roster_status == "IL",
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
    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------
    print(
        "Fetching 40-man roster..."
    )
    roster_40 = get_team_roster(
        "40Man"
    )
    roster_40_map = make_map(
        roster_40
    )
    print(
        "40-man:",
        len(roster_40_map)
    )
    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------
    print(
        "Fetching active roster..."
    )
    active_roster = get_team_roster(
        "active"
    )
    active_map = make_map(
        active_roster
    )
    print(
        "Active:",
        len(active_map)
    )
    # -----------------------------------------------------
    # BUILD
    # -----------------------------------------------------
    players = []
    for entry in roster_40:
        player = build_player(
            entry,
            active_map,
            roster_40_map
        )
        if player:
            players.append(
                player
            )
    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------
    status_order = {
        "26MAN": 0,
        "IL": 1,
        "40MAN": 2
    }
    players.sort(
        key=lambda p: (
            status_order.get(
                p.get(
                    "rosterStatus"
                ),
                99
            ),
            p.get(
                "name"
            )
            or ""
        )
    )
    # -----------------------------------------------------
    # OUTPUT
    # -----------------------------------------------------
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
    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------
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
