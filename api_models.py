from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str
    content: str | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = "debug-natasha"
    messages: list[ChatMessage]
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None


class ChatCompletionResponseMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatCompletionResponseMessage
    finish_reason: Literal["stop", "tool_calls"] = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


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
    service_calls: list[dict[str, Any]] = []
