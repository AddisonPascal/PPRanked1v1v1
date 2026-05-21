import discord
import asyncio
import pickle
import math
import time
import random

import ranked
from ranked import Player, Match, Result

import playerlookup

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

# cf.QUEUEPINGMESSAGE string

# cf.SERVER server ID
# cf.MATCHCATEGORY channel (category) ID
# cf.QUEUECHANNEL channel ID
# cf.RESULTSCHANNEL channel ID
# cf.LOGCHANNEL channel ID
# cf.rank_roles list of role IDs


# Players / Matches
players = {}
current_matches = {}
flagged_matches = {}
historic_matches = {}

# Queue
queue_active = False
queue_pairing = False
queue_1_player = 0
queue_1_join = 0
queue_2_player = 0
queue_2_join = 0


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

        if self.queue_1_player:
            out.append(self.queue_1_player)

        if self.queue_2_player:
            out.append(self.queue_2_player)

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
            if match.has_player(player_id):
                return True
    
        return False
    
    
    def next_match_num(self):
        return (
            len(self.current_matches)
            + len(self.flagged_matches)
            + len(self.historic_matches)
            + 1
        )

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
        
# Save data
def savedata():
    data = [
        state.players,
        state.current_matches,
        state.flagged_matches,
        state.historic_matches
    ]
    pickle.dump(data, open("data.pickle", "wb"))
    
    
    
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
        ...
        
    
    # Init
    async def on_ready(self):
        global boot_time
        global c_log
        global c_queue
        global c_results
        global s_server
        global c_match
        global s_comm
        
        boot_time = time.time();
        
        
        savedata()
        
        print('Ranked 1v1v1 bot active')
        
        # Get channel objects
        
        c_log = self.get_channel(cf.LOGCHANNEL)
        c_queue = self.get_channel(cf.QUEUECHANNEL)
        c_results = self.get_channel(cf.RESULTSCHANNEL)
        c_match = self.get_channel(cf.MATCHCATEGORY)
        s_server = self.get_guild(cf.SERVER)
        
        #s_comm = self.get_guild(cf.COMMUNITYSERVER)
        
        await c_log.send("1v1v1 Bot Ready")
        
      
        
    # On Message
    async def on_message(self, message):
        global boot_time
        global players
        global current_matches
        global flagged_matches
        global historic_matches
        global queue_active
        global queue_pairing
        global queue_1_player
        global queue_1_join
        global queue_2_player
        global queue_2_join
        
        
        # Delete messages in queue channel if not admin or queue command
        if message.channel.id==cf.QUEUECHANNEL and message.content not in ['pp!join', 'pp!leave'] and message.author.id not in cf.ADMINS:
            try:
                await message.delete()
            except:
                pass
            return
            
        # Delete bot replies to queue commands
        if message.author.id in [998175193778372659, 1263039458475901021]:
            if "you have left the queue" in message.content or "you are not in the queue" in message.content or "queue is closed right now" in message.content or "you are in an ongoing match" in message.content or "you are already in the queue" in message.content or "you have joined the queue" in message.content:
                await asyncio.sleep(10)
                try:
                    await message.delete()
                except:
                    pass
            if "you may not join the queue" in message.content or "cannot leave the queue" in message.content:
                try:
                    await asyncio.sleep(10)
                    await message.delete()
                except:
                    pass
                    
        # Send discord server invite
        if message.content=="pp!invite":
            await message.channel.send("https://discord.gg/NwE75sqvxg")
            
        # pp!run admin command
        if message.content.startswith("pp!run!"):
            if message.author.id != 374496541819404299:
                await message.channel.send("You do not have permission to do that!")
                return
            try:
                exec(message.content[7:], globals())
                await message.channel.send("Finished: "+message.content[7:])
            except:
                await message.channel.send("Exception")
                
        # pp!echo admin command
        if message.content.startswith("pp!echo!"):
            if message.author.id != 374496541819404299:
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
            savedata()
        
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
        
                try:
                    await s_server.get_member(message.author.id).add_roles(
                        s_server.get_role(cf.rank_roles[0])
                    )
                except:
                    pass
        
                await c_log.send("Player added to database: " + str(message.author.id))
                savedata()
        
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
                    "Play your 1v1v1 match now!\n"
                    "When finished, enter results like `pp!score a`, `pp!score ab`, or `pp!score tt c`.\n"
                    "`t` means a tied game. `a`, `b`, and `c` are the players who won the final game.\n"
                    "All 3 players must confirm with `pp!score confirm`."
                )
        
                await c_results.send(
                    "Match " + str(match_num) + " started!\n\n"
                    + "A: " + state.players[pA].ign.replace("_", "\\_") + "\n"
                    + "B: " + state.players[pB].ign.replace("_", "\\_") + "\n"
                    + "C: " + state.players[pC].ign.replace("_", "\\_")
                )
        
                await try_delete(message)
        
                return
        
            # Otherwise add to queue
            state.add_to_queue(message.author.id)
            savedata()
        
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
            
            
             
print("Loading")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = MyClient(intents=intents)
client.run(cf.token)