import re
from dataclasses import dataclass
from typing import Any

from .ha_parser import HaObject
from .number_parser import (
    parse_brightness_percent,
    parse_delay_seconds,
    parse_duration_seconds,
    parse_temperature,
)
from .text_normalizer import NormalizedText

# Домены, которые поддерживают стандартные Home Assistant команды turn_on/turn_off.
TURNABLE_DOMAINS = {
    "automation",
    "climate",
    "fan",
    "humidifier",
    "input_boolean",
    "light",
    "media_player",
    "remote",
    "scene",
    "script",
    "switch",
    "vacuum",
}

# Домены, которым разрешено срабатывать без явного командного глагола.
BARE_ACTIVATION_DOMAINS = {"button", "scene"}

# Командные глаголы сравниваются после морфологической нормализации.
TURN_ON_WORDS = {"включить", "активировать", "запустить"}
TURN_OFF_WORDS = {"выключить", "отключить"}
OPEN_WORDS = {"открыть"}
CLOSE_WORDS = {"закрыть"}
ADD_TODO_WORDS = {"добавить"}
UNSUPPORTED_ACTION_WORDS = {"показать"}


@dataclass(frozen=True)
class ParsedTiming:
    delay_seconds: int | None = None
    duration_seconds: int | None = None


def detect_action(command: NormalizedText) -> str | None:
    words = set(command.normal_forms)
    if words & TURN_ON_WORDS:
        return "turn_on"
    if words & TURN_OFF_WORDS:
        return "turn_off"
    if words & OPEN_WORDS:
        return "open"
    if words & CLOSE_WORDS:
        return "close"
    if words & ADD_TODO_WORDS:
        return "add_todo"
    if {"поставить", "установить"} & words and parse_brightness_percent(command.original_text):
        return "turn_on"
    if {"поставить", "установить"} & words and parse_temperature(command.original_text):
        return "set_temperature"
    return None


def is_invalid_device_command(command: NormalizedText) -> bool:
    words = set(command.normal_forms) | set(command.tokens)
    if "кроме" in words or "не" in words:
        return True
    if (words & TURN_ON_WORDS) and (words & TURN_OFF_WORDS):
        return True
    if (words & OPEN_WORDS) and (words & CLOSE_WORDS):
        return True
    stripped_text = command.original_text.strip().lower()
    if stripped_text.endswith((" и", " через")):
        return True
    return False


def has_unsupported_action(command: NormalizedText) -> bool:
    return bool((set(command.normal_forms) | set(command.tokens)) & UNSUPPORTED_ACTION_WORDS)


def is_turnable(entity: HaObject) -> bool:
    return entity_domain(entity) in TURNABLE_DOMAINS


def is_bare_activation_domain(entity: HaObject) -> bool:
    return entity_domain(entity) in BARE_ACTIVATION_DOMAINS


def bare_activation_action(entity: HaObject) -> str | None:
    domain = entity_domain(entity)
    if domain == "button":
        return "press"
    if domain == "scene":
        return "turn_on"
    return None


def build_service_call(
        entity: HaObject,
        action: str,
        brightness_pct: int | None,
        delay_seconds: int | None,
        target_temperature: int | None = None,
        todo_item: str | None = None,
) -> dict[str, Any] | None:
    # Ответ сервиса остается простым JSON-планом, который выполняет интеграция HA.
    domain = entity_domain(entity)
    service = service_for_action(domain, action)
    if service is None:
        return None

    service_data: dict[str, Any] = {"entity_id": entity.entity_id}
    if domain == "light" and service == "turn_on" and brightness_pct is not None:
        service_data["brightness_pct"] = brightness_pct
    if domain == "climate" and service == "set_temperature" and target_temperature is not None:
        service_data["temperature"] = target_temperature
    if domain == "todo" and service == "add_item" and todo_item is None:
        return None
    if domain == "todo" and service == "add_item" and todo_item is not None:
        service_data["item"] = todo_item

    service_call = {
        "domain": domain,
        "service": service,
        "service_data": service_data,
    }
    if delay_seconds is not None:
        service_call["delay_seconds"] = delay_seconds

    return service_call


def build_reverse_service_call(
        entity: HaObject,
        action: str,
        delay_seconds: int | None,
) -> dict[str, Any] | None:
    # Временные команды добавляют обратное действие после указанной длительности.
    if delay_seconds is None:
        return None

    reverse_action = {
        "turn_on": "turn_off",
        "open": "close",
    }.get(action)
    if reverse_action is None:
        return None

    return build_service_call(
        entity=entity,
        action=reverse_action,
        brightness_pct=None,
        target_temperature=None,
        todo_item=None,
        delay_seconds=delay_seconds,
    )


def service_for_action(domain: str, action: str) -> str | None:
    if action in {"turn_on", "turn_off"}:
        if domain == "scene":
            return "turn_on" if action == "turn_on" else None
        if domain in TURNABLE_DOMAINS:
            return action
        return None

    if action == "open" and domain == "cover":
        return "open_cover"
    if action == "close" and domain == "cover":
        return "close_cover"

    if action == "set_temperature" and domain == "climate":
        return "set_temperature"

    if action == "press" and domain == "button":
        return "press"

    if action == "add_todo" and domain == "todo":
        return "add_item"

    return None


def entity_domain(entity: HaObject) -> str:
    return entity.entity_id.split(".", maxsplit=1)[0]


def parse_timing(text: str) -> ParsedTiming:
    # "через" означает задержку, а "на 15 минут" означает временное действие.
    delay_seconds = parse_delay_seconds(text)
    duration_seconds = parse_duration_seconds(text)
    return ParsedTiming(delay_seconds=delay_seconds, duration_seconds=duration_seconds)


def parse_todo_item(command: NormalizedText, entity: HaObject, raw_entity_phrases: list[str]) -> str | None:
    if entity_domain(entity) != "todo":
        return None

    for phrase in sorted(raw_entity_phrases, key=len, reverse=True):
        match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", command.original_text, re.I)
        if match is None:
            continue
        item = command.original_text[match.end():].strip(" .,!?")
        return item or None

    return None
