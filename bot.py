import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    for extension in ("cogs.general", "cogs.fun", "cogs.ai", "cogs.music"):
        try:
            await bot.load_extension(extension)
        except commands.ExtensionAlreadyLoaded:
            pass
    await bot.tree.sync()
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Connected to {len(bot.guilds)} server(s)")


@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(title="PersonalBot", description="AI, music, and fun commands.")
    embed.add_field(name="AI", value="`/ask` or `!ask`", inline=False)
    embed.add_field(name="Music", value="`/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue`, `/nowplaying`", inline=False)
    embed.add_field(name="Fun", value="`/8ball`, `/coinflip`, `/roll`, `/choose`, `/ship`, `/joke`", inline=False)
    await ctx.send(embed=embed)


bot.run(TOKEN)
