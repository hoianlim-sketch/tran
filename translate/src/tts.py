"""한국어 3줄 요약을 MP3로 합성한다."""

from __future__ import annotations

import asyncio
import io
from concurrent.futures import ThreadPoolExecutor

VOICES = {
    "여성": "ko-KR-SunHiNeural",
    "남성": "ko-KR-InJoonNeural",
}


class TTSError(RuntimeError):
    pass


def spoken_script(lines: list[str]) -> str:
    cleaned = [line.strip().rstrip(".。") for line in lines if (line or "").strip()]
    if not cleaned:
        return ""
    return ". ".join(cleaned) + "."


def synthesize_korean(text: str, voice_label: str = "여성") -> bytes:
    script = (text or "").strip()
    if not script:
        raise TTSError("읽을 3줄 요약이 없습니다.")
    voice = VOICES.get(voice_label, VOICES["여성"])
    try:
        return _edge_tts(script, voice)
    except Exception:
        return _gtts(script)


def _edge_tts(text: str, voice: str) -> bytes:
    import edge_tts

    async def _run() -> bytes:
        chunks: list[bytes] = []
        stream = edge_tts.Communicate(text, voice)
        async for item in stream.stream():
            if item["type"] == "audio":
                chunks.append(item["data"])
        audio = b"".join(chunks)
        if not audio:
            raise TTSError("음성 데이터가 비었습니다.")
        return audio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run()).result()


def _gtts(text: str) -> bytes:
    try:
        from gtts import gTTS
    except ImportError as exc:
        raise TTSError("TTS 패키지가 없습니다. pip install edge-tts gTTS") from exc
    buffer = io.BytesIO()
    gTTS(text=text, lang="ko").write_to_fp(buffer)
    data = buffer.getvalue()
    if not data:
        raise TTSError("음성 합성에 실패했습니다.")
    return data
