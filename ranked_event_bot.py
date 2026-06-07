import pickle
import time

import discord

# Needed so pickle can load ranked.Player, ranked.Match, ranked.Result objects.
import ranked

import cf_event


class EventDataCache:
    def __init__(self):
        self.players = {}
        self.current_matches = {}
        self.flagged_matches = {}
        self.historic_matches = {}

        self.last_loaded = 0
        self.last_error = None

    def is_fresh(self):
        return time.time() - self.last_loaded < cf_event.CACHE_SECONDS

    def ensure_loaded(self, force=False):
        if not force and self.is_fresh():
            return True

        try:
            data = load_pickle_with_retries()
        except Exception as e:
            self.last_error = repr(e)
            return False

        self.players = data[0]
        self.current_matches = data[1]
        self.flagged_matches = data[2]
        self.historic_matches = data[3]

        self.last_loaded = time.time()
        self.last_error = None

        return True


def load_pickle_with_retries(max_attempts=20, delay=0.1):
    last_error = None

    for attempt in range(max_attempts):
        try:
            with open(cf_event.DATA_PICKLE, "rb") as f:
                return pickle.load(f)

        except (
            PermissionError,
            EOFError,
            pickle.UnpicklingError,
            OSError,
        ) as e:
            last_error = e
            time.sleep(delay)

    raise RuntimeError("Could not read pickle after retries: " + repr(last_error))


def escape_name(name):
    return str(name).replace("_", "\\_")


def player_name(player_id, players):
    if player_id in players:
        return escape_name(players[player_id].ign)

    return "<@" + str(player_id) + ">"


