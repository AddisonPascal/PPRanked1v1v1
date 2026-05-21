import trueskill

from ranked import Match, Player

# constants
BRONZE_MATCHES = 3
SILVER_WINS_IN_BRONZE = 5
GOLD_UNBEATEN_IN_SILVER = 5

PLATINUM_RATING = 22
MASTER_RATING = 24
GRANDMASTER_RATING = 26


def player_rating(player: Player):
    return trueskill.Rating(mu=player.mu, sigma=player.sigma)


def apply_match_rating(match: Match, players: dict[int, Player]):
    result = match.result

    if result is None:
        raise RuntimeError("Cannot rate match with no result")

    # Voided matches and full match ties should not affect rating.
    if result.voided or len(result.winners) == 0:
        return

    rating_groups = []
    ranks = []

    for pid in match.players:
        rating_groups.append([player_rating(players[pid])])

        if pid in result.winners:
            ranks.append(0)
        else:
            ranks.append(1)

    new_rating_groups = trueskill.rate(rating_groups, ranks=ranks)

    for pid, rating_group in zip(match.players, new_rating_groups):
        new_rating = rating_group[0]
        players[pid].mu = new_rating.mu
        players[pid].sigma = new_rating.sigma

def display_rating(player: Player):
    # Conservative TrueSkill estimate
    return player.mu - 3 * player.sigma
   

def completed_matches(player: Player):
    return player.wins + player.ties + player.losses


def wins_since_rank_start(player_id: int, players, historic_matches):
    player = players[player_id]
    wins = 0

    for match in historic_matches.values():
        if match.num <= player.rank_since_match:
            continue

        if player_id not in match.players:
            continue

        result = match.result

        if result is None:
            continue

        if result.voided:
            continue

        if player_id in result.winners:
            wins += 1

    return wins


def current_unbeaten_streak_since_rank_start(player_id: int, players, historic_matches):
    player = players[player_id]

    matches = []

    for match in historic_matches.values():
        if match.num <= player.rank_since_match:
            continue

        if player_id not in match.players:
            continue

        result = match.result

        if result is None:
            continue

        if result.voided:
            continue

        matches.append(match)

    matches.sort(key=lambda match: match.num, reverse=True)

    streak = 0

    for match in matches:
        result = match.result

        # Full match tie counts as unbeaten.
        if len(result.winners) == 0:
            streak += 1

        # Win counts as unbeaten.
        elif player_id in result.winners:
            streak += 1

        # Loss breaks the streak.
        else:
            break

    return streak


def rank_for_player(player_id: int, players, historic_matches):
    player = players[player_id]

    # Starter -> Bronze: 3 completed matches.
    if player.rank == 0:
        if completed_matches(player) >= BRONZE_MATCHES:
            return 1
        return 0

    # Bronze -> Silver: 5 wins while Bronze.
    if player.rank == 1:
        if wins_since_rank_start(player_id, players, historic_matches) >= SILVER_WINS_IN_BRONZE:
            return 2
        return 1

    # Silver -> Gold: 5 matches unbeaten while Silver.
    if player.rank == 2:
        if current_unbeaten_streak_since_rank_start(player_id, players, historic_matches) >= GOLD_UNBEATEN_IN_SILVER:
            return 3
        return 2

    # Gold and above: TrueSkill-based.
    score = display_rating(player)

    if score >= GRANDMASTER_RATING
        return 6

    if score >= MASTER_RATING:
        return 5

    if score >= PLATINUM_RATING:
        return 4

    return 3