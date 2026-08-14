"""스캔 PDF·이미지 본문 인식. RapidOCR 우선, 실패 시 LLM 비전으로 넘긴다."""

from __future__ import annotations

import io
from collections.abc import Callable
from functools import lru_cache

from PIL import Image

from src.extract_errors import ExtractError

OcrFallback = Callable[[Image.Image], str]
_RAPID_UNAVAILABLE = False


def ocr_image_bytes(data: bytes, fallback: OcrFallback | None = None) -> str:
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise ExtractError(f"이미지를 열지 못했습니다: {exc}") from exc
    return ocr_pil(image, fallback=fallback)


def ocr_pil(image: Image.Image, fallback: OcrFallback | None = None) -> str:
    try:
        text = _rapid_ocr(image)
        if text.strip():
            return text
    except Exception:
        text = ""
    if fallback is not None:
        text = (fallback(image) or "").strip()
        if text:
            return text
    if text:
        return text
    raise ExtractError(
        "이미지에서 글자를 읽지 못했습니다. 스캔본은 OpenAI 또는 Gemini 엔진이 필요합니다."
    )


def _rapid_ocr(image: Image.Image) -> str:
    global _RAPID_UNAVAILABLE
    if _RAPID_UNAVAILABLE:
        raise RuntimeError("RapidOCR를 이 환경에서 사용할 수 없습니다.")
    import numpy as np

    try:
        engine = _engine()
        result, _elapsed = engine(np.array(image.convert("RGB")))
    except Exception:
        _RAPID_UNAVAILABLE = True
        raise
    if not result:
        return ""
    lines: list[str] = []
    for item in result:
        if not item or len(item) < 2:
            continue
        piece = str(item[1]).strip()
        if piece:
            lines.append(piece)
    return "\n".join(lines).strip()


@lru_cache(maxsize=1)
def _engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()
