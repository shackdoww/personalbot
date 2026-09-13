import asyncio
import base64
import os
import time

import edge_tts
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from groq import Groq

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-20b")
STT_MODEL = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
RELAY_SECRET = os.getenv("RELAY_SECRET")
TTS_VOICE = os.getenv("TTS_VOICE", "en-US-GuyNeural")

if not API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set")

if not RELAY_SECRET:
    raise RuntimeError("RELAY_SECRET is not set")

client = Groq(api_key=API_KEY)
app = FastAPI()

SYSTEM_PROMPT = """You are Itot, a conversational Discord voice assistant.
Speak naturally and briefly because your answer will be read aloud.
Do not use markdown, bullet lists, emojis, or stage directions.
Sound like a real person having a casual conversation.
Keep normal answers to one or two short sentences unless more detail is necessary.
If the user asks a simple question, answer directly.
"""


async def transcribe_audio(audio_bytes):
    start = time.perf_counter()

    transcription = await asyncio.to_thread(
        client.audio.transcriptions.create,
        file=("voice.wav", audio_bytes),
        model=STT_MODEL,
        language="en",
        response_format="text",
        temperature=0.0,
    )

    text = getattr(transcription, "text", transcription)
    text = (text or "").strip()

    print(f"Groq STT: {time.perf_counter() - start:.2f}s")
    return text


async def generate_response(text, user_name):
    start = time.perf_counter()

    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"The speaker is named {user_name}. They said: {text}",
            },
        ],
        max_completion_tokens=120,
        temperature=0.7,
    )

    answer = (response.choices[0].message.content or "").strip()
    print(f"Groq LLM: {time.perf_counter() - start:.2f}s")
    return answer


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
        transcript = await transcribe_audio(audio_bytes)

        if not transcript:
            print(f"Voice request total: {time.perf_counter() - request_start:.2f}s")
            return {"response": "", "audio": ""}

        print(f"Voice STT [{user_name}]: {transcript}")

        text = await generate_response(transcript, user_name)

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
        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            print("Groq rate limit or quota reached")
            raise HTTPException(
                status_code=429,
                detail="Groq rate limit or free-tier quota reached. Try again later.",
            )

        print(f"Voice relay error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice AI error: {type(exc).__name__}",
        )
