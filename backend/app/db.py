from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Report(Base):
    """A citizen / volunteer report: someone needs help or spotted a hazard."""
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), default="other")          # flood, fire, medical, earthquake, ...
    description = Column(Text, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    severity = Column(Integer, default=3)               # 1 (low) - 5 (critical)
    status = Column(String(30), default="open")         # open | assigned | resolved
    photo_url = Column(String(300), nullable=True)
    contact = Column(String(100), nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_action = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Shelter(Base):
    """A relief camp / shelter with capacity and resources."""
    __tablename__ = "shelters"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    capacity = Column(Integer, default=100)
    occupied = Column(Integer, default=0)
    food = Column(Integer, default=1)       # 1 = available
    medical = Column(Integer, default=0)
    contact = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """Broadcast alert shown as a banner on the dashboard."""
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), default="warning")   # info | warning | danger
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Unit(Base):
    """A response unit (ambulance, fire tender, rescue boat ...)."""
    __tablename__ = "units"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    type = Column(String(30), nullable=False)       # ambulance | fire_tender | rescue_boat | rescue_team | police
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    status = Column(String(20), default="available")  # available | busy | offline
    current_call_id = Column(Integer, nullable=True)


class Call(Base):
    """An emergency call logged by an operator (CallPrior core table)."""
    __tablename__ = "calls"
    id = Column(Integer, primary_key=True, index=True)
    caller_name = Column(String(100), default="Unknown")
    caller_phone = Column(String(30), nullable=True)
    location_text = Column(String(200), nullable=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    incident_type = Column(String(30), default="other")
    severity = Column(Integer, default=3)               # 1-5
    flags = Column(String(200), default="")             # comma separated: trapped,child,elderly,...
    status = Column(String(20), default="waiting")      # waiting | assigned | closed
    source = Column(String(20), default="operator")     # operator | ivr_sim
    ai_summary = Column(Text, nullable=True)
    ai_action = Column(Text, nullable=True)
    assigned_unit_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    assigned_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
