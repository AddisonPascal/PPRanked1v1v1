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



#def process_result(

# Load data file
if True:
    try:
        dat = pickle.load(open('data.pickle', 'rb'))
        players=dat[0]
        current_matches=dat[1]
        flagged_matches=dat[2]
        historic_matches=dat[3]
    except:
        print("Error loading database")
        input()
        exit()
        
# Get IGN from discord ID in database
def ign(disc):
    try:
        return EloLookup.ign(disc)
    except:
        return None
        
# Save data
def savedata():
    global players
    global current_matches
    global flagged_matches
    global historic_matches
    data = [players, current_matches, flagged_matches, historic_matches]
    pickle.dump(data, open('data.pickle', 'wb'))
        
        
        
# Discord bot
class MyClient(discord.Client):
    
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
        if message.content=="pp!open":
            if message.author.id not in cf.ADMINS:
                await message.channel.send("You do not have permission to do that!")
                return
            if queue_active:
                await message.channel.send("Queue is already open")
                return
            queue_active = True
            queue_pairing = False
            await c_queue.send("The queue has been opened. Type `pp!join` to join!")
            await c_log.send("Admin queue open")
        
        # pp!close - close the queue
        if message.content=="pp!close":
            if message.author.id not in cf.ADMINS:
                await message.channel.send("You do not have permission to do that!")
                return
            if not queue_active:
                await message.channel.send("Queue is already closed")
                return
            if queue_pairing:
                await message.channel.send("Please wait, a match is starting.")
            queue_active = False
            
            if queue_1_player != 0:
                players[queue_1_player]['queuetime'] += time.time() - queue_1_join
            if queue_2_player != 0:
                players[queue_2_player]['queuetime'] += time.time() - queue_2_join
             
            queue_1_player=0
            queue_2_player=0
            savedata()
            await c_queue.send("The queue has been closed. ")
            await c_log.send("Admin queue close")
            
        # pp!status - get status of bot
        if message.content=="pp!status":
            embedVar = discord.Embed(title = "Status", description = '', color = 0xffffff)
            embedVar.add_field(name="Uptime", value=str(math.floor(time.time()-boot_time)))
            embedVar.add_field(name="Queue open", value=str(queue_active))
            embedVar.add_field(name="Total ranked players", value=str(len(players)))
            embedVar.add_field(name="Active matches", value=str(len(current_matches)))
            embedVar.add_field(name="Flagged matches", value=str(len(flagged_matches)))
            embedVar.add_field(name="Completed matches", value=str(len(historic_matches)))
            await message.channel.send(embed=embedVar)
            
         
        