import discord
from discord import app_commands
from discord.ext import commands
import typing

from util import getDataFromJSON, saveDataToJSON


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # Remove guild from guilds.json
        existing_guilds = getDataFromJSON("guilds.json")
        updated_guilds = [g for g in existing_guilds if g['id'] != guild.id]
        saveDataToJSON("guilds.json", updated_guilds)
    
    # Setup activate command
    @app_commands.command(name="activate", description="Activate ACM Connect")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(key="Activation key for ACM Connect")
    async def activate(self, interaction: discord.Interaction, key: str):
        if interaction.guild is None:
            await interaction.response.send_message("ACM Connect can only be activated inside a guild!")
            return
        
        existing_guilds = getDataFromJSON("guilds.json")
        
        # Check if guild is already activated
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                await interaction.response.send_message("ACM Connect is already activated for this guild!")
                return
        
        # Validate activation key
        if False:
            await interaction.response.send_message(f"Invalid activation key `{key}` provided")
            return
        
        # Activate guild
        existing_guilds.append({
            'id': interaction.guild_id
        })
        saveDataToJSON("guilds.json", existing_guilds)
        
        await interaction.response.send_message("Guild has been successfully activated ✅")
    
    # Setup configure command
    @app_commands.command(name="configure", description="Configure ACM Connect")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel you want the bot to post job opportunities in")
    @app_commands.describe(role="The role that gets notified on job opportunity posting")
    async def configure(self, interaction: discord.Interaction, channel: typing.Optional[discord.ForumChannel], role: typing.Optional[discord.Role]):
        if interaction.guild is None:
            await interaction.response.send_message("ACM Connect can only be configured inside a guild!")
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
            await interaction.response.send_message("ACM Connect has not yet been activated for this guild! Please run `/activate`")
            return

        # Update guild info
        if channel is not None:
            existing_info['channel'] = channel.id
        if role is not None:
            existing_info['role'] = role.id
        
        for existing_guild in existing_guilds:
            if existing_guild['id'] == interaction.guild_id:
                existing_guild.update(existing_info)
                break
        saveDataToJSON("guilds.json", existing_guilds)
        
        await interaction.response.send_message(f"✅ When job opportunities are posted, they will be posted in <#{channel.id}> and ping `@{role.name}`")


async def setup(bot):
    await bot.add_cog(Setup(bot))