import discord
import asyncio
import pickle
import math
import time
import random

import ranked
from ranked import Player, Match, Result, apply_match_stats, stats_for_player

import playerlookup

import rating

# Config file
import cf

# Config variables:

# cf.token string
# cf.rank_names list of strings

# cf.COMMUNITYSERVER server ID
# cf.COMM_MASTER_ID role ID

# cf.ADMINS list of user IDs
# cf.VERIFIERS list of user IDs
# cf.BANLIST list of user IDs
# cf.BOTS list of user (bot) IDs

# cf.OWNER user ID

# cf.QUEUEPINGMESSAGE string

# cf.SERVER server ID
# cf.MATCHCATEGORY channel (category) ID
# cf.QUEUECHANNEL channel ID
# cf.RESULTSCHANNEL channel ID
# cf.LOGCHANNEL channel ID
# cf.rank_roles list of role IDs


class RankedState:
    def __init__(self, players=None, current_matches=None, flagged_matches=None, historic_matches=None):
        self.players = players or {}
        self.current_matches = current_matches or {}
        self.flagged_matches = flagged_matches or {}
        self.historic_matches = historic_matches or {}

        self.queue_active = False
        self.queue_pairing = False

        self.queue_1_player = 0
        self.queue_1_join = 0

        self.queue_2_player = 0
        self.queue_2_join = 0
        
    def queue_size(self):
        return (self.queue_1_player != 0) + (self.queue_2_player != 0)

    def queue_players(self):
        out = []
        if self.queue_1_player: out.append(self.queue_1_player)
        if self.queue_2_player: out.append(self.queue_2_player)
        return out

    def in_queue(self, player_id):
        return player_id in self.queue_players()

    def clear_queue(self):
        self.queue_1_player = 0
        self.queue_1_join = 0

        self.queue_2_player = 0
        self.queue_2_join = 0
        
    def add_to_queue(self, player_id):
        if self.queue_1_player == 0:
            self.queue_1_player = player_id
            self.queue_1_join = time.time()
            return
        if self.queue_2_player == 0:
            self.queue_2_player = player_id
            self.queue_2_join = time.time()
            return
        raise RuntimeError("Queue is already full")
        
    def remove_from_queue(self, player_id):
        if self.queue_1_player == player_id:
            self.queue_1_player = 0
            self.queue_1_join = 0
            return True
        if self.queue_2_player == player_id:
            self.queue_2_player = 0
            self.queue_2_join = 0
            return True
        return False
        
    def player_in_current_match(self, player_id):
        for match in self.current_matches.values():
            if match.has_player(player_id): return True
        return False
    
    def next_match_num(self):
        return len(self.current_matches) + len(self.flagged_matches) + len(self.historic_matches) + 1
        

# Load data file
try:
    dat = pickle.load(open("data.pickle", "rb"))
    state = RankedState(dat[0], dat[1], dat[2], dat[3])
except Exception as e:
    print("Error loading database:", e)
    input("Continue to create new one")
    state = RankedState()
    pickle.dump([state.players, state.current_matches, state.flagged_matches, state.historic_matches], open("data.pickle", "wb"))
        
        
# Get IGN from discord ID in database
def ign(disc):
    try:
        return playerlookup.ign(disc)
    except:
        return None
        

def queue_time_leaderboard(players):
    ranked_players = sorted(
        players.values(),
        key=lambda p: p.queuetime,
        reverse=True
    )

    msg = "## Queue Time Leaderboard"

    for i, p in enumerate(ranked_players[:10]):
        msg += (
            "\n#"
            + str(i + 1)
            + ": "
            + p.ign.replace("_", "\\_")
            + " - "
            + str(math.floor(p.queuetime / 60))
            + " min"
        )

    return msg
    
        
def leaderboard_players(players):
    return sorted(
        players.values(),
        key=lambda p: (
            p.rank,
            rating.display_rating(p),
            p.wins,
            -p.losses,
        ),
        reverse=True
    )
    
    
def leaderboard_position(player_id, ranked_players):
    for i, player in enumerate(ranked_players):
        if player.discord_id == player_id:
            return i
    return None
        

