from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AttendanceAction(str, Enum):
    clock_in = "clock_in"
    clock_out = "clock_out"


class EnrollResponse(BaseModel):
    employee_id: str
    external_id: str
    templates: int


class RecognitionResponse(BaseModel):
    event_id: str
    decision: str
    action: AttendanceAction
    employee_id: str | None
    display_name: str | None
    similarity: float = Field(ge=-1, le=1)
    reason: str


class EventResponse(BaseModel):
    id: str
    employee_id: str | None
    action: str
    decision: str
    similarity: float
    camera_id: str
    reason: str
    occurred_at: datetime
    event_hash: str

