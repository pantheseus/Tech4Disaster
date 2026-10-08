from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ReportIn(BaseModel):
    type: str = "other"
    description: str = Field(min_length=3)
    lat: float
    lng: float
    severity: int = Field(default=3, ge=1, le=5)
    photo_url: Optional[str] = None
    contact: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_action: Optional[str] = None


class ReportUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[int] = Field(default=None, ge=1, le=5)
    type: Optional[str] = None


class ReportOut(ReportIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime


class ShelterIn(BaseModel):
    name: str
    lat: float
    lng: float
    capacity: int = 100
    occupied: int = 0
    food: int = 1
    medical: int = 0
    contact: Optional[str] = None


class ShelterOut(ShelterIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AlertIn(BaseModel):
    level: str = "warning"
    message: str = Field(min_length=3)


class AlertOut(AlertIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class AskIn(BaseModel):
    question: str = Field(min_length=2)
    language: str = "English"   # e.g. "Tamil", "Hindi"
