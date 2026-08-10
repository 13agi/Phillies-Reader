import json
import os
import requests
from datetime import datetime, timezone


TEAM_ID = 143  # Philadelphia Phillies

API_BASE = "https://statsapi.mlb.com/api/v1"

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "player_stats.json")


def get_roster():
    url = f"{API_BASE}/teams/{TEAM_ID}/roster"
    params = {
        "rosterType": "40Man",
        "hydrate": "person"
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json().get("roster", [])


def get_stats(player_id, group):
    url = f"{API_BASE}/people/{player_id}/stats"

    params = {
        "stats": "season",
        "group": group,
        "season": "2026"
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    stats = data.get("stats", [])

    if not stats:
        return {}

    splits = stats[0].get("splits", [])

    if not splits:
        return {}

    return splits[0].get("stat", {})


def safe_number(value):
    if value is None:
        return None

    return value


def main():

    os.makedirs(DATA_DIR, exist_ok=True)

    roster = get_roster()

    players = {}

    for entry in roster:

        person = entry.get("person", {})

        player_id = person.get("id")

        if not player_id:
            continue

        name = person.get("fullName", "Unknown")

        position = (
            entry.get("position", {})
            .get("abbreviation", "")
        )

        print(
            f"Getting stats: {name} "
            f"(ID: {player_id})"
        )

        batting = {}
        pitching = {}

        try:
            batting = get_stats(
                player_id,
                "hitting"
            )
        except Exception as e:
            print(
                f"Batting error for {name}: {e}"
            )

        try:
            pitching = get_stats(
                player_id,
                "pitching"
            )
        except Exception as e:
            print(
                f"Pitching error for {name}: {e}"
            )

        players[str(player_id)] = {

            "playerId": player_id,

            "name": name,

            "position": position,

            "season": 2026,

            "batting": {

                "games": safe_number(
                    batting.get("gamesPlayed")
                ),

                "plateAppearances": safe_number(
                    batting.get("plateAppearances")
                ),

                "atBats": safe_number(
                    batting.get("atBats")
                ),

                "hits": safe_number(
                    batting.get("hits")
                ),

                "runs": safe_number(
                    batting.get("runs")
                ),

                "homeRuns": safe_number(
                    batting.get("homeRuns")
                ),

                "rbi": safe_number(
                    batting.get("rbi")
                ),

                "walks": safe_number(
                    batting.get("baseOnBalls")
                ),

                "strikeouts": safe_number(
                    batting.get("strikeOuts")
                ),

                "stolenBases": safe_number(
                    batting.get("stolenBases")
                ),

                "avg": safe_number(
                    batting.get("avg")
                ),

                "obp": safe_number(
                    batting.get("obp")
                ),

                "slg": safe_number(
                    batting.get("slg")
                ),

                "ops": safe_number(
                    batting.get("ops")
                )

            },

            "pitching": {

                "games": safe_number(
                    pitching.get("gamesPlayed")
                ),

                "gamesStarted": safe_number(
                    pitching.get("gamesStarted")
                ),

                "inningsPitched": safe_number(
                    pitching.get("inningsPitched")
                ),

                "wins": safe_number(
                    pitching.get("wins")
                ),

                "losses": safe_number(
                    pitching.get("losses")
                ),

                "saves": safe_number(
                    pitching.get("saves")
                ),

                "era": safe_number(
                    pitching.get("era")
                ),

                "whip": safe_number(
                    pitching.get("whip")
                ),

                "hits": safe_number(
                    pitching.get("hits")
                ),

                "earnedRuns": safe_number(
                    pitching.get("earnedRuns")
                ),

                "homeRuns": safe_number(
                    pitching.get("homeRuns")
                ),

                "walks": safe_number(
                    pitching.get("baseOnBalls")
                ),

                "strikeouts": safe_number(
                    pitching.get("strikeOuts")
                ),

                "k9": safe_number(
                    pitching.get("strikeoutsPer9")
                ),

                "bb9": safe_number(
                    pitching.get("walksPer9")
                )

            }

        }


    output = {

        "team": "Philadelphia Phillies",

        "teamId": TEAM_ID,

        "season": 2026,

        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "players": players

    }


    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )


    print(
        f"Saved {len(players)} players "
        f"to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
