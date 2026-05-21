import cf
import math
import time
import random

from dataclasses import dataclass

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
@dataclass
class Player:
    discord_id: int
    ign: str
    
    rank: int = 0
    
    wins: int = 0
    ties: int = 0
    losses: int = 0
    
    queuetime: float = 0
    
    mu: float = 25
    sigma: float = 8.333333333333334



@dataclass
class Result:
    voided: bool
    ties: int
    winners: set[int]
    

@dataclass
class Match:
    num: int
    channel_id: int
    players: list[int]
    confirmers: set[int]
    result: Result | None
    
    start_time: float
    end_time: float = 0
    
    def has_player(self, player_id):
        return player_id in self.players
        
    def confirm(self, player_id):
        self.confirmers.add(player_id)
        
    def is_confirmed(self):
        return len(self.confirmers)==3
        