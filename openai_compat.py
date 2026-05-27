import csv
import io
import json
import time
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from assistant_logic import build_action_text, build_service_items
from ha_parser import HaObject
from ha_service_call_builder import build_execute_services_tool_call
from text_normalizer import NormalizedText, get_text_normalizer


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


class AssistantBusinessResponse(BaseModel):
    content: str | None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: Literal["stop", "tool_calls"] = "stop"


def build_chat_completion_response(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    user_message = get_last_user_message(request.messages)
    if user_message is None:
        raise HTTPException(status_code=400, detail="No user message found")

    user_text = user_message.content or ""
    normalized_request = get_text_normalizer().normalize(user_text)
    assistant_response = build_assistant_response(
        normalized_request=normalized_request,
        ha_objects=parse_ha_objects(request.messages),
        can_execute_services="execute_services" in requested_tool_names(request),
    )
    prompt_tokens = len(user_text.split())
    completion_tokens = len((assistant_response.content or "").split())

    return ChatCompletionResponse(
        id="chatcmpl-debug-natasha",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionResponseMessage(
                    content=assistant_response.content,
                    tool_calls=assistant_response.tool_calls,
                ),
                finish_reason=assistant_response.finish_reason,
            ),
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


def build_assistant_response(
    normalized_request: NormalizedText,
    ha_objects: list[HaObject],
    can_execute_services: bool,
) -> AssistantBusinessResponse:
    service_items = build_service_items(normalized_request, ha_objects)
    tool_call = (
        build_execute_services_tool_call(service_items)
        if can_execute_services and service_items
        else None
    )

    if tool_call is not None:
        return AssistantBusinessResponse(
            content=build_action_text(normalized_request, service_items),
            tool_calls=[tool_call],
            finish_reason="tool_calls",
        )

    return AssistantBusinessResponse(
        content=json.dumps(
            normalized_request.model_dump(),
            ensure_ascii=False,
            indent=2,
        ),
    )


def requested_tool_names(request: ChatCompletionRequest) -> set[str]:
    names: set[str] = set()
    for tool in request.tools or []:
        function = tool.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            names.add(function["name"])
    return names


def get_last_user_message(messages: list[ChatMessage]) -> ChatMessage | None:
    return next(
        (
            message
            for message in reversed(messages)
            if message.role == "user" and message.content
        ),
        None,
    )


def parse_ha_objects(messages: list[ChatMessage]) -> list[HaObject]:
    system_message = next(
        (message for message in messages if message.role == "system" and message.content),
        None,
    )
    if system_message is None:
        return []

    csv_text = extract_csv_block(system_message.content)
    if csv_text is None:
        return []

    reader = csv.DictReader(io.StringIO(csv_text))
    return [
        HaObject(
            entity_id=row.get("entity_id", ""),
            name=row.get("name", ""),
            state=row.get("state", ""),
            aliases=row.get("aliases", ""),
        )
        for row in reader
        if row.get("entity_id")
    ]


def extract_csv_block(content: str) -> str | None:
    marker = "```csv"
    start = content.find(marker)
    if start == -1:
        return None

    start += len(marker)
    end = content.find("```", start)
    if end == -1:
        return None

    return content[start:end].strip()
