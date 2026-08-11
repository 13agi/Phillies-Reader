import json
import os
import re
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

REQUEST_SLEEP = 0.15


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

    return data.get(
        "roster",
        []
    )


# =========================================================
# PLAYER
# =========================================================

def get_person(player_id):

    url = f"{BASE_URL}/people/{player_id}"

    params = {
        "hydrate": "transactions"
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
# TEAM TRANSACTIONS
# =========================================================

def get_team_transactions():

    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    url = f"{BASE_URL}/transactions"

    params = {
        "teamId": TEAM_ID,
        "startDate": f"{SEASON}-01-01",
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

    code = position.get(
        "abbreviation"
    )

    if code in VALID_POSITIONS:

        return {
            "code": code,
            "name": position.get(
                "name"
            )
        }

    primary = person.get(
        "primaryPosition",
        {}
    )

    code = primary.get(
        "abbreviation"
    )

    if code in VALID_POSITIONS:

        return {
            "code": code,
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

    return {

        "bat":
            bat if bat else None,

        "throw":
            throw if throw else None,

        "display":
            f"{bat}/{throw}"
            if bat and throw
            else None

    }


# =========================================================
# TRANSACTION DATE
# =========================================================

def get_transaction_date(transaction):

    return (
        transaction.get(
            "effectiveDate"
        )
        or
        transaction.get(
            "date"
        )
        or
        ""
    )


# =========================================================
# IL DETECTION
# =========================================================

IL_PLACEMENT_PATTERNS = [

    re.compile(
        r"\bplaced\b.*\binjured list\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\btransferred\b.*\binjured list\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\btransferred\b.*\b\d+[- ]day\b.*\binjured list\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\bto the\b.*\binjured list\b",
        re.IGNORECASE
    )
]


IL_REMOVAL_PATTERNS = [

    re.compile(
        r"\bactivated\b.*\binjured list\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\breinstated\b.*\binjured list\b",
        re.IGNORECASE
    ),

    re.compile(
        r"\bfrom the\b.*\binjured list\b",
        re.IGNORECASE
    )
]


def is_il_placement(description):

    if not description:
        return False

    for pattern in IL_PLACEMENT_PATTERNS:

        if pattern.search(description):

            return True

    return False


def is_il_removal(description):

    if not description:
        return False

    for pattern in IL_REMOVAL_PATTERNS:

        if pattern.search(description):

            return True

    return False


# =========================================================
# IL TYPE
# =========================================================

def extract_il_type(description):

    if not description:
        return None

    patterns = [

        (
            r"(\d+)[ -]?day injured list",
            lambda m:
                f"{m.group(1)}-Day IL"
        ),

        (
            r"(\d+)[ -]?day IL",
            lambda m:
                f"{m.group(1)}-Day IL"
        )

    ]

    for pattern, formatter in patterns:

        match = re.search(
            pattern,
            description,
            re.IGNORECASE
        )

        if match:

            return formatter(match)

    return None


# =========================================================
# PLAYER TRANSACTIONS
# =========================================================

def get_player_transactions(person):

    transactions = person.get(
        "transactions",
        []
    )

    result = []

    for transaction in transactions:

        description = (
            transaction.get(
                "description"
            )
            or ""
        )

        if not (
            is_il_placement(
                description
            )
            or
            is_il_removal(
                description
            )
        ):

            continue

        result.append({

            "date":
                get_transaction_date(
                    transaction
                ),

            "effectiveDate":
                transaction.get(
                    "effectiveDate"
                ),

            "description":
                description,

            "typeCode":
                transaction.get(
                    "typeCode"
                ),

            "typeDesc":
                transaction.get(
                    "typeDesc"
                ),

            "transactionId":
                transaction.get(
                    "id"
                )

        })

    result.sort(
        key=lambda x:
            x.get("date") or ""
    )

    return result


# =========================================================
# CURRENT IL STATE
# =========================================================

def determine_il_state(
    person,
    team_transactions,
    player_id
):

    events = []

    # -----------------------------------------------------
    # PLAYER TRANSACTIONS
    # -----------------------------------------------------

    for transaction in (
        person.get(
            "transactions",
            []
        )
    ):

        transaction_person = (
            transaction.get(
                "person",
                {}
            )
        )

        transaction_player_id = (
            transaction_person.get(
                "id"
            )
        )

        # person hydrateの場合はpersonが
        # 入っていない場合があるためID確認を
        # 厳密に要求しない
        if (
            transaction_player_id
            and
            transaction_player_id != player_id
        ):
            continue

        description = (
            transaction.get(
                "description"
            )
            or ""
        )

        if (
            is_il_placement(
                description
            )
            or
            is_il_removal(
                description
            )
        ):

            events.append({
                "date":
                    get_transaction_date(
                        transaction
                    ),

                "effectiveDate":
                    transaction.get(
                        "effectiveDate"
                    ),

                "description":
                    description,

                "typeCode":
                    transaction.get(
                        "typeCode"
                    ),

                "typeDesc":
                    transaction.get(
                        "typeDesc"
                    ),

                "transactionId":
                    transaction.get(
                        "id"
                    )
            })

    # -----------------------------------------------------
    # TEAM TRANSACTIONS
    # 補完
    # -----------------------------------------------------

    for transaction in team_transactions:

        person_data = (
            transaction.get(
                "person",
                {}
            )
        )

        if person_data.get(
            "id"
        ) != player_id:

            continue

        description = (
            transaction.get(
                "description"
            )
            or ""
        )

        if (
            is_il_placement(
                description
            )
            or
            is_il_removal(
                description
            )
        ):

            events.append({
                "date":
                    get_transaction_date(
                        transaction
                    ),

                "effectiveDate":
                    transaction.get(
                        "effectiveDate"
                    ),

                "description":
                    description,

                "typeCode":
                    transaction.get(
                        "typeCode"
                    ),

                "typeDesc":
                    transaction.get(
                        "typeDesc"
                    ),

                "transactionId":
                    transaction.get(
                        "id"
                    )
            })

    # -----------------------------------------------------
    # 重複除去
    # -----------------------------------------------------

    unique = {}

    for event in events:

        key = (
            event.get(
                "transactionId"
            )
            or
            (
                event.get("date"),
                event.get("description")
            )
        )

        unique[key] = event

    events = list(
        unique.values()
    )

    # -----------------------------------------------------
    # 時系列
    # -----------------------------------------------------

    events.sort(
        key=lambda x:
            x.get("date") or ""
    )

    # -----------------------------------------------------
    # STATE MACHINE
    # -----------------------------------------------------

    is_il = False

    latest_il_event = None

    for event in events:

        description = (
            event.get(
                "description"
            )
            or
            ""
        )

        # IL登録・IL間移動
        if is_il_placement(
            description
        ):

            is_il = True

            latest_il_event = event

        # ILから復帰
        elif is_il_removal(
            description
        ):

            is_il = False

            latest_il_event = event

    # -----------------------------------------------------
    # IL情報
    # -----------------------------------------------------

    il_info = {

        "isIL":
            is_il,

        "ilType":
            None,

        "ilDate":
            None,

        "description":
            None

    }

    if is_il and latest_il_event:

        description = (
            latest_il_event.get(
                "description"
            )
            or
            ""
        )

        il_info["ilType"] = (
            extract_il_type(
                description
            )
        )

        il_info["ilDate"] = (
            latest_il_event.get(
                "effectiveDate"
            )
            or
            latest_il_event.get(
                "date"
            )
        )

        il_info["description"] = (
            description
        )

    return (
        is_il,
        il_info,
        events
    )


# =========================================================
# ROSTER STATUS
# =========================================================

def determine_status(
    player_id,
    is_il,
    active_ids,
    forty_ids
):

    # ILが最優先
    if is_il:

        return "IL"

    # MLB APIのactive roster
    if player_id in active_ids:

        return "ACTIVE"

    # MLB APIの40-man roster
    if player_id in forty_ids:

        return "40-MAN"

    return "UNKNOWN"


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "=============================================="
    )

    print(
        "PHILLIES ROSTER COLLECTOR"
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
        "\nFetching ACTIVE roster..."
    )

    active_roster = get_roster(
        "active"
    )

    # =====================================================
    # 40-MAN
    # =====================================================

    print(
        "Fetching 40-MAN roster..."
    )

    forty_roster = get_roster(
        "40Man"
    )

    # =====================================================
    # FULL
    # =====================================================

    print(
        "Fetching FULL roster..."
    )

    full_roster = get_roster(
        "fullRoster"
    )

    # =====================================================
    # TRANSACTIONS
    # =====================================================

    print(
        "Fetching team transactions..."
    )

    team_transactions = (
        get_team_transactions()
    )

    # =====================================================
    # IDS
    # =====================================================

    active_ids = set()

    forty_ids = set()

    full_ids = set()

    roster_items = {}

    for item in active_roster:

        person = item.get(
            "person",
            {}
        )

        player_id = person.get(
            "id"
        )

        if player_id:

            active_ids.add(
                player_id
            )

            roster_items[
                player_id
            ] = item

    for item in forty_roster:

        person = item.get(
            "person",
            {}
        )

        player_id = person.get(
            "id"
        )

        if player_id:

            forty_ids.add(
                player_id
            )

            roster_items.setdefault(
                player_id,
                item
            )

    for item in full_roster:

        person = item.get(
            "person",
            {}
        )

        player_id = person.get(
            "id"
        )

        if player_id:

            full_ids.add(
                player_id
            )

            roster_items.setdefault(
                player_id,
                item
            )

    # =====================================================
    # FULL ROSTER IS THE MASTER LIST
    # =====================================================

    all_ids = (
        full_ids
        |
        active_ids
        |
        forty_ids
    )

    print(
        f"\nPlayers discovered: "
        f"{len(all_ids)}"
    )

    # =====================================================
    # BUILD
    # =====================================================

    players = []

    for index, player_id in enumerate(
        sorted(all_ids),
        start=1
    ):

        print(
            f"[{index}/{len(all_ids)}] "
            f"{player_id}"
        )

        try:

            roster_item = roster_items.get(
                player_id,
                {}
            )

            # -------------------------------------------------
            # PROFILE
            # -------------------------------------------------

            person = get_person(
                player_id
            )

            if not person:

                print(
                    "  Profile unavailable"
                )

                continue

            time.sleep(
                REQUEST_SLEEP
            )

            # -------------------------------------------------
            # BASIC
            # -------------------------------------------------

            name = person.get(
                "fullName"
            )

            jersey = (
                roster_item.get(
                    "jerseyNumber"
                )
            )

            bt = get_bt(
                person
            )

            position = get_position(
                roster_item,
                person
            )

            # -------------------------------------------------
            # IL
            # -------------------------------------------------

            (
                is_il,
                il_info,
                il_history
            ) = determine_il_state(
                person,
                team_transactions,
                player_id
            )

            # -------------------------------------------------
            # STATUS
            # -------------------------------------------------

            status = determine_status(
                player_id,
                is_il,
                active_ids,
                forty_ids
            )

            # -------------------------------------------------
            # PLAYER
            # -------------------------------------------------

            player = {

                "id":
                    player_id,

                "name":
                    name,

                "firstName":
                    person.get(
                        "firstName"
                    ),

                "lastName":
                    person.get(
                        "lastName"
                    ),

                "jerseyNumber":
                    jersey,

                "bt":
                    bt,

                "position":
                    position,

                "rosterStatus":
                    status,

                "rosterMembership": {

                    "active":
                        player_id
                        in active_ids,

                    "fortyMan":
                        player_id
                        in forty_ids,

                    "fullRoster":
                        player_id
                        in full_ids,

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
                f"  {name} | "
                f"{status} | "
                f"{position.get('code')} | "
                f"{bt.get('display')}"
            )

            if is_il:

                print(
                    f"  >>> IL: "
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
            )
            or
            ""
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
                )
                == "ACTIVE"
            ),

        "il":
            sum(
                1
                for p in players
                if p.get(
                    "rosterStatus"
                )
                == "IL"
            ),

        "fortyMan":
            sum(
                1
                for p in players
                if p.get(
                    "rosterStatus"
                )
                == "40-MAN"
            ),

        "unknown":
            sum(
                1
                for p in players
                if p.get(
                    "rosterStatus"
                )
                == "UNKNOWN"
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
    # REPORT
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
