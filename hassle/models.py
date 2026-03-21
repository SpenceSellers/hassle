from pydantic import BaseModel


class EntityState(BaseModel):
    entity_id: str
    state: str
    attributes: dict
