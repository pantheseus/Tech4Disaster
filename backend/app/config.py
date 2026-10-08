import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'tech4disaster.db'}"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or BASE_DIR / "uploads")
RAG_DOCS_DIR = Path(os.getenv("RAG_DOCS_DIR") or BASE_DIR / "rag_docs")
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# --- LLM settings -----------------------------------------------------------
# LLM_PROVIDER: groq | gemini | nvidia | openai | anthropic | none
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "none").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "")                # empty = provider default
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", "")  # empty = provider default

# Default center of the map (Tirunelveli)
DEFAULT_LAT = float(os.getenv("DEFAULT_LAT") or "8.7139")
DEFAULT_LNG = float(os.getenv("DEFAULT_LNG") or "77.7567")

# Optional email alerts
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RAG_DOCS_DIR.mkdir(parents=True, exist_ok=True)
