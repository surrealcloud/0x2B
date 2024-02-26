import requests
from discord.ext import commands
from discord import app_commands
import discord
import os

from dotenv import load_dotenv

#load environment variables
load_dotenv()
token = os.getenv("DISCORD_TOKEN")

#sets discord api intents and sets "client" as our bot object
intents = discord.Intents.default()
intents.message_content = True
intents.moderation = True
intents.guilds = True

client = commands.Bot(command_prefix='!', intents=intents)

#determines channels
# kick_counter_channel_id = 800194841132007444

#initializes the bot
@client.event
async def on_ready():
    try:
        print(f'We have logged in as {client.user}')
        await client.change_presence(activity=discord.Game(name='Throwing cards, making money'))
    except Exception as exception:
        print(f'Error occurred: {exception}')
        exit()

#checks if specific player was kicked, banned, or timed out. 
@client.event
async def on_audit_log_entry_create(entry):
    # replace placeholder values
    kick_channel = client.get_channel('placeholder')
    kicked_user = await client.fetch_user(entry.target.id)
    if entry.target.id == 'placeholder':
        if entry.after.timed_out_until is not None:
            print(f'{kicked_user.name} has been timed out')
            await kick_channel.send(f'{kicked_user.name} has been timed out')
        elif entry.action == discord.AuditLogAction.kick or entry.action == discord.AuditLogAction.ban:
            print(f'{kicked_user} was removed from the server')
            await kick_channel.send(f'{kicked_user.name} was removed from the server')

client.run(token)