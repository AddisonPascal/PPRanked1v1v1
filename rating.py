import trueskill

from ranked import Match, Player


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