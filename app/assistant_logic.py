import json
import logging
import random
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.ha_parser import HaObject
from app.llm_client import ChatMessage, generate_llm_response
from app.number_parser import (
    parse_brightness_percent,
    parse_delay_seconds,
    parse_duration_seconds,
    parse_temperature,
)
from app.text_normalizer import NormalizedText, get_text_normalizer
from app.text_normalizer import agree_adjective

logger = logging.getLogger(__name__)

# Короткие ответы для успешно распознанных команд умного дома.
OK_RESPONSES = ("окей", "готово", "сделано")
ERROR_ENTITY_NOT_FOUND = "Не нашла такое устройство"
ERROR_ACTION_NOT_FOUND = "Не поняла, что сделать"
ERROR_AREA_NOT_FOUND = "Не нашла такую комнату"
ERROR_FLOOR_NOT_FOUND = "Не нашла такой этаж"
ERROR_AMBIGUOUS_AREA = "Уточните комнату"

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

STATE_ONLY_DOMAINS = {"binary_sensor", "sensor", "todo", "weather"}
DEVICE_WORDS = {"устройство", "устройства", "прибор", "приборы"}
ALL_WORDS = {"весь", "все", "всё", "вся", "всей", "всю"}

# Слова, по которым пользовательская фраза связывается с доменами Home Assistant.
DOMAIN_WORDS = {
    "light": {"свет", "лампа", "лампочка", "люстра", "подсветка", "торшер"},
    "climate": {
        "кондиционер",
        "кондей",
        "климат",
        "термостат",
        "отопление",
        "обогрев",
        "подогрев",
    },
    "cover": {"штора", "шторы", "занавеска", "ворота", "рольставни"},
    "switch": {"выключатель", "розетка", "массаж", "чайник", "комп", "компьютер"},
    "input_boolean": set(),
    "scene": {"сцена"},
    "media_player": {"телевизор", "телек", "тв", "колонка", "плеер"},
    "weather": {"погода", "прогноз"},
    "todo": {"список", "дело", "дела", "задача", "задачи", "покупка", "покупки", "покупок"},
    "sensor": {
        "температура",
        "влажность",
        "потеря",
        "пакет",
        "пакетов",
        "процент",
        "процентов",
    },
    "binary_sensor": {"дверь", "окно", "датчик"},
}

# Общие слова не должны сами по себе повышать точность совпадения с entity.
GENERIC_WORDS = {
    "в",
    "во",
    "на",
    "с",
    "со",
    "и",
    "или",
    "а",
    "то",
    "что",
    "какой",
    "какая",
    "какое",
    "какие",
    "сколько",
    "сейчас",
    "процент",
    "процентов",
    "включить",
    "включи",
    "выключить",
    "выключи",
    "открыть",
    "открой",
    "закрыть",
    "закрой",
    "активировать",
    "запустить",
    "поставить",
    "установить",
    "сделать",
    "через",
    "минута",
    "минут",
    "час",
    "часа",
    "полчаса",
    "этаж",
}

# Командные глаголы сравниваются после морфологической нормализации.
TURN_ON_WORDS = {"включить", "активировать", "запустить"}
TURN_OFF_WORDS = {"выключить", "отключить"}
OPEN_WORDS = {"открыть"}
CLOSE_WORDS = {"закрыть"}
STATE_QUERY_WORDS = {
    "что",
    "какой",
    "какая",
    "какое",
    "сколько",
    "включить",
    "открыть",
    "закрыть",
}


class AssistLogicResult(BaseModel):
    response: str = ""
    service_calls: list[dict[str, Any]] = Field(default_factory=list)
    fallback_to_llm: bool = False


@dataclass(frozen=True)
class EntityMatch:
    entity: HaObject
    score: int


@dataclass(frozen=True)
class ParsedTiming:
    delay_seconds: int | None = None
    duration_seconds: int | None = None


@dataclass(frozen=True)
class LocationContext:
    area_ids: set[str]
    floor_ids: set[str]
    explicit_area: bool = False
    explicit_floor: bool = False
    source_area_id: str | None = None
    source_floor_id: str | None = None

    @property
    def has_explicit_location(self) -> bool:
        return self.explicit_area or self.explicit_floor

    @property
    def has_location(self) -> bool:
        return bool(self.area_ids or self.floor_ids)


