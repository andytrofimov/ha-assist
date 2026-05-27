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
    unit_of_measurement: str | None = None
    device_class: str | None = None
    hvac_modes: list[str] | None = None
    temperature: str | int | float | None = None
    humidity: str | int | float | None = None
    wind_speed: str | int | float | None = None
