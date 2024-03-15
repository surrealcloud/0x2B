import requests
from discord.ext import commands
from discord import app_commands
import discord
import os
import sqlite3
from enum import Enum

from dotenv import load_dotenv

#declares our global variables
global punishment_channel_id
global dbconn
global dbcursor
global tracked_users

#load environment variables
load_dotenv()
token = os.getenv("DISCORD_TOKEN")
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
def editUser(userid, nickname, perms=0, tracked=0, timeouts=0, kickbans=0):
    data = [userid, nickname, perms, tracked, timeouts, kickbans]
    exists = getRow(userid)
    if not exists:
        for i in range(4):
            if data[2+i] is None:
                data[2+i] = 0
        dbcursor.execute("""INSERT INTO users VALUES(
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )""",tuple(data))
    else:
        data=validateEntry(data, exists)
        data.append(data[0])
        data.pop(0)
        dbcursor.execute("""UPDATE users 
        SET nickname = ?,
            perms = ?,
            tracked = ?,
            timeouts = ?,
            kickbans = ?
        WHERE userid = ?
        """,tuple(data))
    if tracked == 1 and userid not in tracked_users:
        tracked_users.append(userid)
    dbconn.commit()
    print("DB has been updated")
    print(getRow(userid))

def getRow(userid):
    dbcursor.execute("SELECT * FROM users WHERE userid = ?",(userid,))
    data = dbcursor.fetchall()
    if data:
        return data[0]

def validateEntry(data, existingentry):
    for i in range(6):
        if data[i] is None:
            data[i] = existingentry[i]
    for i in range(4):
        if data[2+i] is None:
            data[i] = 0
    return data

def isWhitelisted(userid):
    dbcursor.execute("""
        SELECT
            userid,
            perms
        FROM
            users
        WHERE
            userid=? AND
            perms>=1
    """,(userid,))
    allowed = dbcursor.fetchall()
    if allowed:
        return True
    else:
        return False

def incrementPunishment(userid, punishment):
    if punishment=="timeout":
        dbcursor.execute("""
            UPDATE
                users
            SET
                timeouts = timeouts+1
            WHERE
                userid=?
            """,(userid,))
        dbconn.commit()
        dbcursor.execute("""
            SELECT
                timeouts
            FROM
                users
            WHERE
                userid=?
            """,(userid,))
        return dbcursor.fetchall()[0][0]
    elif punishment=="kickban":
        dbcursor.execute("""
            UPDATE
                users
            SET
                kickbans = kickbans+1
            WHERE
                userid=?
            """,(userid,))
        dbconn.commit()
        dbcursor.execute("""
            SELECT
                kickbans
            FROM
                users
            WHERE
                userid=?
            """,(userid,))
        return dbcursor.fetchall()[0][0]

def getNickname(userid):
    dbcursor.execute("""
        SELECT
            nickname
        FROM
            users
        WHERE
            userid=?
    """,(userid,))
    name = dbcursor.fetchall()
    if name[0][0] is not None:
        return name[0][0]
    else:
        return userid

def isTracked(userid):
    dbcursor.execute("""
        SELECT
            *
        FROM
            users
        WHERE
            userid=? AND
            tracked=1
    """,(userid,))
    tracked = dbcursor.fetchall()
    if tracked:
        return True
    else:
        return False

def startupVars():
    varconn = sqlite3.connect("variables.db")
    varcursor = varconn.cursor()
    varcursor.execute("""
        CREATE TABLE IF NOT EXISTS variables (
            varname text UNIQUE,
            value text
        )
    """)
    varconn.commit()
    varconn.close()

def getVar(variable):
    varconn = sqlite3.connect("variables.db")
    varcursor = varconn.cursor()
    varcursor.execute("""
        SELECT value FROM variables WHERE varname = ?
    """, (variable,))
    value = varcursor.fetchall()
    varconn.close()
    if value:
        return value[0][0]
    else:
        return None