def stats_message_for_player(player_id: int):
    if player_id not in state.players:
        return "User is unranked! Do `pp!join` to join the queue."

    player = state.players[player_id]

    stats = stats_for_player(
        player_id,
        state.players,
        state.historic_matches
    )

    if stats is None:
        return "User is unranked! Do `pp!join` to join the queue."

    if stats["last_played"] is None:
        last_played = "Never"
    else:
        last_played = "<t:" + str(round(stats["last_played"])) + ":R>"

    losses = max(1, stats["losses"])

    msg = "## Stats for " + player.ign.replace("_", "\\_") + ":"

    msg += "\n\nMatch Wins: " + str(stats["wins"])
    msg += "\nMatch Ties: " + str(stats["ties"])
    msg += "\nMatch Losses: " + str(stats["losses"])
    msg += "\nMatches Voided: " + str(stats["matches_voided"])
    msg += "\nLast Played: " + last_played

    msg += "\n\nGames Played: " + str(stats["games_played"])
    msg += "\nGames Tied: " + str(stats["games_tied"])

    msg += "\n\nSolo Wins: " + str(stats["solo_wins"])
    msg += "\nTied Wins: " + str(stats["tied_wins"])

    msg += "\n\nTied Losses: " + str(stats["tied_losses"])
    msg += "\nLone Losses: " + str(stats["lone_losses"])

    msg += "\n\nBest Winstreak: " + str(stats["best_winstreak"])
    msg += "\nWorst Losing Streak: " + str(-1 * stats["worst_losing_streak"])
    msg += "\nCurrent Streak: " + str(stats["current_streak"])
    msg += "\n-# *(streaks ignore ties)*"

    msg += "\n\nW/L: " + str(round(stats["wins"] / losses, 2))

    return msg
        
        
# Save data
def savedata():
    data = [
        state.players,
        state.current_matches,
        state.flagged_matches,
        state.historic_matches
    ]
    pickle.dump(data, open("data.pickle", "wb"))
    
    
def signed_round(value, places=3):
    rounded = round(value, places)

    if rounded >= 0:
        return "+" + str(rounded)

    return str(rounded)
    
    
def regenerate_trueskill_from_history():
    # Reset every player's TrueSkill rating.
    for player in state.players.values():
        player.mu = 25
        player.sigma = 25 / 3

    # Replay completed matches in original order.
    matches = list(state.historic_matches.values())
    matches.sort(key=lambda match: match.num)

    recalculated = 0
    skipped = 0

    for match in matches:
        result = match.result

        if result is None or result.voided or len(result.winners) == 0:
            skipped += 1
            continue

        try:
            rating.apply_match_rating(match, state.players)
            recalculated += 1
        except Exception as e:
            raise RuntimeError(
                "Failed while recalculating Match "
                + str(match.num)
                + ": "
                + repr(e)
            )

    return recalculated, skipped
    
    
async def try_delete(message):
    try:
        await message.delete()
    except:
        pass
        
        
async def try_delete_after(message, seconds):
    await asyncio.sleep(seconds)
    await try_delete(message)
        
        
