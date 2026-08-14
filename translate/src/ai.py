"""OpenAI 호환 API, Gemini, Google 번역을 이용한 번역·브리핑·질의."""

from __future__ import annotations

from typing import Callable

from src.config import DEFAULT_GEMINI_MODEL, DEFAULT_OPENAI_MODEL
from src.brief import Brief, parse_brief, spoken_from_text
from src.glossary import apply_glossary
from src.prompts import (
    ask_system,
    ask_user,
    brief_system,
    brief_user,
    map_brief_user,
    spoken_user,
    translate_system,
    unit_user,
)
from src.utils import batch_jobs, split_into_chunks, unpack_marked_units

ProgressCallback = Callable[[str, int, int], None]


class AIError(RuntimeError):
    pass


class Translator:
    def __init__(
        self,
        provider: str,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        tone: str = "보통",
        domain: str = "일반",
        glossary: list[tuple[str, str]] | None = None,
    ) -> None:
        self.provider = provider
        self.api_key = (api_key or "").strip()
        self.model = model.strip()
        self.base_url = (base_url or "").strip()
        self.tone = tone
        self.domain = domain
        self.glossary = glossary or []
        self._openai = None
        self._gemini = None

        if provider == "openai":
            self._init_openai()
        elif provider == "gemini":
            self._init_gemini()
        elif provider == "google":
            self._init_google()
        else:
            raise AIError(f"알 수 없는 엔진입니다: {provider}")

    def _init_openai(self) -> None:
        if not self.api_key:
            raise AIError("OpenAI API 키를 입력해 주세요.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIError("openai 패키지가 설치되어 있지 않습니다.") from exc

        kwargs: dict[str, str] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._openai = OpenAI(**kwargs)
        if not self.model:
            self.model = DEFAULT_OPENAI_MODEL

    def _init_gemini(self) -> None:
        if not self.api_key:
            raise AIError("Gemini API 키를 입력해 주세요.")
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise AIError("google-generativeai 패키지가 설치되어 있지 않습니다.") from exc

        genai.configure(api_key=self.api_key)
        if not self.model:
            self.model = DEFAULT_GEMINI_MODEL
        self._gemini = genai.GenerativeModel(self.model)

    def _init_google(self) -> None:
        try:
            from deep_translator import GoogleTranslator  # noqa: F401
        except ImportError as exc:
            raise AIError("deep-translator 패키지가 설치되어 있지 않습니다.") from exc

    def translate(
        self,
        text: str,
        on_progress: ProgressCallback | None = None,
    ) -> str:
        chunks = split_into_chunks(text)
        if not chunks:
            return ""

        translated: list[str] = []
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            if on_progress:
                on_progress("번역", index, total)
            translated.append(self._translate_chunk(chunk))
        result = "\n\n".join(translated).strip()
        return apply_glossary(result, self.glossary)

    def translate_units(
        self,
        units: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> list[str]:
        """문단·텍스트 상자 단위로 번역해 서식을 유지한다."""
        results = list(units)
        jobs = [(index, text) for index, text in enumerate(units) if (text or "").strip()]
        if not jobs:
            return results

        if self.provider == "google":
            total = len(jobs)
            for count, (index, text) in enumerate(jobs, start=1):
                if on_progress:
                    on_progress("서식 번역", count, total)
                results[index] = apply_glossary(self._google_translate(text), self.glossary)
            return results

        batches = batch_jobs(jobs)
        done = 0
        total = len(jobs)
        for batch in batches:
            if on_progress:
                on_progress("서식 번역", min(done + 1, total), total)
            packed = "\n".join(f"<<<{index}>>>\n{text}" for index, text in batch)
            raw = self._chat(
                translate_system(self.tone, self.domain, self.glossary),
                unit_user(packed),
            )
            parsed = unpack_marked_units(raw)
            for index, text in batch:
                mapped = parsed.get(index, "").strip()
                if mapped:
                    results[index] = apply_glossary(mapped, self.glossary)
                else:
                    results[index] = apply_glossary(self._translate_chunk(text), self.glossary)
            done += len(batch)
        return results

    def brief(
        self,
        text: str,
        on_progress: ProgressCallback | None = None,
    ) -> Brief:
        self._require_llm("브리핑")
        chunks = split_into_chunks(text, max_chars=5000)
        if not chunks:
            return Brief()

        if len(chunks) == 1:
            if on_progress:
                on_progress("브리핑", 1, 1)
            raw = self._chat(brief_system(self.tone, self.domain), brief_user(chunks[0]))
            return parse_brief(raw)

        partials: list[str] = []
        total = len(chunks) + 1
        for index, chunk in enumerate(chunks, start=1):
            if on_progress:
                on_progress("브리핑", index, total)
            partials.append(
                self._chat(
                    "당신은 문서 분석가입니다. 반드시 한국어로, 사실에만 근거해 정리하세요.",
                    map_brief_user(chunk, index, len(chunks)),
                )
            )

        if on_progress:
            on_progress("브리핑", total, total)
        joined = "\n\n".join(
            f"[구간 {i}]\n{part}" for i, part in enumerate(partials, start=1)
        )
        raw = self._chat(brief_system(self.tone, self.domain), brief_user(joined))
        return parse_brief(raw)

    def spoken_summary(self, text: str) -> list[str]:
        if self.provider == "google":
            return spoken_from_text(text)
        raw = self._chat(
            "당신은 한국어 요약 아나운서입니다. 반드시 JSON만 출력하세요.",
            spoken_user(text),
        )
        parsed = parse_brief(raw)
        if parsed.spoken_lines:
            return parsed.spoken_lines[:3]
        return spoken_from_text(text)

    def ask(
        self,
        question: str,
        source_name: str,
        brief: Brief | None,
        original: str,
        translation: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        self._require_llm("질의")
        user = ask_user(
            question=question,
            source_name=source_name,
            brief_markdown=brief.to_markdown() if brief else "",
            original=original,
            translation=translation,
        )
        messages = [{"role": "system", "content": ask_system()}]
        for turn in history or []:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user})
        return self._messages(messages)

    def _require_llm(self, feature: str) -> None:
        if self.provider == "google":
            raise AIError(
                f"{feature}은 OpenAI 또는 Gemini가 필요합니다. "
                "사이드바에서 엔진을 바꿔 주세요."
            )

    def _translate_chunk(self, chunk: str) -> str:
        if self.provider == "google":
            return self._google_translate(chunk)
        return self._chat(
            translate_system(self.tone, self.domain, self.glossary),
            chunk,
        )

    def _google_translate(self, chunk: str) -> str:
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="auto", target="ko")
        pieces = split_into_chunks(chunk, max_chars=4500)
        return "\n".join(translator.translate(piece) for piece in pieces)

    def _chat(self, system: str, user: str) -> str:
        return self._messages(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )

    def _messages(self, messages: list[dict[str, str]]) -> str:
        if self.provider == "openai":
            return self._openai_chat(messages)
        if self.provider == "gemini":
            joined = "\n\n".join(
                f"[{item['role']}]\n{item['content']}" for item in messages
            )
            return self._gemini_chat(joined)
        raise AIError("이 엔진은 대화형 기능을 지원하지 않습니다.")

    def ocr_image(self, image) -> str:
        """스캔 이미지에서 원문 글자를 그대로 추출한다."""
        self._require_llm("이미지 인식")
        import base64
        import io

        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        payload = base64.b64encode(buffer.getvalue()).decode("ascii")
        prompt = (
            "이 이미지에 있는 글자를 원래 언어 그대로 추출하세요. "
            "설명, 번역, 주석 없이 읽은 텍스트만 출력하세요."
        )
        if self.provider == "openai":
            try:
                response = self._openai.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{payload}"},
                                },
                            ],
                        }
                    ],
                )
            except Exception as exc:  # noqa: BLE001
                raise AIError(f"이미지 인식 실패: {exc}") from exc
            content = response.choices[0].message.content if response.choices else ""
            if not content:
                raise AIError("이미지에서 글자를 읽지 못했습니다.")
            return content.strip()

        try:
            response = self._gemini.generate_content(
                [prompt, image],
                generation_config={"temperature": 0},
            )
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"이미지 인식 실패: {exc}") from exc
        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise AIError("이미지에서 글자를 읽지 못했습니다.")
        return text.strip()

    def _openai_chat(self, messages: list[dict[str, str]]) -> str:
        try:
            response = self._openai.chat.completions.create(
                model=self.model,
                temperature=0.2,
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"OpenAI 호출 실패: {exc}") from exc

        content = response.choices[0].message.content if response.choices else ""
        if not content:
            raise AIError("모델이 빈 응답을 반환했습니다.")
        return content.strip()

    def _gemini_chat(self, prompt: str) -> str:
        try:
            response = self._gemini.generate_content(
                prompt,
                generation_config={"temperature": 0.2},
            )
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"Gemini 호출 실패: {exc}") from exc

        text = getattr(response, "text", "") or ""
        if not text.strip():
            raise AIError("모델이 빈 응답을 반환했습니다.")
        return text.strip()
