from pydantic import BaseModel


class HaObject(BaseModel):
    entity_id: str
    name: str
    state: str
    aliases: str
