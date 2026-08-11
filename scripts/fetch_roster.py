import json
import os
import re
import sys
from datetime import datetime, timezone
import requests
# =========================================================
# 設定
# =========================================================
BASE_URL = "https://statsapi.mlb.com/api/v1"
TEAM_ID = 143
SEASON = 2026
OUTPUT_FILE = "data/players.json"
TEMP_FILE = "data/players.json.tmp"
TIMEOUT = 30
# =========================================================
# HTTP
# =========================================================
session = requests.Session()
session.headers.update({
    "User-Agent": "Phillies-Reader-Roster/1.0"
})
def api_get(endpoint, params=None):
    url = f"{BASE_URL}{endpoint}"
    response = session.get(
        url,
        params=params,
        timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json()
# =========================================================
# ロスター取得
# =========================================================
def get_roster(roster_type):
    data = api_get(
        f"/teams/{TEAM_ID}/roster",
        {
            "rosterType": roster_type,
            "season": SEASON
        }
    )
    return data.get("roster", [])
# =========================================================
# 選手情報取得
# =========================================================
def get_player(player_id):
    data = api_get(
        f"/people/{player_id}",
        {
            "hydrate": "transactions"
        }
    )
    people = data.get("people", [])
    if not people:
        return None
    return people[0]
# =========================================================
# チームのTransaction取得
# =========================================================
def get_transactions():
    today = datetime.now(
        timezone.utc
    ).date().isoformat()
    data = api_get(
        "/transactions",
        {
            "teamId": TEAM_ID,
            "startDate": f"{SEASON}-01-01",
            "endDate": today
        }
    )
    return data.get(
        "transactions",
        []
    )
# =========================================================
# IL判定
# =========================================================
IL_WORDS = re.compile(
    r"\binjured list\b|\binjured-list\b|\bIL\b",
    re.IGNORECASE
)
IL_START_WORDS = re.compile(
    r"\bplaced\b|\btransferred\b|\bto the\b",
    re.IGNORECASE
)
IL_END_WORDS = re.compile(
    r"\bactivated\b|\breinstated\b",
    re.IGNORECASE
)
def transaction_is_il_start(description):
    if not description:
        return False
    if not IL_WORDS.search(description):
        return False
    if IL_END_WORDS.search(description):
        return False
    return bool(
        IL_START_WORDS.search(description)
    )
def transaction_is_il_end(description):
    if not description:
        return False
    if not IL_WORDS.search(description):
        return False
    return bool(
        IL_END_WORDS.search(description)
    )
def extract_il_type(description):
    if not description:
        return None
    match = re.search(
        r"(\d+)[ -]?day\s+(?:injured list|IL)",
        description,
        re.IGNORECASE
    )
    if match:
        return f"{match.group(1)}-Day IL"
    return None
# =========================================================
# 選手ごとのIL状態を再構築
# =========================================================
def determine_il_state(
    player_id,
    player_transactions,
    team_transactions
):
    events = []
    # -----------------------------------------------------
    # player transaction
    # -----------------------------------------------------
    for transaction in player_transactions:
        description = (
            transaction.get(
                "description"
            )
            or ""
        )
        if not IL_WORDS.search(description):
            continue
        if not (
            transaction_is_il_start(description)
            or
            transaction_is_il_end(description)
        ):
            continue
        events.append({
            "date": (
                transaction.get(
                    "effectiveDate"
                )
                or
                transaction.get(
                    "date"
                )
                or
                ""
            ),
            "description": description,
            "transactionId":
                transaction.get("id")
        })
    # -----------------------------------------------------
    # team transaction
    # 補完用
    # -----------------------------------------------------
    for transaction in team_transactions:
        person = transaction.get(
            "person",
            {}
        )
        if person.get("id") != player_id:
            continue
        description = (
            transaction.get(
                "description"
            )
            or ""
        )
        if not IL_WORDS.search(description):
            continue
        if not (
            transaction_is_il_start(description)
            or
            transaction_is_il_end(description)
        ):
            continue
        events.append({
            "date": (
                transaction.get(
                    "effectiveDate"
                )
                or
                transaction.get(
                    "date"
                )
                or
                ""
            ),
            "description": description,
            "transactionId":
                transaction.get("id")
        })
    # -----------------------------------------------------
    # 重複削除
    # -----------------------------------------------------
    unique = {}
    for event in events:
        key = (
            event.get("transactionId")
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
    # 日付順
    # -----------------------------------------------------
    events.sort(
        key=lambda x:
            x.get("date") or ""
    )
    # -----------------------------------------------------
    # 状態再構築
    # -----------------------------------------------------
    is_il = False
    latest_il_start = None
    for event in events:
        description = (
            event.get(
                "description"
            )
            or
            ""
        )
        if transaction_is_il_start(
            description
        ):
            is_il = True
            latest_il_start = event
        elif transaction_is_il_end(
            description
        ):
            is_il = False
    # -----------------------------------------------------
    # IL情報
    # -----------------------------------------------------
    il_info = {
        "isIL": is_il,
        "ilType": None,
        "ilDate": None,
        "description": None
    }
    if is_il and latest_il_start:
        description = (
            latest_il_start.get(
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
            latest_il_start.get(
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
def get_position(roster_item, player):
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
    primary = player.get(
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
def get_bt(player):
    bat = (
        player
        .get("batSide", {})
        .get("code")
    )
    throw = (
        player
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
# ロスター状態
# =========================================================
def determine_roster_status(
    player_id,
    is_il,
    active_ids,
    forty_ids
):
    # -----------------------------------------------------
    # IL最優先
    # -----------------------------------------------------
    if is_il:
        return "IL"
    # -----------------------------------------------------
    # ACTIVE
    # -----------------------------------------------------
    if player_id in active_ids:
        return "ACTIVE"
    # -----------------------------------------------------
    # 40-MAN
    # -----------------------------------------------------
    if player_id in forty_ids:
        return "40-MAN"
    # -----------------------------------------------------
    # 保存対象外
    # -----------------------------------------------------
    return None
# =========================================================
# メイン
# =========================================================
def main():
    print("========================================")
    print("Phillies Roster Collector")
    print(f"Season: {SEASON}")
    print("========================================")
    # =====================================================
    # API取得
    # =====================================================
    print("\n[1] ACTIVE roster")
    active_roster = get_roster(
        "active"
    )
    print(
        f"ACTIVE API: {len(active_roster)}"
    )
    print("\n[2] 40-MAN roster")
    forty_roster = get_roster(
        "40Man"
    )
    print(
        f"40-MAN API: {len(forty_roster)}"
    )
    print("\n[3] FULL roster")
    full_roster = get_roster(
        "fullRoster"
    )
    print(
        f"FULL API: {len(full_roster)}"
    )
    print("\n[4] Transactions")
    team_transactions = (
        get_transactions()
    )
    print(
        f"Transactions: "
        f"{len(team_transactions)}"
    )
    # =====================================================
    # ID SET
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
        if player_id:
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
        if player_id:
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
        if player_id:
            full_ids.add(
                player_id
            )
            roster_items.setdefault(
                player_id,
                item
            )
    # =====================================================
    # 母集団
    # =====================================================
    all_ids = (
        full_ids
        |
        active_ids
        |
        forty_ids
    )
    print(
        f"\nCandidate players: "
        f"{len(all_ids)}"
    )
    # =====================================================
    # 選手処理
    # =====================================================
    players = []
    for index, player_id in enumerate(
        sorted(all_ids),
        start=1
    ):
        print(
            f"\n[{index}/{len(all_ids)}] "
            f"ID={player_id}"
        )
        try:
            player = get_player(
                player_id
            )
            if not player:
                print(
                    "  Player data unavailable"
                )
                continue
            roster_item = roster_items.get(
                player_id,
                {}
            )
            player_transactions = (
                player.get(
                    "transactions",
                    []
                )
            )
            # -------------------------------------------------
            # IL判定
            # -------------------------------------------------
            (
                is_il,
                il_info,
                il_history
            ) = determine_il_state(
                player_id,
                player_transactions,
                team_transactions
            )
            # -------------------------------------------------
            # 最終状態
            # -------------------------------------------------
            status = determine_roster_status(
                player_id,
                is_il,
                active_ids,
                forty_ids
            )
            # -------------------------------------------------
            # UNKNOWNは完全除外
            # -------------------------------------------------
            if status is None:
                print(
                    "  Excluded: no valid roster status"
                )
                continue
            # -------------------------------------------------
            # 基本情報
            # -------------------------------------------------
            position = get_position(
                roster_item,
                player
            )
            bt = get_bt(
                player
            )
            # -------------------------------------------------
            # 保存
            # -------------------------------------------------
            result = {
                "id":
                    player_id,
                "name":
                    player.get(
                        "fullName"
                    ),
                "firstName":
                    player.get(
                        "firstName"
                    ),
                "lastName":
                    player.get(
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
                    "il":
                        is_il
                },
                "il":
                    il_info,
                "ilTransactionHistory":
                    il_history
            }
            players.append(
                result
            )
            print(
                f"  {result['name']}"
            )
            print(
                f"  STATUS: {status}"
            )
            print(
                f"  POS: "
                f"{position.get('code')}"
            )
            print(
                f"  B/T: "
                f"{bt.get('display')}"
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
            # 一人の失敗で全体を止めない
            continue
    # =====================================================
    # 件数
    # =====================================================
    counts = {
        "players":
            len(players),
        "active":
            sum(
                1
                for p in players
                if p["rosterStatus"]
                == "ACTIVE"
            ),
        "il":
            sum(
                1
                for p in players
                if p["rosterStatus"]
                == "IL"
            ),
        "fortyMan":
            sum(
                1
                for p in players
                if p["rosterStatus"]
                == "40-MAN"
            )
    }
    # =====================================================
    # 出力
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
    # 保存
    # =====================================================
    os.makedirs(
        "data",
        exist_ok=True
    )
    # 一時ファイルへ書く
    with open(
        TEMP_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )
    # 正常なJSONが作れた場合のみ本番ファイルを置換
    os.replace(
        TEMP_FILE,
        OUTPUT_FILE
    )
    # =====================================================
    # 結果
    # =====================================================
    print("\n========================================")
    print("COMPLETED")
    print("========================================")
    print(
        f"ACTIVE : {counts['active']}"
    )
    print(
        f"IL     : {counts['il']}"
    )
    print(
        f"40-MAN : {counts['fortyMan']}"
    )
    print(
        f"TOTAL  : {counts['players']}"
    )
    print(
        f"FILE   : {OUTPUT_FILE}"
    )
    print("========================================")
if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            "\nFATAL ERROR:"
        )
        print(error)
        # 既存players.jsonは触らない
        if os.path.exists(TEMP_FILE):
            os.remove(
                TEMP_FILE
            )
        sys.exit(1)
