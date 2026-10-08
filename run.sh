#!/usr/bin/env bash
# One command start (Linux / macOS / Git Bash):  ./run.sh
set -e
cd "$(dirname "$0")/backend"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate
pip install -q -r requirements.txt
[ -f .env ] || { [ -f ../.env.example ] && cp ../.env.example .env && echo "Created backend/.env - add your API key there"; }
echo "Open http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
