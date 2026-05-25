import json
from typing import Any, Literal

from pydantic import BaseModel

from ha_parser import HaObject
from ha_service_call_builder import build_execute_services_tool_call, build_service_item
from text_normalizer import NormalizedText, get_text_normalizer


class AssistantBusinessResponse(BaseModel):
    content: str | None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: Literal["stop", "tool_calls"] = "stop"


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


def build_service_items(
    normalized_request: NormalizedText,
    ha_objects: list[HaObject],
) -> list[dict[str, Any]]:
    words = set(normalized_request.normal_forms)
    service = detect_service(words)
    domain = detect_domain(words)
    if service is None or domain is None:
        return []

    target_words = words - ignored_command_words()
    service_items: list[dict[str, Any]] = []

    for ha_object in ha_objects:
        object_domain = ha_object.entity_id.split(".", maxsplit=1)[0]
        if object_domain != domain:
            continue

        object_words = set(normalize_words(f"{ha_object.name} {ha_object.aliases}"))
        if target_words and not target_words <= object_words:
            continue

        service_items.append(
            build_service_item(
                domain=domain,
                service=service,
                entity_id=ha_object.entity_id,
            )
        )

    return service_items


def detect_service(words: set[str]) -> str | None:
    if "включить" in words:
        return "turn_on"
    if "выключить" in words:
        return "turn_off"
    return None


def detect_domain(words: set[str]) -> str | None:
    light_words = {"свет", "лампочка", "люстра", "подсветка"}
    if words & light_words:
        return "light"
    return None


def ignored_command_words() -> set[str]:
    return {
        "включить",
        "выключить",
        "свет",
        "лампочка",
        "люстра",
        "подсветка",
        "в",
        "на",
    }


def normalize_words(text: str) -> list[str]:
    return get_text_normalizer().normalize(text).normal_forms


def build_action_text(
    normalized_request: NormalizedText,
    service_items: list[dict[str, Any]],
) -> str:
    entity_ids = [
        item["service_data"]["entity_id"]
        for item in service_items
        if "service_data" in item and "entity_id" in item["service_data"]
    ]
    return json.dumps(
        {
            "original_text": normalized_request.original_text,
            "normalized_text": normalized_request.normalized_text,
            "action": "execute_services",
            "entity_ids": entity_ids,
        },
        ensure_ascii=False,
        indent=2,
    )
