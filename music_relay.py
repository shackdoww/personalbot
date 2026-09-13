import os

import httpx
import yt_dlp
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

load_dotenv()

RELAY_SECRET = os.getenv("RELAY_SECRET")
if not RELAY_SECRET:
    raise RuntimeError("RELAY_SECRET is not set")

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stream")
async def stream(query: str, x_relay_secret: str | None = Header(default=None)):
    if x_relay_secret != RELAY_SECRET:
        raise HTTPException(status_code=401, detail="Invalid relay secret")

    try:
        info = ytdl.extract_info(query, download=False)
        if "entries" in info:
            entries = [entry for entry in info["entries"] if entry]
            if not entries:
                raise HTTPException(status_code=404, detail="No result found")
            info = entries[0]

        stream_url = info.get("url")
        if not stream_url:
            raise HTTPException(status_code=404, detail="No audio stream found")

        client = httpx.AsyncClient(timeout=None, follow_redirects=True)
        response = await client.stream("GET", stream_url, headers={"User-Agent": "Mozilla/5.0"}).__aenter__()
        if response.status_code >= 400:
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=response.status_code, detail="Upstream stream failed")

        async def content():
            try:
                async for chunk in response.aiter_bytes(65536):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(
            content(),
            media_type=response.headers.get("content-type", "audio/webm"),
            headers={"Cache-Control": "no-cache"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Music relay error: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=f"yt-dlp error: {type(exc).__name__}")
