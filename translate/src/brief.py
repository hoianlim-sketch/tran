"""Acrobat/Notion 스타일 구조화 브리핑."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field


@dataclass
class OutlineItem:
    title: str = ""
    summary: str = ""


@dataclass
class Brief:
    tldr: str = ""
    key_points: list[str] = field(default_factory=list)
    outline: list[OutlineItem] = field(default_factory=list)
    people_orgs: list[str] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    spoken_lines: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        parts: list[str] = []
        if self.spoken_lines:
            parts += ["## 3줄 요약", ""]
            parts += [f"{i}. {line}" for i, line in enumerate(self.spoken_lines, start=1)]
            parts.append("")
        if self.tldr:
            parts += ["## 한 줄 요약", "", self.tldr.strip(), ""]
        if self.key_points:
            parts += ["## 핵심 포인트", ""]
            parts += [f"- {point}" for point in self.key_points]
            parts.append("")
        if self.outline:
            parts += ["## 구간 목차", ""]
            for item in self.outline:
                parts.append(f"### {item.title}")
                if item.summary:
                    parts.append(item.summary)
                parts.append("")
        if self.people_orgs:
            parts += ["## 인물·기관", ""]
            parts += [f"- {name}" for name in self.people_orgs]
            parts.append("")
        if self.figures:
            parts += ["## 수치·일정", ""]
            parts += [f"- {item}" for item in self.figures]
            parts.append("")
        if self.suggested_questions:
            parts += ["## 이어서 물어볼 질문", ""]
            parts += [f"- {q}" for q in self.suggested_questions]
            parts.append("")
        return "\n".join(parts).strip()

    def to_dict(self) -> dict:
        return asdict(self)


def parse_brief(raw: str) -> Brief:
    data = _extract_json(raw)
    if not data:
        text = (raw or "").strip()
        return Brief(
            tldr=text[:400],
            key_points=[text] if text else [],
            spoken_lines=spoken_from_text(text),
        )

    outline_raw = data.get("outline") or []
    outline: list[OutlineItem] = []
    for item in outline_raw:
        if isinstance(item, dict):
            outline.append(
                OutlineItem(
                    title=str(item.get("title") or item.get("heading") or "").strip(),
                    summary=str(item.get("summary") or "").strip(),
                )
            )
        elif item:
            outline.append(OutlineItem(title=str(item).strip()))

    return Brief(
        tldr=str(data.get("tldr") or data.get("one_liner") or "").strip(),
        key_points=_as_str_list(data.get("key_points") or data.get("takeaways")),
        outline=outline,
        people_orgs=_as_str_list(data.get("people_orgs") or data.get("entities")),
        figures=_as_str_list(data.get("figures") or data.get("numbers")),
        suggested_questions=_as_str_list(
            data.get("suggested_questions") or data.get("questions")
        ),
        spoken_lines=ensure_spoken_lines(
            _as_str_list(data.get("spoken_lines") or data.get("spoken_summary")),
            tldr=str(data.get("tldr") or "").strip(),
            key_points=_as_str_list(data.get("key_points") or data.get("takeaways")),
        ),
    )


def ensure_spoken_lines(
    lines: list[str] | None = None,
    tldr: str = "",
    key_points: list[str] | None = None,
) -> list[str]:
    collected = [item.strip() for item in (lines or []) if item and item.strip()]
    for extra in ([tldr] if tldr else []) + list(key_points or []):
        piece = extra.strip()
        if piece and piece not in collected:
            collected.append(piece)
        if len(collected) >= 3:
            break
    return collected[:3]


def spoken_from_text(text: str) -> list[str]:
    body = re.sub(r"\s+", " ", (text or "").strip())
    if not body:
        return []
    parts = re.split(r"(?<=[\.!?다요음습니다])\s+", body)
    lines = [part.strip() for part in parts if part.strip()]
    if len(lines) >= 3:
        return lines[:3]
    if lines:
        return lines
    return [body[:80]]


def _as_str_list(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(item).strip() for item in value if str(item).strip()]


def _extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
