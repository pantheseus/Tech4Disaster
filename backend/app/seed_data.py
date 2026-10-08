"""Fake demo data around Tirunelveli. Clearly labelled as demo data in the README."""
import random
from datetime import datetime, timedelta
from .db import Report, Shelter, Alert, Call, Unit

CENTER = (8.7139, 77.7567)

SHELTERS = [
    ("Palayamkottai Govt School Camp", 8.7270, 77.7380, 300, 120, 1, 1, "0462-0000001"),
    ("Melapalayam Community Hall", 8.7010, 77.7120, 150, 90, 1, 0, "0462-0000002"),
    ("Tirunelveli Junction Relief Centre", 8.7330, 77.6960, 250, 40, 1, 1, "0462-0000003"),
    ("Vannarpettai Marriage Hall", 8.7380, 77.7330, 200, 195, 0, 0, "0462-0000004"),
    ("Thatchanallur Panchayat Building", 8.6760, 77.7350, 120, 30, 1, 0, "0462-0000005"),
    ("Pettai Higher Secondary School", 8.7510, 77.7120, 350, 210, 1, 1, "0462-0000006"),
    ("Gangaikondan Relief Camp", 8.8180, 77.7800, 180, 60, 1, 0, "0462-0000007"),
    ("Cheranmahadevi College Hall", 8.6900, 77.5640, 400, 150, 1, 1, "0462-0000008"),
]

REPORTS = [
    ("flood", "Water entering houses near the river bank, family with two children on the first floor", 5, "Melapalayam"),
    ("flood", "Road submerged, buses stopped, people waiting on the roadside", 3, "Palayamkottai"),
    ("medical", "Elderly man unconscious after climbing to terrace during flooding, needs ambulance", 5, "Vannarpettai"),
    ("fire", "Short circuit fire in a shop, smoke spreading to nearby houses", 4, "Tirunelveli Junction"),
    ("infrastructure", "Electric pole fallen across the road, live wire hanging", 4, "Thatchanallur"),
    ("flood", "Ground floor flooded, need drinking water and food for 20 people", 3, "Pettai"),
    ("medical", "Pregnant woman needs hospital transfer, road blocked by water", 5, "Gangaikondan"),
    ("landslide", "Mud and rocks fallen on the hill road, one vehicle stuck", 4, "Cheranmahadevi"),
    ("cyclone", "Strong wind, large tree uprooted on house roof, nobody hurt", 3, "Palayamkottai"),
    ("infrastructure", "Small bridge cracked and unsafe, villagers still crossing", 3, "Thatchanallur"),
    ("flood", "Cattle and farm tools washed away, farmers need fodder", 2, "Gangaikondan"),
    ("medical", "Need insulin and regular medicines, pharmacy closed due to flood", 3, "Melapalayam"),
    ("fire", "Hut fire near the railway track, fire is under control but family homeless", 3, "Tirunelveli Junction"),
    ("earthquake", "Felt strong tremor, cracks in old building wall, residents outside", 2, "Vannarpettai"),
    ("flood", "Old age home surrounded by water, 15 elderly residents need evacuation", 5, "Pettai"),
    ("other", "Mobile network down in the entire street, cannot call anyone", 2, "Palayamkottai"),
    ("medical", "Child with high fever, no transport available", 3, "Cheranmahadevi"),
    ("infrastructure", "Water pipeline burst, no drinking water since yesterday", 2, "Thatchanallur"),
    ("flood", "Two people trapped on a rooftop, water level still rising", 5, "Melapalayam"),
    ("landslide", "Minor soil slip near a house wall, wall cracked", 2, "Cheranmahadevi"),
]


def seed(db, reset: bool = True) -> dict:
    if reset:
        db.query(Report).delete()
        db.query(Shelter).delete()
        db.query(Alert).delete()
    rnd = random.Random(42)
    for name, lat, lng, cap, occ, food, med, contact in SHELTERS:
        db.add(Shelter(name=name, lat=lat, lng=lng, capacity=cap, occupied=occ,
                       food=food, medical=med, contact=contact))
    for rtype, desc, sev, area in REPORTS:
        db.add(Report(type=rtype, description=f"{desc} ({area})",
                      lat=CENTER[0] + rnd.uniform(-0.06, 0.07),
                      lng=CENTER[1] + rnd.uniform(-0.08, 0.08),
                      severity=sev, status=rnd.choice(["open", "open", "open", "assigned"]),
                      contact="9XXXXXXXXX"))
    db.add(Alert(level="warning", message="DEMO: Control room operating normally. Report emergencies via the Report page or call 112."))
    db.commit()
    cr = seed_control_room(db, reset=reset)
    return {"reports": len(REPORTS), "shelters": len(SHELTERS), "alerts": 1, **cr}


