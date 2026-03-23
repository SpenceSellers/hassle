from datetime import datetime

from pydantic import BaseModel


class EntityState(BaseModel):
    entity_id: str
    state: str
    attributes: dict


class HistoryEntry(BaseModel):
    entity_id: str
    state: str
    attributes: dict
    last_changed: datetime


class Calendar(BaseModel):
    entity_id: str
    name: str


class CalendarEvent(BaseModel):
    summary: str
    start: dict
    end: dict
    uid: str | None = None
    description: str | None = None
    location: str | None = None
    recurrence_id: str | None = None
    rrule: str | None = None


class TodoItem(BaseModel):
    summary: str
    uid: str
    status: str
    description: str | None = None
    due_date: str | None = None
    due_datetime: str | None = None
