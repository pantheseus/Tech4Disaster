import time
import uuid
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import config, llm, rag, alerts as alert_service, external
from .db import init_db, get_db, SessionLocal, Report, Shelter, Alert
from .calls import router as calls_router
from .schemas import (ReportIn, ReportOut, ReportUpdate, ShelterIn, ShelterOut,
                      AlertIn, AlertOut, AskIn)
from .seed_data import seed, seed_control_room

app = FastAPI(title="Tech4Disaster Starter API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(calls_router)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        # Auto-seed demo data the first time so the map is never empty
        if db.query(Report).count() == 0 and db.query(Shelter).count() == 0:
            seed(db, reset=False)
        # Also covers an older database that has no control-room data yet
        seed_control_room(db, reset=False)
    finally:
        db.close()
    try:
        info = rag.build_index()
        print(f"[rag] indexed {info}")
    except Exception as e:
        print(f"[rag] index failed: {e}")


# ----------------------------------------------------------------- health ----
@app.get("/api/health")
def health():
    return {"status": "ok", "time": time.time(), "llm": llm.provider_info(),
            "map_center": [config.DEFAULT_LAT, config.DEFAULT_LNG]}


# ---------------------------------------------------------------- reports ----
@app.get("/api/reports", response_model=list[ReportOut])
def list_reports(status: Optional[str] = None, type: Optional[str] = None,
                 min_severity: int = Query(1, ge=1, le=5), db: Session = Depends(get_db)):
    q = db.query(Report).filter(Report.severity >= min_severity)
    if status:
        q = q.filter(Report.status == status)
    if type:
        q = q.filter(Report.type == type)
    # Triage order: most severe first, then newest
    return q.order_by(Report.severity.desc(), Report.created_at.desc()).all()


@app.post("/api/reports", response_model=ReportOut, status_code=201)
def create_report(payload: ReportIn, db: Session = Depends(get_db)):
    report = Report(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@app.patch("/api/reports/{report_id}", response_model=ReportOut)
def update_report(report_id: int, payload: ReportUpdate, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(report, k, v)
    db.commit()
    db.refresh(report)
    return report


@app.delete("/api/reports/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    db.delete(report)
    db.commit()


# --------------------------------------------------------------- shelters ----
@app.get("/api/shelters", response_model=list[ShelterOut])
def list_shelters(db: Session = Depends(get_db)):
    return db.query(Shelter).all()


@app.post("/api/shelters", response_model=ShelterOut, status_code=201)
def create_shelter(payload: ShelterIn, db: Session = Depends(get_db)):
    s = Shelter(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@app.patch("/api/shelters/{shelter_id}", response_model=ShelterOut)
def update_shelter(shelter_id: int, payload: ShelterIn, db: Session = Depends(get_db)):
    s = db.get(Shelter, shelter_id)
    if not s:
        raise HTTPException(404, "Shelter not found")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


# ----------------------------------------------------------------- alerts ----
@app.get("/api/alerts", response_model=list[AlertOut])
def list_alerts(db: Session = Depends(get_db)):
    return db.query(Alert).order_by(Alert.created_at.desc()).limit(10).all()


@app.post("/api/alerts", response_model=AlertOut, status_code=201)
def create_alert(payload: AlertIn, db: Session = Depends(get_db)):
    a = Alert(**payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    alert_service.send_alert(a.level, a.message)
    return a


# --------------------------------------------------------------- uploads -----
@app.post("/api/upload")
async def upload_photo(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Only JPEG, PNG, WEBP or GIF images are allowed")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Image too large (max 8 MB)")
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}[file.content_type]
    name = f"{uuid.uuid4().hex}.{ext}"
    (config.UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


# --------------------------------------------------------------------- AI ----
@app.post("/api/ai/analyze")
async def ai_analyze(text: str = Form(...), file: Optional[UploadFile] = File(None)):
    """Triage a report: category, severity 1-5, summary, suggested action."""
    image_bytes, media_type = None, None
    if file is not None and file.filename:
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(400, "Only JPEG, PNG, WEBP or GIF images are allowed")
        image_bytes = await file.read()
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image too large (max 8 MB)")
        media_type = file.content_type
    return llm.analyze_report(text, image_bytes, media_type)


@app.post("/api/rag/ask")
def rag_ask(payload: AskIn):
    return rag.answer(payload.question, payload.language)


@app.post("/api/rag/reindex")
def rag_reindex():
    return rag.build_index()


@app.post("/api/rag/upload")
async def rag_upload(file: UploadFile = File(...)):
    """Upload a PDF/TXT/MD guideline during the hackathon and index it instantly."""
    name = (file.filename or "").lower()
    if not name.endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Upload a .pdf, .txt or .md file")
    safe = f"{uuid.uuid4().hex[:8]}_{''.join(c for c in file.filename if c.isalnum() or c in '._-')}"
    (config.RAG_DOCS_DIR / safe).write_bytes(await file.read())
    return {"saved": safe, **rag.build_index()}


# ------------------------------------------------------------ stats / data ---
@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    by_status = dict(db.query(Report.status, func.count(Report.id)).group_by(Report.status).all())
    by_type = dict(db.query(Report.type, func.count(Report.id)).group_by(Report.type).all())
    cap = db.query(func.coalesce(func.sum(Shelter.capacity), 0), func.coalesce(func.sum(Shelter.occupied), 0)).one()
    return {
        "total_reports": db.query(Report).count(),
        "critical_reports": db.query(Report).filter(Report.severity >= 4, Report.status != "resolved").count(),
        "by_status": by_status,
        "by_type": by_type,
        "shelter_capacity": int(cap[0]),
        "shelter_occupied": int(cap[1]),
    }


@app.get("/api/external/weather")
def ext_weather(lat: float = config.DEFAULT_LAT, lng: float = config.DEFAULT_LNG):
    try:
        return external.weather(lat, lng)
    except Exception as e:
        raise HTTPException(502, f"Weather service unavailable: {e}")


@app.get("/api/external/earthquakes")
def ext_quakes(min_magnitude: float = 4.5):
    try:
        return external.earthquakes(min_magnitude)
    except Exception as e:
        raise HTTPException(502, f"USGS service unavailable: {e}")


@app.post("/api/seed")
def reseed(db: Session = Depends(get_db)):
    """Reset the database to the demo data (use before your demo!)."""
    return seed(db, reset=True)


# ----------------------------------------------------------- static files ----
app.mount("/uploads", StaticFiles(directory=str(config.UPLOAD_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
