"""Smoke test. Run before the hackathon on every laptop:   cd backend && python test_smoke.py"""
import os, sys, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["LLM_PROVIDER"] = "none"

from fastapi.testclient import TestClient
from app.main import app


def check(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        check.failed = True
check.failed = False

with TestClient(app) as c:
    r = c.get("/api/health"); check("health", r.status_code == 200 and r.json()["status"] == "ok")

    r = c.get("/api/reports"); data = r.json()
    check("seed data loaded (20 reports)", r.status_code == 200 and len(data) == 20)
    check("sorted by severity desc", data[0]["severity"] == 5)
    check("shelters loaded", len(c.get("/api/shelters").json()) == 8)

    r = c.post("/api/reports", json={"type": "flood", "description": "Test flood report", "lat": 8.7, "lng": 77.7, "severity": 4})
    check("create report", r.status_code == 201); rid = r.json()["id"]
    r = c.patch(f"/api/reports/{rid}", json={"status": "resolved"}); check("update report", r.json()["status"] == "resolved")
    check("validation rejects bad severity", c.post("/api/reports", json={"description": "x y z", "lat": 1, "lng": 1, "severity": 9}).status_code == 422)
    check("delete report", c.delete(f"/api/reports/{rid}").status_code == 204)
    check("404 on missing", c.patch("/api/reports/99999", json={"status": "open"}).status_code == 404)

    r = c.post("/api/ai/analyze", data={"text": "Two children trapped on roof, flood water rising"})
    j = r.json(); check("ai triage (fallback)", r.status_code == 200 and j["category"] == "flood" and j["severity"] >= 4)

    r = c.post("/api/rag/ask", json={"question": "What should I do during a flood?"})
    check("rag answer", r.status_code == 200 and len(r.json()["sources"]) > 0)

    check("alert create", c.post("/api/alerts", json={"level": "danger", "message": "Test alert"}).status_code == 201)
    s = c.get("/api/stats").json(); check("stats", s["total_reports"] == 20)
    check("upload rejects non-image", c.post("/api/upload", files={"file": ("x.txt", b"hi", "text/plain")}).status_code == 400)
    png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cf000000030001015c4d3b0d0000000049454e44ae426082")
    r = c.post("/api/upload", files={"file": ("a.png", png, "image/png")}); check("upload image", r.status_code == 200 and r.json()["url"].startswith("/uploads/"))
    check("frontend served", c.get("/").status_code == 200 and "Command Dashboard" in c.get("/").text)
    check("report page served", c.get("/report.html").status_code == 200)
    check("chat page served", c.get("/chat.html").status_code == 200)
    check("reseed", c.post("/api/seed").status_code == 200)

print("\nALL PASSED" if not check.failed else "\nSOME TESTS FAILED")
sys.exit(1 if check.failed else 0)
