import discord
from discord import app_commands
from discord.ext import commands
import os
import functools            # NEW: needed for the decorator
from logger import Logger
import typing

from util import getDataFromJSON, saveDataToJSON, isValidActivationKey, get_guild_info

logger = Logger()
TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
file = "test_guilds.json" if TEST_MODE else "guilds.json"
logger.log_message(f"TEST_MODE={TEST_MODE} using file {file}", "DEBUG")


def log_exceptions(coro):
    """
    Decorator that catches *any* unhandled exception inside an async coroutine,
    logs the error via `logger.log_message`, and then re-raises it so Discord
    can still handle its usual cleanup.

    Think of it like wrapping your function in bubble-wrap: if it drops,
    we hear the *pop* in the logs instead of silent failure.
    """
    @functools.wraps(coro)
    async def wrapper(*args, **kwargs):
        try:
            return await coro(*args, **kwargs)
        except Exception as e:
            logger.log_message(f"{coro.__qualname__} — {type(e).__name__}: {e}", "ERROR")
            raise
    return wrapper


class Setup(commands.Cog):
    """
    Cog for handling the setup, activation, and configuration of ACM Connect within a Discord guild.
    This includes:
    - Detecting when the bot joins or leaves a server
    - Activation using a secure key
    - Configuring a target channel and role for job opportunity announcements
    """

    def __init__(self, bot):
        """
        Initializes the Setup cog.

        Args:
            bot (commands.Bot): The instance of the bot this cog is attached to.
        """
        self.bot = bot

    @commands.Cog.listener()
    @log_exceptions                   # NEW
    async def on_guild_remove(self, guild):
        """
        Event listener that triggers when the bot is removed from a guild.
        It removes the guild's data from the JSON file.

        Args:
            guild (discord.Guild): The guild the bot was removed from.
        """
        # Load current guilds
        existing_guilds = getDataFromJSON(file)

        # Remove the guild from the list
        updated_guilds = [g for g in existing_guilds if g['id'] != guild.id]

        # Get readable guild info for logging
        guild_info = get_guild_info({'id': guild.id}, self.bot)

        # Save updated list
        saveDataToJSON(file, updated_guilds)

        logger.log_message(f"Guild {guild_info['guild']} with guild id: {guild.id} removed from {file}", "SUCCESS")

    @commands.Cog.listener()
    @log_exceptions                   # NEW
    async def on_guild_join(self, guild):
        """
        Event listener that triggers when the bot joins a new guild.
        Logs a message but does not perform setup.

        Args:
            guild (discord.Guild): The guild the bot just joined.
        """
        guild_info = get_guild_info({'id': guild.id}, self.bot)
        logger.log_message(f"Bot was added to guild: {guild_info['guild']} with id: {guild.id} but has not been setup yet", "SUCCESS")

    @app_commands.command(name="activate", description="Activate ACM Connect")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(key="Activation key for ACM Connect")
    @log_exceptions                   # NEW
    async def activate(self, interaction: discord.Interaction, key: str):
        """
        Slash command to activate ACM Connect for the current guild using an activation key.

        Args:
            interaction (discord.Interaction): The interaction context.
            key (str): Activation key provided by the administrator.
        """
        if interaction.guild is None:
            await interaction.response.send_message(f"{self.bot.user.name} can only be activated inside a guild!")
            return

        existing_guilds = getDataFromJSON(file)

        # Check if the guild is already activated
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                await interaction.response.send_message(f"{self.bot.user.name} is already activated for this guild!")
                return

        # Validate activation key
        if not isValidActivationKey(key):
            await interaction.response.send_message(f"Invalid activation key `{key}` provided!")
            return

        # Add guild to data
        existing_guilds.append({
            'id': interaction.guild_id,
            'name': interaction.guild.name,
            'key-used': key,
            'status': "activated"
        })

        # Log and save activation
        logger.log_message(f"Guild id: {interaction.guild_id} has activated its key and was added to {file}", "SUCCESS")
        saveDataToJSON(file, existing_guilds)

        await interaction.response.send_message("Guild has been successfully activated ✅")

    @app_commands.command(name="configure", description="Configure ACM Connect")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel you want the bot to post job opportunities in")
    @app_commands.describe(role="The role that gets notified on job opportunity posting")
    @log_exceptions                   # NEW
    async def configure(self, interaction: discord.Interaction,
                         channel: typing.Optional[discord.ForumChannel],
                         role: typing.Optional[discord.Role]):
        """
        Slash command to configure where job opportunities should be posted and who gets pinged.

        Args:
            interaction (discord.Interaction): The interaction context.
            channel (discord.ForumChannel, optional): Forum channel for job posts.
            role (discord.Role, optional): Role to notify when posting.
        """
        if interaction.guild is None:
            await interaction.response.send_message(f"{self.bot.user.name} can only be configured inside a guild!")
            return

        if channel is None and role is None:
            await interaction.response.send_message("No channel or role provided to configure!")
            return

        existing_guilds = getDataFromJSON(file)

        # Check if the guild has been activated
        existing_info = None
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                existing_info = existing_guild
                break

        if existing_info is None:
            await interaction.response.send_message(f"{self.bot.user.name} has not yet been activated for this guild! Please run `/activate`")
            return

        # Update channel and/or role
        channel_updated = False
        if channel is not None:
            channel_updated = channel.id != existing_info.get('channel')
            existing_info['channel'] = channel.id
        if role is not None:
            existing_info['role'] = role.id

        # Update status
        existing_info['status'] = "configured"

        # Save updated info back to the list
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                existing_guild.update(existing_info)
                break

        logger.log_message(f"Guild {get_guild_info(existing_info, self.bot)['guild']} was updated with: {existing_info}", "SETUP_COMPLETION")
        saveDataToJSON(file, existing_guilds)

        # If channel was updated, create a thread to post info
        if channel_updated:
            acm_logo = discord.File("acm_logo.png", filename="acm_logo.png")

            embed = discord.Embed(
                colour=discord.Colour(0x5865f2),
                title="Info",
                description=(
                    f"The bot has successfully been configured to post to this forum channel (<#{channel.id}>)."
                )
            )
            embed.set_thumbnail(url=f"attachment://{acm_logo.filename}")

            await channel.create_thread(
                name=f"{self.bot.user.name} | UF ACM",
                embed=embed,
                files=[acm_logo]
            )
            logger.log_message(f"Thread created in channel {channel.id} for guild {interaction.guild_id} to update posting location", "SETUP_COMPLETION")

        # Final response summarizing the setup
        if 'role' in existing_info and 'channel' in existing_info:
            role_name = interaction.guild.get_role(existing_info['role']).name
            await interaction.response.send_message(f"✅ When job opportunities are posted, they will be posted in <#{existing_info['channel']}> and ping `@{role_name}`.")
        elif 'role' in existing_info:
            role_name = interaction.guild.get_role(existing_info['role']).name
            await interaction.response.send_message(f"✅ When job opportunities are posted, they will ping `@{role_name}`. **NOTE: Forum channel has not yet been configured!**")
        else:
            await interaction.response.send_message(f"✅ When job opportunities are posted, they will be posted in <#{existing_info['channel']}>. **NOTE: Role has not yet been configured!**")


async def setup(bot):
    """
    Registers the Setup cog with the bot.

    Args:
        bot (commands.Bot): The instance of the bot to add the cog to.
    """
    await bot.add_cog(Setup(bot))

