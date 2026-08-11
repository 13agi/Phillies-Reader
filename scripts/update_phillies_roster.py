from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


TEAM_ID = 143
API_BASE = "https://statsapi.mlb.com/api/v1"
OUTPUT_FILE = Path("data/phillies-roster.json")
TIMEOUT = 30

POSITION_MAP = {
    "P": "P",
    "1": "P",
    "C": "C",
    "2": "C",
    "1B": "1B",
    "3": "1B",
    "2B": "2B",
    "4": "2B",
    "3B": "3B",
    "5": "3B",
    "SS": "SS",
    "6": "SS",
    "LF": "LF",
    "7": "LF",
    "CF": "CF",
    "8": "CF",
    "RF": "RF",
    "9": "RF",
    "DH": "DH",
    "10": "DH",
}


class MLBAPIError(Exception):
    pass


def get_json(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:

    url = f"{API_BASE}{endpoint}"

    try:
        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT,
            headers={
                "Accept": "application/json",
                "User-Agent": "Phillies-Reader/1.0",
            },
        )

        response.raise_for_status()

    except requests.RequestException as exc:
        raise MLBAPIError(
            f"MLB API request failed: {url}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise MLBAPIError(
            f"MLB API returned invalid JSON: {url}"
        ) from exc

    if not isinstance(data, dict):
        raise MLBAPIError(
            f"Unexpected MLB API response: {url}"
        )

    return data


def get_roster(roster_type: str) -> list[dict[str, Any]]:

    data = get_json(
        f"/teams/{TEAM_ID}/roster",
        {
            "rosterType": roster_type,
        },
    )

    roster = data.get("roster")

    if not isinstance(roster, list):
        raise MLBAPIError(
            f"Invalid roster response: {roster_type}"
        )

    return roster


def player_id(entry: dict[str, Any]) -> int | None:

    person = entry.get("person")

    if not isinstance(person, dict):
        return None

    value = person.get("id")

    if isinstance(value, int):
        return value

    return None


def text(value: Any) -> str | None:

    if not isinstance(value, str):
        return None

    value = value.strip()

    return value if value else None


def get_player_name(entry: dict[str, Any]) -> str | None:

    person = entry.get("person")

    if not isinstance(person, dict):
        return None

    return text(person.get("fullName"))


def get_jersey_number(entry: dict[str, Any]) -> str | None:

    return text(entry.get("jerseyNumber"))


def get_position_from_object(
    position: Any,
) -> str | None:

    if not isinstance(position, dict):
        return None

    abbreviation = position.get("abbreviation")

    if isinstance(abbreviation, str):

        abbreviation = abbreviation.strip().upper()

        if abbreviation in POSITION_MAP:
            return POSITION_MAP[abbreviation]

    code = position.get("code")

    if isinstance(code, str):

        code = code.strip().upper()

        if code in POSITION_MAP:
            return POSITION_MAP[code]

    return None


def get_position(
    roster_entry: dict[str, Any],
    person: dict[str, Any] | None,
) -> str | None:

    # Roster position is preferred.
    position = get_position_from_object(
        roster_entry.get("position")
    )

    if position is not None:
        return position

    # Fall back to primaryPosition from person data.
    if person is not None:

        position = get_position_from_object(
            person.get("primaryPosition")
        )

        if position is not None:
            return position

    return None


def get_bat_side(
    person: dict[str, Any] | None,
) -> str | None:

    if person is None:
        return None

    bat_side = person.get("batSide")

    if not isinstance(bat_side, dict):
        return None

    return text(bat_side.get("code"))


def get_pitch_hand(
    person: dict[str, Any] | None,
) -> str | None:

    if person is None:
        return None

    pitch_hand = person.get("pitchHand")

    if not isinstance(pitch_hand, dict):
        return None

    return text(pitch_hand.get("code"))


def get_status(
    entry: dict[str, Any],
) -> dict[str, str | None]:

    status = entry.get("status")

    if not isinstance(status, dict):
        return {
            "code": None,
            "description": None,
        }

    return {
        "code": text(status.get("code")),
        "description": text(status.get("description")),
    }


def determine_il(
    entry: dict[str, Any],
) -> bool | None:

    status = get_status(entry)

    code = status["code"]
    description = status["description"]

    if code is not None:

        code_upper = code.upper()

        if code_upper in {
            "D7",
            "D10",
            "D15",
            "D60",
        }:
            return True

    if description is not None:

        description_lower = description.lower()

        if (
            "injured list" in description_lower
            or "injured-list" in description_lower
        ):
            return True

    return None


