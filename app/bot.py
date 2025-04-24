import asyncio
import discord
from discord.ext import commands

import os
from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True  # Ensure this is enabled

bot = commands.Bot(command_prefix="", intents=intents)

TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"

token = os.getenv("TEST_BOT_TOKEN") if TEST_MODE else os.getenv("BOT_TOKEN")

@bot.event
async def on_ready():
    try:
        activity = discord.Activity(
            type=discord.ActivityType.watching, name="for new opportunities!")
        await bot.change_presence(activity=activity)
        print(f'Logged in as {bot.user} (ID: {bot.user.id})')
        
        # Sync slash commands
        await bot.tree.sync()
    except Exception as e:
        if bot.user.id == 0:
            print('Could not connect to channel. Make sure the token is valid.')
        if bot.user is None:
            print('Could not connect to ACMConnect bot user. Make sure the token is valid.')

async def main():
    await bot.load_extension("setup")
    await bot.load_extension("post_listings")
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