def build_assist_result(
    text: str,
    ha_objects: list[HaObject],
    areas: list[Any] | None = None,
    floors: list[Any] | None = None,
    source_area_id: str | None = None,
    source_area_name: str | None = None,
    source_floor_id: str | None = None,
    source_floor_name: str | None = None,
) -> AssistLogicResult:
    normalized_request = normalize(text)
    command_parts = split_compound_commands(normalized_request.original_text)
    all_service_calls: list[dict[str, Any]] = []
    state_answers: list[str] = []
    found_smart_home_signal = False

    for command_text in command_parts:
        command = normalize(command_text)
        action = detect_action(command)
        timing = parse_timing(command.original_text)
        brightness_pct = parse_brightness_percent(command.original_text)
        target_temperature = parse_temperature(command.original_text)
        requested_domains = detect_requested_domains(command)
        location_context = detect_location_context(
            command=command,
            ha_objects=ha_objects,
            areas=areas or [],
            floors=floors or [],
            source_area_id=source_area_id,
            source_area_name=source_area_name,
            source_floor_id=source_floor_id,
            source_floor_name=source_floor_name,
        )
        matches = find_entity_matches(
            command,
            ha_objects,
            location_context=location_context,
        )

        found_smart_home_signal = (
            found_smart_home_signal
            or action is not None
            or bool(matches)
            or bool(requested_domains)
            or location_context.has_location
        )

        if is_state_query(command):
            if not matches:
                if not found_smart_home_signal:
                    return llm_fallback_result()
                return AssistLogicResult(response=ERROR_ENTITY_NOT_FOUND)
            state_answers.extend(build_state_answer(match.entity, command) for match in matches)
            continue

        if action is None and is_general_question(command):
            return llm_fallback_result()

        if action is None and matches:
            if all(entity_domain(match.entity) in STATE_ONLY_DOMAINS for match in matches):
                state_answers.extend(build_state_answer(match.entity, command) for match in matches)
                continue
            if all(entity_domain(match.entity) == "button" for match in matches):
                action = "press"
            else:
                action = "turn_on" if all(is_turnable(match.entity) for match in matches) else None

        if action is None:
            if found_smart_home_signal:
                return AssistLogicResult(response=ERROR_ACTION_NOT_FOUND)
            return llm_fallback_result()

        if not matches:
            if has_unknown_floor(command, ha_objects, floors or []):
                return AssistLogicResult(response=ERROR_FLOOR_NOT_FOUND)
            if has_unknown_location(command, ha_objects, areas or [], floors or []):
                return AssistLogicResult(response=ERROR_AREA_NOT_FOUND)
            return AssistLogicResult(response=ERROR_ENTITY_NOT_FOUND)

        if is_ambiguous_location(matches, location_context):
            if has_unknown_floor(command, ha_objects, floors or []):
                return AssistLogicResult(response=ERROR_FLOOR_NOT_FOUND)
            if has_unknown_location(command, ha_objects, areas or [], floors or []):
                return AssistLogicResult(response=ERROR_AREA_NOT_FOUND)
            return AssistLogicResult(response=ERROR_AMBIGUOUS_AREA)

        for match in matches:
            service_call = build_service_call(
                entity=match.entity,
                action=action,
                brightness_pct=brightness_pct,
                target_temperature=target_temperature,
                delay_seconds=timing.delay_seconds,
            )
            if service_call is None:
                continue

            all_service_calls.append(service_call)
            reverse_call = build_reverse_service_call(
                entity=match.entity,
                action=action,
                delay_seconds=timing.duration_seconds,
            )
            if reverse_call is not None:
                all_service_calls.append(reverse_call)

    if all_service_calls:
        return AssistLogicResult(
            response=random.choice(OK_RESPONSES),
            service_calls=all_service_calls,
        )

    if state_answers:
        return AssistLogicResult(response="; ".join(state_answers))

    return llm_fallback_result()


def llm_fallback_result() -> AssistLogicResult:
    return AssistLogicResult(fallback_to_llm=True)


async def build_assist_result_with_llm(
    text: str,
    ha_objects: list[HaObject],
    areas: list[Any] | None = None,
    floors: list[Any] | None = None,
    source_area_id: str | None = None,
    source_area_name: str | None = None,
    source_floor_id: str | None = None,
    source_floor_name: str | None = None,
    llm_messages: list[ChatMessage] | None = None,
) -> AssistLogicResult:
    result = build_assist_result(
        text,
        ha_objects,
        areas=areas,
        floors=floors,
        source_area_id=source_area_id,
        source_area_name=source_area_name,
        source_floor_id=source_floor_id,
        source_floor_name=source_floor_name,
    )
    if not result.fallback_to_llm:
        return result

    messages = llm_messages or [
        {
            "role": "user",
            "content": text,
        },
    ]
    logger.info("LLM fallback requested for non-smart-home text: %s", text)
    llm_response = await generate_llm_response(messages)
    if llm_response is None:
        logger.info("LLM fallback did not return a response")
        return result

    return AssistLogicResult(response=strip_trailing_period(llm_response))


