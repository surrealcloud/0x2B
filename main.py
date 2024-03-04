import requests
from discord.ext import commands
from discord import app_commands
import discord
import os
import sqlite3

from dotenv import load_dotenv

#declares our global variables
global kick_counter_channel_id
global dbconn
global dbcursor
global tracked_users
tracked_users = []

#load environment variables
load_dotenv()
token = os.getenv("DISCORD_TOKEN")
kick_counter_channel_id = os.getenv("KICK_CHANNEL")
admin_id = os.getenv("ADMIN_ID")
admin_nick = os.getenv("ADMIN_NICK")

#sets discord api intents and sets "client" as our bot object
intents = discord.Intents.default()
intents.message_content = True
intents.moderation = True
intents.guilds = True

client = commands.Bot(command_prefix="!",intents=intents)

###SQLITE3 FUNCTIONS
#defines our sqlite3 functions
def edituser(userid, nickname, perms, tracked):
    dbcursor.execute("SELECT userid FROM users WHERE userid=?", (userid,))
    exists = dbcursor.fetchall()
    if not exists:
        dbcursor.execute("""INSERT INTO users VALUES(
            ?,
            ?,
            ?,
            ?
        )""",(userid, nickname, perms, tracked))
    else:
        dbcursor.execute("""UPDATE users 
        SET nickname = ?,
            perms = ?,
            tracked = ?
        WHERE userid = ?
        """,(nickname, perms, tracked, userid))
    if tracked == 1 and userid not in tracked_users:
        tracked_users.append(userid)
    dbconn.commit()
    print("DB has been updated")

def isWhitelisted(userid):
    dbcursor.execute("""
        SELECT
            userid,
            perms
        FROM
            users
        WHERE
            userid=? AND
            perms>=2
    """,(userid,))
    allowed = dbcursor.fetchall()
    if allowed:
        return True
    else:
        return False


###DISCORD.PY FUNCTIONS
#initializes the bot
@client.event
async def on_ready():
    try:
        print(f'We have logged in as {client.user}')
        await client.change_presence(activity=discord.Game(name='Throwing cards, making money'))
        comm = await client.tree.sync()
        print(comm)
    except Exception as exception:
        print(f'Error occurred: {exception}')
        exit()

#checks if userid is being tracked by the bot. if true, messages punishment in target channel
@client.event
async def on_audit_log_entry_create(entry):
    # replace placeholder values
    kick_channel = await client.fetch_channel(kick_counter_channel_id)
    kicked_user = await client.fetch_user(entry.target.id)
    if entry.target.id in tracked_users:
        if entry.after.timed_out_until is not None:
            print(f'{kicked_user.name} has been timed out')
            await kick_channel.send(f'{kicked_user.name} has been timed out')
        elif entry.action == discord.AuditLogAction.kick or entry.action == discord.AuditLogAction.ban:
            print(f'{kicked_user} was removed from the server')
            await kick_channel.send(f'{kicked_user.name} was removed from the server')

###COMMAND TREE FUNCTIONS
#Add user to users database
@client.tree.command(name="track",description="Adds userid to tracking list")
async def track(interaction: discord.Interaction, *,member: discord.Member, nickname: str = None):
    if isWhitelisted(interaction.user.id):
        edituser(member.id, nickname, 0, 1)
        await interaction.response.send_message(f"{member.id} has been added to the watch list")
    else:
        await interaction.response.send_message(f"{interaction.user.mention} you do not have permission for this command.")

###STARTUP

#database headers: {USERID, NICKNAME, PERMS, TRACKED}
#checks if users.db exists, if note then initiate and use set user in admin as admin
if os.path.isfile("users.db"):
    dbconn = sqlite3.connect("users.db")
    dbcursor = dbconn.cursor()
else:
    dbconn = sqlite3.connect("users.db")
    dbcursor = dbconn.cursor()
    dbcursor.execute("""CREATE TABLE users (
        userid integer,
        nickname text,
        perms integer,
        tracked integer
    )""")
    edituser(admin_id, admin_nick, 2, 0)
    dbconn.commit()

client.run(token)
