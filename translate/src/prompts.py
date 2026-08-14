"""참조 제품에서 가져온 번역·브리핑·질의 프롬프트."""

from __future__ import annotations

from src.glossary import glossary_block

TONE_INSTRUCTIONS = {
    "격식체": "한국어는 격식 있는 합니다체(보도·공문 문장)로 쓰세요. 반말과 과도한 구어체는 쓰지 마세요.",
    "보통": "한국어는 자연스러운 문어체로 쓰세요. 신문 기사와 업무 보고서 사이의 톤을 유지하세요.",
    "쉬운 말": "한국어는 중학생도 읽히게 쉬운 말로 쓰세요. 전문 용어는 괄호로 짧게 풀어 주세요.",
}

DOMAIN_INSTRUCTIONS = {
    "일반": "일반적인 문서입니다. 의미가 왜곡되지 않게 정확하고 자연스럽게 옮기세요.",
    "뉴스·시사": "뉴스 문체입니다. 사실·인용·수치는 바꾸지 말고, 표제는 한국어 뉴스처럼 간결하게 하세요.",
    "학술": "학술 문서입니다. 가설·방법·결과·한계를 구분하고, 용어는 해당 분야의 관례를 따르세요.",
    "법률·계약": "법률·계약 문서입니다. 의무·권리·조건·예외를 빠뜨리지 마세요. 모호하면 원문 구조를 유지하세요.",
    "기술": "기술 문서입니다. API, 코드, 명령, 식별자는 원문을 유지하고 설명만 한국어로 하세요.",
    "비즈니스": "비즈니스 문서입니다. 의사결정자 관점으로 목표, 수치, 리스크, 다음 행동을 분명히 하세요.",
}


def unit_user(packed: str) -> str:
    return (
        "아래 번호 블록을 각각 한국어로 번역하세요. "
        "같은 <<<번호>>> 형식을 유지하고, 각 번호 아래에는 번역문만 넣으세요. "
        "번호를 바꾸거나 여러 항목을 합치지 마세요.\n\n"
        f"{packed}"
    )


def translate_system(tone: str, domain: str, glossary_pairs: list[tuple[str, str]]) -> str:
    parts = [
        "당신은 한국어 대상의 전문 번역가입니다.",
        "외국어 원문을 자연스럽고 정확한 한국어로 번역하세요.",
        "의미, 고유명사, 숫자, 날짜, 목록·표 구조를 유지하세요.",
        "설명, 주석, 머리말을 덧붙이지 말고 번역문만 출력하세요.",
        TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["보통"]),
        DOMAIN_INSTRUCTIONS.get(domain, DOMAIN_INSTRUCTIONS["일반"]),
    ]
    block = glossary_block(glossary_pairs)
    if block:
        parts.append(block)
    return " ".join(parts[:4]) + "\n" + "\n".join(parts[4:])


def brief_system(tone: str, domain: str) -> str:
    return (
        "당신은 한국어 문서 브리핑 전문가입니다. Adobe Acrobat AI Assistant처럼 "
        "긴 문서를 바로 의사결정에 쓸 수 있게 구조화하세요. "
        "추측하지 말고 주어진 텍스트에 있는 내용만 사용하세요. "
        f"{TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS['보통'])} "
        f"{DOMAIN_INSTRUCTIONS.get(domain, DOMAIN_INSTRUCTIONS['일반'])} "
        "반드시 JSON만 출력하세요."
    )


def brief_user(text: str) -> str:
    return f"""아래 문서를 한국어로 브리핑하세요. JSON 외의 텍스트는 출력하지 마세요.

스키마:
{{
  "tldr": "문서 전체를 한 문장으로",
  "spoken_lines": ["읽기 좋은 1번째 문장", "2번째 문장", "3번째 문장"],
  "key_points": ["핵심 사실 5~8개"],
  "outline": [{{"title": "구간 제목", "summary": "2~3문장"}}],
  "people_orgs": ["인물 또는 기관"],
  "figures": ["숫자, 날짜, 금액, 비율 등 중요 수치"],
  "suggested_questions": ["이 문서를 더 깊게 읽는 한국어 질문 4개"]
}}

규칙:
- spoken_lines는 정확히 3문장. 입으로 읽기 쉽게, 각 문장은 한 호흡.
- key_points는 완전한 문장
- outline은 원문 흐름 순서
- 없는 항목은 빈 배열
- 수치와 고유명사는 원문 값을 보존

--- 문서 ---
{text}
"""


def map_brief_user(chunk: str, index: int, total: int) -> str:
    return (
        f"긴 문서의 {index}/{total} 구간입니다. 나중 전체 브리핑을 위해 "
        "이 구간의 핵심 사실, 고유명사, 수치만 한국어로 정리하세요. "
        "추측하지 마세요.\n\n"
        f"--- 구간 ---\n{chunk}"
    )


def spoken_user(text: str) -> str:
    return (
        "아래 문서를 한국어로 정확히 3문장 요약하세요. "
        "TTS로 읽을 문장이므로 구어체에 가깝게, 한 문장에 한 가지 핵심만 담으세요. "
        "JSON만 출력하세요.\n"
        '{"spoken_lines":["문장1","문장2","문장3"]}\n\n'
        f"--- 문서 ---\n{text[:6000]}"
    )


def ask_system() -> str:
    return (
        "당신은 문서 기반 분석가입니다. 제공된 원문·번역·브리핑 범위 안에서만 "
        "한국어로 답하세요. 문서에 없으면 '문서에서 확인되지 않습니다'라고 하세요. "
        "가능하면 근거가 되는 구절을 짧게 인용하세요."
    )


def ask_user(
    question: str,
    source_name: str,
    brief_markdown: str,
    original: str,
    translation: str,
) -> str:
    original_clip = original[:8000]
    translation_clip = translation[:8000]
    return (
        f"문서: {source_name}\n\n"
        f"--- 브리핑 ---\n{brief_markdown or '(없음)'}\n\n"
        f"--- 한국어 번역(발췌) ---\n{translation_clip or '(없음)'}\n\n"
        f"--- 원문(발췌) ---\n{original_clip}\n\n"
        f"질문: {question}"
    )
