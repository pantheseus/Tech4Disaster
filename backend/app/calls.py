"""
CallPrior core: emergency call intake, priority scoring, queue, unit assignment, supervisor metrics.

PRIORITY SCORE (recomputed live, so waiting calls rise in the queue):
    score = severity x 20                         (20 - 100)
          + vulnerability flags (max +30)         trapped +15, unconscious +12, bleeding +10, pregnant +10,
                                                  child +8, elderly +8, disabled +6
          + waiting bonus (max +30)               +1.5 points per minute a call is still waiting
    label: >=110 CRITICAL | >=80 HIGH | >=50 MEDIUM | else LOW

SLA (max wait before a unit must be assigned): sev5 2 min, sev4 5, sev3 10, sev2 20, sev1 30.
"""
import math
import random
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import config, llm
from .db import get_db, Call, Unit

router = APIRouter(prefix="/api", tags=["control-room"])

FLAG_POINTS = {"trapped": 15, "unconscious": 12, "bleeding": 10, "pregnant": 10,
               "child": 8, "elderly": 8, "disabled": 6}
FLAG_KEYWORDS = {
    "trapped": ["trapped", "stuck", "cannot get out", "can't get out", "locked in"],
    "unconscious": ["unconscious", "not breathing", "fainted", "unresponsive"],
    "bleeding": ["bleed", "blood"],
    "pregnant": ["pregnan"],
    "child": ["child", "children", "baby", "kid", "infant"],
    "elderly": ["elderly", "old man", "old woman", "old age", "senior", "grandmother", "grandfather"],
    "disabled": ["disabled", "wheelchair", "bedridden", "handicap"],
}
SLA_SECONDS = {5: 120, 4: 300, 3: 600, 2: 1200, 1: 1800}
TYPE_TO_UNIT = {"flood": "rescue_boat", "fire": "fire_tender", "medical": "ambulance", "accident": "ambulance",
                "earthquake": "rescue_team", "cyclone": "rescue_team", "landslide": "rescue_team",
                "infrastructure": "rescue_team", "other": "police"}
UNIT_TYPES = ["ambulance", "fire_tender", "rescue_boat", "rescue_team", "police"]
AVG_SPEED_KMH = 35


# ------------------------------------------------------------------ helpers --
def detect_flags(text: str) -> List[str]:
    t = text.lower()
    return [f for f, kws in FLAG_KEYWORDS.items() if any(k in t for k in kws)]


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _flags(call: Call) -> List[str]:
    return [f for f in (call.flags or "").split(",") if f]


def priority_info(call: Call, now: Optional[datetime] = None) -> dict:
    now = now or datetime.utcnow()
    waiting = call.status == "waiting"
    wait_s = max(0.0, (now - call.created_at).total_seconds()) if waiting else 0.0
    flag_pts = min(30, sum(FLAG_POINTS.get(f, 0) for f in _flags(call)))
    wait_bonus = min(30.0, wait_s / 60 * 1.5)
    score = round(call.severity * 20 + flag_pts + wait_bonus, 1)
    label = "CRITICAL" if score >= 110 else "HIGH" if score >= 80 else "MEDIUM" if score >= 50 else "LOW"
    sla = SLA_SECONDS.get(call.severity, 600)
    if waiting:
        breached = wait_s > sla
    elif call.assigned_at:
        breached = (call.assigned_at - call.created_at).total_seconds() > sla
    elif call.closed_at:
        breached = (call.closed_at - call.created_at).total_seconds() > sla
    else:
        breached = False
    return {"priority_score": score, "priority_label": label, "wait_seconds": int(wait_s),
            "sla_seconds": sla, "sla_breached": breached}


def serialize(call: Call, unit_names: dict, now: Optional[datetime] = None) -> dict:
    d = {
        "id": call.id, "caller_name": call.caller_name, "caller_phone": call.caller_phone,
        "location_text": call.location_text, "lat": call.lat, "lng": call.lng,
        "description": call.description, "incident_type": call.incident_type, "severity": call.severity,
        "flags": _flags(call), "status": call.status, "source": call.source,
        "ai_summary": call.ai_summary, "ai_action": call.ai_action,
        "assigned_unit_id": call.assigned_unit_id, "assigned_unit_name": unit_names.get(call.assigned_unit_id),
        "created_at": call.created_at.isoformat(),
        "assigned_at": call.assigned_at.isoformat() if call.assigned_at else None,
        "closed_at": call.closed_at.isoformat() if call.closed_at else None,
        "time_to_assign_seconds": int((call.assigned_at - call.created_at).total_seconds()) if call.assigned_at else None,
        "recommended_unit_type": TYPE_TO_UNIT.get(call.incident_type, "police"),
    }
    d.update(priority_info(call, now))
    return d


def _unit_names(db: Session) -> dict:
    return {u.id: u.name for u in db.query(Unit).all()}


