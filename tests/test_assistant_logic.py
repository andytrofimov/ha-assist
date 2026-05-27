import pytest

from assistant_logic import build_assist_result
from ha_parser import HaObject


def entity(
    entity_id: str,
    name: str,
    state: str = "off",
    aliases: str = "",
) -> HaObject:
    return HaObject(
        entity_id=entity_id,
        name=name,
        state=state,
        aliases=aliases,
    )


@pytest.fixture
def entities() -> list[HaObject]:
    return [
        entity("light.living_room", "Свет гостиная", aliases="свет в гостиной"),
        entity("light.kitchen", "Свет кухня", aliases="свет на кухне"),
        entity("light.office", "Свет кабинет", state="on", aliases="свет в кабинете"),
        entity("light.floor_1", "Свет первый этаж", aliases="свет на первом этаже"),
        entity("cover.bedroom_curtain", "Штора спальня", aliases="шторы в спальне"),
        entity("cover.gate", "Ворота", state="closed"),
        entity("scene.movie", "Режим кино"),
        entity("switch.massage", "Массаж"),
        entity(
            "climate.bedroom_ac",
            "Кондиционер спальня",
            aliases="кондиционер в спальне",
        ),
        entity(
            "sensor.pool_temperature",
            "Температура бассейн",
            state="23.4",
            aliases="температура воды в бассейне",
        ),
        entity(
            "sensor.pool_temperature_battery",
            "Температура воды в бассейне Батарея",
            state="100",
        ),
        entity(
            "sensor.pool_temperature_secondary_battery",
            "Температура бассейн темп Батарея",
            state="100",
        ),
        entity(
            "sensor.pool_temperature_secondary",
            "Температура бассейн темп Температура",
            state="22.1",
        ),
        entity(
            "sensor.packet_loss",
            "77.88.8.1 Packet loss",
            state="0.0",
            aliases="потеря пакетов",
        ),
        entity("media_player.tv", "Телевизор", aliases="телек"),
        entity(
            "binary_sensor.office_door",
            "Дверь кабинет",
            aliases="дверь в кабинет",
        ),
        entity("input_boolean.sleep_mode", "Режим сна"),
    ]


def test_turns_on_named_scene_and_switch(entities: list[HaObject]) -> None:
    movie = build_assist_result("режим кино", entities)
    massage = build_assist_result("массаж", entities)

    assert movie.service_calls[0]["domain"] == "scene"
    assert movie.service_calls[0]["service"] == "turn_on"
    assert movie.service_calls[0]["service_data"]["entity_id"] == "scene.movie"
    assert massage.service_calls[0]["domain"] == "switch"
    assert massage.service_calls[0]["service"] == "turn_on"


def test_opens_cover_and_closes_gate(entities: list[HaObject]) -> None:
    curtain = build_assist_result("открой штору в спальне", entities)
    gate = build_assist_result("закрой ворота", entities)

    assert curtain.service_calls[0]["service"] == "open_cover"
    assert (
        curtain.service_calls[0]["service_data"]["entity_id"]
        == "cover.bedroom_curtain"
    )
    assert gate.service_calls[0]["service"] == "close_cover"
    assert gate.service_calls[0]["service_data"]["entity_id"] == "cover.gate"


def test_matches_domain_and_room_words(entities: list[HaObject]) -> None:
    result = build_assist_result("включи кондиционер в спальне", entities)

    assert result.service_calls[0]["domain"] == "climate"
    assert result.service_calls[0]["service"] == "turn_on"
    assert result.service_calls[0]["service_data"]["entity_id"] == "climate.bedroom_ac"


def test_turns_off_light_in_multiple_rooms(entities: list[HaObject]) -> None:
    result = build_assist_result("выключи свет в гостиной и на кухне", entities)
    entity_ids = {
        call["service_data"]["entity_id"]
        for call in result.service_calls
    }

    assert entity_ids == {"light.living_room", "light.kitchen"}
    assert all(call["service"] == "turn_off" for call in result.service_calls)


def test_compound_command_with_brightness_duration_and_cover(
    entities: list[HaObject],
) -> None:
    result = build_assist_result(
        "включи свет в гостиной на 15 процентов на 15 минут "
        "и закрой штору в спальне",
        entities,
    )

    assert result.service_calls[0]["domain"] == "light"
    assert result.service_calls[0]["service"] == "turn_on"
    assert result.service_calls[0]["service_data"]["brightness_pct"] == 15
    assert result.service_calls[1]["service"] == "turn_off"
    assert result.service_calls[1]["delay_seconds"] == 15 * 60
    assert result.service_calls[2]["domain"] == "cover"
    assert result.service_calls[2]["service"] == "close_cover"


def test_delayed_commands(entities: list[HaObject]) -> None:
    ac = build_assist_result("включи кондиционер в спальне на полчаса", entities)
    office = build_assist_result("выключи свет в кабинете через 15 минут", entities)

    assert ac.service_calls[0]["service"] == "turn_on"
    assert ac.service_calls[1]["service"] == "turn_off"
    assert ac.service_calls[1]["delay_seconds"] == 30 * 60
    assert office.service_calls[0]["service"] == "turn_off"
    assert office.service_calls[0]["delay_seconds"] == 15 * 60


def test_floor_light(entities: list[HaObject]) -> None:
    result = build_assist_result("выключи свет на первом этаже", entities)

    assert result.service_calls[0]["service"] == "turn_off"
    assert result.service_calls[0]["service_data"]["entity_id"] == "light.floor_1"


def test_sets_brightness_for_all_lights_when_room_is_not_specified(
    entities: list[HaObject],
) -> None:
    result = build_assist_result("включи свет на 15 процентов", entities)
    light_calls = [
        call for call in result.service_calls if call["domain"] == "light"
    ]

    assert len(light_calls) == 4
    assert all(call["service_data"]["brightness_pct"] == 15 for call in light_calls)


def test_state_questions(entities: list[HaObject]) -> None:
    assert "Телевизор: выключено" in build_assist_result(
        "телевизор включен?",
        entities,
    ).response
    assert "Дверь кабинет: закрыто" in build_assist_result(
        "дверь в кабинет закрыта?",
        entities,
    ).response
    assert "Режим сна: выключено" in build_assist_result(
        "режим сна включен?",
        entities,
    ).response
    assert "Температура бассейн: 23.4" in build_assist_result(
        "какая температура в бассейне?",
        entities,
    ).response
    assert "77.88.8.1 Packet loss: 0.0%" in build_assist_result(
        "сколько процентов потеря пакетов?",
        entities,
    ).response


def test_temperature_question_does_not_include_related_battery_sensors(
    entities: list[HaObject],
) -> None:
    result = build_assist_result("какая температура в бассейне?", entities)

    assert result.response == "Температура бассейн: 23.4"
    assert "Батарея" not in result.response
    assert "22.1" not in result.response


def test_non_smart_home_request_falls_back_to_llm(entities: list[HaObject]) -> None:
    result = build_assist_result("расскажи анекдот", entities)

    assert result.fallback_to_llm
    assert result.service_calls == []
