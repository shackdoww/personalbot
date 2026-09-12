import discord
from discord import app_commands
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot latency.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.bot.latency * 1000)} ms")

    @commands.command(name="ping")
    async def ping_prefix(self, ctx):
        await ctx.send(f"Pong! {round(self.bot.latency * 1000)} ms")

    @app_commands.command(name="about", description="Show information about PersonalBot.")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(title="PersonalBot", description="A personal Discord bot with AI, music, and fun commands.")
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)))
        embed.add_field(name="Library", value="discord.py")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Show the bot commands.")
    async def help_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(title="PersonalBot Commands")
        embed.add_field(name="AI", value="`/ask` or `!ask <question>`", inline=False)
        embed.add_field(name="Music", value="`/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue`, `/nowplaying`", inline=False)
        embed.add_field(name="Fun", value="`/8ball`, `/coinflip`, `/roll`, `/choose`, `/ship`, `/joke`", inline=False)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(General(bot))
