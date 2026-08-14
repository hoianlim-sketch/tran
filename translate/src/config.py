"""설정값: Streamlit secrets → 환경변수(.env) → 기본값."""

from __future__ import annotations

import os

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def setting(name: str, default: str = "") -> str:
    value = _from_streamlit_secrets(name)
    if value:
        return value
    return (os.getenv(name, default) or default).strip()


def _from_streamlit_secrets(name: str) -> str:
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return ""
    try:
        if name in secrets:
            return str(secrets[name] or "").strip()
    except Exception:
        return ""
    return ""