def rank_units(call: Call, db: Session) -> List[dict]:
    """Available units, best first: matching type, then nearest."""
    wanted = TYPE_TO_UNIT.get(call.incident_type, "police")
    out = []
    for u in db.query(Unit).filter(Unit.status == "available").all():
        km = haversine_km(call.lat, call.lng, u.lat, u.lng)
        out.append({"unit_id": u.id, "name": u.name, "type": u.type, "type_match": u.type == wanted,
                    "distance_km": round(km, 2), "eta_minutes": round(km / AVG_SPEED_KMH * 60, 1)})
    out.sort(key=lambda x: (not x["type_match"], x["distance_km"]))
    return out


def create_call_record(db: Session, data: dict) -> Call:
    """Shared by the API and the IVR simulator. Auto-triages with AI when type/severity not given."""
    description = data["description"].strip()
    incident_type, severity = data.get("incident_type"), data.get("severity")
    summary = action = None
    if not incident_type or not severity:
        t = llm.analyze_report(description)
        incident_type = incident_type or t["category"]
        severity = severity or t["severity"]
        summary, action = t["summary"], t["suggested_action"]
    if incident_type not in llm.CATEGORIES:
        incident_type = "other"
    flags = sorted({f for f in data.get("flags", []) if f in FLAG_POINTS} | set(detect_flags(description)))
    call = Call(caller_name=(data.get("caller_name") or "Unknown")[:100], caller_phone=data.get("caller_phone"),
                location_text=data.get("location_text"), lat=data["lat"], lng=data["lng"],
                description=description, incident_type=incident_type, severity=int(severity),
                flags=",".join(flags), status="waiting", source=data.get("source", "operator"),
                ai_summary=summary, ai_action=action)
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


# ------------------------------------------------------------------ schemas --
class CallIn(BaseModel):
    caller_name: str = "Unknown"
    caller_phone: Optional[str] = None
    location_text: Optional[str] = None
    lat: float
    lng: float
    description: str = Field(min_length=3)
    incident_type: Optional[str] = None
    severity: Optional[int] = Field(default=None, ge=1, le=5)
    flags: List[str] = Field(default_factory=list)
    source: str = "operator"


class AssignIn(BaseModel):
    unit_id: Optional[int] = None


class UnitIn(BaseModel):
    name: str
    type: str
    lat: float
    lng: float


class UnitPatch(BaseModel):
    status: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


# ---------------------------------------------------------------- endpoints --
@router.post("/calls", status_code=201)
def create_call(payload: CallIn, db: Session = Depends(get_db)):
    call = create_call_record(db, payload.model_dump())
    return serialize(call, _unit_names(db))


