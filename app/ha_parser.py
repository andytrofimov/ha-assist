from pydantic import BaseModel, ConfigDict


class HaObject(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    name: str
    state: str
    aliases: str
    area_id: str | None = None
    area_name: str | None = None
    floor_id: str | None = None
    floor_name: str | None = None
