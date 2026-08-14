"""텍스트 분할, 언어 감지, 파일명 유틸."""

from __future__ import annotations

import re
from pathlib import Path

try:
    from langdetect import DetectorFactory, detect
    from langdetect.lang_detect_exception import LangDetectException

    DetectorFactory.seed = 0
except ImportError:  # pragma: no cover
    detect = None
    LangDetectException = Exception


LANGUAGE_NAMES = {
    "ko": "한국어",
    "en": "영어",
    "ja": "일본어",
    "zh-cn": "중국어(간체)",
    "zh-tw": "중국어(번체)",
    "zh": "중국어",
    "es": "스페인어",
    "fr": "프랑스어",
    "de": "독일어",
    "ru": "러시아어",
    "pt": "포르투갈어",
    "it": "이탈리아어",
    "vi": "베트남어",
    "th": "태국어",
    "id": "인도네시아어",
    "ar": "아랍어",
    "hi": "힌디어",
    "nl": "네덜란드어",
    "pl": "폴란드어",
    "tr": "터키어",
}


def language_label(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)


def detect_language(text: str) -> str:
    sample = (text or "").strip()
    if not sample:
        return "unknown"
    if detect is None:
        return "unknown"
    try:
        return detect(sample[:4000])
    except LangDetectException:
        return "unknown"


def split_into_chunks(text: str, max_chars: int = 3500) -> list[str]:
    """문장 경계를 최대한 유지하면서 긴 글을 나눈다."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[\.!?。！？\n])\s+", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        piece = sentence.strip()
        if not piece:
            continue
        extra = len(piece) + (1 if current else 0)
        if current and current_len + extra > max_chars:
            chunks.append("\n".join(current))
            current = [piece]
            current_len = len(piece)
        else:
            current.append(piece)
            current_len += extra

    if current:
        chunks.append("\n".join(current))

    overflow: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars * 2:
            overflow.append(chunk)
        else:
            for i in range(0, len(chunk), max_chars):
                overflow.append(chunk[i : i + max_chars])
    return overflow


def unpack_marked_units(raw: str) -> dict[int, str]:
    chunks = re.split(r"<<<(\d+)>>>", raw or "")
    mapping: dict[int, str] = {}
    index = 1
    while index + 1 < len(chunks):
        try:
            key = int(chunks[index])
        except ValueError:
            index += 2
            continue
        mapping[key] = chunks[index + 1].strip()
        index += 2
    return mapping


def batch_jobs(jobs: list[tuple[int, str]], max_chars: int = 2800) -> list[list[tuple[int, str]]]:
    batches: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    size = 0
    for item in jobs:
        extra = len(item[1]) + 12
        if current and size + extra > max_chars:
            batches.append(current)
            current = [item]
            size = extra
        else:
            current.append(item)
            size += extra
    if current:
        batches.append(current)
    return batches


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w\-가-힣]+", "_", stem).strip("_")
    return cleaned or "document"
