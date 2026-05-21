import cf
import math
import time
import random

## Player format
# discord_id: {'ign': 'ign', 'rank': 0, 'wins': 0, 'ties': 0, 'losses': 0, 'queuetime': 0, 'mu': 25, 'sigma': 8.333333333333334}

## Match format
# old:
# match_channel_id: {'p1': piq_id, 'p2': message.author.id, 'confirming': False, 'confirmer': 0, 'result': "", 'starttime': time.time(), 'endtime': 0}
# new:
# match_channel_id: {'num': match_num, 'pA': pA_id, 'pB': pB_id, 'pC': pC_id, 'pD': pD_id,
#                   'confAB': False, 'confCD': False, 'result': "", 'starttime': time, 'endtime': time}

# 1v1v1:
# match_channel_id: {'num': match_num, 'pA': pA_id, 'pB': pB_id, 'pC': pC_id, 'confA': False, 'confB': False, 'confC': False, 'result': "", starttime: time,
#                   endtime: time)

# Results:
# (voided, num_ties, a_won, b_won, c_won)

# Player class to hold player data
class Player:
    def __init__(self, discord_id, ign, rank=0, wins=0, ties=0, losses=0, queuetime=0, mu=25, sigma=8.333333333333334):
        self.discord_id = discord_id
        self.ign = ign
        self.rank = rank
        self.wins = wins
        self.ties = ties
        self.losses = losses
        self.queuetime = queuetime
        self.mu = mu
        self.sigma = sigma


# 
class Match:
    def __init__(self, channel_id, a_id, b_id, c_id, a_confirmed, b_confirmed, c_confirmed, result, start_time, end_time):
        self.channel_id = channel_id
        self.a_id = a_id
        self.b_id = b_id
        self.c_id = c_id
        self.a_confirmed = a_confirmed
        self.b_confirmed = b_confirmed
        self.c_confirmed = c_confirmed
        self.result = result
        self.start_time = start_time
        self.end_time = end_time
        
class Result:
    def __init__(self, voided, num_ties, a_won, b_won, c_won):
        self.voided = voided
        self.num_ties = num_ties
        self.a_won = a_won
        self.b_won = b_won
        self.c_won = c_won
