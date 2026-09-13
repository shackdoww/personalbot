import asyncio
import base64
import io
import os
import tempfile
import time
import wave
from array import array

import discord
import httpx
from discord import app_commands
from discord.ext import commands, voice_recv


class VoiceSession:
    def __init__(self):
        self.buffers = {}
        self.last_audio = {}
        self.flush_tasks = {}
        self.processing = False


class VoiceAI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = {}
        self.relay_url = os.getenv("VOICE_AI_RELAY_URL")
        self.relay_secret = os.getenv("RELAY_SECRET")
        self.silence_seconds = 0.45
        self.min_audio_seconds = 0.30
        self.http = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    def cog_unload(self):
        asyncio.create_task(self.http.aclose())

    def get_session(self, guild_id):
        if guild_id not in self.sessions:
            self.sessions[guild_id] = VoiceSession()
        return self.sessions[guild_id]

    @staticmethod
    def rms(pcm):
        samples = array("h")
        samples.frombytes(pcm)
        if not samples:
            return 0
        total = sum(sample * sample for sample in samples)
        return (total / len(samples)) ** 0.5

    def wav_bytes(self, pcm):
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(pcm)
        return output.getvalue()

    async def send_to_relay(self, pcm, member):
        if not self.relay_url or not self.relay_secret:
            return "Voice AI relay is not configured yet.", None

        start = time.perf_counter()
        wav_data = self.wav_bytes(pcm)

        response = await self.http.post(
            self.relay_url,
            headers={"X-Relay-Secret": self.relay_secret},
            files={"audio": ("voice.wav", wav_data, "audio/wav")},
            data={"user_name": member.display_name},
        )
        response.raise_for_status()
        data = response.json()

        elapsed = time.perf_counter() - start
        print(f"Voice relay round trip: {elapsed:.2f}s")

        text = data.get("response", "")
        audio_b64 = data.get("audio", "")
        audio = base64.b64decode(audio_b64) if audio_b64 else None
        return text or "I couldn't understand that.", audio

    async def play_audio(self, voice, audio):
        if not audio or not voice or not voice.is_connected():
            return

        start = time.perf_counter()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp:
            temp.write(audio)
            path = temp.name

        finished = asyncio.Event()

        def after(error):
            if error:
                print(f"Voice AI playback error: {error}")
            self.bot.loop.call_soon_threadsafe(finished.set)

        try:
            if voice.is_playing():
                voice.stop()

            source = discord.FFmpegPCMAudio(path, options="-vn")
            voice.play(source, after=after)
            await finished.wait()

            print(f"Voice playback: {time.perf_counter() - start:.2f}s")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    async def process_user_audio(self, guild, member):
        session = self.get_session(guild.id)
        if session.processing:
            return

        pcm = b"".join(session.buffers.pop(member.id, []))
        session.last_audio.pop(member.id, None)

        if len(pcm) < int(48000 * 2 * 2 * self.min_audio_seconds):
            return
        if self.rms(pcm) < 250:
            return

        session.processing = True
        start = time.perf_counter()

        try:
            voice = guild.voice_client
            text, audio = await self.send_to_relay(pcm, member)

            if text:
                print(f"Voice AI [{member.display_name}]: {text}")

            if voice and voice.is_connected():
                await self.play_audio(voice, audio)

            print(f"Voice request total: {time.perf_counter() - start:.2f}s")
        except Exception as exc:
            print(f"Voice AI error: {type(exc).__name__}: {exc}")
        finally:
            session.processing = False

    async def flush_later(self, guild, member):
        await asyncio.sleep(self.silence_seconds)

        session = self.get_session(guild.id)
        last = session.last_audio.get(member.id, 0)

        if time.monotonic() - last >= self.silence_seconds:
            await self.process_user_audio(guild, member)
        else:
            session.flush_tasks[member.id] = asyncio.create_task(
                self.flush_later(guild, member)
            )

    def receive_callback(self, guild, user, data):
        if user is None or user.bot:
            return
        if self.bot.user and user.id == self.bot.user.id:
            return

        pcm = data.pcm
        if not pcm:
            return

        session = self.get_session(guild.id)
        session.buffers.setdefault(user.id, []).append(pcm)
        session.last_audio[user.id] = time.monotonic()

        task = session.flush_tasks.get(user.id)
        if task and not task.done():
            task.cancel()

        future = asyncio.run_coroutine_threadsafe(
            self.flush_later(guild, user),
            self.bot.loop,
        )
        session.flush_tasks[user.id] = future

    async def start_voice(self, guild, channel):
        current = guild.voice_client

        if current:
            if current.channel != channel:
                await current.move_to(channel)
            voice = current
        else:
            voice = await channel.connect(cls=voice_recv.VoiceRecvClient)

        voice.stop_listening()
        voice.listen(
            voice_recv.BasicSink(
                lambda user, data: self.receive_callback(guild, user, data)
            )
        )
        return voice

    @app_commands.command(
        name="talk",
        description="Join your voice channel and start the AI voice assistant.",
    )
    async def talk(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server."
            )
            return

        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("Join a voice channel first.")
            return

        if not self.relay_url or not self.relay_secret:
            await interaction.response.send_message(
                "Voice AI relay is not configured yet."
            )
            return

        await interaction.response.defer()

        try:
            voice = await self.start_voice(
                interaction.guild,
                interaction.user.voice.channel,
            )
            await interaction.followup.send(
                f"🗣️ I'm listening in **{voice.channel.name}**. "
                "Talk normally and I'll respond."
            )
        except Exception as exc:
            await interaction.followup.send(
                f"❌ Could not start voice AI: `{type(exc).__name__}`"
            )
            print(f"Voice AI join error: {type(exc).__name__}: {exc}")

    @commands.command(name="talk")
    async def talk_prefix(self, ctx):
        if not ctx.guild:
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("Join a voice channel first.")
            return

        if not self.relay_url or not self.relay_secret:
            await ctx.send("Voice AI relay is not configured yet.")
            return

        try:
            voice = await self.start_voice(ctx.guild, ctx.author.voice.channel)
            await ctx.send(f"🗣️ I'm listening in **{voice.channel.name}**.")
        except Exception as exc:
            await ctx.send(f"❌ Could not start voice AI: `{type(exc).__name__}`")

    @app_commands.command(
        name="shutup",
        description="Stop the AI voice assistant and leave VC.",
    )
    async def shutup(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This command can only be used in a server."
            )
            return

        voice = interaction.guild.voice_client
        if voice:
            voice.stop()
            await voice.disconnect()

        self.sessions.pop(interaction.guild.id, None)
        await interaction.response.send_message("🔇 Voice AI stopped.")

    @commands.command(name="shutup")
    async def shutup_prefix(self, ctx):
        if not ctx.guild:
            return

        voice = ctx.guild.voice_client
        if voice:
            voice.stop()
            await voice.disconnect()

        self.sessions.pop(ctx.guild.id, None)
        await ctx.send("🔇 Voice AI stopped.")


async def setup(bot):
    await bot.add_cog(VoiceAI(bot))
