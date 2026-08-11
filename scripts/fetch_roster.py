import json
import os
import re
from datetime import datetime, timezone

import requests


# =========================================================
# SETTINGS
# =========================================================

BASE_URL = "https://statsapi.mlb.com/api/v1"

TEAM_ID = 143
SEASON = 2026

OUTPUT_FILE = "data/players.json"

# MLBシーズン開始から現在までのTransactionを取得
TRANSACTION_START = f"{SEASON}-01-01"


# =========================================================
# HTTP SESSION
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
        "season": SEASON
    }

    data = get_json(
        url,
        params
    )

    return data.get("roster", [])


# =========================================================
# PLAYER PROFILE
# =========================================================

def get_person(player_id):

    url = f"{BASE_URL}/people/{player_id}"

    data = get_json(url)

    people = data.get("people", [])

    if not people:
        return {}

    return people[0]


# =========================================================
# TRANSACTIONS
# =========================================================

def get_transactions():

    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    url = f"{BASE_URL}/transactions"

    params = {
        "teamId": TEAM_ID,
        "startDate": TRANSACTION_START,
        "endDate": today
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


def get_position(roster_item, person):

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
            "name": position.get("name")
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
            "name": primary.get("name")
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
        .get("batSide", {})
        .get("code")
    )

    throw = (
        person
        .get("pitchHand", {})
        .get("code")
    )

    return {
        "bat": bat if bat else None,
        "throw": throw if throw else None,
        "display": (
            f"{bat}/{throw}"
            if bat and throw
            else None
        )
    }


# =========================================================
# TRANSACTION DATE
# =========================================================

def transaction_date(transaction):

    value = (
        transaction.get("effectiveDate")
        or transaction.get("date")
        or ""
    )

    return value


# =========================================================
# IL TRANSACTION DETECTION
# =========================================================

IL_PATTERN = re.compile(
    r"(injured list|injured-list)",
    re.IGNORECASE
)

IL_PLACEMENT_PATTERN = re.compile(
    r"(placed|transferred).*(injured list|injured-list)",
    re.IGNORECASE
)

IL_ACTIVATION_PATTERN = re.compile(
    r"(activated|reinstated).*(injured list|injured-list)",
    re.IGNORECASE
)


def classify_il_transaction(transaction):

    description = (
        transaction.get("description")
        or ""
    )

    # -----------------------------------------------------
    # ILから復帰
    # -----------------------------------------------------

    if IL_ACTIVATION_PATTERN.search(
        description
    ):

        return "ACTIVATED"

    # -----------------------------------------------------
    # ILへ登録
    # -----------------------------------------------------

    if IL_PLACEMENT_PATTERN.search(
        description
    ):

        return "PLACED"

    # -----------------------------------------------------
    # その他
    # -----------------------------------------------------

    return None


# =========================================================
# CURRENT IL STATE
# =========================================================

def determine_current_il(
    player_id,
    transactions
):

    player_transactions = []

    for transaction in transactions:

        person = transaction.get(
            "person",
            {}
        )

        if person.get("id") != player_id:
            continue

        description = (
            transaction.get("description")
            or ""
        )

        if not IL_PATTERN.search(
            description
        ):
            continue

        event_type = classify_il_transaction(
            transaction
        )

        if event_type is None:
            continue

        player_transactions.append({
            "date":
                transaction_date(
                    transaction
                ),

            "effectiveDate":
                transaction.get(
                    "effectiveDate"
                ),

            "type":
                event_type,

            "description":
                description,

            "typeCode":
                transaction.get(
                    "typeCode"
                ),

            "transactionId":
                transaction.get(
                    "id"
                )
        })

    # -----------------------------------------------------
    # 日付順
    # -----------------------------------------------------

    player_transactions.sort(
        key=lambda x: (
            x.get("date") or ""
        )
    )

    # -----------------------------------------------------
    # 最後のIL関連イベントを確認
    # -----------------------------------------------------

    current_il = False
    latest_il = None

    for event in player_transactions:

        if event["type"] == "PLACED":

            current_il = True
            latest_il = event

        elif event["type"] == "ACTIVATED":

            current_il = False
            latest_il = event

    # -----------------------------------------------------
    # IL情報
    # -----------------------------------------------------

    il_info = {
        "isIL": current_il,
        "ilType": None,
        "ilDate": None,
        "injuryDescription": None
    }

    if current_il and latest_il:

        description = (
            latest_il["description"]
        )

        # 例:
        # 10-day injured list
        # 15-day injured list
        # 60-day injured list
        # 7-day injured list

        match = re.search(
            r"(\d+)[ -]?day injured list",
            description,
            re.IGNORECASE
        )

        if match:

            il_info["ilType"] = (
                f"{match.group(1)}-Day IL"
            )

        il_info["ilDate"] = (
            latest_il.get(
                "effectiveDate"
            )
            or latest_il.get(
                "date"
            )
        )

        # 「Left knee...」など、
        # ILの種類より後ろにある説明を保存
        il_info[
            "injuryDescription"
        ] = description

    return (
        current_il,
        il_info,
        player_transactions
    )