def get_people(
    player_ids: list[int],
) -> dict[int, dict[str, Any]]:

    result: dict[int, dict[str, Any]] = {}

    for start in range(0, len(player_ids), 50):

        batch = player_ids[start:start + 50]

        data = get_json(
            "/people",
            {
                "personIds": ",".join(
                    str(player_id)
                    for player_id in batch
                )
            },
        )

        people = data.get("people")

        if not isinstance(people, list):
            raise MLBAPIError(
                "Invalid people response."
            )

        for person in people:

            if not isinstance(person, dict):
                continue

            pid = person.get("id")

            if isinstance(pid, int):
                result[pid] = person

    return result


def determine_status(
    active: bool,
    il: bool | None,
) -> str | None:

    if active:
        return "ACTIVE"

    if il is True:
        return "IL"

    if il is False:
        return "40-MAN / MINORS"

    return None


def build_player(
    entry: dict[str, Any],
    person: dict[str, Any] | None,
    active_ids: set[int],
) -> dict[str, Any]:

    pid = player_id(entry)

    if pid is None:
        raise MLBAPIError(
            "40-man roster entry has no player ID."
        )

    active = pid in active_ids

    il = determine_il(entry)

    return {
        "id": pid,
        "name": get_player_name(entry),
        "number": get_jersey_number(entry),
        "bat": get_bat_side(person),
        "throw": get_pitch_hand(person),
        "position": get_position(entry, person),
        "status": determine_status(
            active=active,
            il=il,
        ),
        "roster40": True,
        "active": active,
        "il": il,
    }


def write_json(data: dict[str, Any]) -> None:

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = OUTPUT_FILE.with_suffix(
        ".json.tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")

    temporary_file.replace(
        OUTPUT_FILE
    )


def main() -> None:

    print(
        "Updating Philadelphia Phillies roster..."
    )

    # Authoritative 40-man set.
    roster_40 = get_roster("40Man")

    # Current active roster.
    active_roster = get_roster("active")

    # Full roster is retrieved as an additional MLB source.
    full_roster = get_roster("fullRoster")

    if not roster_40:
        raise MLBAPIError(
            "40-man roster is empty."
        )

    roster_40_ids = {
        pid
        for entry in roster_40
        if (pid := player_id(entry)) is not None
    }

    active_ids = {
        pid
        for entry in active_roster
        if (pid := player_id(entry)) is not None
    }

    full_by_id = {
        pid: entry
        for entry in full_roster
        if (pid := player_id(entry)) is not None
    }

    people = get_people(
        sorted(roster_40_ids)
    )

    players = []

    for entry in roster_40:

        pid = player_id(entry)

        if pid is None:
            continue

        # Start with 40-man data.
        merged = dict(entry)

        # Add fullRoster fields only when the 40-man
        # response does not already contain them.
        full_entry = full_by_id.get(pid)

        if full_entry is not None:

            for key, value in full_entry.items():

                if key not in merged:
                    merged[key] = value

        person = people.get(pid)

        players.append(
            build_player(
                merged,
                person,
                active_ids,
            )
        )

    def sort_key(player: dict[str, Any]):

        number = player["number"]

        if (
            isinstance(number, str)
            and number.isdigit()
        ):
            return (
                0,
                int(number),
                player["name"] or "",
            )

        return (
            1,
            999,
            player["name"] or "",
        )

    players.sort(
        key=sort_key
    )

    active_count = sum(
        player["active"] is True
        for player in players
    )

    il_count = sum(
        player["il"] is True
        for player in players
    )

    unknown_status_count = sum(
        player["status"] is None
        for player in players
    )

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "team": {
            "id": TEAM_ID,
            "name": "Philadelphia Phillies",
            "abbreviation": "PHI",
        },
        "source": {
            "name": "MLB Stats API",
            "baseUrl": API_BASE,
        },
        "roster": {
            "total40": len(players),
            "active": active_count,
            "il": il_count,
            "unknownStatus": unknown_status_count,
        },
        "players": players,
    }

    write_json(output)

    print(
        f"40-man: {len(players)}"
    )

    print(
        f"ACTIVE: {active_count}"
    )

    print(
        f"IL: {il_count}"
    )

    print(
        f"Unknown status: {unknown_status_count}"
    )

    print(
        f"Written: {OUTPUT_FILE}"
    )


if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        # Critical behavior:
        # roster JSON is not replaced with invalid/empty data.
        sys.exit(1)
