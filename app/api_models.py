from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssistEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    name: str
    state: str
    aliases: str = ""
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


class AssistArea(BaseModel):
    model_config = ConfigDict(extra="allow")

    area_id: str | None = None
    name: str
    floor_id: str | None = None
    aliases: str = ""


class AssistFloor(BaseModel):
    model_config = ConfigDict(extra="allow")

    floor_id: str | None = None
    name: str
    aliases: str = ""


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    language: str | None = None
    conversation_id: str | None = None
    entities: list[AssistEntity]
    areas: list[AssistArea] = Field(default_factory=list)
    floors: list[AssistFloor] = Field(default_factory=list)
    source_device_id: str | None = None
    source_area_id: str | None = None
    source_area_name: str | None = None
    source_floor_id: str | None = None
    source_floor_name: str | None = None


class AssistResponse(BaseModel):
    response: str
    service_calls: list[dict[str, Any]] = Field(default_factory=list)
