"""Voice proxy endpoints — Sarvam TTS + STT.

Keeps the Sarvam subscription key server-side. The frontend hits:
    POST /api/voice/tts  — text → base64-encoded WAV
    POST /api/voice/stt  — audio upload (webm/wav) → transcript
"""

from __future__ import annotations

import logging
import time

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import get_settings
from app.services import tracing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

SARVAM_BASE = "https://api.sarvam.ai"


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------
class TTSRequest(BaseModel):
    text: str
    language: str = "en-IN"
    speaker: str = "anushka"  # female, warm. Alts: manisha, arya, abhilash, etc.


class TTSResponse(BaseModel):
    audio_base64: str
    mime_type: str = "audio/wav"


@router.post("/tts", response_model=TTSResponse)
@tracing.observe(name="voice.tts")
async def tts(req: TTSRequest) -> TTSResponse:
    settings = get_settings()
    if not settings.sarvam_api_key:
        raise HTTPException(500, "SARVAM_API_KEY not configured")

    text = req.text.strip()
    if not text:
        raise HTTPException(400, "empty text")
    # Sarvam TTS has a 1500-char input limit per call.
    text = text[:1400]

    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=30.0) as c:
        resp = await c.post(
            f"{SARVAM_BASE}/text-to-speech",
            headers={
                "api-subscription-key": settings.sarvam_api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "target_language_code": req.language,
                "speaker": req.speaker,
                "model": "bulbul:v2",
                "enable_preprocessing": True,
            },
        )
    latency = (time.monotonic() - t0) * 1000

    if resp.status_code >= 400:
        logger.error("sarvam tts %d: %s", resp.status_code, resp.text[:300])
        raise HTTPException(502, f"sarvam tts failed: {resp.status_code}")

    data = resp.json()
    audios = data.get("audios") or []
    if not audios:
        logger.error("sarvam tts returned no audio: %s", data)
        raise HTTPException(502, "sarvam returned no audio")

    logger.info("tts ok len=%d latency_ms=%.0f", len(text), latency)
    return TTSResponse(audio_base64=audios[0])


# ---------------------------------------------------------------------------
# STT (Sarvam Saarika)
# ---------------------------------------------------------------------------
class STTResponse(BaseModel):
    transcript: str
    language_code: str | None = None


@router.post("/stt", response_model=STTResponse)
@tracing.observe(name="voice.stt")
async def stt(
    audio: UploadFile = File(...),
    language: str = Form("en-IN"),
) -> STTResponse:
    settings = get_settings()
    if not settings.sarvam_api_key:
        raise HTTPException(500, "SARVAM_API_KEY not configured")

    content = await audio.read()
    if not content:
        raise HTTPException(400, "empty audio")

    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=45.0) as c:
        resp = await c.post(
            f"{SARVAM_BASE}/speech-to-text",
            headers={"api-subscription-key": settings.sarvam_api_key},
            data={"model": "saarika:v2.5", "language_code": language},
            files={
                "file": (
                    audio.filename or "user.webm",
                    content,
                    "application/octet-stream",
                ),
            },
        )
    latency = (time.monotonic() - t0) * 1000

    if resp.status_code >= 400:
        logger.error("sarvam stt %d: %s", resp.status_code, resp.text[:300])
        raise HTTPException(502, f"sarvam stt failed: {resp.status_code}")

    data = resp.json()
    transcript = data.get("transcript") or ""
    lang = data.get("language_code")
    logger.info(
        "stt ok bytes=%d transcript_len=%d lang=%s latency_ms=%.0f",
        len(content), len(transcript), lang, latency,
    )
    return STTResponse(transcript=transcript, language_code=lang)
