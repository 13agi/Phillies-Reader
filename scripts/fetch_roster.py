import json
import os
from datetime import datetime, timezone, timedelta
import requests
# =========================================================
# SETTINGS
# =========================================================
BASE_URL = "https://statsapi.mlb.com/api/v1"
TEAM_ID = 143
SEASON = 2026
OUTPUT_FILE = "data/players.json"
# トランザクション確認期間
TRANSACTION_LOOKBACK_DAYS = 365
# =========================================================
# SESSION
# =========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Phillies-Reader/1.0"
})
# =========================================================
# API
# =========================================================
def get_json(url, params=None):
    response = session.get(
        url,
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()
# =========================================================
# TEAM ROSTER
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
# PLAYER PROFILE
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
# TRANSACTIONS
# =========================================================
def get_transactions():
    today = datetime.now(
        timezone.utc
    ).date()
    start_date = (
        today -
        timedelta(
            days=TRANSACTION_LOOKBACK_DAYS
        )
    )
    url = f"{BASE_URL}/transactions"
    params = {
        "teamId": TEAM_ID,
        "startDate":
            start_date.isoformat(),
        "endDate":
            today.isoformat()
    }
    data = get_json(
        url,
        params
    )
    return data.get(
        "transactions",
        []
    )
# =========================================================
# POSITION
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
def get_position(
    roster_item,
    person
):
    position = roster_item.get(
        "position",
        {}
    )
    abbreviation = position.get(
        "abbreviation"
    )
    if abbreviation in VALID_POSITIONS:
        return {
            "code": abbreviation,
            "name": position.get(
                "name"
            )
        }
    primary = person.get(
        "primaryPosition",
        {}
    )
    abbreviation = primary.get(
        "abbreviation"
    )
    if abbreviation in VALID_POSITIONS:
        return {
            "code": abbreviation,
            "name": primary.get(
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
    bat = (
        person
        .get(
            "batSide",
            {}
        )
        .get(
            "code"
        )
    )
    throw = (
        person
        .get(
            "pitchHand",
            {}
        )
        .get(
            "code"
        )
    )
    if bat and throw:
        return {
            "bat": bat,
            "throw": throw,
            "display":
                f"{bat}/{throw}"
        }
    return {
        "bat": None,
        "throw": None,
        "display": None
    }
# =========================================================
# TRANSACTION HISTORY FOR PLAYER
# =========================================================
def player_transactions(
    transactions,
    player_id
):
    result = []
    for transaction in transactions:
        person = transaction.get(
            "person",
            {}
        )
        if person.get(
            "id"
        ) != player_id:
            continue
        result.append({
            "id":
                transaction.get(
                    "id"
                ),
            "date":
                transaction.get(
                    "date"
                ),
            "effectiveDate":
                transaction.get(
                    "effectiveDate"
                ),
            "resolutionDate":
                transaction.get(
                    "resolutionDate"
                ),
            "typeCode":
                transaction.get(
                    "typeCode"
                ),
            "typeDesc":
                transaction.get(
                    "typeDesc"
                ),
            "description":
                transaction.get(
                    "description"
                )
        })
    return result
# =========================================================
# STATUS
# =========================================================
def determine_status(
    player_id,
    active_ids,
    forty_ids,
    full_ids
):
    # -----------------------------------------------------
    # ACTIVE HAS HIGHEST CONFIDENCE FOR ACTIVE STATUS
    # -----------------------------------------------------
    if player_id in active_ids:
        return "ACTIVE"
    # -----------------------------------------------------
    # If the player exists in the full roster but not
    # active, classify as 40-MAN unless an explicit IL
    # roster source is available.
    #
    # We do NOT infer IL merely because the player is
    # absent from ACTIVE.
    # -----------------------------------------------------
    if player_id in forty_ids:
        return "40-MAN"
    if player_id in full_ids:
        return "40-MAN"
    return "UNKNOWN"
# =========================================================
# MAIN
# =========================================================
def main():
    print(
        "=========================================="
    )
    print(
        "Phillies Roster Collector"
    )
    print(
        f"Season: {SEASON}"
    )
    print(
        "=========================================="
    )
    # =====================================================
    # ACTIVE
    # =====================================================
    print(
        "\nFetching ACTIVE roster..."
    )
    active_roster = get_roster(
        "active"
    )
    print(
        f"ACTIVE players: "
        f"{len(active_roster)}"
    )
    # =====================================================
    # 40-MAN
    # =====================================================
    print(
        "\nFetching 40-MAN roster..."
    )
    forty_roster = get_roster(
        "40Man"
    )
    print(
        f"40-MAN players: "
        f"{len(forty_roster)}"
    )
    # =====================================================
    # FULL ROSTER
    # =====================================================
    print(
        "\nFetching FULL roster..."
    )
    full_roster = get_roster(
        "fullRoster"
    )
    print(
        f"FULL roster players: "
        f"{len(full_roster)}"
    )
    # =====================================================
    # TRANSACTIONS
    # =====================================================
    print(
        "\nFetching transactions..."
    )
    transactions = get_transactions()
    print(
        f"Transactions: "
        f"{len(transactions)}"
    )
    # =====================================================
    # ID SETS
    # =====================================================
    active_ids = set()
    forty_ids = set()
    full_ids = set()
    roster_items = {}
    # ACTIVE
    for item in active_roster:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if not player_id:
            continue
        active_ids.add(
            player_id
        )
        roster_items[
            player_id
        ] = item
    # 40-MAN
    for item in forty_roster:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if not player_id:
            continue
        forty_ids.add(
            player_id
        )
        roster_items.setdefault(
            player_id,
            item
        )
    # FULL
    for item in full_roster:
        person = item.get(
            "person",
            {}
        )
        player_id = person.get(
            "id"
        )
        if not player_id:
            continue
        full_ids.add(
            player_id
        )
        roster_items.setdefault(
            player_id,
            item
        )
    # =====================================================
    # ALL PLAYER IDS
    # =====================================================
    all_ids = (
        active_ids |
        forty_ids |
        full_ids
    )
    print(
        f"\nUnique players: "
        f"{len(all_ids)}"
    )
    # =====================================================
    # BUILD PLAYERS
    # =====================================================
    players = []
    for index, player_id in enumerate(
        sorted(all_ids),
        start=1
    ):
        roster_item = roster_items.get(
            player_id,
            {}
        )
        print(
            f"[{index}/{len(all_ids)}] "
            f"Player ID: {player_id}"
        )
        try:
            person = get_person(
                player_id
            )
            if not person:
                print(
                    "  Profile unavailable"
                )
                continue
            position = get_position(
                roster_item,
                person
            )
            bt = get_bt(
                person
            )
            status = determine_status(
                player_id,
                active_ids,
                forty_ids,
                full_ids
            )
            history = player_transactions(
                transactions,
                player_id
            )
            player = {
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
                "jerseyNumber":
                    roster_item.get(
                        "jerseyNumber"
                    ),
                "bt":
                    bt,
                "position":
                    position,
                "rosterStatus":
                    status,
                "rosterMembership": {
                    "active":
                        player_id in active_ids,
                    "fortyMan":
                        player_id in forty_ids,
                    "fullRoster":
                        player_id in full_ids,
                    # ILはこの段階では
                    # 「ACTIVEではない」という理由だけで
                    # trueにはしない。
                    "il":
                        None
                },
                "transactions":
                    history
            }
            players.append(
                player
            )
        except Exception as error:
            print(
                f"  ERROR: {error}"
            )
    # =====================================================
    # SORT
    # =====================================================
    status_order = {
        "ACTIVE": 0,
        "IL": 1,
        "40-MAN": 2,
        "UNKNOWN": 3
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
            ) or ""
        )
    )
    # =====================================================
    # COUNTS
    # =====================================================
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
        "unknown":
            sum(
                1
                for p in players
                if p.get(
                    "rosterStatus"
                ) == "UNKNOWN"
            )
    }
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
        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "counts":
            counts,
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
    # RESULT
    # =====================================================
    print(
        "\n=========================================="
    )
    print(
        "Roster update completed"
    )
    print(
        f"Players : {counts['players']}"
    )
    print(
        f"ACTIVE  : {counts['active']}"
    )
    print(
        f"IL      : {counts['il']}"
    )
    print(
        f"40-MAN  : {counts['fortyMan']}"
    )
    print(
        f"UNKNOWN : {counts['unknown']}"
    )
    print(
        "=========================================="
    )
if __name__ == "__main__":
    main()
