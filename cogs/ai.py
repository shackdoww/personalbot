import os

import discord
import httpx
from discord import app_commands
from discord.ext import commands


class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.relay_url = os.getenv("AI_RELAY_URL")
        self.relay_secret = os.getenv("RELAY_SECRET")

    async def ask_ai(self, prompt: str) -> str:
        if not self.relay_url or not self.relay_secret:
            return "The AI relay is not configured yet."

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                self.relay_url,
                headers={"X-Relay-Secret": self.relay_secret},
                json={"prompt": prompt},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "") or "I couldn't generate a response."

    async def send_response(self, send, answer: str):
        if not answer:
            answer = "I couldn't generate a response."

        for i in range(0, len(answer), 2000):
            await send(answer[i:i + 2000])

    @app_commands.command(name="ask", description="Ask the AI assistant something.")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)
        try:
            answer = await self.ask_ai(question)
            await self.send_response(interaction.followup.send, answer)
        except Exception as exc:
            await interaction.followup.send(f"AI error: `{type(exc).__name__}`")

    @commands.command(name="ask")
    async def ask_prefix(self, ctx, *, question: str):
        async with ctx.typing():
            try:
                answer = await self.ask_ai(question)
                await self.send_response(ctx.send, answer)
            except Exception as exc:
                await ctx.send(f"AI error: `{type(exc).__name__}`")


async def setup(bot):
    await bot.add_cog(AI(bot))