# =========================================================
# ROSTER STATUS
# =========================================================

def determine_roster_status(
    player_id,
    is_il,
    active_ids,
    forty_ids
):

    # -----------------------------------------------------
    # ILを最優先
    # -----------------------------------------------------

    if is_il:

        return "IL"

    # -----------------------------------------------------
    # 現在Active
    # -----------------------------------------------------

    if player_id in active_ids:

        return "ACTIVE"

    # -----------------------------------------------------
    # 40-Man
    # -----------------------------------------------------

    if player_id in forty_ids:

        return "40-MAN"

    # -----------------------------------------------------
    # 不明
    # -----------------------------------------------------

    return "UNKNOWN"


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=============================================="
    )

    print(
        "Philadelphia Phillies Roster Collector"
    )

    print(
        f"Season: {SEASON}"
    )

    print(
        "=============================================="
    )

    # =====================================================
    # ACTIVE
    # =====================================================

    print(
        "\n[1] Fetching ACTIVE roster..."
    )

    active_roster = get_roster(
        "active"
    )

    print(
        f"ACTIVE: {len(active_roster)}"
    )

    # =====================================================
    # 40-MAN
    # =====================================================

    print(
        "\n[2] Fetching 40-MAN roster..."
    )

    forty_roster = get_roster(
        "40Man"
    )

    print(
        f"40-MAN: {len(forty_roster)}"
    )

    # =====================================================
    # FULL ROSTER
    # =====================================================

    print(
        "\n[3] Fetching FULL roster..."
    )

    full_roster = get_roster(
        "fullRoster"
    )

    print(
        f"FULL: {len(full_roster)}"
    )

    # =====================================================
    # TRANSACTIONS
    # =====================================================

    print(
        "\n[4] Fetching transactions..."
    )

    transactions = get_transactions()

    print(
        f"Transactions: {len(transactions)}"
    )

    # =====================================================
    # ID SETS
    # =====================================================

    active_ids = set()

    forty_ids = set()

    full_ids = set()

    roster_items = {}

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

        if not player_id:
            continue

        active_ids.add(
            player_id
        )

        roster_items[
            player_id
        ] = item

    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # FULL
    # -----------------------------------------------------

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
    # ALL PLAYERS
    # =====================================================

    all_ids = (
        active_ids |
        forty_ids |
        full_ids
    )

    print(
        f"\nUnique players: {len(all_ids)}"
    )

    # =====================================================
    # BUILD PLAYERS
    # =====================================================

    players = []

    for index, player_id in enumerate(
        sorted(all_ids),
        start=1
    ):

        print(
            f"\n[{index}/{len(all_ids)}] "
            f"Player ID: {player_id}"
        )

        try:

            roster_item = roster_items.get(
                player_id,
                {}
            )

            person = get_person(
                player_id
            )

            if not person:

                print(
                    "  Profile unavailable"
                )

                continue

            # -------------------------------------------------
            # 基本情報
            # -------------------------------------------------

            position = get_position(
                roster_item,
                person
            )

            bt = get_bt(
                person
            )

            # -------------------------------------------------
            # IL判定
            # -------------------------------------------------

            (
                is_il,
                il_info,
                il_history
            ) = determine_current_il(
                player_id,
                transactions
            )

            # -------------------------------------------------
            # 最終ロスター状態
            # -------------------------------------------------

            roster_status = (
                determine_roster_status(
                    player_id,
                    is_il,
                    active_ids,
                    forty_ids
                )
            )

            # -------------------------------------------------
            # PLAYER
            # -------------------------------------------------

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
                    roster_status,

                "rosterMembership": {

                    "active":
                        player_id in active_ids,

                    "fortyMan":
                        player_id in forty_ids,

                    "fullRoster":
                        player_id in full_ids,

                    "il":
                        is_il

                },

                "il":
                    il_info,

                "ilTransactionHistory":
                    il_history

            }

            players.append(
                player
            )

            print(
                f"  {player.get('name')}"
            )

            print(
                f"  Position: "
                f"{position.get('code')}"
            )

            print(
                f"  B/T: "
                f"{bt.get('display')}"
            )

            print(
                f"  Status: "
                f"{roster_status}"
            )

            if is_il:

                print(
                    f"  IL: "
                    f"{il_info.get('ilType')}"
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
    # FINAL REPORT
    # =====================================================

    print(
        "\n=============================================="
    )

    print(
        "UPDATE COMPLETED"
    )

    print(
        "=============================================="
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
        f"Output  : {OUTPUT_FILE}"
    )

    print(
        "=============================================="
    )


if __name__ == "__main__":

    main()
