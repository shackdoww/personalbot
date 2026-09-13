import asyncio
import base64
import os
import time

import edge_tts
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from google import genai
from google.genai import types

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
RELAY_SECRET = os.getenv("RELAY_SECRET")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-GuyNeural")

if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

if not RELAY_SECRET:
    raise RuntimeError("RELAY_SECRET is not set")

client = genai.Client(api_key=API_KEY)
app = FastAPI()

SYSTEM_PROMPT = """You are Itot, a conversational Discord voice assistant.
Speak naturally and briefly because your answer will be read aloud.
Do not use markdown, bullet lists, emojis, or stage directions.
Sound like a real person having a casual conversation.
Keep normal answers to one or two short sentences unless more detail is necessary.
If the user asks a simple question, answer directly.
If the audio contains no understandable speech, return an empty response.
"""


async def make_tts(text):
    start = time.perf_counter()
    audio = bytearray()

    communicate = edge_tts.Communicate(text, TTS_VOICE)

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])

    result = bytes(audio)
    print(f"Voice TTS: {time.perf_counter() - start:.2f}s, {len(result)} bytes")
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    user_name: str = Form("User"),
    x_relay_secret: str | None = Header(default=None),
):
    request_start = time.perf_counter()

    if x_relay_secret != RELAY_SECRET:
        raise HTTPException(status_code=401, detail="Invalid relay secret")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio")

    try:
        gemini_start = time.perf_counter()

        audio_part = types.Part.from_bytes(
            data=audio_bytes,
            mime_type="audio/wav",
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=MODEL,
            contents=[
                SYSTEM_PROMPT,
                f"The speaker is named {user_name}.",
                audio_part,
                "Transcribe what the speaker said and respond to it.",
            ],
            config=types.GenerateContentConfig(
                max_output_tokens=120,
            ),
        )

        print(f"Gemini: {time.perf_counter() - gemini_start:.2f}s")

        text = (response.text or "").strip()

        if not text:
            print(f"Voice request total: {time.perf_counter() - request_start:.2f}s")
            return {"response": "", "audio": ""}

        tts_audio = await make_tts(text)

        print(f"Voice request total: {time.perf_counter() - request_start:.2f}s")

        return {
            "response": text,
            "audio": base64.b64encode(tts_audio).decode("ascii"),
        }

    except Exception as exc:
        print(f"Voice relay error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice AI error: {type(exc).__name__}",
        )