def build_service_items(
    normalized_request: NormalizedText,
    ha_objects: list[HaObject],
) -> list[dict[str, Any]]:
    return build_assist_result(normalized_request.original_text, ha_objects).service_calls


def build_action_text(
    normalized_request: NormalizedText,
    service_items: list[dict[str, Any]],
) -> str:
    if service_items:
        return random.choice(OK_RESPONSES)

    return json.dumps(
        {
            "original_text": normalized_request.original_text,
            "normalized_text": normalized_request.normalized_text,
            "action": None,
            "entity_ids": [],
        },
        ensure_ascii=False,
        indent=2,
    )


def normalize(text: str) -> NormalizedText:
    return get_text_normalizer().normalize(text)


def strip_trailing_period(text: str) -> str:
    return text.rstrip().removesuffix(".").rstrip()


def normalized_words(text: NormalizedText) -> set[str]:
    words = set(text.normal_forms) | set(text.tokens)
    expanded: set[str] = set()
    for word in words:
        if word and not word.isdigit():
            expanded.update(word_variants(word))
    return expanded


def raw_words(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-zА-Яа-яЁё]+", text.lower()))


def raw_word_variants(text: str) -> set[str]:
    return expanded_words(raw_words(text))


def word_variants(word: str) -> set[str]:
    variants = {word}
    if word.endswith("ая") and len(word) > 3:
        variants.add(f"{word[:-2]}ый")
        variants.add(f"{word[:-2]}ой")
    if word.endswith("яя") and len(word) > 3:
        variants.add(f"{word[:-2]}ий")
        variants.add(f"{word[:-2]}ей")
    if word.endswith(("а", "я")) and len(word) > 3:
        variants.add(f"{word[:-1]}е")
    if word[-1:] not in {"а", "е", "ё", "и", "й", "о", "у", "ы", "ь", "э", "ю", "я"}:
        variants.add(f"{word}е")
    return variants


def expanded_words(words: set[str]) -> set[str]:
    expanded: set[str] = set()
    for word in words:
        expanded.update(word_variants(word))
    return expanded


def split_compound_commands(text: str) -> list[str]:
    # Делим только там, где после союза явно начинается новая команда.
    parts = re.split(
        r"\s+и\s+(?=(?:включ|выключ|отключ|откро|закро|активир|запуст|постав|установ))",
        text,
        flags=re.IGNORECASE,
    )
    return [part.strip(" .,!?") for part in parts if part.strip(" .,!?")]


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
    if {"поставить", "установить"} & words and parse_brightness_percent(command.original_text):
        return "turn_on"
    if {"поставить", "установить"} & words and parse_temperature(command.original_text):
        return "set_temperature"
    return None


