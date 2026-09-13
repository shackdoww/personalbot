import base64
import os
import tempfile

import edge_tts
from fastapi import FastAPI, File, Header, HTTPException, UploadFile, Form
from google import genai
from google.genai import types
from dotenv import load_dotenv

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
If the user asks a simple question, answer directly.
"""


@app.get("/health")
async def health():
    return {"status": "ok"}


async def make_tts(text):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp:
        path = temp.name

    try:
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save(path)
        with open(path, "rb") as audio_file:
            return audio_file.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    user_name: str = Form("User"),
    x_relay_secret: str | None = Header(default=None),
):
    if x_relay_secret != RELAY_SECRET:
        raise HTTPException(status_code=401, detail="Invalid relay secret")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio")

    try:
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                SYSTEM_PROMPT,
                f"The speaker is named {user_name}.",
                audio_part,
                "Transcribe what the speaker said and respond to it. If there is no understandable speech, reply with an empty response.",
            ],
        )

        text = (response.text or "").strip()
        if not text:
            return {"response": "", "audio": ""}

        tts_audio = await make_tts(text)
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
