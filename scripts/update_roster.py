import json
import os
import requests
from datetime import datetime, timezone, timedelta


# =========================================================
# Philadelphia Phillies
# =========================================================

TEAM_ID = 143
SEASON = 2026

BASE_URL = "https://statsapi.mlb.com/api/v1"

OUTPUT_FILE = "data/roster.json"

JST = timezone(timedelta(hours=9))


# =========================================================
# API REQUEST
# =========================================================

def get_json(url, params=None):

    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={
            "User-Agent":
                "Phillies-Reader/1.0"
        }
    )

    response.raise_for_status()

    return response.json()


# =========================================================
# 40-MAN
# =========================================================

def get_40_man():

    url = (
        f"{BASE_URL}/teams/"
        f"{TEAM_ID}/roster"
    )

    params = {
        "rosterType": "40Man",
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
# ACTIVE ROSTER
#
# MLBのActive rosterを取得。
# レギュラーシーズン中は基本的に26-man。
# =========================================================

def get_active_roster():

    url = (
        f"{BASE_URL}/teams/"
        f"{TEAM_ID}/roster"
    )

    params = {
        "rosterType": "active",
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
# FULL ROSTER
#
# ILを含むチームの完全なロスター情報を取得する。
# =========================================================

def get_full_roster():

    url = (
        f"{BASE_URL}/teams/"
        f"{TEAM_ID}/roster"
    )

    params = {
        "rosterType": "fullRoster",
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
# ID SET
# =========================================================

def make_id_set(roster):

    ids = set()

    for player in roster:

        person = player.get(
            "person",
            {}
        )

        player_id = person.get(
            "id"
        )

        if player_id:

            ids.add(
                player_id
            )

    return ids


# =========================================================
# PLAYER DETAILS
# =========================================================

def get_player_details(
    player_id
):

    url = (
        f"{BASE_URL}/people/"
        f"{player_id}"
    )

    data = get_json(
        url
    )

    people = data.get(
        "people",
        []
    )

    if not people:

        return {}

    return people[0]


# =========================================================
# STATUS
#
# 26MAN
# IL
# 40MAN
# =========================================================

def determine_roster_status(
    player_id,
    active_ids,
    full_roster_ids
):

    # Active roster
    if player_id in active_ids:

        return "26MAN"


    # Full rosterに存在するが
    # Active rosterにはいない場合
    #
    # IL判定はここだけでは確定できない。
    # roster entryのstatus / designationを確認する。
    return "40MAN"


# =========================================================
# IL判定
#
# MLB APIのroster entryに含まれる
# status / designation / rosterStatus等を確認。
# =========================================================

def is_injured_list(
    entry
):

    status = entry.get(
        "status",
        {}
    )

    if isinstance(
        status,
        dict
    ):

        code = str(
            status.get(
                "code",
                ""
            )
        ).lower()

        description = str(
            status.get(
                "description",
                ""
            )
        ).lower()

        if (
            "injured" in description
            or
            "disabled" in description
            or
            code in {
                "il",
                "10day",
                "15day",
                "60day",
                "7day"
            }
        ):

            return True


    designation = str(
        entry.get(
            "designation",
            ""
        )
    ).lower()


    if (
        "injured" in designation
        or
        "disabled" in designation
        or
        "il" == designation
    ):

        return True


    roster_status = str(
        entry.get(
            "rosterStatus",
            ""
        )
    ).lower()


    if (
        "injured" in roster_status
        or
        "il" == roster_status
    ):

        return True


    return False


# =========================================================
# PLAYER DATA
# =========================================================

def build_player(
    entry,
    active_ids,
    full_roster_ids
):

    person = entry.get(
        "person",
        {}
    )

    player_id = person.get(
        "id"
    )

    if not player_id:

        return None


    details = get_player_details(
        player_id
    )


    position = entry.get(
        "position",
        {}
    )


    bat_side = details.get(
        "batSide",
        {}
    ).get(
        "code",
        ""
    )


    pitch_hand = details.get(
        "pitchHand",
        {}
    ).get(
        "code",
        ""
    )


    # -----------------------------------------------------
    # IL
    # -----------------------------------------------------

    il = is_injured_list(
        entry
    )


    # -----------------------------------------------------
    # ROSTER STATUS
    # -----------------------------------------------------

    if il:

        roster_status = "IL"

    elif player_id in active_ids:

        roster_status = "26MAN"

    else:

        roster_status = "40MAN"


    # -----------------------------------------------------
    # DATA
    # -----------------------------------------------------

    return {

        "id":
            player_id,

        "name":
            details.get(
                "fullName",
                person.get(
                    "fullName",
                    ""
                )
            ),

        "number":
            entry.get(
                "jerseyNumber",
                ""
            ),

        "bt":
            (
                f"{bat_side}/{pitch_hand}"
                if bat_side or pitch_hand
                else ""
            ),

        "position":
            position.get(
                "abbreviation",
                ""
            ),

        "positionName":
            position.get(
                "name",
                ""
            ),

        "rosterStatus":
            roster_status,

        "fortyMan":
            True,

        "activeRoster":
            roster_status == "26MAN",

        "il":
            roster_status == "IL"
    }


# =========================================================
# MAIN
# =========================================================

def main():

    print("")
    print(
        "========================================"
    )
    print(
        "PHILLIES ROSTER UPDATE"
    )
    print(
        "========================================"
    )


    # -----------------------------------------------------
    # 最新40-man
    # -----------------------------------------------------

    roster_40 = get_40_man()

    print(
        "40-man:",
        len(roster_40)
    )


    if not roster_40:

        raise RuntimeError(
            "40-man roster is empty."
        )


    # -----------------------------------------------------
    # 最新Active
    # -----------------------------------------------------

    active_roster = (
        get_active_roster()
    )

    active_ids = make_id_set(
        active_roster
    )

    print(
        "Active:",
        len(active_ids)
    )


    # -----------------------------------------------------
    # Full roster
    # -----------------------------------------------------

    full_roster = (
        get_full_roster()
    )

    full_roster_ids = (
        make_id_set(
            full_roster
        )
    )

    print(
        "Full roster:",
        len(full_roster_ids)
    )


    # -----------------------------------------------------
    # 40-manを母集団として再生成
    # -----------------------------------------------------

    players = []


    for entry in roster_40:

        player = build_player(
            entry,
            active_ids,
            full_roster_ids
        )

        if player:

            players.append(
                player
            )


    # -----------------------------------------------------
    # 背番号順の基本ソート
    # -----------------------------------------------------

    def number_key(player):

        try:

            return int(
                player["number"]
            )

        except:

            return 999


    players.sort(
        key=number_key
    )


    # -----------------------------------------------------
    # STATUS COUNT
    # -----------------------------------------------------

    count_26 = sum(
        1
        for p in players
        if p["rosterStatus"] == "26MAN"
    )


    count_il = sum(
        1
        for p in players
        if p["rosterStatus"] == "IL"
    )


    count_40 = sum(
        1
        for p in players
        if p["rosterStatus"] == "40MAN"
    )


    # -----------------------------------------------------
    # OUTPUT
    # -----------------------------------------------------

    output = {

        "team": {

            "id":
                TEAM_ID,

            "name":
                "Philadelphia Phillies"
        },

        "season":
            SEASON,

        "updated":
            datetime.now(
                JST
            ).isoformat(),

        "count":
            len(players),

        "statusCount": {

            "26MAN":
                count_26,

            "IL":
                count_il,

            "40MAN":
                count_40
        },

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


    print("")
    print(
        "26-man:",
        count_26
    )

    print(
        "IL:",
        count_il
    )

    print(
        "40-man only:",
        count_40
    )

    print(
        "TOTAL:",
        len(players)
    )

    print("")
    print(
        "roster.json updated."
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()
