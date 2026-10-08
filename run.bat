@echo off
REM One command start on Windows: double-click run.bat
cd /d "%~dp0backend"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if not exist .env ( copy ..\.env.example .env >nul & echo Created backend\.env - add your API key there )
echo Open http://localhost:8000
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
