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
    
    def human(self, match, players):
        out = ""
    
        for i in range(self.ties):
            out += "Game " + str(i + 1) + ": Tie\n"
    
        if self.voided:
            out += "Match voided"
            return out
    
        if len(self.winners) == 0:
            out += "**Winner: Tie**"
            return out
    
        winner_names = []
    
        for pid in match.players:
            if pid in self.winners:
                winner_names.append(players[pid].ign.replace("_", "\\_"))
    
        out += "Game "+str(self.ties+1)+": "
        if len(winner_names) == 1:
            out += winner_names[0] + " wins\n"
            out += "**Winner: " + winner_names[0] + "**"
        else:
            out += winner_names[0] + " and "+winner_names[1]+" win\n"
            out += "**Winners: " + ", ".join(winner_names) + "**"
    
        return out
        
    
    @classmethod
    def parse(cls, string, match, is_admin=False):
        voided = False
        ties = 0
        winners = set()

        for char in string:
            match char.lower():
                case "t":
                    ties += 1
                case "a":
                    winners.add(match.players[0])
                case "b":
                    winners.add(match.players[1])
                case "c":
                    winners.add(match.players[2])
                case "v":
                    if is_admin: voided = True
                case " " | "\n" | "\t":
                    pass
                case _:
                    return None

        if ties > 5: return None

        if voided: return cls(voided=True, ties=ties, winners=winners)

        if ties == 5:
            if len(winners) != 0: return None
            return cls(voided=False, ties=5, winners=set())

        if len(winners) == 0: return None

        if len(winners) == 3: return None

        return cls(voided=False, ties=ties, winners=winners)
        

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
        already_confirmed = player_id in self.confirmers
        self.confirmers.add(player_id)
        return not already_confirmed
        
    def is_confirmed(self):
        return len(self.confirmers)==3
        
    def header(self, players):
        names = []
    
        for pid in self.players:
            names.append(players[pid].ign.replace("_", "\\_"))
    
        return "Match " + str(self.num) + "\n**" + names[0] + " vs " + names[1] + " vs " + names[2] + "**\n"
     
    def human(self, players):
        out = self.header(players)
    
        if self.result is None:
            return out + "No results entered yet"
    
        out += self.result.human(self, players)
    
        if not self.is_confirmed():
            out += "\n\n*Awaiting confirmation: " + str(len(self.confirmers)) + "/3*"
    
        return out
        
        
def apply_match_stats(match: Match, players: dict[int, Player]):
    result = match.result

    if result is None:
        raise RuntimeError("Cannot apply stats for match with no result")

    if result.voided:
        return

    if len(result.winners) == 0:
        for pid in match.players:
            players[pid].ties += 1
        return

    for pid in match.players:
        if pid in result.winners:
            players[pid].wins += 1
        else:
            players[pid].losses += 1