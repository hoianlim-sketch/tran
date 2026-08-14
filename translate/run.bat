@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo 가상환경을 먼저 만드세요: python -m venv .venv
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m streamlit run app.py --server.headless false
