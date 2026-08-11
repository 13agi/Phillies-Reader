import json
import os
from datetime import datetime, timezone
import requests
# =========================================================
# SETTINGS
# =========================================================
TEAM_ID = 143
SEASON = datetime.now(timezone.utc).year
BASE_URL = "https://statsapi.mlb.com/api/v1"
OUTPUT_FILE = "data/roster.json"
# =========================================================
# API
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
# 40-MAN ROSTER
# =========================================================
def get_40_man():
    url = f"{BASE_URL}/teams/{TEAM_ID}/roster"
    params = {
        "rosterType": "40Man",
        "season": SEASON
    }
    data = get_json(
        url,
        params
    )
    return data.get("roster", [])
# =========================================================
# ACTIVE ROSTER
# =========================================================
def get_active_roster():
    url = f"{BASE_URL}/teams/{TEAM_ID}/roster"
    params = {
        "rosterType": "active",
        "season": SEASON
    }
    data = get_json(
        url,
        params
    )
    return data.get("roster", [])
# =========================================================
# FULL ROSTER
# =========================================================
def get_full_roster():
    url = f"{BASE_URL}/teams/{TEAM_ID}/roster"
    params = {
        "rosterType": "fullSeason",
        "season": SEASON
    }
    data = get_json(
        url,
        params
    )
    return data.get("roster", [])
# =========================================================
# PLAYER DETAILS
# =========================================================
def get_player(player_id):
    url = f"{BASE_URL}/people/{player_id}"
    params = {
        "hydrate": "currentTeam"
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
        return {}
    return people[0]
# =========================================================
# ID SET
# =========================================================
def make_id_set(roster):
    result = set()
    for entry in roster:
        person = entry.get(
            "person",
            {}
        )
        player_id = person.get("id")
        if player_id:
            result.add(player_id)
    return result
# =========================================================
# PLAYER
# =========================================================
def build_player(
    entry,
    active_ids,
    full_ids
):
    person = entry.get(
        "person",
        {}
    )
    player_id = person.get("id")
    if not player_id:
        return None
    detail = get_player(
        player_id
    )
    position = entry.get(
        "position",
        {}
    )
    bat_side = detail.get(
        "batSide",
        {}
    ).get(
        "code",
        ""
    )
    pitch_hand = detail.get(
        "pitchHand",
        {}
    ).get(
        "code",
        ""
    )
    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------
    if player_id in active_ids:
        status = "ACTIVE"
    elif player_id in full_ids:
        status = "IL"
    else:
        status = "40-MAN"
    return {
        "id": player_id,
        "name": detail.get(
            "fullName",
            person.get(
                "fullName",
                ""
            )
        ),
        "firstName": detail.get(
            "firstName",
            ""
        ),
        "lastName": detail.get(
            "lastName",
            ""
        ),
        "number": entry.get(
            "jerseyNumber",
            ""
        ),
        "bt": (
            f"{bat_side}/{pitch_hand}"
            if bat_side or pitch_hand
            else ""
        ),
        "position": position.get(
            "abbreviation",
            ""
        ),
        "positionName": position.get(
            "name",
            ""
        ),
        "fortyMan": True,
        "activeRoster":
            player_id in active_ids,
        "status": status
    }
# =========================================================
# MAIN
# =========================================================
def main():
    print("")
    print("========================================")
    print("PHILADELPHIA PHILLIES ROSTER UPDATE")
    print("========================================")
    print("")
    # -----------------------------------------------------
    # 最新40-man
    # -----------------------------------------------------
    print(
        "Fetching latest 40-man roster..."
    )
    roster_40 = get_40_man()
    print(
        f"40-man entries: {len(roster_40)}"
    )
    # -----------------------------------------------------
    # 最新Active roster
    # -----------------------------------------------------
    print(
        "Fetching latest active roster..."
    )
    active_roster = get_active_roster()
    active_ids = make_id_set(
        active_roster
    )
    print(
        f"Active roster entries: {len(active_ids)}"
    )
    # -----------------------------------------------------
    # 最新Full Season roster
    # -----------------------------------------------------
    print(
        "Fetching latest roster status..."
    )
    full_roster = get_full_roster()
    full_ids = make_id_set(
        full_roster
    )
    print(
        f"Full roster entries: {len(full_ids)}"
    )
    # -----------------------------------------------------
    # 40-manを母集団として完全再生成
    # -----------------------------------------------------
    players = []
    for entry in roster_40:
        player = build_player(
            entry,
            active_ids,
            full_ids
        )
        if player:
            players.append(
                player
            )
    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------
    output = {
        "team": {
            "id": TEAM_ID,
            "name":
                "Philadelphia Phillies"
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
    # 保存
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
    print("")
    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print(
        f"Players: {len(players)}"
    )
    print("")
    print(
        "Roster update completed."
    )
# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    main()
