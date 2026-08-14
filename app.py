"""외국어 문서·링크를 한국어로 번역·브리핑하는 워크스페이스."""

from __future__ import annotations

import html

import streamlit as st
from dotenv import load_dotenv

from src import (
    AIError,
    Brief,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    ExtractError,
    ExtractedDocument,
    TTSError,
    Translator,
    brief_markdown,
    build_docx,
    build_markdown,
    build_txt,
    can_preserve,
    detect_language,
    language_label,
    load_file,
    load_pasted,
    load_url,
    parse_glossary,
    safe_stem,
    setting,
    spoken_script,
    synthesize_korean,
    translate_preserving,
)

load_dotenv()

st.set_page_config(
    page_title="문서 번역·브리핑",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .stApp { background: #f6f7f9; }
    h1, h2, h3 { color: #12263a !important; letter-spacing: -0.03em; }
    .hero {
        background: #12263a;
        color: #fff;
        padding: 1.35rem 1.6rem;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    .hero h1 { color: #fff !important; font-size: 1.55rem; margin: 0 0 0.35rem 0; }
    .hero p { margin: 0; opacity: 0.88; }
    .tldr {
        background: #fff;
        border-left: 4px solid #1b6b93;
        padding: 0.9rem 1.1rem;
        border-radius: 4px;
        font-size: 1.05rem;
        line-height: 1.55;
        color: #12263a;
    }
    .meta-row { color: #5b6b7a; font-size: 0.88rem; margin-bottom: 0.6rem; }
    .stTextArea textarea { font-size: 0.95rem; line-height: 1.65; }
    div[data-testid="stSidebar"] { background: #fbfcfd; }
    .block-container { padding-top: 1.4rem; }
</style>
"""

TONES = ["격식체", "보통", "쉬운 말"]
DOMAINS = ["일반", "뉴스·시사", "학술", "법률·계약", "기술", "비즈니스"]
METHOD_LABELS = {
    "pdf": "PDF 텍스트",
    "pdf-ocr": "스캔 PDF OCR",
    "ocr": "이미지 OCR",
    "docx": "Word",
    "pptx": "PowerPoint",
    "url": "웹 페이지",
    "paste": "붙여넣기",
    "html": "HTML",
    "text": "텍스트",
}
FILE_TYPES = [
    "pdf",
    "docx",
    "pptx",
    "txt",
    "md",
    "html",
    "htm",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "tif",
    "tiff",
    "bmp",
]


def _env(name: str, default: str = "") -> str:
    return setting(name, default)


def init_state() -> None:
    defaults = {
        "original": "",
        "translation": "",
        "brief": None,
        "language": "unknown",
        "source_name": "",
        "error": "",
        "chat": [],
        "tone": "보통",
        "domain": "일반",
        "pending_question": "",
        "method": "",
        "suffix": "",
        "file_bytes": None,
        "formatted_bytes": None,
        "spoken_lines": [],
        "tts_audio": b"",
        "tts_autoplay": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_sidebar() -> dict:
    with st.sidebar:
        st.markdown("### 품질 설정")
        provider_label = st.selectbox(
            "AI 엔진",
            ["Google Gemini", "OpenAI / 호환 API", "Google 번역 (무료, 번역만)"],
            help="기본 엔진은 Gemini입니다. 브리핑과 질의는 OpenAI 또는 Gemini가 필요합니다.",
        )
        provider_map = {
            "Google Gemini": "gemini",
            "OpenAI / 호환 API": "openai",
            "Google 번역 (무료, 번역만)": "google",
        }
        provider = provider_map[provider_label]

        api_key = model = base_url = ""
        if provider == "openai":
            stored_key = _env("OPENAI_API_KEY")
            override = st.text_input(
                "OpenAI API 키 (비우면 secrets/.env 사용)",
                type="password",
                help="Streamlit secrets 또는 .env의 OPENAI_API_KEY를 씁니다.",
            )
            api_key = override.strip() or stored_key
            if stored_key and not override.strip():
                st.caption("API 키를 secrets 또는 .env에서 불러왔습니다.")
            base_url = st.text_input(
                "Base URL",
                value=_env("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL),
                help="Groq, Ollama, LM Studio 등",
            )
            model = st.text_input("모델", value=_env("OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
        elif provider == "gemini":
            stored_key = _env("GEMINI_API_KEY")
            override = st.text_input(
                "Gemini API 키 (비우면 secrets/.env 사용)",
                type="password",
                help="Streamlit secrets 또는 .env의 GEMINI_API_KEY를 씁니다.",
            )
            api_key = override.strip() or stored_key
            if stored_key and not override.strip():
                st.caption("API 키를 secrets 또는 .env에서 불러왔습니다.")
            elif not api_key:
                st.warning(
                    "`.streamlit/secrets.toml` 또는 `.env`에 GEMINI_API_KEY를 넣으세요."
                )
            model = st.text_input(
                "모델",
                value=_env("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
            )
        else:
            st.caption("무료 번역만 됩니다. 브리핑·질의는 꺼집니다.")

        st.divider()
        tone = st.radio("문체", TONES, index=1, horizontal=True, help="DeepL 격식체 + Papago 문체")
        domain = st.selectbox("분야", DOMAINS, help="ChatGPT식 도메인 프롬프트")
        glossary_raw = st.text_area(
            "용어집",
            placeholder="API = 응용 프로그래밍 인터페이스\nboard → 이사회",
            height=110,
            help="DeepL/Papago Glossary. 한 줄에 원문 = 한국어",
        )

        st.divider()
        do_translate = st.checkbox("한국어 번역", value=True)
        do_brief = st.checkbox("구조화 브리핑", value=True, disabled=provider == "google")
        do_tts = st.checkbox("3줄 요약 읽어주기", value=True)
        tts_voice = st.radio("음성", ["여성", "남성"], horizontal=True, disabled=not do_tts)

        st.caption("입력: PDF(스캔 OCR), DOCX/PPTX 서식 유지, 이미지, URL, 붙여넣기")
        return {
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "base_url": base_url,
            "tone": tone,
            "domain": domain,
            "glossary": parse_glossary(glossary_raw),
            "do_translate": do_translate,
            "do_brief": do_brief and provider != "google",
            "do_tts": do_tts,
            "tts_voice": tts_voice,
        }


def extract_source(input_mode: str, uploaded, url: str, pasted: str, settings: dict) -> ExtractedDocument:
    fallback = _ocr_fallback(settings)
    if input_mode == "파일":
        if uploaded is None:
            raise ExtractError("번역할 문서를 업로드해 주세요.")
        return load_file(uploaded.name, uploaded.getvalue(), ocr_fallback=fallback)
    if input_mode == "링크":
        return load_url(url, ocr_fallback=fallback)
    return load_pasted(pasted)


def _ocr_fallback(settings: dict):
    if settings.get("provider") == "google":
        return None

    engine = None

    def fallback(image):
        nonlocal engine
        try:
            if engine is None:
                engine = make_engine(settings)
            return engine.ocr_image(image)
        except AIError as exc:
            raise ExtractError(str(exc)) from exc

    return fallback


def make_engine(settings: dict) -> Translator:
    return Translator(
        provider=settings["provider"],
        api_key=settings["api_key"],
        model=settings["model"],
        base_url=settings["base_url"],
        tone=settings["tone"],
        domain=settings["domain"],
        glossary=settings["glossary"],
    )


def run_pipeline(settings: dict) -> None:
    original = st.session_state.original
    if not original:
        raise ExtractError("먼저 문서를 불러오세요.")
    if not settings["do_translate"] and not settings["do_brief"]:
        raise AIError("번역 또는 브리핑을 선택해 주세요.")

    engine = make_engine(settings)
    progress = st.progress(0, text="작업을 시작합니다…")
    status = st.empty()

    def on_progress(stage: str, current: int, total: int) -> None:
        progress.progress(min(current / max(total, 1), 1.0), text=f"{stage} {current}/{total}")
        status.caption(f"{stage} 구간 {current} / {total}")

    translation = ""
    brief = None
    formatted_bytes = None
    spoken_lines: list[str] = []
    tts_audio = b""
    if settings["do_translate"]:
        translation = engine.translate(original, on_progress=on_progress)
        suffix = st.session_state.suffix
        file_bytes = st.session_state.file_bytes
        if file_bytes and can_preserve(suffix):
            formatted_bytes = translate_preserving(
                st.session_state.source_name,
                file_bytes,
                lambda units: engine.translate_units(units, on_progress=on_progress),
            )
    if settings["do_brief"]:
        brief = engine.brief(translation or original, on_progress=on_progress)
        spoken_lines = list(brief.spoken_lines or [])
    if settings["do_tts"] and not spoken_lines:
        if on_progress:
            on_progress("3줄 요약", 1, 1)
        spoken_lines = engine.spoken_summary(translation or original)
        if brief is not None:
            brief.spoken_lines = spoken_lines

    if settings["do_tts"] and spoken_lines:
        if on_progress:
            on_progress("음성", 1, 1)
        try:
            tts_audio = synthesize_korean(
                spoken_script(spoken_lines),
                voice_label=settings.get("tts_voice", "여성"),
            )
        except TTSError as exc:
            tts_audio = b""
            st.warning(str(exc))

    progress.progress(1.0, text="완료")
    status.empty()

    st.session_state.translation = translation
    st.session_state.brief = brief
    st.session_state.formatted_bytes = formatted_bytes
    st.session_state.spoken_lines = spoken_lines
    st.session_state.tts_audio = tts_audio
    st.session_state.tts_autoplay = bool(tts_audio)
    st.session_state.tone = settings["tone"]
    st.session_state.domain = settings["domain"]
    st.session_state.chat = []
    st.session_state.error = ""


def render_spoken_player(settings: dict) -> None:
    lines = st.session_state.get("spoken_lines") or []
    if not lines:
        return
    st.markdown("**3줄 요약**")
    for index, line in enumerate(lines, start=1):
        st.markdown(f"{index}. {line}")

    audio = st.session_state.get("tts_audio") or b""
    if audio:
        st.audio(
            audio,
            format="audio/mp3",
            autoplay=bool(st.session_state.get("tts_autoplay")),
        )
        st.session_state.tts_autoplay = False

    play, download = st.columns(2)
    if play.button("다시 읽기", use_container_width=True):
        try:
            st.session_state.tts_audio = synthesize_korean(
                spoken_script(lines),
                voice_label=settings.get("tts_voice", "여성"),
            )
            st.session_state.tts_autoplay = True
            st.session_state.error = ""
        except TTSError as exc:
            st.session_state.error = str(exc)
        st.rerun()
    if audio:
        download.download_button(
            "MP3 저장",
            data=audio,
            file_name=f"{safe_stem(st.session_state.source_name)}_3줄요약.mp3",
            mime="audio/mpeg",
            use_container_width=True,
        )


def render_brief(brief: Brief | None) -> None:
    if brief is None:
        st.caption("브리핑은 OpenAI 또는 Gemini에서 생성됩니다.")
        return
    if not any([brief.tldr, brief.key_points, brief.outline]):
        st.caption("브리핑 결과가 없습니다.")
        return

    if brief.tldr:
        st.markdown(
            f'<div class="tldr">{html.escape(brief.tldr)}</div>',
            unsafe_allow_html=True,
        )
        st.write("")

    if brief.key_points:
        st.markdown("**핵심 포인트**")
        for point in brief.key_points:
            st.markdown(f"- {point}")

    if brief.outline:
        st.markdown("**구간 목차**")
        for item in brief.outline:
            with st.expander(item.title or "구간", expanded=False):
                st.write(item.summary)

    cols = st.columns(2)
    with cols[0]:
        if brief.people_orgs:
            st.markdown("**인물·기관**")
            for name in brief.people_orgs:
                st.markdown(f"- {name}")
    with cols[1]:
        if brief.figures:
            st.markdown("**수치·일정**")
            for item in brief.figures:
                st.markdown(f"- {item}")

    if brief.suggested_questions:
        st.markdown("**이어서 물어볼 질문**")
        for index, question in enumerate(brief.suggested_questions):
            if st.button(question, key=f"sq_{index}", use_container_width=True):
                st.session_state.pending_question = question
                st.rerun()


def render_dual_pane() -> None:
    original = st.session_state.original
    translation = st.session_state.translation
    left, right = st.columns(2, gap="medium")
    with left:
        st.caption("원문")
        st.text_area("원문", original, height=520, label_visibility="collapsed")
    with right:
        st.caption("한국어 번역")
        if translation:
            st.text_area("번역", translation, height=520, label_visibility="collapsed")
        else:
            st.info("번역을 실행하면 여기에 대조됩니다.")


def render_qa(settings: dict) -> None:
    brief: Brief | None = st.session_state.brief
    if settings["provider"] == "google":
        st.info("질의는 OpenAI 또는 Gemini가 필요합니다.")
        return
    if not st.session_state.original:
        st.caption("문서를 불러온 뒤 질문할 수 있습니다.")
        return

    if brief and brief.suggested_questions and not st.session_state.chat:
        st.caption("브리핑에서 추천한 질문으로 시작할 수 있습니다.")

    for turn in st.session_state.chat:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])

    question = st.chat_input("이 문서에 대해 질문하세요")
    if st.session_state.pending_question:
        question = st.session_state.pending_question
        st.session_state.pending_question = ""

    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        try:
            engine = make_engine(settings)
            answer = engine.ask(
                question=question,
                source_name=st.session_state.source_name,
                brief=brief,
                original=st.session_state.original,
                translation=st.session_state.translation,
                history=st.session_state.chat[:-1],
            )
        except AIError as exc:
            answer = str(exc)
        st.session_state.chat.append({"role": "assistant", "content": answer})
        st.rerun()


def render_export() -> None:
    original = st.session_state.original
    if not original:
        st.caption("결과가 있으면 여기서 저장합니다.")
        return
    lang = language_label(st.session_state.language)
    summary = brief_markdown(st.session_state.brief)
    stem = safe_stem(st.session_state.source_name)
    md = build_markdown(
        st.session_state.source_name,
        lang,
        original,
        st.session_state.translation,
        summary,
        tone=st.session_state.tone,
        domain=st.session_state.domain,
    )
    txt = build_txt(st.session_state.translation, summary)
    docx = build_docx(
        st.session_state.source_name,
        lang,
        original,
        st.session_state.translation,
        summary,
        tone=st.session_state.tone,
        domain=st.session_state.domain,
    )
    formatted = st.session_state.formatted_bytes
    suffix = st.session_state.suffix
    audio = st.session_state.get("tts_audio") or b""
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.download_button("Markdown", md, file_name=f"{stem}_브리핑.md", mime="text/markdown")
    d2.download_button("텍스트", txt, file_name=f"{stem}_브리핑.txt", mime="text/plain")
    d3.download_button(
        "Word 브리핑",
        docx,
        file_name=f"{stem}_브리핑.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    if formatted and suffix == ".docx":
        d4.download_button(
            "원본 서식 Word",
            formatted,
            file_name=f"{stem}_ko.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    elif formatted and suffix == ".pptx":
        d4.download_button(
            "원본 서식 PPT",
            formatted,
            file_name=f"{stem}_ko.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    else:
        d4.caption("DOCX/PPTX는 원본 서식 파일을 함께 저장합니다.")
    if audio:
        d5.download_button(
            "3줄 요약 MP3",
            audio,
            file_name=f"{stem}_3줄요약.mp3",
            mime="audio/mpeg",
        )


def render_results(settings: dict) -> None:
    original = st.session_state.original
    if not original:
        st.info("문서를 불러온 다음 **번역·브리핑 실행**을 누르세요.")
        return

    lang = language_label(st.session_state.language)
    method = METHOD_LABELS.get(st.session_state.method, st.session_state.method)
    st.markdown(
        f'<div class="meta-row">{html.escape(str(st.session_state.source_name))} · {html.escape(lang)} · '
        f"{len(original):,}자 · {html.escape(method)} · {html.escape(st.session_state.tone)} · "
        f"{html.escape(st.session_state.domain)}</div>",
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["브리핑", "원문 · 번역", "질의", "내보내기"])
    with tabs[0]:
        render_spoken_player(settings)
        render_brief(st.session_state.brief)
    with tabs[1]:
        render_dual_pane()
    with tabs[2]:
        render_qa(settings)
    with tabs[3]:
        render_export()


def main() -> None:
    init_state()
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero">
            <h1>문서 번역 · 브리핑</h1>
            <p>파일을 올리거나 링크·원문을 넣으면, 한국어 번역과 의사결정용 브리핑을 만듭니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    settings = render_sidebar()
    left, right = st.columns([0.92, 1.28], gap="large")

    with left:
        st.subheader("입력")
        input_mode = st.radio("방식", ["파일", "링크", "붙여넣기"], horizontal=True)
        uploaded = None
        url = ""
        pasted = ""
        if input_mode == "파일":
            uploaded = st.file_uploader("문서", type=FILE_TYPES)
        elif input_mode == "링크":
            url = st.text_input("URL", placeholder="https://example.com/article")
        else:
            pasted = st.text_area("원문 붙여넣기", height=180, placeholder="번역할 텍스트를 붙여 넣으세요.")

        load = st.button("문서 불러오기", use_container_width=True)
        if load:
            try:
                with st.spinner("문서를 읽고 있습니다…"):
                    document = extract_source(input_mode, uploaded, url, pasted, settings)
                st.session_state.original = document.text
                st.session_state.source_name = document.source_name
                st.session_state.language = detect_language(document.text)
                st.session_state.method = document.method
                st.session_state.suffix = document.suffix
                st.session_state.file_bytes = document.file_bytes
                st.session_state.translation = ""
                st.session_state.brief = None
                st.session_state.chat = []
                st.session_state.formatted_bytes = None
                st.session_state.spoken_lines = []
                st.session_state.tts_audio = b""
                st.session_state.tts_autoplay = False
                st.session_state.error = ""
            except (ExtractError, ValueError) as exc:
                st.session_state.error = str(exc)

        if st.session_state.original:
            with st.expander("추출된 본문 미리보기", expanded=not st.session_state.translation):
                preview = st.session_state.original
                method = METHOD_LABELS.get(st.session_state.method, st.session_state.method)
                st.caption(
                    f"{language_label(st.session_state.language)} · {method} · {len(preview):,}자"
                )
                st.text_area(
                    "미리보기",
                    preview[:8000] + ("…" if len(preview) > 8000 else ""),
                    height=220,
                    label_visibility="collapsed",
                    disabled=True,
                )

        run = st.button("번역 · 브리핑 실행", type="primary", use_container_width=True)
        if run:
            try:
                run_pipeline(settings)
            except (ExtractError, AIError, TTSError, ValueError) as exc:
                st.session_state.error = str(exc)

        if st.session_state.error:
            st.error(st.session_state.error)

    with right:
        st.subheader("워크스페이스")
        render_results(settings)


if __name__ == "__main__":
    main()
