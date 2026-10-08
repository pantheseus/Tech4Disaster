# Hackathon Day Playbook (9 AM - 5 PM)

## Before you walk in (checklist)
- [ ] All 3 laptops: clone repo, `./run.sh` or `run.bat`, `python test_smoke.py` prints ALL PASSED
- [ ] API key in `backend/.env` on each laptop (Groq / Gemini free), `/api/health` shows enabled
- [ ] Chargers, extension cord, mobile hotspot as backup internet
- [ ] GitHub repo created, all 3 are collaborators, `.env` NOT committed
- [ ] Pitch template copied into Canva / Google Slides / Gamma
- [ ] Browser tabs ready: http://localhost:8000, /docs, GitHub repo

## Roles (decide now)
| Person | Owns | Files |
|---|---|---|
| A - Frontend | pages, map, UX, demo flow | `frontend/` |
| B - Backend + data | API, database, public data, deploy | `backend/app/main.py`, `db.py`, `external.py` |
| C - AI + pitch | prompts, RAG, slides, speaking | `llm.py`, `rag.py`, `docs/PITCH_TEMPLATE.md` |

Git rule: each person works in their own files, commit small, `git pull --rebase` before every push.

## Timeline
| Time | Do |
|---|---|
| 9:00-9:30 | Listen to the problem statement. Ask the coordinator questions. |
| 9:30-10:15 | **Think, don't code.** Who is the user? What is the ONE core flow? What data do we need? Write the one-sentence pitch. |
| 10:15-10:40 | Paper sketch of 3 screens. Agree on API endpoints and JSON shape. |
| 10:40-1:00 | Build the core flow end to end (even ugly). Use mock data. |
| 1:00-1:45 | Lunch + first demo run. Fix what is broken. |
| 1:45-3:30 | Add 1-2 differentiators (AI, live data, alerts). Deploy to Render. |
| 3:30-4:00 | **Feature freeze.** Click through the full demo 3 times. |
| 4:00-4:45 | Slides, 3-minute pitch rehearsal with a timer, record a backup demo video. |
| 4:45-5:00 | Reseed demo data, open everything, charge laptops. |

## Judging criteria and how to score
- **Innovation:** one clear twist (AI triage from photo, multilingual, live risk + action). Say it in one sentence.
- **Feasibility:** show it works live. Mention who would use it (district control rooms, NGOs, panchayats) and why it is cheap to run.
- **Impact:** give a number. Example: "Triage cuts the time to find the 5 most critical reports from minutes to seconds."
- **Technical approach:** show a simple architecture diagram and name the stack, the fallback, and the data sources.

## Demo-day rules
1. Always have a **backup**: screenshot deck + 60-second screen recording of the working demo.
2. Click **Reset demo data** right before presenting.
3. Do not live-demo a feature that failed in the last test. Show it in the video instead.
4. Be honest about mock data and limitations. Judges respect "this is the next step".
5. Eat, drink water, and take one 10 minute break. Tired teams ship bugs.
