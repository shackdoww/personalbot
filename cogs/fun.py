import random
import discord
from discord import app_commands
from discord.ext import commands


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.describe(question="Your question")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        answers = [
            "Yes.", "No.", "Definitely.", "Probably not.",
            "Ask again later.", "Absolutely.", "I wouldn't count on it.",
            "Signs point to yes.", "Signs point to no."
        ]
        await interaction.response.send_message(f"🎱 **{question}**\n{random.choice(answers)}")

    @commands.command(name="8ball")
    async def eight_ball_prefix(self, ctx, *, question: str):
        answers = ["Yes.", "No.", "Definitely.", "Probably not.", "Ask again later.", "Absolutely."]
        await ctx.send(f"🎱 {random.choice(answers)}")

    @app_commands.command(name="coinflip", description="Flip a coin.")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🪙 **{random.choice(['Heads', 'Tails'])}!**")

    @app_commands.command(name="roll", description="Roll a die.")
    @app_commands.describe(sides="Number of sides")
    async def roll(self, interaction: discord.Interaction, sides: app_commands.Range[int, 2, 1000] = 6):
        await interaction.response.send_message(f"🎲 You rolled **{random.randint(1, sides)}** / {sides}")

    @app_commands.command(name="choose", description="Choose between options separated by commas.")
    @app_commands.describe(options="Example: pizza, burger, ramen")
    async def choose(self, interaction: discord.Interaction, options: str):
        choices = [x.strip() for x in options.split(",") if x.strip()]
        if len(choices) < 2:
            await interaction.response.send_message("Give me at least two options separated by commas.")
            return
        await interaction.response.send_message(f"I choose **{random.choice(choices)}**.")

    @app_commands.command(name="ship", description="Calculate a totally scientific compatibility score.")
    @app_commands.describe(first="First name", second="Second name")
    async def ship(self, interaction: discord.Interaction, first: str, second: str):
        score = (sum(ord(c.lower()) for c in first + second) * 7) % 101
        await interaction.response.send_message(f"💘 **{first} + {second} = {score}%** compatibility")

    @app_commands.command(name="joke", description="Tell a random joke.")
    async def joke(self, interaction: discord.Interaction):
        jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            "There are 10 kinds of people: those who understand binary and those who don't.",
            "A SQL query walks into a bar, walks up to two tables and asks: Can I join you?",
            "I would tell you a UDP joke, but you might not get it."
        ]
        await interaction.response.send_message(f"😂 {random.choice(jokes)}")


async def setup(bot):
    await bot.add_cog(Fun(bot))
