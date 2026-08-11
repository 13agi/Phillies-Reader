import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://statsapi.mlb.com/api/v1"
PHILLIES_ID = 143

OUTPUT_FILE = "data/score.json"


def get_json(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Phillies-Reader/1.0"
        }
    )

    with urlopen(request, timeout=20) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def today():
    return datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")


def get_schedule(date):
    params = urlencode({
        "sportId": 1,
        "date": date,
        "teamId": PHILLIES_ID,
        "hydrate": "team,venue"
    })

    url = f"{API_BASE}/schedule?{params}"

    data = get_json(url)

    for date_block in data.get("dates", []):
        games = date_block.get("games", [])

        if games:
            return games[0]

    return None


def get_game_feed(game_pk):
    url = (
        f"{API_BASE}/game/"
        f"{game_pk}/feed/live"
    )

    return get_json(url)


def team_abbreviation(team):
    return (
        team.get("abbreviation")
        or team.get("teamName")
        or ""
    )


def build_game(game, feed):
    away = game["teams"]["away"]
    home = game["teams"]["home"]

    status = game.get("status", {})

    return {
        "gamePk": game["gamePk"],
        "date": game.get("officialDate"),

        "status": {
            "abstract": status.get(
                "abstractGameState"
            ),
            "detailed": status.get(
                "detailedState"
            ),
            "coded": status.get(
                "codedGameState"
            )
        },

        "venue": {
            "name":
                game.get("venue", {}).get("name", ""),
            "city":
                game.get("venue", {})
                    .get("location", {})
                    .get("city", "")
        },

        "away": {
            "id":
                away.get("team", {}).get("id"),
            "name":
                away.get("team", {}).get("name", ""),
            "abbr":
                team_abbreviation(
                    away.get("team", {})
                ),
            "score":
                away.get("score", 0)
        },

        "home": {
            "id":
                home.get("team", {}).get("id"),
            "name":
                home.get("team", {}).get("name", ""),
            "abbr":
                team_abbreviation(
                    home.get("team", {})
                ),
            "score":
                home.get("score", 0)
        }
    }


def build_linescore(feed):
    linescore = (
        feed.get("liveData", {})
            .get("linescore", {})
    )

    innings = []

    for inning in linescore.get(
        "innings", []
    ):
        innings.append({
            "num":
                inning.get("num"),

            "away":
                inning.get("away", {})
                    .get("runs"),

            "home":
                inning.get("home", {})
                    .get("runs")
        })

    teams = linescore.get(
        "teams", {}
    )

    return {
        "innings": innings,

        "away": {
            "runs":
                teams.get("away", {})
                    .get("runs", 0),
            "hits":
                teams.get("away", {})
                    .get("hits", 0),
            "errors":
                teams.get("away", {})
                    .get("errors", 0)
        },

        "home": {
            "runs":
                teams.get("home", {})
                    .get("runs", 0),
            "hits":
                teams.get("home", {})
                    .get("hits", 0),
            "errors":
                teams.get("home", {})
                    .get("errors", 0)
        }
    }


def build_batting(feed):
    boxscore = (
        feed.get("liveData", {})
            .get("boxscore", {})
            .get("teams", {})
    )

    phillies = None

    for side in ["away", "home"]:
        team = boxscore.get(side, {})

        if (
            team.get("team", {})
                .get("id")
            == PHILLIES_ID
        ):
            phillies = team
            break

    if not phillies:
        return []

    players = phillies.get(
        "players", {}
    )

    batting_order = phillies.get(
        "battingOrder", []
    )

    result = []

    for player_id in batting_order:
        player = players.get(
            f"ID{player_id}"
        )

        if not player:
            continue

        stats = player.get(
            "stats", {}
        ).get("batting")

        if not stats:
            continue

        result.append({
            "order":
                len(result) + 1,

            "name":
                player.get("person", {})
                    .get("fullName", ""),

            "PA":
                stats.get(
                    "plateAppearances", 0
                ),

            "H":
                stats.get("hits", 0),

            "HR":
                stats.get("homeRuns", 0),

            "RBI":
                stats.get("rbi", 0),

            "BB":
                stats.get("baseOnBalls", 0),

            "R":
                stats.get("runs", 0),

            "AB":
                stats.get("atBats", 0),

            "SO":
                stats.get("strikeOuts", 0)
        })

    return result


