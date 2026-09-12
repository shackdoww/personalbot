import os
import discord
from discord import app_commands
from discord.ext import commands
from openai import OpenAI


class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    async def ask_ai(self, prompt: str) -> str:
        if not self.client:
            return "The AI assistant is not configured yet. Set `OPENAI_API_KEY` in `.env`."

        response = await self.bot.loop.run_in_executor(
            None,
            lambda: self.client.responses.create(
                model=self.model,
                instructions="You are PersonalBot, a helpful and concise Discord AI assistant. Use plain language. Keep Discord replies reasonably short unless the user asks for detail.",
                input=prompt,
                max_output_tokens=700,
            ),
        )
        return response.output_text or "I couldn't generate a response."

    @app_commands.command(name="ask", description="Ask the AI assistant something.")
    @app_commands.describe(question="Your question")
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)
        try:
            answer = await self.ask_ai(question)
            await interaction.followup.send(answer[:2000])
        except Exception as exc:
            await interaction.followup.send(f"AI error: `{type(exc).__name__}`")

    @commands.command(name="ask")
    async def ask_prefix(self, ctx, *, question: str):
        async with ctx.typing():
            try:
                answer = await self.ask_ai(question)
                await ctx.send(answer[:2000])
            except Exception as exc:
                await ctx.send(f"AI error: `{type(exc).__name__}`")


async def setup(bot):
    await bot.add_cog(AI(bot))
