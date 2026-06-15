from typing import Any

from .assistant_logic import build_assist_result_with_llm
from .conversation_memory import build_llm_messages, get_previous_exchange, remember_exchange
from .ha_parser import HaObject


async def process_assist_payload(
        *,
        text: str,
        entities: list[dict[str, Any] | HaObject],
        areas: list[dict[str, Any]] | None = None,
        floors: list[dict[str, Any]] | None = None,
        conversation_id: str | None = None,
        source_area_id: str | None = None,
        source_area_name: str | None = None,
        source_floor_id: str | None = None,
        source_floor_name: str | None = None,
        llm_api_key: str | None = None,
        llm_api_url: str | None = None,
) -> dict[str, Any]:
    ha_objects = [
        entity if isinstance(entity, HaObject) else HaObject.model_validate(entity)
        for entity in entities
    ]
    result = await build_assist_result_with_llm(
        text=text,
        ha_objects=ha_objects,
        areas=areas or [],
        floors=floors or [],
        source_area_id=source_area_id,
        source_area_name=source_area_name,
        source_floor_id=source_floor_id,
        source_floor_name=source_floor_name,
        llm_messages=build_llm_messages(conversation_id, text),
        previous_exchange=get_previous_exchange(conversation_id),
        llm_api_key=llm_api_key,
        llm_api_url=llm_api_url,
    )
    remember_exchange(
        conversation_id=conversation_id,
        user_text=text,
        assistant_text=result.response,
    )
    return {
        "response": result.response,
        "service_calls": result.service_calls,
    }
