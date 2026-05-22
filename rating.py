import trueskill

from ranked import Match, Player

# constants
BRONZE_MATCHES = 3
SILVER_WINS_IN_BRONZE = 5
GOLD_UNBEATEN_IN_SILVER = 5

PLATINUM_RATING = 20
MASTER_RATING = 22
GRANDMASTER_RATING = 24

# TrueSkill parameters
TRUESKILL_MU = 25
TRUESKILL_SIGMA = TRUESKILL_MU / 3

# Higher beta = luckier/noisier game = slower rating movement.
# Default-ish would be TRUESKILL_SIGMA / 2 = 25 / 6.
TRUESKILL_BETA = TRUESKILL_MU / 4

# Leave this alone for now.
TRUESKILL_TAU = TRUESKILL_SIGMA / 100

env = trueskill.TrueSkill(
    mu=TRUESKILL_MU,
    sigma=TRUESKILL_SIGMA,
    beta=TRUESKILL_BETA,
    tau=TRUESKILL_TAU,
    draw_probability=0
)


def player_rating(player: Player):
    return env.Rating(mu=player.mu, sigma=player.sigma)

def apply_match_rating(match: Match, players: dict[int, Player]):
    result = match.result

    if result is None:
        raise RuntimeError("Cannot rate match with no result")

    # Voided matches and full match ties should not affect rating.
    if result.voided or len(result.winners) == 0:
        return

    winners = []
    losers = []

    for pid in match.players:
        if pid in result.winners:
            winners.append(pid)
        else:
            losers.append(pid)

    # Snapshot ratings before the match so pairwise update order does not matter.
    old = {}

    for pid in match.players:
        p = players[pid]
        old[pid] = player_rating(p)

    delta_mu = {}
    delta_sigma = {}

    for pid in match.players:
        delta_mu[pid] = 0
        delta_sigma[pid] = 0

    # Every winner is rated as beating every loser.
    # For a solo win: winner beats 2 players.
    # For a shared win: each winner beats the 1 loser.
    for winner_id in winners:
        for loser_id in losers:
            new_winner_group, new_loser_group = env.rate(
                [[old[winner_id]], [old[loser_id]]],
                ranks=[0, 1]
            )

            new_winner = new_winner_group[0]
            new_loser = new_loser_group[0]

            delta_mu[winner_id] += new_winner.mu - old[winner_id].mu
            delta_sigma[winner_id] += new_winner.sigma - old[winner_id].sigma

            delta_mu[loser_id] += new_loser.mu - old[loser_id].mu
            delta_sigma[loser_id] += new_loser.sigma - old[loser_id].sigma

    # There are 2 winner-vs-loser comparisons in every decisive 1v1v1 match.
    # Weight 0.75 gives average per-player match weight of 1:
    #
    # Solo win:
    # winner gets 2 * 0.75 = 1.5
    # each loser gets 0.75
    #
    # Shared win:
    # each winner gets 0.75
    # lone loser gets 2 * 0.75 = 1.5
    PAIRWISE_WEIGHT = 0.75

    for pid in match.players:
        p = players[pid]

        p.mu = old[pid].mu + delta_mu[pid] * PAIRWISE_WEIGHT
        p.sigma = old[pid].sigma + delta_sigma[pid] * PAIRWISE_WEIGHT

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

    if score >= GRANDMASTER_RATING:
        return 6

    if score >= MASTER_RATING:
        return 5

    if score >= PLATINUM_RATING:
        return 4

    return 3