def build_pitching(feed):
    boxscore = (
        feed.get("liveData", {})
            .get("boxscore", {})
            .get("teams", {})
    )

    phillies = None

    for side in ["away", "home"]:
        team = boxscore.get(side, {})

        if (
            team.get("team", {})
                .get("id")
            == PHILLIES_ID
        ):
            phillies = team
            break

    if not phillies:
        return []

    players = phillies.get(
        "players", {}
    )

    result = []

    for player in players.values():

        stats = player.get(
            "stats", {}
        ).get("pitching")

        if not stats:
            continue

        result.append({
            "name":
                player.get("person", {})
                    .get("fullName", ""),

            "IP":
                stats.get(
                    "inningsPitched",
                    "0.0"
                ),

            "H":
                stats.get("hits", 0),

            "K":
                stats.get("strikeOuts", 0),

            "HR":
                stats.get("homeRuns", 0),

            "R":
                stats.get("runs", 0),

            "ER":
                stats.get("earnedRuns", 0),

            "BB":
                stats.get("baseOnBalls", 0)
        })

    return result


def get_current_play(feed):

    plays = (
        feed.get("liveData", {})
            .get("plays", {})
    )

    current = plays.get(
        "currentPlay"
    )

    if not current:
        return None

    about = current.get(
        "about", {}
    )

    matchup = current.get(
        "matchup", {}
    )

    count = current.get(
        "count", {}
    )

    half = about.get(
        "halfInning"
    )

    current_type = (
        "AT_BAT"
        if half == "bottom"
        else "PITCHING"
    )

    latest_pitch = None

    for event in reversed(
        current.get("playEvents", [])
    ):

        if (
            event.get("isPitch")
            and event.get("pitchData")
        ):

            pitch_data = event.get(
                "pitchData", {}
            )

            details = event.get(
                "details", {}
            )

            pitch_type = details.get(
                "type", {}
            )

            speed = (
                pitch_data
                    .get("startSpeed")
            )

            latest_pitch = {
                "speed":
                    round(speed)
                    if speed
                    else None,

                "type":
                    pitch_type.get(
                        "description"
                    )
            }

            break

    runners = []

    for runner in current.get(
        "runners", []
    ):

        movement = runner.get(
            "movement", {}
        )

        details = runner.get(
            "details", {}
        )

        runners.append({
            "base":
                movement.get(
                    "start"
                ),

            "end":
                movement.get(
                    "end"
                ),

            "isOnBase":
                details.get(
                    "isOnBase",
                    False
                )
        })

    return {
        "type": current_type,

        "inning":
            about.get("inning"),

        "half":
            half,

        "outs":
            count.get("outs", 0),

        "balls":
            count.get("balls", 0),

        "strikes":
            count.get("strikes", 0),

        "batter": {
            "id":
                matchup.get("batter", {})
                    .get("id"),

            "name":
                matchup.get("batter", {})
                    .get("fullName")
        },

        "pitcher": {
            "id":
                matchup.get("pitcher", {})
                    .get("id"),

            "name":
                matchup.get("pitcher", {})
                    .get("fullName")
        },

        "batSide":
            matchup.get(
                "batSide", {}
            ).get("code"),

        "pitch":
            latest_pitch,

        "runners":
            runners
    }


def main():

    date = today()

    print(
        f"Fetching Phillies game for {date}"
    )

    game = get_schedule(date)

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    if not game:

        output = {
            "date": date,
            "game": None,
            "updatedAt":
                datetime.now(
                    timezone.utc
                ).isoformat()
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

        print("No Phillies game.")

        return

    game_pk = game["gamePk"]

    print(
        f"Found gamePk: {game_pk}"
    )

    feed = get_game_feed(
        game_pk
    )

    output = {

        "date": date,

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "game":
            build_game(
                game,
                feed
            ),

        "linescore":
            build_linescore(
                feed
            ),

        "batting":
            build_batting(
                feed
            ),

        "pitching":
            build_pitching(
                feed
            ),

        "current":
            get_current_play(
                feed
            )
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
        "score.json updated successfully."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"ERROR: {error}"
        )
        sys.exit(1)
