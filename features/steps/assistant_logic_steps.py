import asyncio
from typing import Any

from behave import step

from app.assistant_logic import build_assist_result, build_assist_result_with_llm
from app.ha_parser import HaObject


def row_value(row: Any, key: str, default: str = "") -> str:
    return (row.get(key, default) or "").strip()


def int_or_none(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    return int(value)


def entities_from_table(table: Any) -> list[HaObject]:
    entities: list[HaObject] = []
    known_columns = {
        "entity_id",
        "name",
        "state",
        "aliases",
        "area_id",
        "area_name",
        "floor_id",
        "floor_name",
        "unit_of_measurement",
        "device_class",
        "hvac_modes",
        "attributes",
    }
    for row in table:
        attributes: dict[str, Any] = {}
        for heading in table.headings:
            value = row_value(row, heading)
            if not value:
                continue
            if heading.startswith("attributes."):
                attributes[heading.removeprefix("attributes.")] = value
            elif heading not in known_columns:
                attributes[heading] = value

        entity_data: dict[str, Any] = {
            "entity_id": row_value(row, "entity_id"),
            "name": row_value(row, "name"),
            "state": row_value(row, "state"),
            "aliases": row_value(row, "aliases"),
            "area_id": row_value(row, "area_id") or None,
            "area_name": row_value(row, "area_name") or None,
            "floor_id": row_value(row, "floor_id") or None,
            "floor_name": row_value(row, "floor_name") or None,
            "unit_of_measurement": row_value(row, "unit_of_measurement") or None,
            "device_class": row_value(row, "device_class") or None,
            "hvac_modes": split_cell(row_value(row, "hvac_modes")),
            "attributes": attributes,
        }
        entities.append(HaObject(**entity_data))
    return entities


def split_cell(value: str) -> list[str]:
    return [
        item.strip()
        for item in value.replace(",", "/").split("/")
        if item.strip()
    ]


def dicts_from_table(table: Any) -> list[dict[str, Any]]:
    return [
        {
            heading: row_value(row, heading)
            for heading in table.headings
        }
        for row in table
    ]


def build_result(context: Any, text: str) -> None:
    context.result = build_assist_result(
        text,
        context.ha_objects,
        areas=getattr(context, "areas", []),
        floors=getattr(context, "floors", []),
        source_area_id=getattr(context, "source_area_id", None),
        source_area_name=getattr(context, "source_area_name", None),
        source_floor_id=getattr(context, "source_floor_id", None),
        source_floor_name=getattr(context, "source_floor_name", None),
    )


@step("доступны сущности:")
def step_given_entities(context: Any) -> None:
    context.ha_objects = entities_from_table(context.table)
    context.areas = []
    context.floors = []
    context.source_area_id = None
    context.source_area_name = None
    context.source_floor_id = None
    context.source_floor_name = None
    context.llm_response = None


@step("доступны комнаты:")
def step_given_areas(context: Any) -> None:
    context.areas = dicts_from_table(context.table)


@step("доступны этажи:")
def step_given_floors(context: Any) -> None:
    floors = dicts_from_table(context.table)
    for floor in floors:
        if floor.get("level"):
            floor["level"] = int(floor["level"])
    context.floors = floors


@step("запрос пришел из комнаты:")
def step_given_source_area(context: Any) -> None:
    row = context.table[0]
    context.source_area_id = row_value(row, "source_area_id") or None
    context.source_area_name = row_value(row, "source_area_name") or None


@step('LLM отвечает "{response}"')
def step_given_llm_response(context: Any, response: str) -> None:
    context.llm_response = response


@step('пользователь говорит "{text}"')
def step_when_user_says(context: Any, text: str) -> None:
    build_result(context, text)


@step("пользователь говорит:")
def step_when_user_says_docstring(context: Any) -> None:
    build_result(context, context.text)


@step('пользователь говорит с LLM "{text}"')
def step_when_user_says_with_llm(context: Any, text: str) -> None:
    import app.assistant_logic as assistant_logic

    async def fake_generate_llm_response(messages: list[dict[str, str]]) -> str:
        assert messages == [{"role": "user", "content": text}]
        return context.llm_response

    original_generate_llm_response = assistant_logic.generate_llm_response
    assistant_logic.generate_llm_response = fake_generate_llm_response
    try:
        context.result = asyncio.run(
            build_assist_result_with_llm(
                text,
                context.ha_objects,
                areas=getattr(context, "areas", []),
                floors=getattr(context, "floors", []),
                source_area_id=getattr(context, "source_area_id", None),
                source_area_name=getattr(context, "source_area_name", None),
                source_floor_id=getattr(context, "source_floor_id", None),
                source_floor_name=getattr(context, "source_floor_name", None),
            ),
        )
    finally:
        assistant_logic.generate_llm_response = original_generate_llm_response


@step("ассистент вызывает сервисы:")
def step_then_service_calls(context: Any) -> None:
    expected = []
    for row in context.table:
        service_data: dict[str, Any] = {"entity_id": row_value(row, "entity_id")}
        if "brightness_pct" in context.table.headings and row_value(row, "brightness_pct"):
            service_data["brightness_pct"] = int(row_value(row, "brightness_pct"))
        if "temperature" in context.table.headings and row_value(row, "temperature"):
            service_data["temperature"] = int(row_value(row, "temperature"))

        service_call: dict[str, Any] = {
            "domain": row_value(row, "domain"),
            "service": row_value(row, "service"),
            "service_data": service_data,
        }
        if "delay_seconds" in context.table.headings:
            delay_seconds = int_or_none(row_value(row, "delay_seconds"))
            if delay_seconds is not None:
                service_call["delay_seconds"] = delay_seconds
        expected.append(service_call)

    assert context.result.service_calls == expected, (
        context.result.response,
        context.result.service_calls,
    )


@step("ассистент не вызывает сервисы")
def step_then_no_service_calls(context: Any) -> None:
    assert context.result.service_calls == []


@step('ответ ассистента содержит "{text}"')
def step_then_response_contains(context: Any, text: str) -> None:
    assert text in context.result.response


@step('ответ ассистента не содержит "{text}"')
def step_then_response_not_contains(context: Any, text: str) -> None:
    assert text not in context.result.response


@step('ответ ассистента равен "{text}"')
def step_then_response_equals(context: Any, text: str) -> None:
    assert context.result.response == text, context.result.response


@step("ответ ассистента пустой")
def step_then_response_empty(context: Any) -> None:
    assert context.result.response == "", context.result.response


@step("ассистент просит LLM fallback")
def step_then_fallback_to_llm(context: Any) -> None:
    assert context.result.fallback_to_llm


@step("ассистент не просит LLM fallback")
def step_then_not_fallback_to_llm(context: Any) -> None:
    assert not context.result.fallback_to_llm
