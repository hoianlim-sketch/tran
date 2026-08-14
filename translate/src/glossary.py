"""DeepL/Papago 스타일 용어집 파싱."""

from __future__ import annotations

import re

_SEPARATORS = (" = ", " → ", " -> ", " => ", "=", ":", "→")


def parse_glossary(raw: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        source = target = ""
        for sep in _SEPARATORS:
            if sep in line:
                left, right = line.split(sep, 1)
                source, target = left.strip(), right.strip()
                break
        if not source or not target:
            continue
        key = source.lower()
        if key in seen:
            continue
        seen.add(key)
        pairs.append((source, target))
    return pairs


def glossary_block(pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    lines = "\n".join(f"- {src} → {dst}" for src, dst in pairs)
    return (
        "용어집을 반드시 지키세요. 왼쪽 원문 표현은 항상 오른쪽 한국어로만 옮기고, "
        "같은 문서는 표기를 바꾸지 마세요.\n"
        f"{lines}"
    )


def apply_glossary(text: str, pairs: list[tuple[str, str]]) -> str:
    """기계번역 결과에서 원문 용어가 남은 경우 한국어 표기로 치환한다."""
    result = text or ""
    ordered = sorted(pairs, key=lambda item: len(item[0]), reverse=True)
    for source, target in ordered:
        if not source:
            continue
        result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
    return result