def is_state_query(command: NormalizedText) -> bool:
    # Вопросы состояния не должны превращаться в сервисные вызовы.
    text = command.original_text.strip().lower()
    words = set(command.normal_forms)

    if text.endswith("?"):
        return True
    if words & {"сколько", "какой", "какая", "какое", "что"}:
        return True
    if words & DOMAIN_WORDS["weather"]:
        return True
    if (words & {"включить", "открыть", "закрыть"}) and not (
        words & (TURN_ON_WORDS | TURN_OFF_WORDS | OPEN_WORDS | CLOSE_WORDS)
    ):
        return True
    return bool(
        re.search(
            r"\b(включ[её]н|включена|выключ[её]н|выключена|открыт|открыта|закрыт|закрыта)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def is_general_question(command: NormalizedText) -> bool:
    return bool(
        set(command.normal_forms)
        & {"почему", "зачем", "кто", "когда", "где", "как", "каков", "какова"}
    )


def find_entity_matches(
    command: NormalizedText,
    ha_objects: list[HaObject],
    location_context: LocationContext | None = None,
) -> list[EntityMatch]:
    request_words = normalized_words(command)
    requested_domains = detect_requested_domains(command)
    search_objects = filter_entities_by_location(ha_objects, location_context)
    # Сначала ищем точные и частичные совпадения по имени и alias.
    scored_matches = [
        match
        for entity in search_objects
        if (match := score_entity_match(entity, command, request_words, requested_domains))
        is not None
    ]
    if (
        scored_matches
        and location_context
        and location_context.has_location
        and not location_context.has_explicit_location
        and requested_domains
    ):
        source_matches = [
            match
            for match in scored_matches
            if entity_in_location(match.entity, location_context)
        ]
        if source_matches:
            scored_matches = source_matches

    if not scored_matches:
        broad_matches = broad_domain_matches(
            command,
            search_objects,
            requested_domains,
            location_context,
        )
        if broad_matches:
            return broad_matches
        return []

    best_score = max(match.score for match in scored_matches)
    if best_score >= 100:
        # При точном совпадении не подтягиваем похожие entity, кроме явных списков через "и".
        allow_related_matches = "и" in command.normal_forms
        exact_domains = {
            match.entity.entity_id.split(".", maxsplit=1)[0]
            for match in scored_matches
            if match.score >= 100
        }
        return [
            match
            for match in scored_matches
            if match.score >= 100
            or (
                allow_related_matches
                and
                match.score >= 50
                and match.entity.entity_id.split(".", maxsplit=1)[0] in exact_domains
            )
        ]

    if "и" in command.tokens and requested_domains:
        return [
            match
            for match in scored_matches
            if match.score >= 50
            and match.entity.entity_id.split(".", maxsplit=1)[0] in requested_domains
        ]

    return [match for match in scored_matches if match.score == best_score]


def detect_location_context(
    command: NormalizedText,
    ha_objects: list[HaObject],
    areas: list[Any],
    floors: list[Any],
    source_area_id: str | None,
    source_area_name: str | None,
    source_floor_id: str | None,
    source_floor_name: str | None,
) -> LocationContext:
    area_ids = matched_location_ids(command, areas, "area_id")
    floor_ids = matched_location_ids(command, floors, "floor_id")
    if not area_ids:
        area_ids = matched_location_ids(command, entity_area_entries(ha_objects), "area_id")
    if not floor_ids:
        floor_ids = matched_location_ids(command, entity_floor_entries(ha_objects), "floor_id")

    explicit_area = bool(area_ids)
    explicit_floor = bool(floor_ids)
    source_area = source_area_id or id_by_name(source_area_name, areas, "area_id")
    source_floor = source_floor_id or id_by_name(source_floor_name, floors, "floor_id")

    if not area_ids and not floor_ids:
        if source_area:
            area_ids.add(source_area)
        elif source_floor:
            floor_ids.add(source_floor)

    if area_ids and not floor_ids:
        floor_ids.update(
            str(area_floor_id)
            for area in areas
            if (area_id := get_value(area, "area_id")) in area_ids
            and (area_floor_id := get_value(area, "floor_id"))
        )

    if floor_ids and not area_ids:
        area_ids.update(
            str(area_id)
            for area in areas
            if (area_id := get_value(area, "area_id"))
            and get_value(area, "floor_id") in floor_ids
        )

    # Если справочники не пришли, используем привязку самих entity.
    if floor_ids and not area_ids:
        area_ids.update(
            str(entity.area_id)
            for entity in ha_objects
            if entity.area_id and entity.floor_id in floor_ids
        )

    return LocationContext(
        area_ids=area_ids,
        floor_ids=floor_ids,
        explicit_area=explicit_area,
        explicit_floor=explicit_floor,
        source_area_id=source_area,
        source_floor_id=source_floor,
    )


def matched_location_ids(
    command: NormalizedText,
    entries: list[Any],
    id_field: str,
) -> set[str]:
    matches: set[str] = set()
    request_words = normalized_words(command)
    for entry in entries:
        entry_id = get_value(entry, id_field)
        if not entry_id:
            continue
        for phrase in location_entry_phrases(entry):
            normalized = normalize(phrase)
            words = normalized_words(normalized) - expanded_words(GENERIC_WORDS)
            if (
                id_field == "floor_id"
                and "этаж" not in request_words
                and "этаж" not in words
                and normalized.normalized_text != str(entry_id).lower()
            ):
                continue
            if normalized.normalized_text in command.normalized_text or (
                words and words <= request_words
            ):
                matches.add(str(entry_id))
                break
    return matches


def location_entry_phrases(entry: Any) -> list[str]:
    phrases = [
        str(value)
        for key in ("name", "area_id", "floor_id")
        if (value := get_value(entry, key))
    ]
    if get_value(entry, "area_id") is None and (name := get_value(entry, "name")):
        phrases.append(f"{name} этаж")
    phrases.extend(split_aliases(str(get_value(entry, "aliases") or "")))
    return [phrase for phrase in phrases if phrase.strip()]


def entity_area_entries(ha_objects: list[HaObject]) -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for entity in ha_objects:
        if entity.area_id and entity.area_id not in entries:
            entries[entity.area_id] = {
                "area_id": entity.area_id,
                "name": entity.area_name or entity.area_id,
                "floor_id": entity.floor_id or "",
                "aliases": "",
            }
    return list(entries.values())


def entity_floor_entries(ha_objects: list[HaObject]) -> list[dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for entity in ha_objects:
        if entity.floor_id and entity.floor_id not in entries:
            entries[entity.floor_id] = {
                "floor_id": entity.floor_id,
                "name": entity.floor_name or entity.floor_id,
                "aliases": "",
            }
    return list(entries.values())


def id_by_name(name: str | None, entries: list[Any], id_field: str) -> str | None:
    if not name:
        return None
    normalized_name = normalize(name).normalized_text
    for entry in entries:
        entry_id = get_value(entry, id_field)
        if not entry_id:
            continue
        if any(
            normalize(phrase).normalized_text == normalized_name
            for phrase in location_entry_phrases(entry)
        ):
            return str(entry_id)
    return None


def get_value(entry: Any, key: str) -> Any:
    if isinstance(entry, dict):
        return entry.get(key)
    return getattr(entry, key, None)


def filter_entities_by_location(
    ha_objects: list[HaObject],
    location_context: LocationContext | None,
) -> list[HaObject]:
    if (
        not location_context
        or not location_context.has_location
        or not location_context.has_explicit_location
    ):
        return ha_objects

    return [
        entity
        for entity in ha_objects
        if entity_in_location(entity, location_context)
    ]


def entity_in_location(entity: HaObject, location_context: LocationContext) -> bool:
    if location_context.explicit_floor and not location_context.explicit_area:
        return bool(entity.floor_id and entity.floor_id in location_context.floor_ids)
    if location_context.area_ids:
        return bool(entity.area_id and entity.area_id in location_context.area_ids)
    return bool(entity.floor_id and entity.floor_id in location_context.floor_ids)


def has_unknown_location(
    command: NormalizedText,
    ha_objects: list[HaObject],
    areas: list[Any],
    floors: list[Any],
) -> bool:
    if not re.search(r"\b(?:в|во|на)\s+[A-Za-zА-Яа-яЁё]", command.original_text, re.I):
        return False
    context = detect_location_context(
        command=command,
        ha_objects=ha_objects,
        areas=areas,
        floors=floors,
        source_area_id=None,
        source_area_name=None,
        source_floor_id=None,
        source_floor_name=None,
    )
    if context.has_explicit_location:
        return False
    known_location_words = all_location_words(areas, floors) | location_words(ha_objects)
    command_words = normalized_words(command)
    non_generic_words = command_words - expanded_words(GENERIC_WORDS)
    domain_words = expanded_words(set().union(*DOMAIN_WORDS.values()))
    return bool(non_generic_words - domain_words - known_location_words)


def has_unknown_floor(
        command: NormalizedText,
        ha_objects: list[HaObject],
        floors: list[Any],
) -> bool:
    request_words = normalized_words(command)
    if "этаж" not in request_words:
        return False

    context = detect_location_context(
        command=command,
        ha_objects=ha_objects,
        areas=[],
        floors=floors,
        source_area_id=None,
        source_area_name=None,
        source_floor_id=None,
        source_floor_name=None,
    )
    if context.explicit_floor:
        return False

    known_floor_words = floor_words(floors) | entity_floor_words(ha_objects)
    non_generic_words = request_words - expanded_words(GENERIC_WORDS)
    domain_words = expanded_words(set().union(*DOMAIN_WORDS.values()))
    return bool(non_generic_words - domain_words - known_floor_words)


def is_ambiguous_location(
    matches: list[EntityMatch],
    location_context: LocationContext,
) -> bool:
    if location_context.has_location:
        return False
    area_ids = {match.entity.area_id for match in matches if match.entity.area_id}
    return len(area_ids) > 1


def is_all_devices_request(
    request_words: set[str],
    location_context: LocationContext | None,
) -> bool:
    return bool(
        request_words & ALL_WORDS
        and location_context
        and location_context.has_location
    )


def location_words(ha_objects: list[HaObject]) -> set[str]:
    words: set[str] = set()
    for entity in ha_objects:
        for value in (entity.area_name, entity.floor_name, entity.area_id, entity.floor_id):
            if value:
                words.update(normalized_words(normalize(value)))
                words.update(raw_word_variants(value))
    return words


def all_location_words(areas: list[Any], floors: list[Any]) -> set[str]:
    words: set[str] = set()
    for entry in [*areas, *floors]:
        for phrase in location_entry_phrases(entry):
            words.update(normalized_words(normalize(phrase)))
            words.update(raw_word_variants(phrase))
    return words


def floor_words(floors: list[Any]) -> set[str]:
    words: set[str] = set()
    for floor in floors:
        for phrase in location_entry_phrases(floor):
            words.update(normalized_words(normalize(phrase)))
            words.update(raw_word_variants(phrase))
    return words


def entity_floor_words(ha_objects: list[HaObject]) -> set[str]:
    words: set[str] = set()
    for entity in ha_objects:
        for value in (entity.floor_name, entity.floor_id):
            if value:
                words.update(normalized_words(normalize(value)))
                words.update(raw_word_variants(value))
    return words


def score_entity_match(
    entity: HaObject,
    command: NormalizedText,
    request_words: set[str],
    requested_domains: set[str],
) -> EntityMatch | None:
    entity_domain = entity.entity_id.split(".", maxsplit=1)[0]
    phrases = entity_phrases(entity)

    for phrase in phrases:
        # Полная фраза из имени или alias сильнее отдельных слов.
        if contains_phrase(command.normalized_text, phrase):
            return EntityMatch(entity=entity, score=100 + len(phrase.split()))
    for phrase in raw_entity_phrases(entity):
        if contains_phrase(command.original_text.lower(), phrase):
            return EntityMatch(entity=entity, score=100 + len(phrase.split()))

    if requested_domains and entity_domain not in requested_domains:
        return None

    phrase_scores = [
        score_phrase_words(phrase_words, request_words, entity_domain)
        for phrase_words in entity_phrase_word_sets(entity)
    ]
    climate_metadata_score = score_climate_metadata(entity, request_words, requested_domains)
    if climate_metadata_score is not None:
        phrase_scores.append(climate_metadata_score)
    phrase_scores = [score for score in phrase_scores if score is not None]
    if requested_domains and phrase_scores:
        return EntityMatch(entity=entity, score=max(phrase_scores))

    entity_words = entity_search_words(entity)
    specific_words = entity_words - generic_entity_words(entity_domain)
    if entity_domain in STATE_ONLY_DOMAINS and not requested_domains:
        return None
    if requested_domains and not specific_words and entity_domain in requested_domains:
        return EntityMatch(entity=entity, score=30)

    if not requested_domains and specific_words and specific_words <= request_words:
        return EntityMatch(entity=entity, score=40 + len(specific_words))

    return None


def score_phrase_words(
    phrase_words: set[str],
    request_words: set[str],
    entity_domain: str,
) -> int | None:
    specific_words = phrase_words - generic_entity_words(entity_domain)
    matched_specific_words = request_words & specific_words
    matched_domain_words = request_words & phrase_words & DOMAIN_WORDS.get(entity_domain, set())
    if matched_domain_words:
        unmatched_specific_words = specific_words - request_words
        return 45 + (5 * len(matched_domain_words)) - len(unmatched_specific_words)
    if not matched_specific_words:
        return None

    unmatched_specific_words = specific_words - request_words
    return 50 + (10 * len(matched_specific_words)) - len(unmatched_specific_words)


def score_climate_metadata(
        entity: HaObject,
        request_words: set[str],
        requested_domains: set[str],
) -> int | None:
    if entity.entity_id.split(".", maxsplit=1)[0] != "climate":
        return None
    if "climate" not in requested_domains:
        return None

    if request_words & {"отопление", "обогрев", "подогрев"}:
        if "heat" in (entity.hvac_modes or []) or entity.state == "heat":
            return 65
        return None

    if "термостат" in request_words and entity.device_class == "thermostat":
        return 65

    return None


def broad_domain_matches(
    command: NormalizedText,
    ha_objects: list[HaObject],
    requested_domains: set[str],
    location_context: LocationContext | None = None,
) -> list[EntityMatch]:
    if location_context and location_context.has_location:
        ha_objects = [
            entity
            for entity in ha_objects
            if entity_in_location(entity, location_context)
        ]

    # Широкие команды без комнаты ниже отсекаются как неоднозначные, если есть разные комнаты.
    request_words = normalized_words(command)
    if not requested_domains:
        if not is_all_devices_request(request_words, location_context):
            return []
        return [
            EntityMatch(entity=entity, score=30)
            for entity in ha_objects
            if is_turnable(entity) and entity.entity_id.split(".", maxsplit=1)[0] != "scene"
        ]

    if is_all_devices_request(request_words, location_context):
        return [
            EntityMatch(entity=entity, score=30)
            for entity in ha_objects
            if is_turnable(entity) and entity.entity_id.split(".", maxsplit=1)[0] != "scene"
        ]

    if requested_domains == {"light"} and (request_words & ALL_WORDS):
        return [
            EntityMatch(entity=entity, score=30)
            for entity in ha_objects
            if entity.entity_id.split(".", maxsplit=1)[0] == "light"
        ]

    domain_generic_words = set(GENERIC_WORDS)
    for domain in requested_domains:
        domain_generic_words.update(DOMAIN_WORDS.get(domain, set()))
    domain_generic_words.update(location_words(ha_objects))

    if request_words - domain_generic_words:
        return []

    return [
        EntityMatch(entity=entity, score=30)
        for entity in ha_objects
        if entity.entity_id.split(".", maxsplit=1)[0] in requested_domains
    ]


def detect_requested_domains(command: NormalizedText) -> set[str]:
    request_words = normalized_words(command)
    domains: set[str] = set()
    for domain, words in DOMAIN_WORDS.items():
        if request_words & words:
            domains.add(domain)

    if "температура" in request_words:
        domains.add("sensor")
    if "пакет" in request_words or "пакетов" in request_words:
        domains.add("sensor")

    return domains


def entity_phrases(entity: HaObject) -> list[str]:
    # Home Assistant иногда присылает служебные псевдонимы, их нельзя использовать для поиска.
    raw_phrases = [entity.name, *split_aliases(entity.aliases)]
    phrases: list[str] = []
    for phrase in raw_phrases:
        normalized = normalize(phrase).normalized_text.strip()
        if normalized and not normalized.startswith("computednametype"):
            phrases.append(normalized)
    return phrases


def contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text))


def raw_entity_phrases(entity: HaObject) -> list[str]:
    return [
        phrase.strip().lower()
        for phrase in [entity.name, *split_aliases(entity.aliases)]
        if phrase.strip() and not phrase.strip().startswith("ComputedNameType.")
    ]


def split_aliases(aliases: str) -> list[str]:
    return [
        alias.strip()
        for alias in aliases.replace(",", "/").split("/")
        if alias.strip() and not alias.strip().startswith("ComputedNameType.")
    ]


def entity_search_words(entity: HaObject) -> set[str]:
    words = normalized_words(normalize(entity.name))
    words.update(raw_word_variants(entity.name))
    for alias in split_aliases(entity.aliases):
        words.update(normalized_words(normalize(alias)))
        words.update(raw_word_variants(alias))
    for location_name in (entity.area_name, entity.floor_name):
        if location_name:
            words.update(normalized_words(normalize(location_name)))
            words.update(raw_word_variants(location_name))
    return {word for word in words if word and word not in GENERIC_WORDS}


def entity_phrase_word_sets(entity: HaObject) -> list[set[str]]:
    return [
        normalized_words(normalize(phrase)) | raw_word_variants(phrase)
        for phrase in [
            entity.name,
            *split_aliases(entity.aliases),
            entity.area_name or "",
            entity.floor_name or "",
        ]
        if phrase.strip()
    ]


def generic_entity_words(domain: str) -> set[str]:
    words = set(GENERIC_WORDS)
    words.update(DOMAIN_WORDS.get(domain, set()))
    return words


def is_turnable(entity: HaObject) -> bool:
    domain = entity.entity_id.split(".", maxsplit=1)[0]
    return domain in TURNABLE_DOMAINS


def build_service_call(
    entity: HaObject,
    action: str,
    brightness_pct: int | None,
    delay_seconds: int | None,
        target_temperature: int | None = None,
) -> dict[str, Any] | None:
    # Ответ сервиса остается простым JSON-планом, который выполняет интеграция HA.
    domain = entity.entity_id.split(".", maxsplit=1)[0]
    service = service_for_action(domain, action)
    if service is None:
        return None

    service_data: dict[str, Any] = {"entity_id": entity.entity_id}
    if domain == "light" and service == "turn_on" and brightness_pct is not None:
        service_data["brightness_pct"] = brightness_pct
    if domain == "climate" and service == "set_temperature" and target_temperature is not None:
        service_data["temperature"] = target_temperature

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

    return None


def entity_domain(entity: HaObject) -> str:
    return entity.entity_id.split(".", maxsplit=1)[0]


def parse_timing(text: str) -> ParsedTiming:
    # "через" означает задержку, а "на 15 минут" означает временное действие.
    delay_seconds = parse_delay_seconds(text)
    duration_seconds = parse_duration_seconds(text)
    return ParsedTiming(delay_seconds=delay_seconds, duration_seconds=duration_seconds)


def build_state_answer(entity: HaObject, command: NormalizedText | None = None) -> str:
    # Состояния Home Assistant переводим в короткий русский ответ для Assist.
    domain = entity.entity_id.split(".", maxsplit=1)[0]
    state = entity.state
    words = normalized_words(command) if command is not None else set()

    if domain == "binary_sensor":
        is_open = state == "on"
        if words & {"закрыть", "закрытый"}:
            return yes_no_state_answer(not is_open, entity.name, is_open)
        if words & {"открыть", "открытый"}:
            return yes_no_state_answer(is_open, entity.name, is_open)
        return named_open_closed_state(entity.name, is_open)

    if state in {"on", "off"}:
        is_on = state == "on"
        if words & {"включить", "включенный"}:
            return yes_no_power_state_answer(is_on, entity.name, is_on)
        if words & {"выключить", "выключенный"}:
            return yes_no_power_state_answer(not is_on, entity.name, is_on)
        return named_power_state(entity.name, is_on)

    if state in {"open", "closed"}:
        is_open = state == "open"
        if words & {"закрыть", "закрытый"}:
            return yes_no_state_answer(not is_open, entity.name, is_open)
        if words & {"открыть", "открытый"}:
            return yes_no_state_answer(is_open, entity.name, is_open)
        return named_open_closed_state(entity.name, is_open)

    if domain == "sensor" and entity.unit_of_measurement == "%":
        return format_percent_state(state)

    if domain == "sensor" and is_temperature_unit(entity.unit_of_measurement):
        return format_temperature_state(state)

    if domain == "weather":
        return build_weather_answer(entity)

    return state


WEATHER_STATE_WORDS = {
    "clear-night": "ясно",
    "cloudy": "облачно",
    "exceptional": "необычная погода",
    "fog": "туман",
    "hail": "град",
    "lightning": "гроза",
    "lightning-rainy": "гроза с дождем",
    "partlycloudy": "переменная облачность",
    "pouring": "ливень",
    "rainy": "дождь",
    "snowy": "снег",
    "snowy-rainy": "снег с дождем",
    "sunny": "ясно",
    "windy": "ветрено",
    "windy-variant": "ветрено с облачностью",
}


def build_weather_answer(entity: HaObject) -> str:
    parts = [WEATHER_STATE_WORDS.get(entity.state, entity.state)]
    temperature = format_temperature_value((entity.attributes or {}).get("temperature"))
    if temperature:
        parts.append(temperature)
    return ", ".join(parts)


def format_temperature_value(value: str | int | float | None) -> str:
    if value is None:
        return ""
    parsed_value = parse_float(str(value))
    if parsed_value is None:
        return ""
    temperature = round_half_up(parsed_value)
    return temperature_text(temperature)


def is_temperature_unit(unit: str | None) -> bool:
    return unit in {"°", "°C", "°F"}


def format_temperature_state(state: str) -> str:
    value = parse_float(state)
    if value is None:
        return state
    temperature = round_half_up(value)
    return temperature_text(temperature)


def format_percent_state(state: str) -> str:
    value = parse_float(state)
    if value is None:
        return state
    percent = round_half_up(value)
    return f"{percent} {percent_word(percent)}"


def temperature_text(value: int) -> str:
    if value < 0:
        return f"минус {abs(value)} {degree_word(value)}"
    return f"{value} {degree_word(value)}"


def parse_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def round_half_up(value: float) -> int:
    if value >= 0:
        return int(value + 0.5)
    return int(value - 0.5)


def degree_word(value: int) -> str:
    value = abs(value)
    if 11 <= value % 100 <= 14:
        return "градусов"
    if value % 10 == 1:
        return "градус"
    if 2 <= value % 10 <= 4:
        return "градуса"
    return "градусов"


def percent_word(value: int) -> str:
    value = abs(value)
    if 11 <= value % 100 <= 14:
        return "процентов"
    if value % 10 == 1:
        return "процент"
    if 2 <= value % 10 <= 4:
        return "процента"
    return "процентов"


def yes_no_state_answer(
        is_expected_state: bool,
        entity_name: str,
        actual_is_open: bool,
) -> str:
    return f"{'да' if is_expected_state else 'нет'}, {open_closed_adjective(entity_name, actual_is_open)}"


def yes_no_power_state_answer(
        is_expected_state: bool,
        entity_name: str,
        actual_is_on: bool,
) -> str:
    return f"{'да' if is_expected_state else 'нет'}, {power_adjective(entity_name, actual_is_on)}"


def named_power_state(entity_name: str, is_on: bool) -> str:
    features = get_text_normalizer().first_word_agreement(entity_name)
    return f"{features.word} {power_adjective(entity_name, is_on)}"


def power_adjective(entity_name: str, is_on: bool) -> str:
    features = get_text_normalizer().first_word_agreement(entity_name)
    if is_on:
        return agree_adjective(features, "включен", "включена", "включено", "включены")
    return agree_adjective(features, "выключен", "выключена", "выключено", "выключены")


def named_open_closed_state(entity_name: str, is_open: bool) -> str:
    features = get_text_normalizer().first_word_agreement(entity_name)
    return f"{features.word} {open_closed_adjective(entity_name, is_open)}"


def open_closed_adjective(entity_name: str, is_open: bool) -> str:
    features = get_text_normalizer().first_word_agreement(entity_name)
    if is_open:
        return agree_adjective(features, "открыт", "открыта", "открыто", "открыты")
    return agree_adjective(features, "закрыт", "закрыта", "закрыто", "закрыты")
