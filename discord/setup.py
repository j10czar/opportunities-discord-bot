import discord
from discord import app_commands
from discord.ext import commands
import os
from logger import Logger
import typing

from util import getDataFromJSON, saveDataToJSON, isValidActivationKey, get_guild_info

logger = Logger()

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # Remove guild from guilds.json
        existing_guilds = getDataFromJSON("guilds.json")
        updated_guilds = [g for g in existing_guilds if g['id'] != guild.id]
        saveDataToJSON("guilds.json", updated_guilds)
        guild_info = get_guild_info({'id': guild.id}, self.bot)
        logger.log_message(f"Guild {guild_info['guild']} with guild id: {guild.id} removed from guilds.json", "SUCCESS")


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        guild_info = get_guild_info({'id': guild.id}, self.bot)
        logger.log_message(f"Bot was added to guild: {guild_info['guild']} with id: {guild.id} but has not been setup yet", "SUCCESS")
    
    # Setup activate command
    @app_commands.command(name="activate", description=f"Activate ACM Connect")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(key="Activation key for ACM Connect")
    async def activate(self, interaction: discord.Interaction, key: str):
        if interaction.guild is None:
            await interaction.response.send_message(f"{self.bot.user.name} can only be activated inside a guild!")
            return
        
        existing_guilds = getDataFromJSON("guilds.json")
        
        # Check if guild is already activated
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                await interaction.response.send_message(f"{self.bot.user.name} is already activated for this guild!")
                return
        
        # Validate activation key
        if not isValidActivationKey(key):
            await interaction.response.send_message(f"Invalid activation key `{key}` provided!")
            return
        
        # Activate guild
        existing_guilds.append({
            'id': interaction.guild_id
        })
        saveDataToJSON("guilds.json", existing_guilds)
        logger.log_message(f"Guild id: {interaction.guild_id} has activated its key and was added to guilds.json", "SUCCESS")

        await interaction.response.send_message("Guild has been successfully activated ✅")
    
    # Setup configure command
    @app_commands.command(name="configure", description="Configure ACM Connect")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel you want the bot to post job opportunities in")
    @app_commands.describe(role="The role that gets notified on job opportunity posting")
    async def configure(self, interaction: discord.Interaction, channel: typing.Optional[discord.ForumChannel], role: typing.Optional[discord.Role]):
        if interaction.guild is None:
            await interaction.response.send_message(f"{self.bot.user.name} can only be configured inside a guild!")
            return
        
        if channel is None and role is None:
            await interaction.response.send_message("No channel or role provided to configure!")
            return
        
        existing_guilds = getDataFromJSON("guilds.json")
        
        # Check if guild is not yet activated
        existing_info = None
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                existing_info = existing_guild
                break
        
        if existing_info is None:
            await interaction.response.send_message(f"{self.bot.user.name} has not yet been activated for this guild! Please run `/activate`")
            return

        # Update guild info
        channel_updated = False
        if channel is not None:
            channel_updated = channel.id != existing_info.get('channel')
            existing_info['channel'] = channel.id
        if role is not None:
            existing_info['role'] = role.id
        
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                existing_guild.update(existing_info)
                break

        saveDataToJSON("guilds.json", existing_guilds)
        logger.log_message(f"Guild {get_guild_info(existing_info, self.bot)['guild']} was updated with: {existing_info}", "SETUP_COMPLETION")
        
        # If channel was updated, send info message in channel
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
        
        # Respond to slash command
        if 'role' in existing_info and 'channel' in existing_info:
            role_name = interaction.guild.get_role(existing_info['role']).name
            await interaction.response.send_message(f"✅ When job opportunities are posted, they will be posted in <#{existing_info['channel']}> and ping `@{role_name}`.")
        elif 'role' in existing_info:
            role_name = interaction.guild.get_role(existing_info['role']).name
            await interaction.response.send_message(f"✅ When job opportunities are posted, they will ping `@{role_name}`. **NOTE: Forum channel has not yet been configured!**")
        else:
            await interaction.response.send_message(f"✅ When job opportunities are posted, they will be posted in <#{existing_info['channel']}>. **NOTE: Role has not yet been configured!**")


async def setup(bot):
    await bot.add_cog(Setup(bot))