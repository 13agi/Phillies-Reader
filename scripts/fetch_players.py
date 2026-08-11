import json
import os
import time
from datetime import datetime, timezone
import requests
# =========================================================
# SETTINGS
# =========================================================
BASE_URL = "https://statsapi.mlb.com/api/v1"
TEAM_ID = 143
SEASON = 2026
OUTPUT_FILE = "data/players.json"
REQUEST_DELAY = 0.10
POSITION_CODES = {
    "P",
    "C",
    "1B",
    "2B",
    "3B",
    "SS",
    "LF",
    "CF",
    "RF",
    "DH",
}
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
# ROSTER
# =========================================================
def get_roster(roster_type):
    url = f"{BASE_URL}/teams/{TEAM_ID}/roster"
    params = {
        "rosterType": roster_type,
        "season": SEASON,
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
# PLAYER PROFILE
# =========================================================
def get_player(player_id):
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
# PLAYER STATS
# =========================================================
def get_player_stats(
    player_id,
    group,
    stat_type
):
    url = (
        f"{BASE_URL}/people/"
        f"{player_id}/stats"
    )
    params = {
        "stats": stat_type,
        "group": group,
        "season": SEASON,
    }
    data = get_json(
        url,
        params
    )
    result = {}
    for stats_block in data.get(
        "stats",
        []
    ):
        for split in stats_block.get(
            "splits",
            []
        ):
            stat = split.get(
                "stat",
                {}
            )
            if stat:
                result.update(
                    stat
                )
    return result
# =========================================================
# ALL STAT TYPES
# =========================================================
STAT_TYPES = [
    "season",
    "seasonAdvanced",
    "sabermetrics",
    "expectedStatistics",
]
def collect_stats(
    player_id,
    group
):
    result = {}
    for stat_type in STAT_TYPES:
        try:
            stats = get_player_stats(
                player_id,
                group,
                stat_type
            )
            result[stat_type] = stats
        except Exception as error:
            print(
                f"    {group} "
                f"{stat_type} error: "
                f"{error}"
            )
            result[stat_type] = {}
        time.sleep(
            REQUEST_DELAY
        )
    return result
# =========================================================
# POSITION
# =========================================================
def get_position(
    roster_item,
    person
):
    position = roster_item.get(
        "position",
        {}
    )
    abbreviation = position.get(
        "abbreviation",
        ""
    )
    if abbreviation in POSITION_CODES:
        return abbreviation
    primary_position = person.get(
        "primaryPosition",
        {}
    )
    abbreviation = primary_position.get(
        "abbreviation",
        ""
    )
    if abbreviation in POSITION_CODES:
        return abbreviation
    return ""
# =========================================================
# ROSTER MAP
# =========================================================
def create_roster_map(
    active_roster,
    forty_man_roster
):
    roster_map = {}
    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------
    for item in forty_man_roster:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if player_id:
            roster_map[player_id] = {
                "status": "40-MAN",
                "item": item,
            }
    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------
    for item in active_roster:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if player_id:
            roster_map[player_id] = {
                "status": "ACTIVE",
                "item": item,
            }
    return roster_map
# =========================================================
# PLAYER
# =========================================================
def build_player(
    player_id,
    person,
    roster_entry
):
    roster_item = roster_entry.get(
        "item",
        {}
    )
    roster_status = roster_entry.get(
        "status",
        "UNKNOWN"
    )
    position = get_position(
        roster_item,
        person
    )
    bat_side = (
        person
        .get(
            "batSide",
            {}
        )
        .get(
            "code",
            ""
        )
    )
    pitch_hand = (
        person
        .get(
            "pitchHand",
            {}
        )
        .get(
            "code",
            ""
        )
    )
    # -----------------------------------------------------
    # BASE
    # -----------------------------------------------------
    player = {
        "id": player_id,
        "name": person.get(
            "fullName",
            ""
        ),
        "firstName": person.get(
            "firstName",
            ""
        ),
        "lastName": person.get(
            "lastName",
            ""
        ),
        "jerseyNumber":
            roster_item.get(
                "jerseyNumber"
            ),
        "bt": (
            f"{bat_side}/{pitch_hand}"
            if bat_side and pitch_hand
            else None
        ),
        "batSide": (
            bat_side
            if bat_side
            else None
        ),
        "pitchHand": (
            pitch_hand
            if pitch_hand
            else None
        ),
        "position": (
            position
            if position
            else None
        ),
        "positionName":
            roster_item
            .get(
                "position",
                {}
            )
            .get(
                "name"
            ),
        "rosterStatus":
            roster_status,
    }
    # -----------------------------------------------------
    # PITCHER
    # -----------------------------------------------------
    if position == "P":
        print(
            f"    Type: PITCHER"
        )
        stats = collect_stats(
            player_id,
            "pitching"
        )
        player[
            "pitching"
        ] = stats
        # 野手成績は作らない
        player[
            "hitting"
        ] = None
    # -----------------------------------------------------
    # HITTER
    # -----------------------------------------------------
    else:
        print(
            f"    Type: HITTER"
        )
        stats = collect_stats(
            player_id,
            "hitting"
        )
        player[
            "hitting"
        ] = stats
        # 投手成績は作らない
        player[
            "pitching"
        ] = None
    # -----------------------------------------------------
    # 更新時刻
    # -----------------------------------------------------
    player[
        "updatedAt"
    ] = datetime.now(
        timezone.utc
    ).isoformat()
    return player
# =========================================================
# MAIN
# =========================================================
def main():
    print(
        "======================================"
    )
    print(
        "Phillies Player Data"
    )
    print(
        f"Season: {SEASON}"
    )
    print(
        "======================================"
    )
    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------
    print(
        "\nFetching ACTIVE roster..."
    )
    active_roster = get_roster(
        "active"
    )
    print(
        f"ACTIVE: "
        f"{len(active_roster)}"
    )
    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------
    print(
        "\nFetching 40-MAN roster..."
    )
    forty_man_roster = get_roster(
        "40Man"
    )
    print(
        f"40-MAN: "
        f"{len(forty_man_roster)}"
    )
    # -----------------------------------------------------
    # ROSTER MAP
    # -----------------------------------------------------
    roster_map = create_roster_map(
        active_roster,
        forty_man_roster
    )
    # -----------------------------------------------------
    # ALL PLAYER IDS
    # -----------------------------------------------------
    player_ids = sorted(
        roster_map.keys()
    )
    print(
        f"\nPlayers: "
        f"{len(player_ids)}"
    )
    players = []
    # -----------------------------------------------------
    # PROCESS
    # -----------------------------------------------------
    for index, player_id in enumerate(
        player_ids,
        start=1
    ):
        print(
            f"\n[{index}/{len(player_ids)}] "
            f"Player ID: {player_id}"
        )
        try:
            person = get_player(
                player_id
            )
            if not person:
                print(
                    "  Profile unavailable"
                )
                continue
            roster_entry = roster_map[
                player_id
            ]
            player = build_player(
                player_id,
                person,
                roster_entry
            )
            players.append(
                player
            )
        except Exception as error:
            print(
                f"  ERROR: {error}"
            )
    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------
    status_order = {
        "ACTIVE": 0,
        "IL": 1,
        "40-MAN": 2,
        "UNKNOWN": 3,
    }
    players.sort(
        key=lambda p: (
            status_order.get(
                p.get(
                    "rosterStatus",
                    "UNKNOWN"
                ),
                99
            ),
            p.get(
                "position"
            ) or "",
            p.get(
                "name"
            ) or "",
        )
    )
    # -----------------------------------------------------
    # COUNTS
    # -----------------------------------------------------
    counts = {
        "players":
            len(players),
        "active":
            sum(
                1
                for p in players
                if p.get(
                    "rosterStatus"
                ) == "ACTIVE"
            ),
        "il":
            sum(
                1
                for p in players
                if p.get(
                    "rosterStatus"
                ) == "IL"
            ),
        "fortyMan":
            sum(
                1
                for p in players
                if p.get(
                    "rosterStatus"
                ) == "40-MAN"
            ),
        "hitters":
            sum(
                1
                for p in players
                if p.get(
                    "position"
                ) != "P"
            ),
        "pitchers":
            sum(
                1
                for p in players
                if p.get(
                    "position"
                ) == "P"
            ),
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
                "PHI",
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
            players,
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
        "\n======================================"
    )
    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print(
        f"Players: {len(players)}"
    )
    print(
        f"Hitters: {counts['hitters']}"
    )
    print(
        f"Pitchers: {counts['pitchers']}"
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
        "======================================"
    )
if __name__ == "__main__":
    main()
