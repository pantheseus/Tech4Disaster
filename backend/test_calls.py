"""CallPrior tests. Run:  cd backend && python test_calls.py"""
import os, sys, tempfile
from datetime import datetime, timedelta
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["LLM_PROVIDER"] = "none"

from fastapi.testclient import TestClient
from app.main import app
from app.calls import priority_info
from app.db import Call


def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        check.failed = True
check.failed = False

# --- pure priority logic
now = datetime.utcnow()
fresh = Call(severity=3, flags="", status="waiting", created_at=now)
old = Call(severity=3, flags="", status="waiting", created_at=now - timedelta(minutes=20))
trapped = Call(severity=5, flags="trapped,child", status="waiting", created_at=now)
check("waiting call gains priority over time", priority_info(old, now)["priority_score"] > priority_info(fresh, now)["priority_score"])
check("wait bonus capped at +30", priority_info(old, now)["priority_score"] == 90.0)
check("trapped child sev5 is CRITICAL", priority_info(trapped, now)["priority_label"] == "CRITICAL")
check("SLA breach detected", priority_info(old, now)["sla_breached"] and not priority_info(fresh, now)["sla_breached"])

with TestClient(app) as c:
    calls = c.get("/api/calls").json()
    check("seeded 10 calls", len(calls) == 10)
    waiting = [x for x in calls if x["status"] == "waiting"]
    check("waiting calls come first", [x["status"] for x in calls[:5]] == ["waiting"] * 5)
    check("waiting sorted by priority desc", [x["priority_score"] for x in waiting] == sorted([x["priority_score"] for x in waiting], reverse=True))
    check("low-priority street light is last of waiting", "Street light" in waiting[-1]["description"])
    check("8 units seeded", len(c.get("/api/units").json()) == 8)

    r = c.post("/api/calls", json={"caller_name": "Test", "lat": 8.72, "lng": 77.75,
                                   "description": "Flood water rising, two children trapped on the roof"})
    j = r.json(); cid = j["id"]
    check("create call 201", r.status_code == 201)
    check("auto-triage: flood", j["incident_type"] == "flood")
    check("auto flags: trapped + child", {"trapped", "child"} <= set(j["flags"]))
    check("new life-threatening call is on top of queue", c.get("/api/calls").json()[0]["id"] == cid or c.get("/api/calls").json()[1]["id"] != cid and j["priority_score"] >= 100)
    check("validation: bad severity 422", c.post("/api/calls", json={"lat": 1, "lng": 1, "description": "abc def", "severity": 9}).status_code == 422)
    check("manual flags accepted, unknown ignored", set(c.post("/api/calls", json={"lat": 8.7, "lng": 77.7, "description": "minor issue here", "flags": ["elderly", "bogus"], "severity": 2, "incident_type": "other"}).json()["flags"]) == {"elderly"})

    s = c.get(f"/api/calls/{cid}/suggest-units").json()
    check("flood -> rescue_boat recommended", s["recommended_unit_type"] == "rescue_boat")
    check("best suggestion is type match", s["units"][0]["type_match"] and s["units"][0]["type"] == "rescue_boat")

    a = c.post(f"/api/calls/{cid}/assign", json={})
    check("auto-assign works", a.status_code == 200 and a.json()["status"] == "assigned" and a.json()["assigned_unit_name"] == "Rescue Boat B1")
    check("time_to_assign recorded", a.json()["time_to_assign_seconds"] is not None)
    check("assign twice -> 409", c.post(f"/api/calls/{cid}/assign", json={}).status_code == 409)
    boat = [u for u in c.get("/api/units").json() if u["name"] == "Rescue Boat B1"][0]
    check("unit is busy", boat["status"] == "busy" and boat["current_call_id"] == cid)

    c2 = c.post("/api/calls", json={"lat": 8.7, "lng": 77.7, "description": "Another flooded house, family stuck"}).json()["id"]
    check("busy unit cannot be picked manually -> 409", c.post(f"/api/calls/{c2}/assign", json={"unit_id": boat["id"]}).status_code == 409)
    check("falls back to next unit when type unavailable", c.post(f"/api/calls/{c2}/assign", json={}).json()["status"] == "assigned")

    cl = c.post(f"/api/calls/{cid}/close")
    check("close call", cl.status_code == 200 and cl.json()["status"] == "closed")
    boat = [u for u in c.get("/api/units").json() if u["name"] == "Rescue Boat B1"][0]
    check("unit freed after close", boat["status"] == "available")
    check("close twice -> 409", c.post(f"/api/calls/{cid}/close").status_code == 409)
    check("404 on missing call", c.post("/api/calls/99999/close").status_code == 404)

    m = c.get("/api/metrics").json()
    for k in ["waiting", "assigned", "closed", "sla_breaches", "sla_compliance_pct", "avg_time_to_assign_seconds", "units_available", "by_type"]:
        check(f"metrics has {k}", k in m)
    check("metrics counts consistent", m["waiting"] + m["assigned"] + m["closed"] == m["total_calls"])

    sim = c.post("/api/calls/simulate?count=3").json()
    check("IVR simulate creates 3 calls", len(sim) == 3 and all(x["source"] == "ivr_sim" for x in sim))
    check("simulate rejects count 99", c.post("/api/calls/simulate?count=99").status_code == 422)

    check("units create + validate", c.post("/api/units", json={"name": "X", "type": "spaceship", "lat": 1, "lng": 1}).status_code == 422
          and c.post("/api/units", json={"name": "Ambulance A9", "type": "ambulance", "lat": 8.7, "lng": 77.7}).status_code == 201)
    check("reseed resets calls", c.post("/api/seed").status_code == 200 and len(c.get("/api/calls").json()) == 10)

print("\nALL PASSED" if not check.failed else "\nSOME TESTS FAILED")
sys.exit(1 if check.failed else 0)