# Discord bot
class MyClient(discord.Client):
    
    async def finalise_match(self, match: Match):
        match.end_time = time.time()

        # Update player stats and ratings
        rating_before = {}
        
        for pid in match.players:
            p = state.players[pid]
            rating_before[pid] = (
                p.mu,
                p.sigma,
                rating.display_rating(p)
            )
        
        apply_match_stats(match, state.players)
        rating.apply_match_rating(match, state.players)
        
        rating_log = "Rating changes for Match " + str(match.num) + ":\n"
        
        for pid in match.players:
            p = state.players[pid]
        
            old_mu, old_sigma, old_display = rating_before[pid]
        
            new_mu = p.mu
            new_sigma = p.sigma
            new_display = rating.display_rating(p)
        
            rating_log += (
                p.ign
                + ": mu "
                + str(round(old_mu, 3))
                + " -> "
                + str(round(new_mu, 3))
                + " ("
                + signed_round(new_mu - old_mu, 3)
                + "), sigma "
                + str(round(old_sigma, 3))
                + " -> "
                + str(round(new_sigma, 3))
                + " ("
                + signed_round(new_sigma - old_sigma, 3)
                + "), display "
                + str(round(old_display, 3))
                + " -> "
                + str(round(new_display, 3))
                + " ("
                + signed_round(new_display - old_display, 3)
                + ")\n"
            )

        # Move match out of active/flagged and into history
        if match.channel_id in state.current_matches:
            del state.current_matches[match.channel_id]

        if match.channel_id in state.flagged_matches:
            del state.flagged_matches[match.channel_id]

        state.historic_matches[match.channel_id] = match

        # Update ranks after adding the match to history,
        # so Bronze/Silver/Gold progression can count this match.
        rank_messages = []

        for pid in match.players:
            player = state.players[pid]

            old_rank = player.rank
            new_rank = rating.rank_for_player(
                pid,
                state.players,
                state.historic_matches
            )

            if new_rank != old_rank:
                player.rank = new_rank
                player.rank_since_match = match.num

                if new_rank > old_rank:
                    rank_messages.append(
                        "<@" + str(pid) + "> has been promoted to " + cf.rank_names[new_rank] + "!"
                    )
                    log_word = "promoted"
                else:
                    rank_messages.append(
                        "<@" + str(pid) + "> has been demoted to " + cf.rank_names[new_rank] + "."
                    )
                    log_word = "demoted"

                await c_log.send(
                    str(pid)
                    + " "
                    + log_word
                    + " from "
                    + cf.rank_names[old_rank]
                    + " to "
                    + cf.rank_names[new_rank]
                )

                member = s_server.get_member(pid)

                if member is not None:
                    try:
                        old_role = s_server.get_role(cf.rank_roles[old_rank])
                        new_role = s_server.get_role(cf.rank_roles[new_rank])

                        if old_role is not None:
                            await member.remove_roles(old_role)

                        if new_role is not None:
                            await member.add_roles(new_role)

                    except Exception as e:
                        await c_log.send(
                            "Failed to update rank role for "
                            + str(pid)
                            + ": "
                            + repr(e)
                        )

        savedata()
        
        await c_results.send(match.human(state.players))

        for msg in rank_messages:
            await c_results.send(msg)
            
        await c_log.send(rating_log.replace("_", "\\_"))

        await c_log.send("Match " + str(match.num) + " finalised")

        channel = self.get_channel(match.channel_id)

        if channel is not None:
            try:
                await channel.delete(reason="Match finalised")
            except Exception as e:
                await c_log.send(
                    "Failed to delete match channel for Match "
                    + str(match.num)
                    + ": "
                    + repr(e)
                )


    # Init
    async def on_ready(self):
        global boot_time
        global c_log
        global c_queue
        global c_results
        global s_server
        global c_match
        
        boot_time = time.time();
        
        
        print('Ranked 1v1v1 bot active')
        
        # Get channel objects
        
        c_log = self.get_channel(cf.LOGCHANNEL)
        c_queue = self.get_channel(cf.QUEUECHANNEL)
        c_results = self.get_channel(cf.RESULTSCHANNEL)
        c_match = self.get_channel(cf.MATCHCATEGORY)
        s_server = self.get_guild(cf.SERVER)
        
        await c_log.send("1v1v1 Bot Ready")

        
    # On Message
    async def on_message(self, message):
        global boot_time
        global state
        
        # Delete messages in queue channel if not admin or queue command
        if message.channel.id==cf.QUEUECHANNEL and message.content not in ['pp!join', 'pp!leave'] and message.author.id not in cf.ADMINS:
            await try_delete(message)
            return
                    
        # Delete bot replies to queue commands
        if message.author.id in cf.BOTS:
            auto_delete_phrases = [
                "you have left the queue",
                "you are not in the queue",
                "queue is closed right now",
                "you are in an ongoing match",
                "you are already in the queue",
                "you have joined the queue",
                "you may not join the queue",
                "cannot leave the queue",
            ]
        
            if any(phrase in message.content for phrase in auto_delete_phrases):
                await try_delete_after(message, 10)
                return
                    
        # Send discord server invite
        if message.content=="pp!invite":
            await message.channel.send("https://discord.gg/NwE75sqvxg")
            
        # Recalculate TrueSkill ratings (not ranks)    
        if message.content == "pp!recalcratings":
            if message.author.id != cf.OWNER:
                await message.channel.send("You do not have permission to do that!")
                return
        
            try:
                recalculated, skipped = regenerate_trueskill_from_history()
                savedata()
        
                await message.channel.send(
                    "Recalculated TrueSkill ratings from history.\n"
                    + "Rated matches replayed: "
                    + str(recalculated)
                    + "\nSkipped voided/tied/unrateable matches: "
                    + str(skipped)
                )
        
                await c_log.send(
                    "TrueSkill ratings recalculated by "
                    + str(message.author.id)
                    + ". Rated matches replayed: "
                    + str(recalculated)
                    + ", skipped: "
                    + str(skipped)
                )
        
            except Exception as e:
                await message.channel.send("Failed to recalculate ratings: `" + repr(e) + "`")
                await c_log.send("Failed to recalculate ratings: " + repr(e))
        
            return

        # pp!run admin command
        if message.content.startswith("pp!run!"):
            if message.author.id != cf.OWNER:
                await message.channel.send("You do not have permission to do that!")
                return
            try:
                exec(message.content[7:], globals())
                await message.channel.send("Finished: "+message.content[7:])
            except:
                await message.channel.send("Exception")
                
        # pp!echo admin command
        if message.content.startswith("pp!echo!"):
            if message.author.id != cf.OWNER:
                await message.channel.send("You do not have permission to do that!")
                return
            try:
                await message.channel.send(str(eval(message.content[8:])))
            except:
                await message.channel.send("Exception")
        
        # pp!verify - Verify player by setting nick
        if message.content.startswith("pp!verify "):
            if message.author.id not in cf.VERIFIERS:
                await message.channel.send("You do not have permission to do that!")
                return
            m_mem = s_server.get_member(message.mentions[0].id)
            if m_mem.nick!=None:
                await message.channel.send("Cannot verify already verified user. ")
                return
            if '<' in message.content.split(' ')[-1]:
                await message.channel.send("Please use `pp!verify @player playername`")
                return
            await m_mem.edit(nick=message.content.split(' ')[-1].replace('\\', ''))
            await message.channel.send("Verified user <@"+str(message.mentions[0].id)+">")
            await c_log.send("User <@"+str(message.mentions[0].id)+"> verified by <@"+str(message.author.id)+">")
            return
            try:
                m_mem = s_server.get_member(message.mentions[0].id)
                if m_mem.nick!=None:
                    await message.channel.send("Cannot verify already verified user. ")
                await m_mem.edit(nick=message.content.split(' ')[-1].replace('\\', ''))
                await message.channel.send("Verified user <@"+str(message.mentions[0].id)+">")
                await c_log.send("User <@"+str(message.mentions[0].id)+"> verified by <@"+str(message.author.id)+">")
            except:
                await message.channel.send("Error verifying user. ")
                
        # pp!open - open the queue
        if message.content == "pp!open":
            if message.author.id not in cf.ADMINS:
                await message.channel.send("You do not have permission to do that!")
                return
        
            if state.queue_active:
                await message.channel.send("Queue is already open")
                return
        
            state.queue_active = True
            state.queue_pairing = False
        
            await c_queue.send("The queue has been opened. Type `pp!join` to join!")
            await c_log.send("Admin queue open")
            return
        
        # pp!close - close the queue
        if message.content == "pp!close":
            if message.author.id not in cf.ADMINS:
                await message.channel.send("You do not have permission to do that!")
                return
        
            if not state.queue_active:
                await message.channel.send("Queue is already closed")
                return
        
            if state.queue_pairing:
                await message.channel.send("Please wait, a match is starting.")
                return
        
            state.queue_active = False
        
            if state.queue_1_player != 0:
                state.players[state.queue_1_player].queuetime += time.time() - state.queue_1_join
        
            if state.queue_2_player != 0:
                state.players[state.queue_2_player].queuetime += time.time() - state.queue_2_join
        
            state.clear_queue()
            savedata()
        
            await c_queue.send("The queue has been closed.")
            await c_log.send("Admin queue close")
            return
            
        # pp!status - get status of bot
        if message.content == "pp!status":
            embedVar = discord.Embed(title="Status", color=0xffffff)

            for name, value in [
                ("Uptime", math.floor(time.time() - boot_time)),
                ("Queue open", state.queue_active),
                ("Players in queue", state.queue_size()),
                ("Total ranked players", len(state.players)),
                ("Active matches", len(state.current_matches)),
                ("Flagged matches", len(state.flagged_matches)),
                ("Completed matches", len(state.historic_matches)),
            ]:
                embedVar.add_field(name=name, value=str(value))

            await message.channel.send(embed=embedVar)
            return
            
        # pp!qlb - queue time leaderboard 
        if message.content == "pp!qlb":
            if len(state.players) == 0:
                await message.channel.send("Queue time leaderboard is empty.")
                return
        
            await message.channel.send(queue_time_leaderboard(state.players))
            return
            
        # pp!lb - leaderboard
        if message.content.startswith("pp!lb"):
            ranked_players = leaderboard_players(state.players)

            if len(ranked_players) == 0:
                await message.channel.send("Leaderboard is empty.")
                return

            # Default: show top 10
            if message.content == "pp!lb":
                start = 0
                end = min(10, len(ranked_players))
                focus_id = None

            # Mention version: show around mentioned player
            else:
                try:
                    focus_id = message.mentions[0].id
                except:
                    await message.channel.send("Usage: `pp!lb` or `pp!lb @player`.")
                    return

                if focus_id not in state.players:
                    await message.channel.send("That user is unranked.")
                    return

                pos = leaderboard_position(focus_id, ranked_players)

                if pos is None:
                    await message.channel.send("That user is not on the leaderboard.")
                    return

                start = max(0, pos - 5)
                end = min(len(ranked_players), pos + 6)

            msg = "## Leaderboard"

            for i in range(start, end):
                p = ranked_players[i]

                line = (
                    "\n#"
                    + str(i + 1)
                    + ": "
                    + p.ign.replace("_", "\\_")
                    + " ("
                    + cf.rank_names[p.rank]
                    + ")"
                    + " - "
                    + str(round(rating.display_rating(p), 2))
                )

                if focus_id == p.discord_id:
                    line = "\n**" + line.strip() + "**"

                msg += line

            await message.channel.send(msg)
            return
            
            
        if message.content.startswith("pp!user"):
            if message.content == "pp!user":
                pid = message.author.id
            else:
                try:
                    pid = message.mentions[0].id
                except:
                    pid = message.author.id

            if pid not in state.players:
                await message.channel.send("User is unranked! Do `pp!join` to join the queue.")
                return

            p = state.players[pid]

            embed = discord.Embed(
                title=p.ign.replace("_", "\\_"),
                description="**Ranked Info**",
                color=0xff0000
            )

            embed.add_field(name="Rank", value=cf.rank_names[p.rank])
            embed.add_field(name="Match Wins", value=str(p.wins))
            embed.add_field(name="Match Ties", value=str(p.ties))
            embed.add_field(name="Match Losses", value=str(p.losses))
            embed.add_field(name="Time in Queue", value=str(math.floor(p.queuetime / 60)) + " min")
            embed.add_field(name="TrueSkill", value=str(round(rating.display_rating(p), 2)))


            embed.set_thumbnail(url="https://mc-heads.net/avatar/" + p.ign)

            await message.channel.send(embed=embed)
            return
            
        # pp!match - get progress to next rank
        if message.content == "pp!rank":
            pid = message.author.id
        
            await message.channel.send(
                "<@" + str(pid) + ">\n"
                + rating.rank_status_text(
                    pid,
                    state.players,
                    state.historic_matches,
                    cf.rank_names
                )
            )
            return
            
        # pp!match - inspect match by match number or channel id
        if message.content.startswith("pp!match "):
            if message.author.id not in cf.ADMINS:
                await message.channel.send("You do not have permission to do that!")
                return

            try:
                query = int(message.content[len("pp!match "):].strip())
            except:
                await message.channel.send("Usage: `pp!match <match number or channel id>`")
                return

            found = False

            for label, db in [
                ("current_matches", state.current_matches),
                ("flagged_matches", state.flagged_matches),
                ("historic_matches", state.historic_matches),
            ]:
                for channel_id, match in db.items():
                    if query == channel_id or query == match.num:
                        found = True

                        msg = (
                            "Found in `" + label + "`:\n"
                            + "Channel ID: `" + str(channel_id) + "`\n"
                            + match.human(state.players)
                        )

                        if label != "historic_matches":
                            msg += "\nChannel: <#" + str(channel_id) + ">"

                        await message.channel.send(msg)

            if not found:
                await message.channel.send("No match found with that match number or channel ID.")

            return
            
        # pp!flag - flag an active match for admin resolution
        if message.content == "pp!flag":
            if message.channel.id not in state.current_matches:
                return

            await message.channel.send(
                "Are you sure you want to flag this match?\n"
                "If you flag a match, no further games should be played in it, "
                "but all players will be free to queue again.\n"
                "If there is a dispute about results or restarts, ask a Referee for a decision, do not flag the match.\n"
                "If a player has left or hasn't shown up, make sure to give them at least 5 minutes before flagging.\n\n"
                "To confirm, type `pp!flag confirm`."
            )
            return
    
        # pp!flag confirm actually does it
        if message.content == "pp!flag confirm":
            if message.channel.id not in state.current_matches:
                return

            match = state.current_matches[message.channel.id]

            state.flagged_matches[message.channel.id] = state.current_matches.pop(message.channel.id)
            savedata()

            await c_log.send(
                "Match "
                + str(match.num)
                + " flagged by "
                + str(message.author.id)
                + " in channel "
                + str(message.channel.id)
            )

            await message.channel.send(
                "The match has been flagged. An admin will resolve the problem.\n"
                "All players are now free to queue again."
            )

            return
            
        # pp!score - enter or confirm match results
        if message.content.startswith("pp!score"):
            if message.channel.id not in state.current_matches:
                await message.channel.send("This is not an active match channel.")
                return

            match = state.current_matches[message.channel.id]

            if not match.has_player(message.author.id):
                await message.channel.send("You are not a player in this match.")
                return

            args = message.content[len("pp!score"):].strip()

            if args == "":
                await message.channel.send("Usage: `pp!score a`, `pp!score ab`, `pp!score tt c`, or `pp!score confirm`.")
                return

            if args.lower() == "confirm":
                if match.result is None:
                    await message.channel.send("No result has been entered yet.")
                    return

                if not match.confirm(message.author.id):
                    await message.channel.send("You have already confirmed these results.")
                    return
                    
                
                if match.is_confirmed():
                    await self.finalise_match(match)
                else:
                    savedata()
                    await message.channel.send("You have confirmed these results.")

                return

            result = Result.parse(
                args,
                match,
                is_admin=False
            )

            if result is None:
                await message.channel.send("<@"+str(message.author.id)+">, those results are invalid. Please use the correct format. ")
                return

            match.result = result
            match.confirmers = {message.author.id}
            savedata()

            await message.channel.send("Entered Results: \n"+result.human(match, state.players)+"\nPlease confirm these results by typing `pp!score confirm`. If there is a mistake enter results again with `pp!score`")
            
            await c_log.send("Player "+str(message.author.id)+" entered results for "+str(message.channel.id))
            
            return
            
        # pp!adminscore - admin result entry for flagged matches only
        if message.content.startswith("pp!adminscore"):
            if message.author.id not in cf.ADMINS:
                await message.channel.send("You do not have permission to do that!")
                return

            if message.channel.id not in state.flagged_matches:
                await message.channel.send("This is not a flagged match channel.")
                return

            match = state.flagged_matches[message.channel.id]

            args = message.content[len("pp!adminscore"):].strip()

            result = Result.parse(
                args,
                match,
                is_admin=True
            )

            if result is None:
                await message.channel.send("Invalid admin result.")
                return

            match.result = result
            match.confirmers = set(match.players)  # force fully confirmed
            
            await self.finalise_match(match)
            
            await c_log.send("Admin "+str(message.author.id)+" entered results for "+str(message.channel.id))
            
            return
            
        # pp!join - join queue
        if message.content == "pp!join":
            if message.author.id in cf.BANLIST:
                await message.channel.send(
                    "<@" + str(message.author.id) + ">, you may not join the queue as you are currently banned from Ranked."
                )
                await c_log.send("Banned player attempted to queue: " + str(message.author.id))
                
                await try_delete(message)
                
                return
        
            if not state.queue_active:
                await message.channel.send("The queue is closed right now.")
                await try_delete(message)
                return
        
            if state.player_in_current_match(message.author.id):
                await message.channel.send(
                    "<@" + str(message.author.id) + ">, you are in an ongoing match. You cannot queue until that match is complete."
                )
                await try_delete(message)
                return
        
            if state.in_queue(message.author.id):
                await message.channel.send(
                    "<@" + str(message.author.id) + ">, you are already in the queue."
                )
                await try_delete(message)
                return
        
            if state.queue_pairing:
                await message.channel.send("A match is currently starting so you may not join the queue.")
                await try_delete(message)
                return
        
            # Create player if they do not exist
            if message.author.id not in state.players:
                pign = ign(message.author.id)
        
                if pign is None:
                    m_mem = s_server.get_member(message.author.id)
                    nick = m_mem.nick if m_mem else None
        
                    if nick in [None, ""]:
                        await message.channel.send(
                            "<@" + str(message.author.id) + ">, you may not join the queue as you are not verified."
                        )
                        await c_log.send("Player rejected from joining database: " + str(message.author.id))
                        await try_delete(message)
                        return
        
                    pign = nick.split(" ")[-1]
        
                state.players[message.author.id] = Player(
                    discord_id=message.author.id,
                    ign=pign
                )
                
                savedata()
        
                try:
                    await s_server.get_member(message.author.id).add_roles(
                        s_server.get_role(cf.rank_roles[0])
                    )
                except:
                    pass
        
                await c_log.send("Player added to database: " + str(message.author.id))
        
            # If 2 people are already queued, this player starts the match.
            if state.queue_size() == 2:
                state.queue_pairing = True
        
                queued = state.queue_players()
                match_players = queued + [message.author.id]
        
                # Add queue time for queued players
                if state.queue_1_player:
                    state.players[state.queue_1_player].queuetime += time.time() - state.queue_1_join
        
                if state.queue_2_player:
                    state.players[state.queue_2_player].queuetime += time.time() - state.queue_2_join
        
                random.shuffle(match_players)
        
                match_num = state.next_match_num()
                new_channel_name = "match-" + str(match_num)
        
                overwrites = {
                    s_server.default_role: discord.PermissionOverwrite(read_messages=False),
                    s_server.me: discord.PermissionOverwrite(read_messages=True),
                }
        
                for pid in match_players:
                    member = s_server.get_member(pid)
                    if member is not None:
                        overwrites[member] = discord.PermissionOverwrite(read_messages=True)
        
                channel = await s_server.create_text_channel(
                    new_channel_name,
                    category=c_match,
                    overwrites=overwrites
                )
        
                match = Match(
                    num=match_num,
                    channel_id=channel.id,
                    players=match_players,
                    confirmers=set(),
                    result=None,
                    start_time=time.time()
                )
        
                state.current_matches[channel.id] = match
                state.clear_queue()
                state.queue_pairing = False
                savedata()
        
                pA = match_players[0]
                pB = match_players[1]
                pC = match_players[2]
        
                await c_queue.send("There are now 0 players in the queue! Type `pp!join` to join!")
        
                await channel.send(
                    "Match " + str(match_num) + " started!\n\n"
                    + "A: <@" + str(pA) + "> (" + state.players[pA].ign.replace("_", "\\_") + ")\n"
                    + "B: <@" + str(pB) + "> (" + state.players[pB].ign.replace("_", "\\_") + ")\n"
                    + "C: <@" + str(pC) + "> (" + state.players[pC].ign.replace("_", "\\_") + ")\n"
                )
        
                await channel.send(
                    "**Play your 1v1v1 match (normal mode no pwps) now!**\n"
                    "Whoever makes it to the furthest round wins the match (can be 2 people)! If there are 3 ties the match is tied.\n"
                    "When you are done, one player must enter the results, for example `pp!score t ab` - "
                    "t for each tie followed by the letters of each player that won in the final game.\n"
                    "The other players must then confirm with `pp!score confirm`.\n\n"
                    "If lag or interference affects the result, the game should be restarted. *If you collect a powerup, that's considered dying on the round you collect it.*\n"
                    "*In any disputes, ping a Referee in #ranked-chat. If someone leaves or doesn't show up, do `pp!flag`*"
                )
        
        
                await c_results.send(
                    "Match " + str(match_num) + " started!\n\n"
                    + "A: " + state.players[pA].ign.replace("_", "\\_") + "\n"
                    + "B: " + state.players[pB].ign.replace("_", "\\_") + "\n"
                    + "C: " + state.players[pC].ign.replace("_", "\\_")
                )
                
                await c_log.send("Match started: "+str(message.channel.id))
                
                await message.channel.send(
                    "<@" + str(message.author.id) + ">, you have joined the queue! Match started."
                )
        
                await try_delete(message)
                
                
                
        
                return
        
            # Otherwise add to queue
            state.add_to_queue(message.author.id)
        
            queue_size = state.queue_size()
        
            if queue_size == 1:
                await c_queue.send("There is now 1 player in the queue! Type `pp!join` to join!")
            else:
                await c_queue.send("There are now " + str(queue_size) + " players in the queue! Type `pp!join` to join!")
        
            if queue_size == 2 and len(state.current_matches) == 0:
                await c_queue.send(cf.QUEUEPINGMESSAGE)
        
            await message.channel.send(
                "<@" + str(message.author.id) + ">, you have joined the queue! Do `pp!leave` to leave."
            )
            
            await try_delete(message)
        
            await c_log.send("Player joined queue: " + str(message.author.id))
            return
             
        # pp!leave - leave the queue
        if message.content == "pp!leave":
            if state.queue_pairing:
                await message.channel.send("You cannot leave the queue right now, a match is starting!")
                await try_delete(message)
                return

            if not state.in_queue(message.author.id):
                await message.channel.send("<@" + str(message.author.id) + ">, you are not in the queue.")
                await try_delete(message)
                return

            if state.queue_1_player == message.author.id:
                waited = time.time() - state.queue_1_join

                if waited < 30:
                    await message.channel.send(
                        "You cannot leave the queue right now, please wait "
                        + str(round(30 - waited))
                        + " more seconds!"
                    )
                    await try_delete(message)
                    return

                state.players[message.author.id].queuetime += waited
                state.queue_1_player = 0
                state.queue_1_join = 0

            elif state.queue_2_player == message.author.id:
                waited = time.time() - state.queue_2_join

                if waited < 30:
                    await message.channel.send(
                        "You cannot leave the queue right now, please wait "
                        + str(round(30 - waited))
                        + " more seconds!"
                    )
                    await try_delete(message)
                    return

                state.players[message.author.id].queuetime += waited
                state.queue_2_player = 0
                state.queue_2_join = 0

            savedata()

            queue_size = state.queue_size()

            if queue_size == 1:
                await c_queue.send("There is now 1 player in the queue! Type `pp!join` to join!")
            else:
                await c_queue.send("There are now " + str(queue_size) + " players in the queue! Type `pp!join` to join!")

            await message.channel.send("<@" + str(message.author.id) + ">, you have left the queue!")
            await try_delete(message)

            await c_log.send("Player left queue: " + str(message.author.id))
            return
            
        
# Run the bot        
print("Loading")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = MyClient(intents=intents)
client.run(cf.token)