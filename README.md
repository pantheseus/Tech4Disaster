# Tech4Disaster Starter Kit

A ready-to-extend base for a disaster management / emergency response hackathon.
Everything works out of the box **with no API key and no internet** (AI falls back to rules), and gets smarter when you add a free key.

**Stack:** FastAPI + SQLAlchemy (SQLite, or MySQL) + Bootstrap + Leaflet/OpenStreetMap + pluggable LLM + TF-IDF RAG.

## What is included

| Piece | Where | What it does |
|---|---|---|
| Dashboard + live map | `frontend/index.html` | Reports and shelters on a map, severity colors, priority queue, assign/resolve, stats, alert banner, live weather and flood risk |
| Report form | `frontend/report.html` | Description, photo, GPS or map pin, **AI triage** (category, severity, action) |
| Safety chatbot (RAG) | `frontend/chat.html` | Answers from guideline documents, multilingual, upload a PDF to add knowledge |
| REST API | `backend/app/main.py` | Reports, shelters, alerts, upload, AI, RAG, stats, weather, earthquakes, reseed |
| LLM helper | `backend/app/llm.py` | `analyze_report()`, `ask_llm()`, `ask_json()`; Groq / Gemini / NVIDIA / OpenAI / Anthropic or none |
| RAG engine | `backend/app/rag.py` | Loads PDF/TXT/MD from `backend/rag_docs/`, retrieves, answers |
| Alerts | `backend/app/alerts.py` | Console + optional email; swap in SMS here |
| Public data | `backend/app/external.py` | USGS earthquakes + Open-Meteo weather (no keys) |
| Demo data | `backend/app/seed_data.py` | 20 reports + 8 shelters around Tirunelveli (**fake, for demo only**) |
| Deploy files | `Procfile`, `render.yaml` | One-click Render deploy |
| Smoke test | `backend/test_smoke.py` | 20+ checks, run on every laptop |
| Playbook + pitch | `docs/` | Hackathon timeline, team roles, 3-minute pitch template |

## Run it (3 minutes)

**Windows:** double-click `run.bat`
**Linux / macOS / Git Bash:** `./run.sh`

Or manually:
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate      Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # Windows: copy ..\.env.example .env
uvicorn app.main:app --reload --port 8000
```
Open **http://localhost:8000** (dashboard), `/report.html`, `/chat.html`. API docs: **http://localhost:8000/docs**

Test everything: `cd backend && python test_smoke.py` (must print `ALL PASSED`).

## Turn on real AI (free options)

1. Get a free key: [Groq](https://console.groq.com) (fast, supports photos), [Google AI Studio](https://aistudio.google.com) (Gemini), or [NVIDIA NIM](https://build.nvidia.com).
2. Edit `backend/.env`:
```
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
```
3. Restart. `GET /api/health` shows `"enabled": true`.

If a model name is retired, set `LLM_MODEL` / `LLM_VISION_MODEL` in `.env` to a current one from the provider's docs.
If the API ever fails mid-demo, the app silently falls back to rule-based triage, so the demo never breaks.

## Use MySQL instead of SQLite
```bash
pip install pymysql
# in backend/.env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/tech4disaster
```
Create the empty database first (`CREATE DATABASE tech4disaster;`). Tables are created automatically.

## Deploy free
**Render:** push to GitHub, then New > Blueprint (reads `render.yaml`), add `GROQ_API_KEY` in the dashboard. Free instances sleep after inactivity and SQLite resets on redeploy, so open the site once before presenting and click **Reset demo data**.
Backend and frontend are served from the same app, so there is no CORS or URL setup.

## How to adapt it once the problem statement is announced

1. **Keep:** database layer, map, upload, AI helper, RAG, alerts, deploy.
2. **Change the data model:** edit `Report` / `Shelter` in `backend/app/db.py` (add columns such as `people_count`, `resource_type`, `volunteer_id`). Delete `tech4disaster.db` to recreate.
3. **Change the AI prompt:** edit `TRIAGE_SYSTEM` in `llm.py`, or call `ask_json(system, prompt)` for any new JSON task (damage assessment from photo, resource matching, route advice).
4. **Change the knowledge:** drop new PDFs into `backend/rag_docs/`.
5. **Add a page:** copy `report.html`, keep `js/api.js` and `css/style.css`.

### Idea starters that need only small changes
- **Flood early warning:** `external.weather()` already returns 3-day rain and risk. Add multiple locations and SMS alerts.
- **Rescue triage:** already built. Add volunteer assignment and nearest-shelter suggestion.
- **Resource matching:** use the `Shelter` table (food, medical, capacity) and match to reports by distance.
- **Photo damage assessment:** `analyze_report()` already accepts photos; change the prompt to damage levels.
- **Multilingual safety bot:** already built. Add voice input using the browser's Web Speech API.

## Project layout
```
tech4disaster-starter/
  backend/
    app/  main.py  db.py  schemas.py  llm.py  rag.py  alerts.py  external.py  seed_data.py  config.py
    rag_docs/disaster_safety_guide.md     <- sample knowledge (replace with NDMA PDFs)
    uploads/                              <- user photos
    requirements.txt  test_smoke.py
  frontend/  index.html  report.html  chat.html  js/api.js  css/style.css
  docs/  HACKATHON_PLAYBOOK.md  PITCH_TEMPLATE.md
  .env.example  .gitignore  run.sh  run.bat  Procfile  render.yaml
```

## Security notes (so your demo is clean)
- Never commit `.env`. It is in `.gitignore`.
- The API has **no login** and CORS is open. That is fine for a hackathon demo; say in the pitch that auth (OTP/role-based) is the next step.
- User text is HTML-escaped in the frontend; uploads are type- and size-checked.
- Demo data is fake. Say so if a judge asks. Do not present it as real incidents.

## CallPrior (control-room) module - problem #09
Backend: `backend/app/calls.py`. Test: `cd backend && python test_calls.py`.
- `POST /api/calls` log a call (AI auto-triage + vulnerability flags), `GET /api/calls` queue by live priority
- `GET /api/calls/{id}/suggest-units`, `POST /api/calls/{id}/assign` (auto-picks best unit), `POST /api/calls/{id}/close`
- `GET/POST/PATCH /api/units`, `GET /api/metrics` (supervisor numbers), `POST /api/calls/simulate?count=3` (IVR simulator)
- Priority score = severity x 20 + vulnerability flags (max 30) + waiting time (max 30). Rules are at the top of `calls.py`.