def event_period_index(start_time):
    if start_time < cf_event.EVENT_START:
        return None

    if start_time >= cf_event.EVENT_END:
        return None

    period = int((start_time - cf_event.EVENT_START) // cf_event.EVENT_PERIOD_SECONDS)

    if period < 0 or period >= cf_event.EVENT_PERIOD_COUNT:
        return None

    return period


def blank_player_event_stats():
    return {
        "period_points": [0 for _ in range(cf_event.EVENT_PERIOD_COUNT)],

        "best_points": 0,
        "total_points": 0,

        "matches_played": 0,
        "games_played": 0,

        "solo_wins": 0,
        "tied_wins": 0,
        "match_ties": 0,
        "tied_losses": 0,
        "solo_losses": 0,
        "voids": 0,

        "last_match_time": None,
    }


def add_player_if_needed(stats, player_id):
    if player_id not in stats:
        stats[player_id] = blank_player_event_stats()


def add_points(stats, player_id, period, points):
    add_player_if_needed(stats, player_id)
    stats[player_id]["period_points"][period] += points


def game_count_for_result(result):
    # Matches use:
    # - decisive result: result.ties + 1 games
    # - match tie: result.ties games
    # - voided result: result.ties games
    #
    if result.voided:
        return result.ties

    if len(result.winners) == 0:
        return result.ties

    return result.ties + 1


def calculate_event_stats(players, historic_matches):
    stats = {}

    matches = list(historic_matches.values())
    matches.sort(key=lambda match: match.num)

    for match in matches:
        period = event_period_index(match.start_time)

        if period is None:
            continue

        result = match.result

        if result is None:
            continue

        for player_id in match.players:
            add_player_if_needed(stats, player_id)

        games_played = game_count_for_result(result)

        for player_id in match.players:
            stats[player_id]["games_played"] += games_played
            stats[player_id]["last_match_time"] = match.end_time or match.start_time

        if result.voided:
            for player_id in match.players:
                stats[player_id]["voids"] += 1

                # Voided matches get no result points.
                # They only get game bonus for recorded tied/restarted games.
                if games_played > 0:
                    add_points(
                        stats,
                        player_id,
                        period,
                        games_played * cf_event.EVENT_GAME_BONUS
                    )

            continue

        # Non-voided completed match.
        for player_id in match.players:
            stats[player_id]["matches_played"] += 1

            add_points(
                stats,
                player_id,
                period,
                games_played * cf_event.EVENT_GAME_BONUS
            )

        # Match tie: no winners.
        if len(result.winners) == 0:
            for player_id in match.players:
                stats[player_id]["match_ties"] += 1

                add_points(
                    stats,
                    player_id,
                    period,
                    cf_event.EVENT_POINTS["match_tie"]
                )

            continue

        # Solo win: 1 winner, 2 tied losses.
        if len(result.winners) == 1:
            for player_id in match.players:
                if player_id in result.winners:
                    stats[player_id]["solo_wins"] += 1

                    add_points(
                        stats,
                        player_id,
                        period,
                        cf_event.EVENT_POINTS["solo_win"]
                    )

                else:
                    stats[player_id]["tied_losses"] += 1

                    add_points(
                        stats,
                        player_id,
                        period,
                        cf_event.EVENT_POINTS["tied_loss"]
                    )

            continue

        # Tied win: 2 winners, 1 solo loss.
        if len(result.winners) == 2:
            for player_id in match.players:
                if player_id in result.winners:
                    stats[player_id]["tied_wins"] += 1

                    add_points(
                        stats,
                        player_id,
                        period,
                        cf_event.EVENT_POINTS["tied_win"]
                    )

                else:
                    stats[player_id]["solo_losses"] += 1

                    add_points(
                        stats,
                        player_id,
                        period,
                        cf_event.EVENT_POINTS["solo_loss"]
                    )

            continue

    for player_id in stats:
        period_points = stats[player_id]["period_points"]
        best_periods = sorted(period_points, reverse=True)[:cf_event.EVENT_BEST_PERIODS]

        stats[player_id]["total_points"] = sum(period_points)
        stats[player_id]["best_points"] = sum(best_periods)

    return stats


def rank_event_players(stats):
    leaderboard = list(stats.items())

    # Official tied scores are broken randomly.
    # For live display, this uses stable tie ordering so the leaderboard
    # doesn't shuffle every command.
    leaderboard.sort(
        key=lambda item: (
            item[1]["best_points"],
            item[1]["total_points"],
            item[1]["games_played"],
        ),
        reverse=True
    )

    return leaderboard


def rank_game_players(stats):
    leaderboard = list(stats.items())

    leaderboard.sort(
        key=lambda item: (
            item[1]["games_played"],
            item[1]["matches_played"],
            item[1]["best_points"],
        ),
        reverse=True
    )

    return leaderboard


def format_periods(period_points):
    return " / ".join(str(x) for x in period_points)


def event_info_message(player_id, players, stats):
    msg = (
        "## " + cf_event.EVENT_NAME + "\n"
        "Event time: <t:" + str(cf_event.EVENT_START) + ":F> to <t:" + str(cf_event.EVENT_END) + ":t>\n"
        "Queue in Ranked with `pp!join` during the event.\n\n"
        "**Scoring:**\n"
        "- Solo loss: 5 points\n"
        "- Tied loss: 10 points\n"
        "- Match tie: 15 points\n"
        "- Tied win: 20 points\n"
        "- Solo win: 25 points\n"
        "- Bonus: 1 point per game played\n\n"
        "Your event score is your **best 3** of the 4 hourly periods."
    )

    if player_id not in stats:
        msg += "\n\nYou have no event points yet."
        return msg

    s = stats[player_id]

    msg += (
        "\n\n## <@"+str(player_id)"> Event Stats"
        "\nScore: **" + str(s["best_points"]) + "**"
        "\nAll periods: `" + format_periods(s["period_points"]) + "`"
        "\nGames played: **" + str(s["games_played"]) + "**"
        "\nMatches completed: **" + str(s["matches_played"]) + "**"
        "\n\nSolo Wins: " + str(s["solo_wins"])
        + "\nTied Wins: " + str(s["tied_wins"])
        + "\nMatch Ties: " + str(s["match_ties"])
        + "\nTied Losses: " + str(s["tied_losses"])
        + "\nSolo Losses: " + str(s["solo_losses"])
        + "\nVoided Matches: " + str(s["voids"])
    )

    return msg


def leaderboard_message(players, stats):
    leaderboard = rank_event_players(stats)

    if len(leaderboard) == 0:
        return "No event matches have been completed yet."

    msg = "## Event Leaderboard"

    previous_score = None
    previous_rank = 0

    for index, item in enumerate(leaderboard, start=1):
        player_id, s = item

        if s["best_points"] == previous_score:
            rank = previous_rank
        else:
            rank = index
            previous_rank = rank
            previous_score = s["best_points"]

        msg += (
            "\n#"
            + str(rank)
            + ": "
            + player_name(player_id, players)
            + " - **"
            + str(s["best_points"])
            + "** points"
            + " `("
            + format_periods(s["period_points"])
            + ")`"
        )

    msg += "\n\n-# Score is best 3 hourly periods."

    return msg


def games_leaderboard_message(players, stats):
    leaderboard = rank_game_players(stats)

    if len(leaderboard) == 0:
        return "No event games have been played yet."

    msg = "## Event Games Leaderboard"

    previous_games = None
    previous_rank = 0

    for index, item in enumerate(leaderboard, start=1):
        player_id, s = item

        if s["games_played"] == previous_games:
            rank = previous_rank
        else:
            rank = index
            previous_rank = rank
            previous_games = s["games_played"]

        msg += (
            "\n#"
            + str(rank)
            + ": "
            + player_name(player_id, players)
            + " - **"
            + str(s["games_played"])
            + "** games"
            + " ("
            + str(s["matches_played"])
            + " matches)"
        )

    return msg


class EventClient(discord.Client):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache = EventDataCache()

    async def on_ready(self):
        print("Ranked event bot active as", self.user)

        loaded = self.cache.ensure_loaded(force=True)

        if loaded:
            print("Loaded event data")
        else:
            print("Failed to load event data:", self.cache.last_error)

    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.strip()

        if message.channel.id==cf_event.QUEUECHANNEL:
            return

        if not content.startswith(cf_event.PREFIX):
            return

        command = content[len(cf_event.PREFIX):].strip().lower()

        valid_commands = [
            "event",
            "eventlb",
            "eventgames",
            "eventreload",
        ]

        if command not in valid_commands:
            return

        force_reload = command == "eventreload"

        loaded = self.cache.ensure_loaded(force=force_reload)

        if not loaded:
            await message.channel.send(
                "Could not load event data right now. Please try again in a few seconds.\n"
                "`" + str(self.cache.last_error) + "`"
            )
            return

        stats = calculate_event_stats(
            self.cache.players,
            self.cache.historic_matches
        )

        if command == "event":
            await message.channel.send(
                event_info_message(
                    message.author.id,
                    self.cache.players,
                    stats
                )
            )
            return

        if command == "eventlb":
            await message.channel.send(
                leaderboard_message(
                    self.cache.players,
                    stats
                )
            )
            return

        if command == "eventgames":
            await message.channel.send(
                games_leaderboard_message(
                    self.cache.players,
                    stats
                )
            )
            return

        if command == "eventreload":
            await message.channel.send("Reloaded event data.")
            return


print("Loading event bot")

intents = discord.Intents.default()
intents.message_content = True

client = EventClient(intents=intents)
client.run(cf_event.token)