def setVar(variable, value):
    varconn = sqlite3.connect("variables.db")
    varcursor = varconn.cursor()
    varcursor.execute("""
        INSERT INTO variables(varname, value) VALUES (?, ?)
        ON CONFLICT(varname) DO UPDATE SET value=? WHERE varname = ?
    """, (variable, value, value, variable))
    varconn.commit()
    varconn.close()

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
    kick_channel = await client.fetch_channel(punishment_channel_id)
    if kick_channel is None:
        print("No punishment channel set")
    if isTracked(entry.target.id):
        kicked_user = getNickname(entry.target.id)
        if entry.after.timed_out_until is not None:
            print(f'{kicked_user} has been timed out')
            await kick_channel.send(f'{kicked_user} has been timed out {incrementPunishment(entry.target.id,"timeout")} times.')
        elif entry.action == discord.AuditLogAction.kick or entry.action == discord.AuditLogAction.ban:
            print(f'{kicked_user} was removed from the server')
            await kick_channel.send(f'{kicked_user} was removed from the server {incrementPunishment(entry.target.id,"kickban")} times.')

###COMMAND TREE FUNCTIONS

#Adds user to users database with tracking turned on
@client.tree.command(name="track",description="Adds userid to tracking list")
async def track(interaction: discord.Interaction, *,member: discord.Member, nickname: str = None, timeout_count: app_commands.Range[int, 0, None] = None, kickban_count: app_commands.Range[int, 0, None] = None):
    if isWhitelisted(interaction.user.id):
        editUser(member.id, nickname=nickname, tracked=1, timeouts=timeout_count, kickbans=kickban_count)
        await interaction.response.send_message(f"{getNickname(member.id)} has been added to the watch list")
    else:
        await interaction.response.send_message(f"{interaction.user.mention} you do not have permission for this command.")

#Allows superadmin to edit user data
@client.tree.command(name="edit",description="Edits user entry in database")
async def edit(interaction: discord.Interaction, *, member: discord.Member, nickname: str = None, perms: app_commands.Range[int, 0, 1] = None, tracked: app_commands.Range[int, 0, 1] = None, timeouts: app_commands.Range[int, 0, None] = None, kickbans: app_commands.Range[int, 0, None] = None):
    if isWhitelisted(interaction.user.id):
        editUser(member.id, nickname, perms, tracked, timeouts, kickbans)
        await interaction.response.send_message(f"Entry for user {getNickname(member.id)} has been edited.")
    else:
        await interaction.response.send_message(f"{interaction.user.mention} you do not have permission for this command.")

#Displays db values for a given server member
@client.tree.command(name="getuser",description="Show database values for a given server member")
async def showdata(interaction: discord.Interaction, *, member: discord.Member):
    data = getRow(member.id)
    if data:
        await interaction.response.send_message(f"""Data for {getNickname(member.id)}:
        userid: {data[0]}
        nickname: {data[1]}
        perms: {data[2]}
        tracked: {data[3]}
        timeout counter: {data[4]}
        kick/ban counter: {data[5]}""")
    else:
        await interaction.response.send_message(f"No data found for {getNickname(member.id)}")

#Returns list of tracked users
@client.tree.command(name="trackedusers",description="Returns list of tracked users")
async def trackedusers(interaction: discord.Interaction):
    dbcursor.execute("SELECT userid FROM users WHERE tracked==1")
    users = dbcursor.fetchall()
    await interaction.response.send_message(f"{users}")

#Sets the punishment channel
@client.tree.command(name="set_punishment_channel",description="Sets the kick/ban/timeout channel")
async def setPunishmentChannel(interaction: discord.Interaction):
    if isWhitelisted(interaction.user.id):
        setVar("punishment_channel_id",interaction.channel_id)
        punishment_channel_id = int(getVar("punishment_channel_id"))
        await interaction.response.send_message("Punishment channel has been set to this channel.")
    else:
        await interaction.response.send_message(f"{interaction.user.mention} you do not have permission for this command.")

###STARTUP

#database headers: {USERID, NICKNAME, PERMS, TRACKED, TIMEOUTS, KICKBANS}
#checks if users.db exists, if note then initiate and use set user in admin as admin
#just checks for whether a file exists or not, less lines + probably less compute needed vs using "CREATE IF NOT EXISTS" and searching for a userid
if os.path.isfile("users.db"):
    dbconn = sqlite3.connect("users.db")
    dbcursor = dbconn.cursor()
else:
    dbconn = sqlite3.connect("users.db")
    dbcursor = dbconn.cursor()
    dbcursor.execute("""CREATE TABLE users (
        userid integer UNIQUE,
        nickname text,
        perms integer,
        tracked integer,
        timeouts integer,
        kickbans integer
    )""")
    editUser(admin_id, admin_nick, 2, 0)
    dbconn.commit()

startupVars()
punishment_channel_id = getVar("punishment_channel_id")
if punishment_channel_id:
    punishment_channel_id = int(punishment_channel_id)

client.run(token)