# ---------------------------------------------------------------- CallPrior --
UNITS = [
    ("Ambulance A1", "ambulance", 8.7290, 77.7400),
    ("Ambulance A2", "ambulance", 8.7050, 77.7200),
    ("Ambulance A3", "ambulance", 8.7500, 77.7700),
    ("Fire Tender F1", "fire_tender", 8.7340, 77.7000),
    ("Fire Tender F2", "fire_tender", 8.6900, 77.7600),
    ("Rescue Boat B1", "rescue_boat", 8.7100, 77.7150),
    ("Rescue Team R1", "rescue_team", 8.7400, 77.7300),
    ("Police P1", "police", 8.7200, 77.7500),
]

# (description, type, severity, flags, minutes_ago, state, minutes_to_assign, minutes_to_close, unit_index)
SEED_CALLS = [
    ("Water entering house, old woman bedridden and cannot get out", "flood", 5, "elderly,disabled", 9, "waiting", None, None, None),
    ("Bike and lorry collision, one rider bleeding heavily", "accident", 5, "bleeding", 4, "waiting", None, None, None),
    ("Street light not working since last night", "other", 1, "", 14, "waiting", None, None, None),
    ("Smoke from a closed shop, no one inside as far as caller knows", "fire", 3, "", 6, "waiting", None, None, None),
    ("Two children on a rooftop, flood water rising", "flood", 5, "child,trapped", 1, "waiting", None, None, None),
    ("Elderly man chest pain, conscious", "medical", 4, "elderly", 22, "assigned", 1.5, None, 0),
    ("Tree fell on road, traffic blocked, nobody hurt", "infrastructure", 2, "", 30, "assigned", 8, None, 6),
    ("Car overturned, driver injured leg", "accident", 4, "", 55, "closed", 3, 31, 1),
    ("Kitchen fire in a house, controlled by neighbours", "fire", 3, "", 70, "closed", 4, 25, 3),
    ("Pregnant woman needs hospital transfer", "medical", 5, "pregnant", 95, "closed", 1, 40, 2),
]


def seed_control_room(db, reset: bool = True) -> dict:
    """Units + a realistic mix of waiting / assigned / closed calls so metrics look alive."""
    if reset:
        db.query(Call).delete()
        db.query(Unit).delete()
        db.commit()
    elif db.query(Unit).count() or db.query(Call).count():
        return {"units": 0, "calls": 0}
    rnd = random.Random(7)
    units = []
    for name, utype, lat, lng in UNITS:
        u = Unit(name=name, type=utype, lat=lat, lng=lng, status="available")
        db.add(u)
        units.append(u)
    db.flush()
    now = datetime.utcnow()
    for desc, ctype, sev, flags, mins_ago, state, to_assign, to_close, unit_idx in SEED_CALLS:
        created = now - timedelta(minutes=mins_ago)
        call = Call(caller_name=rnd.choice(["Murugan", "Lakshmi", "Karthik", "Priya", "Selvam"]),
                    caller_phone="9XXXXXXXXX", location_text="Tirunelveli",
                    lat=CENTER[0] + rnd.uniform(-0.05, 0.06), lng=CENTER[1] + rnd.uniform(-0.07, 0.07),
                    description=desc, incident_type=ctype, severity=sev, flags=flags, status=state,
                    source="operator", created_at=created)
        if state in ("assigned", "closed"):
            call.assigned_at = created + timedelta(minutes=to_assign)
            call.assigned_unit_id = units[unit_idx].id
        if state == "closed":
            call.closed_at = created + timedelta(minutes=to_close)
        db.add(call)
        db.flush()
        if state == "assigned":
            units[unit_idx].status, units[unit_idx].current_call_id = "busy", call.id
    db.commit()
    return {"units": len(UNITS), "calls": len(SEED_CALLS)}
