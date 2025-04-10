import discord
from discord.ext import commands
import os
from logger import Logger

from util import getDataFromJSON, saveDataToJSON


async def setup_guild(bot, guild):
    channel = await guild.create_forum(
        name="opportunities",
        default_sort_order=discord.ForumOrderType.creation_date,
        default_layout=discord.ForumLayoutType.list_view
    )

    # Create embed
    acm_logo = discord.File("acm_logo.png", filename="acm_logo.png")

    embed = discord.Embed(
        colour=discord.Colour(0x5865f2),
        title="Info",
        description=(
            f"Thank you for inviting **{bot.user.name}** to your server! This bot will gather job opportunities and post "
            f"them in this forum channel - <#{channel.id}>. "
        )
    )
    embed.set_thumbnail(url=f"attachment://{acm_logo.filename}")

    await channel.create_thread(
        name=f"{bot.user.name} | UF ACM",
        embed=embed,
        files=[acm_logo]
    )

    return channel


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # test mode logic; only processes the test server if enabled 
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        test_guild_id = int(os.getenv("TEST_GUILD_ID")) if test_mode else None

        # Load guild data and confirm guild info exists and is up-to-date
        existing_guilds = getDataFromJSON("guilds.json")

        for guild in self.bot.guilds:
            if test_mode and guild.id != test_guild_id:
                continue

            # Check if guild and opportunities channel exists within saved guild data
            exists = False
            up_to_date = False
            for existing_guild in existing_guilds:
                if existing_guild['id'] == guild.id:
                    exists = True
                    if guild.get_channel(existing_guild['channel']) is not None:
                        up_to_date = True
                    break
            if not up_to_date:
                # Create opportunities channel and save guild to data
                channel = await setup_guild(self.bot, guild)

                guild_data = {
                    'id': guild.id,
                    'channel': channel.id
                }

                if exists:  # Edit existing entry with new channel
                    for existing_guild in existing_guilds:
                        if existing_guild['id'] == guild.id:
                            existing_guild.update(guild_data)
                            break
                else:  # Create new entry
                    existing_guilds.append(guild_data)
                saveDataToJSON("guilds.json", existing_guilds)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # in test mode only process join if it's the test server
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        if test_mode:
            test_guild_id = int(os.getenv("TEST_GUILD_ID"))
            if guild.id != test_guild_id:
                return

        # Create opportunities channel if newly added to server
        channel = await setup_guild(self.bot, guild)

        # Create new entry
        guild_data = {
            'id': guild.id,
            'channel': channel.id
        }

        existing_guilds = getDataFromJSON("guilds.json")
        existing_guilds.append(guild_data)
        saveDataToJSON("guilds.json", existing_guilds)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        # only process deletion of test server if in test mode 
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        if test_mode:
            test_guild_id = int(os.getenv("TEST_GUILD_ID"))
            if channel.guild.id != test_guild_id:
                return

        # If opportunities channel was deleted, create new replacement channel
        existing_guilds = getDataFromJSON("guilds.json")

        for existing_guild in existing_guilds:
            if existing_guild['channel'] == channel.id:
                new_channel = await setup_guild(self.bot, channel.guild)

                guild_data = {
                    'id': channel.guild.id,
                    'channel': new_channel.id
                }

                existing_guild.update(guild_data)
                break
        saveDataToJSON("guilds.json", existing_guilds)
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # In test mode, only process removal if it's the test server.
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        if test_mode:
            test_guild_id = int(os.getenv("TEST_GUILD_ID"))
            if guild.id != test_guild_id:
                return

        # Remove guild from guilds.json
        existing_guilds = getDataFromJSON("guilds.json")
        updated_guilds = [g for g in existing_guilds if g['id'] != guild.id]
        saveDataToJSON("guilds.json", updated_guilds)


async def setup(bot):
    await bot.add_cog(Setup(bot))
