# 문서 번역 · 브리핑

외국어 문서·링크·원문을 한국어로 번역하고, 의사결정용 브리핑을 만듭니다.

Papago(대면 창·용어집), DeepL(문체·용어 고정), Acrobat AI(구조화 요약·질의), ChatGPT(분야·문맥)의 강점을 한 화면에 모았습니다.

## 실행

```powershell
cd c:\Users\KCCI_GFA\Downloads\Cursor_tantra\translate
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

또는 `run.bat`. 주소는 `http://localhost:8501`.

## 사용 순서

1. 엔진과 문체·분야·용어집을 고릅니다.
2. 파일 / 링크 / 붙여넣기로 문서를 불러와 본문을 확인합니다.
3. **번역 · 브리핑 실행**을 누릅니다.
4. 브리핑 → 원문·번역 대조 → 질의 → 파일 저장 순으로 읽습니다.

스캔 PDF·사진 문서는 OCR로 읽고, Word/PowerPoint는 표·슬라이드 서식을 유지한 채 한국어 파일로 저장합니다.

## 엔진

| 엔진 | 번역 | 브리핑·질의 |
|------|------|-------------|
| OpenAI / Groq / Ollama 등 | O | O |
| Google Gemini | O | O |
| Google 번역 (무료) | O | X |

API 키는 **Streamlit secrets** 또는 **`.env`**에 넣습니다. 둘 다 GitHub에 올라가지 않습니다.

1. `.streamlit/secrets.toml`에 `GEMINI_API_KEY`를 넣거나
2. `.env`에 `GEMINI_API_KEY`를 넣습니다.

기본 엔진은 Gemini, 기본 모델은 `gemini-2.5-flash`입니다. 키 발급: [Gemini](https://aistudio.google.com/apikey), [OpenAI](https://platform.openai.com/api-keys).

`.env.example`과 `.streamlit/secrets.toml.example`만 저장소에 포함됩니다.
