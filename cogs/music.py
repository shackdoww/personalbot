import asyncio
import os
from urllib.parse import quote

import discord
from discord import app_commands
from discord.ext import commands

MUSIC_RELAY_URL = os.getenv("MUSIC_RELAY_URL")
RELAY_SECRET = os.getenv("RELAY_SECRET")


class GuildPlayer:
    def __init__(self):
        self.queue = []
        self.current = None
        self.voice = None


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    def get_player(self, guild_id):
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer()
        return self.players[guild_id]

    def stream_url(self, query):
        if not MUSIC_RELAY_URL or not RELAY_SECRET:
            return None
        return f"{MUSIC_RELAY_URL}?query={quote(query, safe='')}"

    async def start_next(self, guild):
        player = self.get_player(guild.id)
        if not player.voice or not player.voice.is_connected():
            return
        if player.voice.is_playing() or player.voice.is_paused():
            return
        if not player.queue:
            player.current = None
            return

        player.current = player.queue.pop(0)
        ffmpeg_options = {
            "before_options": (
                "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
                f"-headers \"X-Relay-Secret: {RELAY_SECRET}\\r\\n\""
            ),
            "options": "-vn",
        }
        source = discord.FFmpegPCMAudio(player.current["url"], **ffmpeg_options)

        def after_play(error):
            if error:
                print(f"Music playback error: {error}")
            asyncio.run_coroutine_threadsafe(self.start_next(guild), self.bot.loop)

        player.voice.play(source, after=after_play)

    async def ensure_voice(self, interaction):
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.")
            return None
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send("Join a voice channel first.")
            return None

        player = self.get_player(interaction.guild.id)
        channel = interaction.user.voice.channel
        if player.voice and player.voice.is_connected():
            if player.voice.channel != channel:
                await player.voice.move_to(channel)
        else:
            player.voice = await channel.connect()
        return player

    @app_commands.command(name="play", description="Play a song or YouTube search result.")
    @app_commands.describe(query="Song name or URL")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        player = await self.ensure_voice(interaction)
        if not player:
            return

        if not MUSIC_RELAY_URL or not RELAY_SECRET:
            await interaction.followup.send("❌ Music relay is not configured on the bot.")
            return

        stream_url = self.stream_url(query)
        track = {
            "title": query,
            "url": stream_url,
            "webpage": query,
        }
        player.queue.append(track)
        position = len(player.queue)
        await self.start_next(interaction.guild)

        if player.current == track:
            await interaction.followup.send(f"🎵 Now playing **{query}**")
        else:
            await interaction.followup.send(f"🎵 Added **{query}** to the queue at position {position}.")

    @app_commands.command(name="pause", description="Pause the current song.")
    async def pause(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild.id)
        if player.voice and player.voice.is_playing():
            player.voice.pause()
            await interaction.response.send_message("⏸️ Paused.")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="resume", description="Resume the current song.")
    async def resume(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild.id)
        if player.voice and player.voice.is_paused():
            player.voice.resume()
            await interaction.response.send_message("▶️ Resumed.")
        else:
            await interaction.response.send_message("Nothing is paused.")

    @app_commands.command(name="skip", description="Skip the current song.")
    async def skip(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild.id)
        if player.voice and (player.voice.is_playing() or player.voice.is_paused()):
            player.voice.stop()
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="stop", description="Stop music and disconnect.")
    async def stop(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild.id)
        player.queue.clear()
        player.current = None
        if player.voice and player.voice.is_connected():
            await player.voice.disconnect()
        player.voice = None
        await interaction.response.send_message("⏹️ Stopped and disconnected.")

    @app_commands.command(name="queue", description="Show the music queue.")
    async def queue(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild.id)
        lines = []
        if player.current:
            lines.append(f"**Now:** {player.current['title']}")
        if player.queue:
            lines.extend(f"`{i}.` {track['title']}" for i, track in enumerate(player.queue, 1))
        if not lines:
            lines.append("The queue is empty.")
        await interaction.response.send_message("🎵 **Queue**\n" + "\n".join(lines[:21]))

    @app_commands.command(name="nowplaying", description="Show the current song.")
    async def nowplaying(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild.id)
        if player.current:
            await interaction.response.send_message(f"🎶 **Now playing:** {player.current['title']}")
        else:
            await interaction.response.send_message("Nothing is playing.")

    @app_commands.command(name="join", description="Join your voice channel.")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer()
        player = await self.ensure_voice(interaction)
        if player:
            await interaction.followup.send(f"🔊 Joined **{player.voice.channel.name}**.")


async def setup(bot):
    await bot.add_cog(Music(bot))