@router.get("/calls")
def list_calls(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Queue order: waiting (highest priority first), then assigned, then closed (newest first)."""
    q = db.query(Call)
    if status:
        q = q.filter(Call.status == status)
    now, names = datetime.utcnow(), _unit_names(db)
    rows = [serialize(c, names, now) for c in q.all()]
    order = {"waiting": 0, "assigned": 1, "closed": 2}
    rows.sort(key=lambda r: (order[r["status"]], -r["priority_score"]) if r["status"] != "closed"
              else (2, -datetime.fromisoformat(r["created_at"]).timestamp()))
    return rows


@router.get("/calls/{call_id}")
def get_call(call_id: int, db: Session = Depends(get_db)):
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    return serialize(call, _unit_names(db))


@router.get("/calls/{call_id}/suggest-units")
def suggest_units(call_id: int, db: Session = Depends(get_db)):
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    return {"recommended_unit_type": TYPE_TO_UNIT.get(call.incident_type, "police"), "units": rank_units(call, db)}


@router.post("/calls/{call_id}/assign")
def assign_call(call_id: int, payload: AssignIn, db: Session = Depends(get_db)):
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    if call.status != "waiting":
        raise HTTPException(409, f"Call is already {call.status}")
    if payload.unit_id is None:
        ranked = rank_units(call, db)
        if not ranked:
            raise HTTPException(409, "No available units")
        unit = db.get(Unit, ranked[0]["unit_id"])
    else:
        unit = db.get(Unit, payload.unit_id)
        if not unit:
            raise HTTPException(404, "Unit not found")
        if unit.status != "available":
            raise HTTPException(409, f"{unit.name} is {unit.status}")
    unit.status, unit.current_call_id = "busy", call.id
    call.status, call.assigned_unit_id, call.assigned_at = "assigned", unit.id, datetime.utcnow()
    db.commit()
    db.refresh(call)
    return serialize(call, _unit_names(db))


@router.post("/calls/{call_id}/close")
def close_call(call_id: int, db: Session = Depends(get_db)):
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found")
    if call.status == "closed":
        raise HTTPException(409, "Call already closed")
    if call.assigned_unit_id:
        unit = db.get(Unit, call.assigned_unit_id)
        if unit and unit.current_call_id == call.id:
            unit.status, unit.current_call_id = "available", None
    call.status, call.closed_at = "closed", datetime.utcnow()
    db.commit()
    db.refresh(call)
    return serialize(call, _unit_names(db))


@router.get("/units")
def list_units(db: Session = Depends(get_db)):
    names_to_call = {c.id: c for c in db.query(Call).filter(Call.status == "assigned").all()}
    out = []
    for u in db.query(Unit).order_by(Unit.type, Unit.name).all():
        c = names_to_call.get(u.current_call_id)
        out.append({"id": u.id, "name": u.name, "type": u.type, "lat": u.lat, "lng": u.lng, "status": u.status,
                    "current_call_id": u.current_call_id,
                    "current_call_summary": (c.description[:70] if c else None)})
    return out


@router.post("/units", status_code=201)
def create_unit(payload: UnitIn, db: Session = Depends(get_db)):
    if payload.type not in UNIT_TYPES:
        raise HTTPException(422, f"type must be one of {UNIT_TYPES}")
    u = Unit(**payload.model_dump())
    db.add(u)
    db.commit()
    db.refresh(u)
    return {"id": u.id, "name": u.name, "type": u.type, "status": u.status}


@router.patch("/units/{unit_id}")
def patch_unit(unit_id: int, payload: UnitPatch, db: Session = Depends(get_db)):
    u = db.get(Unit, unit_id)
    if not u:
        raise HTTPException(404, "Unit not found")
    if payload.status and payload.status not in ("available", "busy", "offline"):
        raise HTTPException(422, "status must be available, busy or offline")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(u, k, v)
    db.commit()
    return {"id": u.id, "name": u.name, "status": u.status, "lat": u.lat, "lng": u.lng}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    """Supervisor dashboard numbers."""
    now = datetime.utcnow()
    calls = db.query(Call).all()
    rows = [(c, priority_info(c, now)) for c in calls]
    waiting = [(c, p) for c, p in rows if c.status == "waiting"]
    assign_times = [(c.assigned_at - c.created_at).total_seconds() for c in calls if c.assigned_at]
    close_times = [(c.closed_at - c.created_at).total_seconds() for c in calls if c.closed_at]
    breaches = sum(1 for _, p in rows if p["sla_breached"])
    by_type, by_sev = {}, {}
    for c in calls:
        by_type[c.incident_type] = by_type.get(c.incident_type, 0) + 1
        by_sev[str(c.severity)] = by_sev.get(str(c.severity), 0) + 1
    units = db.query(Unit).all()
    avg = lambda xs: round(sum(xs) / len(xs), 1) if xs else None
    return {
        "total_calls": len(calls),
        "waiting": len(waiting),
        "assigned": sum(1 for c in calls if c.status == "assigned"),
        "closed": sum(1 for c in calls if c.status == "closed"),
        "critical_waiting": sum(1 for _, p in waiting if p["priority_label"] in ("CRITICAL", "HIGH")),
        "longest_wait_seconds": max((p["wait_seconds"] for _, p in waiting), default=0),
        "avg_time_to_assign_seconds": avg(assign_times),
        "avg_time_to_close_seconds": avg(close_times),
        "sla_breaches": breaches,
        "sla_compliance_pct": round(100 * (1 - breaches / len(calls)), 1) if calls else 100.0,
        "by_type": by_type, "by_severity": by_sev,
        "units_total": len(units),
        "units_available": sum(1 for u in units if u.status == "available"),
        "units_busy": sum(1 for u in units if u.status == "busy"),
    }


# ------------------------------------------------------- IVR call simulator --
SIM_CALLS = [
    "Our house is flooded, my mother is bedridden and we cannot get out, water is rising fast",
    "Bike and lorry collision on the highway, one person bleeding heavily and not moving",
    "Fire in a textile shop, smoke is coming out and people are stuck inside on the first floor",
    "My father is having chest pain and is sweating a lot, please send an ambulance",
    "Tree fell on the road near the school, traffic is blocked but nobody is hurt",
    "Two children are trapped on a rooftop, water is all around the house",
    "Pregnant woman in labour pain, road is waterlogged, we cannot reach the hospital",
    "Car overturned in a ditch, driver is conscious but his leg is injured",
    "Street light is not working since last night",
    "Water tank leaking in our building, please check when you are free",
    "Landslide blocked the hill road, a jeep is stuck, driver is shouting for help",
    "Short circuit sparks in a transformer, people are gathering around, afraid of fire",
    "Elderly neighbour fell in the bathroom and is unconscious",
    "Stray dogs near the bus stand are scaring people",
    "Strong wind, electric pole fell on a house, a child inside is crying",
]
SIM_NAMES = ["Murugan", "Lakshmi", "Karthik", "Priya", "Selvam", "Meena", "Ravi", "Anitha", "Suresh", "Divya"]


@router.post("/calls/simulate")
def simulate_calls(count: int = Query(1, ge=1, le=5), db: Session = Depends(get_db)):
    """Pretend the IVR just received call(s). Great for the live demo."""
    created = []
    for text in random.sample(SIM_CALLS, count):
        call = create_call_record(db, {
            "caller_name": random.choice(SIM_NAMES), "caller_phone": "9" + "".join(random.choices("0123456789", k=9)),
            "location_text": "Reported via IVR (location pinned from caller)",
            "lat": config.DEFAULT_LAT + random.uniform(-0.05, 0.06),
            "lng": config.DEFAULT_LNG + random.uniform(-0.07, 0.07),
            "description": text, "source": "ivr_sim"})
        created.append(serialize(call, _unit_names(db)))
    return created
