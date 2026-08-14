"""문서 번역·브리핑 패키지."""

from src.ai import AIError, Translator
from src.brief import Brief
from src.extract import (
    ExtractError,
    ExtractedDocument,
    extract_from_bytes,
    extract_from_url,
    load_file,
    load_pasted,
    load_url,
)
from src.export import brief_markdown, build_docx, build_markdown, build_txt
from src.glossary import parse_glossary
from src.config import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_BASE_URL,
    DEFAULT_OPENAI_MODEL,
    setting,
)
from src.preserve import can_preserve, translate_preserving
from src.tts import TTSError, spoken_script, synthesize_korean
from src.utils import detect_language, language_label, safe_stem

__all__ = [
    "AIError",
    "Brief",
    "ExtractError",
    "ExtractedDocument",
    "Translator",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_OPENAI_BASE_URL",
    "DEFAULT_OPENAI_MODEL",
    "brief_markdown",
    "build_docx",
    "build_markdown",
    "build_txt",
    "can_preserve",
    "detect_language",
    "extract_from_bytes",
    "extract_from_url",
    "language_label",
    "load_file",
    "load_pasted",
    "load_url",
    "parse_glossary",
    "safe_stem",
    "setting",
    "spoken_script",
    "synthesize_korean",
    "translate_preserving",
    "TTSError",
]
