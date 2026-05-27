from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssistEntity(BaseModel):
    model_config = ConfigDict(extra="allow")

    entity_id: str
    name: str
    state: str
    aliases: str = ""


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    text: str
    language: str | None = None
    conversation_id: str | None = None
    entities: list[AssistEntity]


class AssistResponse(BaseModel):
    response: str
    service_calls: list[dict[str, Any]] = Field(default_factory=list)
