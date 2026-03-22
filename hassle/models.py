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
