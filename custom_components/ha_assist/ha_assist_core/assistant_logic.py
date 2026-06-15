import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from . import custom_intents, device_command, location_resolver, state_query
from .assistant_result import (
    AssistLogicResult,
    ResponseText,
    llm_fallback_result,
    strip_trailing_period,
)
from .ha_parser import HaObject
from .llm_client import ChatMessage, generate_llm_response
from .number_parser import parse_brightness_percent, parse_temperature
from .text_normalizer import (
    NormalizedText,
    normalize,
    normalized_words,
    split_aliases,
)

logger = logging.getLogger(__name__)

ActionKind = Literal[
    "turn_on",
    "turn_off",
    "open",
    "close",
    "set_temperature",
    "todo_add",
]

BARE_ACTIVATION_DOMAINS = {"button", "scene"}
STATE_ONLY_DOMAINS = {"binary_sensor", "sensor", "todo", "weather"}
TEMPERATURE_UNITS = {"°", "°C", "°F"}

# Эти слова не должны превращать комнату, параметр или глагол в имя устройства.
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
    "состояние",
    "процент",
    "градус",
    "включить",
    "включи",
    "выключить",
    "выключи",
    "отключить",
    "отключи",
    "добавить",
    "добавь",
    "напомнить",
    "напомни",
    "открыть",
    "открой",
    "закрыть",
    "закрой",
    "активировать",
    "активируй",
    "запустить",
    "запусти",
    "поставить",
    "поставь",
    "установить",
    "установи",
    "через",
    "кроме",
    "минута",
    "секунда",
    "час",
    "полчаса",
    "этаж",
    *location_resolver.ALL_WORDS,
    *location_resolver.ALL_LOCATIONS_WORDS,
}

DOMAIN_REQUEST_WORDS = {
    "automation": {"автоматизация"},
    "binary_sensor": {"датчик", "сенсор"},
    "button": {"кнопка"},
    "climate": {
        "климат",
        "кондиционер",
        "отопление",
        "обогрев",
        "подогрев",
        "термостат",
    },
    "cover": {
        "ворота",
        "жалюзи",
        "роллета",
        "рольставни",
        "ставни",
        "штора",
    },
    "fan": {"вентилятор"},
    "humidifier": {"увлажнитель"},
    "input_boolean": {"переключатель", "тумблер"},
    "light": {
        "лампа",
        "лампочка",
        "люстра",
        "освещение",
        "подсветка",
        "свет",
        "светильник",
    },
    "media_player": {"колонка", "медиаплеер", "плеер", "телевизор", "телек"},
    "remote": {"пульт"},
    "scene": {"режим", "сцена"},
    "script": {"скрипт", "сценарий"},
    "sensor": {"датчик", "сенсор"},
    "switch": {"выключатель", "розетка", "реле", "свитч", "переключатель"},
    "vacuum": {"пылесос"},
}

# Эти слова означают весь домен, а не конкретный вид сущности внутри домена.
BROAD_DOMAIN_WORDS = {
    "light": {"свет", "освещение"},
    "climate": {"климат"},
}

STATE_CATEGORY_WORDS = {
    "temperature": {"температура"},
    "door": {"дверь"},
    "window": {"окно"},
    "gate": {"ворота"},
    "humidity": {"влажность"},
    "weather": {"погода"},
}

ACTION_START_PATTERN = re.compile(
    r"\s+и\s+(?=(?:включ|выключ|отключ|откро|закро|активир|запуст|постав|установ|добав|напом))",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RequestContext:
    source_area_id: str | None = None
    source_area_name: str | None = None
    source_floor_id: str | None = None
    source_floor_name: str | None = None


@dataclass(frozen=True)
class EntityIndex:
    entities: list[HaObject]
    by_id: dict[str, HaObject]
    by_domain: dict[str, tuple[HaObject, ...]]
    domains: frozenset[str]
    normalized_names: dict[str, tuple[str, ...]]
    raw_names: dict[str, tuple[str, ...]]
    name_words: dict[str, frozenset[str]]
    normalized_area_names: dict[str, str]
    location_words: frozenset[str]


@dataclass
class ParsedAction:
    raw_text: str
    command: NormalizedText
    action: ActionKind
    target_domains: set[str]
    target_entity_ids: set[str]
    category_words: set[str]
    location_context: location_resolver.LocationContext
    excluded_area_ids: set[str]
    excluded_floor_ids: set[str]
    all_locations: bool
    broad_target: bool
    delay_seconds: int | None = None
    duration_seconds: int | None = None
    brightness_percent: int | None = None
    temperature: int | None = None
    todo_text: str | None = None
    todo_entity_id: str | None = None
    error_response: str | None = None


def build_assist_result(
        text: str,
        ha_objects: list[HaObject],
        areas: list[Any] | None = None,
        floors: list[Any] | None = None,
        source_area_id: str | None = None,
        source_area_name: str | None = None,
        source_floor_id: str | None = None,
        source_floor_name: str | None = None,
        previous_exchange: list[ChatMessage] | None = None,
) -> AssistLogicResult:
    command = normalize(text)
    entity_index = build_entity_index(ha_objects)
    context = RequestContext(
        source_area_id=source_area_id,
        source_area_name=source_area_name,
        source_floor_id=source_floor_id,
        source_floor_name=source_floor_name,
    )
    areas = areas or []
    floors = floors or []
    logger.debug("normalized: %s", command.normalized_text)

    custom_intent_result = custom_intents.handle_custom_intent(
        command,
        previous_exchange=previous_exchange,
    )
    if custom_intent_result is not None:
        return custom_intent_result

    result = handle_bare_activation(command, entity_index, context)
    if result is not None:
        return result

    todo_action = parse_todo_action(command, entity_index, areas, floors, context)
    if todo_action is not None:
        return execute_action_plan([todo_action], entity_index)

    if is_general_question(command):
        return llm_fallback_result()

    result = handle_state_request(
        command,
        entity_index,
        areas,
        floors,
        context,
    )
    if result is not None:
        return result

    action_plan = parse_action_plan(command, entity_index, areas, floors, context)
    if action_plan is None:
        return llm_fallback_result()

    return execute_action_plan(action_plan, entity_index)


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
        previous_exchange: list[ChatMessage] | None = None,
        llm_api_key: str | None = None,
        llm_api_url: str | None = None,
) -> AssistLogicResult:
    result = await asyncio.to_thread(
        build_assist_result,
        text,
        ha_objects,
        areas=areas,
        floors=floors,
        source_area_id=source_area_id,
        source_area_name=source_area_name,
        source_floor_id=source_floor_id,
        source_floor_name=source_floor_name,
        previous_exchange=previous_exchange or (llm_messages[:-1] if llm_messages else None),
    )
    if not result.fallback_to_llm:
        return result

    messages = llm_messages or [{"role": "user", "content": text}]
    logger.info("LLM fallback requested for non-smart-home text: %s", text)
    llm_response = await generate_llm_response(
        messages,
        api_key=llm_api_key,
        api_url=llm_api_url,
    )
    if llm_response is None:
        return result
    return AssistLogicResult(response=strip_trailing_period(llm_response))


def handle_bare_activation(
        command: NormalizedText,
        entity_index: EntityIndex,
        context: RequestContext,
) -> AssistLogicResult | None:
    request = command.normalized_text.strip()
    matches = [
        entity
        for entity in entity_index.entities
        if entity_domain(entity) in BARE_ACTIVATION_DOMAINS
           and request in entity_index.normalized_names[entity.entity_id]
    ]
    if not matches:
        return None
    if len(matches) == 1:
        return build_bare_activation_result(matches[0])

    filtered = filter_by_source_room(matches, entity_index, context)
    if len(filtered) == 1:
        return build_bare_activation_result(filtered[0])
    if not filtered:
        return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)
    return AssistLogicResult(response=ResponseText.AMBIGUOUS_AREA)


def build_bare_activation_result(entity: HaObject) -> AssistLogicResult:
    action = device_command.bare_activation_action(entity)
    service_call = device_command.build_service_call(entity=entity, action=action or "")
    if service_call is None:
        return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)
    return AssistLogicResult(
        response=ResponseText.ok(),
        service_calls=[service_call],
    )


def handle_state_request(
        command: NormalizedText,
        entity_index: EntityIndex,
        areas: list[Any],
        floors: list[Any],
        context: RequestContext,
) -> AssistLogicResult | None:
    if not looks_like_state_request(command, entity_index):
        return None

    location_context = detect_location_context(
        command,
        entity_index.entities,
        areas,
        floors,
        context,
    )
    matches = find_state_candidates(command, entity_index)
    if location_context.has_explicit_location:
        matches = [
            entity
            for entity in matches
            if location_resolver.entity_in_location(entity, location_context)
        ]
        if not matches:
            return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)

    category_request = bool(
        normalized_words(command)
        & set().union(*STATE_CATEGORY_WORDS.values())
    )
    if location_context.has_location and (len(matches) > 1 or category_request):
        room_matches = [
            entity
            for entity in matches
            if location_resolver.entity_in_location(entity, location_context)
        ]
        if room_matches:
            matches = room_matches
        elif category_request:
            return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)

    if len(matches) != 1:
        if matches:
            return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)
        return None

    answer = state_query.build_state_answer(
        matches[0],
        command,
        normalized_words(command),
    )
    return AssistLogicResult(response=strip_trailing_period(answer))


def looks_like_state_request(command: NormalizedText, entity_index: EntityIndex) -> bool:
    if state_query.is_state_query(command):
        return True
    if detect_action(command) is not None:
        return False
    request = command.normalized_text.strip()
    return any(
        entity_domain(entity) in STATE_ONLY_DOMAINS
        and any(
            contains_phrase(request, phrase)
            for phrase in entity_index.normalized_names[entity.entity_id]
        )
        for entity in entity_index.entities
    )


def find_state_candidates(
        command: NormalizedText,
        entity_index: EntityIndex,
) -> list[HaObject]:
    request_words = normalized_words(command)
    scored: list[tuple[int, HaObject]] = []
    for entity in entity_index.entities:
        score = state_entity_score(
            entity,
            command,
            request_words,
            entity_index,
        )
        if score is not None:
            scored.append((score, entity))

    if not scored:
        return []
    best_score = max(score for score, _ in scored)
    return [entity for score, entity in scored if score == best_score]


def state_entity_score(
        entity: HaObject,
        command: NormalizedText,
        request_words: set[str],
        entity_index: EntityIndex,
) -> int | None:
    phrases = entity_index.normalized_names[entity.entity_id]
    for phrase in phrases:
        if contains_phrase(command.normalized_text, phrase):
            return 120 + len(phrase.split())

    category_score = state_category_score(entity, request_words, entity_index)
    phrase_words = entity_index.name_words[entity.entity_id]
    specific_words = phrase_words - GENERIC_WORDS - entity_index.location_words
    matched_words = request_words & specific_words
    if matched_words:
        return max(category_score or 0, 70 + (10 * len(matched_words)))
    return category_score


def state_category_score(
        entity: HaObject,
        request_words: set[str],
        entity_index: EntityIndex,
) -> int | None:
    if (
            request_words & STATE_CATEGORY_WORDS["temperature"]
            and is_temperature_entity(entity, entity_index)
    ):
        return 80
    if (
            request_words & STATE_CATEGORY_WORDS["humidity"]
            and is_humidity_entity(entity, entity_index)
    ):
        return 80
    if request_words & STATE_CATEGORY_WORDS["weather"] and entity_domain(entity) == "weather":
        return 80

    entity_words = entity_index.name_words[entity.entity_id]
    device_class = (entity.device_class or "").lower()
    if request_words & STATE_CATEGORY_WORDS["door"]:
        if "дверь" in entity_words or device_class in {"door", "opening"}:
            return 80
    if request_words & STATE_CATEGORY_WORDS["window"]:
        if "окно" in entity_words or device_class == "window":
            return 80
    if request_words & STATE_CATEGORY_WORDS["gate"]:
        if "ворота" in entity_words or device_class == "garage_door":
            return 80
    return None


def is_temperature_entity(entity: HaObject, entity_index: EntityIndex) -> bool:
    return bool(
        entity_domain(entity) == "sensor"
        and (
                entity.device_class == "temperature"
                or entity.unit_of_measurement in TEMPERATURE_UNITS
                or "температура" in entity_index.name_words[entity.entity_id]
        )
    )


def is_humidity_entity(entity: HaObject, entity_index: EntityIndex) -> bool:
    return bool(
        entity_domain(entity) == "sensor"
        and (
                entity.device_class == "humidity"
                or "влажность" in entity_index.name_words[entity.entity_id]
        )
    )


def parse_action_plan(
        command: NormalizedText,
        entity_index: EntityIndex,
        areas: list[Any],
        floors: list[Any],
        context: RequestContext,
) -> list[ParsedAction] | None:
    parts = split_action_parts(command)
    actions: list[ParsedAction] = []
    for part in parts:
        action = parse_action_part(part, entity_index, areas, floors, context)
        if action is None:
            return None
        actions.append(action)
    return actions or None


def split_action_parts(command: NormalizedText) -> list[NormalizedText]:
    parts = [
        part.strip(" .,!?")
        for part in ACTION_START_PATTERN.split(command.original_text)
        if part.strip(" .,!?")
    ]
    return [normalize(part) for part in parts]


def parse_action_part(
        command: NormalizedText,
        entity_index: EntityIndex,
        areas: list[Any],
        floors: list[Any],
        context: RequestContext,
) -> ParsedAction | None:
    action = detect_action(command)
    if action is None or action == "todo_add":
        return None

    include_command, exclude_command = split_exclusion(command)
    location_context = detect_location_context(
        include_command,
        entity_index.entities,
        areas,
        floors,
        context,
    )
    error_response = detect_location_error(
        include_command,
        entity_index.entities,
        areas,
        floors,
    )
    excluded_area_ids: set[str] = set()
    excluded_floor_ids: set[str] = set()
    if exclude_command is not None:
        excluded_context = detect_location_context(
            exclude_command,
            entity_index.entities,
            areas,
            floors,
            RequestContext(),
        )
        if excluded_context.explicit_area:
            excluded_area_ids = excluded_context.area_ids
        elif excluded_context.explicit_floor:
            excluded_floor_ids = excluded_context.floor_ids
        if not excluded_context.has_explicit_location:
            error_response = ResponseText.AREA_NOT_FOUND

    target_domains = detect_target_domains(command, entity_index)
    category_words = domain_words_in_request(command, target_domains)
    target_entity_ids = {
        entity.entity_id
        for entity in find_exact_action_entities(command, entity_index, target_domains)
    }
    all_locations = is_all_locations_action(command, location_context, exclude_command)
    broad_target = bool(
        all_locations
        or not target_entity_ids
        or (
                category_words
                and not has_specific_target_words(
            command,
            category_words,
            entity_index,
        )
        )
    )
    timing = device_command.parse_timing(command)
    temperature = parse_temperature(command)
    if action == "set_temperature":
        target_domains = {"climate"} if "climate" in entity_index.domains else set()

    return ParsedAction(
        raw_text=command.original_text,
        command=command,
        action=action,
        target_domains=target_domains,
        target_entity_ids=target_entity_ids,
        category_words=category_words,
        location_context=location_context,
        excluded_area_ids=excluded_area_ids,
        excluded_floor_ids=excluded_floor_ids,
        all_locations=all_locations,
        broad_target=broad_target,
        delay_seconds=timing.delay_seconds,
        duration_seconds=timing.duration_seconds,
        brightness_percent=parse_brightness_percent(command),
        temperature=temperature,
        error_response=error_response,
    )


def parse_todo_action(
        command: NormalizedText,
        entity_index: EntityIndex,
        areas: list[Any],
        floors: list[Any],
        context: RequestContext,
) -> ParsedAction | None:
    if not normalized_words(command) & {"добавить", "добавь", "напомнить", "напомни"}:
        return None

    candidates: list[tuple[int, HaObject, str | None]] = []
    for entity in entity_index.by_domain.get("todo", ()):
        if entity_domain(entity) != "todo":
            continue
        for phrase in entity_index.raw_names[entity.entity_id]:
            match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", command.original_text, re.IGNORECASE)
            if match is None:
                continue
            item = extract_todo_item(command.original_text, match)
            candidates.append((len(phrase.split()), entity, item))

    if not candidates:
        return None
    best_score = max(score for score, _, _ in candidates)
    best = [
        (entity, item)
        for score, entity, item in candidates
        if score == best_score
    ]
    if len(best) != 1:
        return ParsedAction(
            raw_text=command.original_text,
            command=command,
            action="todo_add",
            target_domains={"todo"},
            target_entity_ids=set(),
            category_words=set(),
            location_context=detect_location_context(
                command,
                entity_index.entities,
                areas,
                floors,
                context,
            ),
            excluded_area_ids=set(),
            excluded_floor_ids=set(),
            all_locations=False,
            broad_target=False,
            error_response=ResponseText.ENTITY_NOT_FOUND,
        )

    entity, item = best[0]
    return ParsedAction(
        raw_text=command.original_text,
        command=command,
        action="todo_add",
        target_domains={"todo"},
        target_entity_ids={entity.entity_id},
        category_words=set(),
        location_context=detect_location_context(
            command,
            entity_index.entities,
            areas,
            floors,
            context,
        ),
        excluded_area_ids=set(),
        excluded_floor_ids=set(),
        all_locations=False,
        broad_target=False,
        todo_text=item,
        todo_entity_id=entity.entity_id,
        error_response=None if item else ResponseText.ACTION_NOT_FOUND,
    )


def extract_todo_item(text: str, match: re.Match[str]) -> str | None:
    before = text[:match.start()].strip(" .,!?")
    after = text[match.end():].strip(" .,!?")
    if after:
        return after

    before = re.sub(
        r"^\s*(?:добавь|добавить|напомни|напомнить)\s+",
        "",
        before,
        flags=re.IGNORECASE,
    ).strip(" .,!?")
    before = re.sub(
        r"(?:^|\s)(?:в|во|на)$",
        "",
        before,
        flags=re.IGNORECASE,
    ).strip(" .,!?")
    return before or None


def detect_action(command: NormalizedText) -> ActionKind | None:
    words = normalized_words(command)
    temperature = parse_temperature(command)
    brightness = parse_brightness_percent(command)
    if words & {"добавить", "добавь", "напомнить", "напомни"}:
        return "todo_add"
    if temperature is not None and words & {
        "включить",
        "включи",
        "поставить",
        "поставь",
        "установить",
        "установи",
    }:
        return "set_temperature"
    if words & {"включить", "включи", "активировать", "активируй", "запустить", "запусти"}:
        return "turn_on"
    if words & {"выключить", "выключи", "отключить", "отключи"}:
        return "turn_off"
    if words & {"открыть", "открой"}:
        return "open"
    if words & {"закрыть", "закрой"}:
        return "close"
    if brightness is not None and words & {"поставить", "поставь", "установить", "установи"}:
        return "turn_on"
    return None


def detect_target_domains(
        command: NormalizedText,
        entity_index: EntityIndex,
) -> set[str]:
    request_words = normalized_words(command)
    domains: set[str] = set()
    available_domains = entity_index.domains
    for domain, words in DOMAIN_REQUEST_WORDS.items():
        if domain in available_domains and request_words & words:
            domains.add(domain)

    for entity in entity_index.entities:
        entity_words = (
                entity_index.name_words[entity.entity_id]
                - GENERIC_WORDS
                - entity_index.location_words
        )
        if request_words & entity_words:
            domains.add(entity_domain(entity))

    if request_words & {"отопление", "обогрев", "подогрев"}:
        if "climate" in available_domains:
            domains.add("climate")
    return domains


def find_exact_action_entities(
        command: NormalizedText,
        entity_index: EntityIndex,
        target_domains: set[str],
) -> list[HaObject]:
    scored: list[tuple[int, HaObject]] = []
    non_bare_domains = target_domains - BARE_ACTIVATION_DOMAINS
    for entity in entity_index.entities:
        domain = entity_domain(entity)
        if target_domains and domain not in target_domains:
            continue
        if domain in BARE_ACTIVATION_DOMAINS and non_bare_domains:
            continue
        for phrase in entity_index.normalized_names[entity.entity_id]:
            if contains_phrase(command.normalized_text, phrase):
                scored.append((100 + len(phrase.split()), entity))
                break

    if not scored:
        return []
    best_score = max(score for score, _ in scored)
    return [entity for score, entity in scored if score == best_score]


def execute_action_plan(
        actions: list[ParsedAction],
        entity_index: EntityIndex,
) -> AssistLogicResult:
    service_calls: list[dict[str, Any]] = []
    for action in actions:
        if action.error_response:
            return AssistLogicResult(response=action.error_response)
        calls, error_response = build_service_calls(action, entity_index)
        if error_response:
            return AssistLogicResult(response=error_response)
        service_calls.extend(calls)

    if not service_calls:
        return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)
    if len(actions) == 1 and actions[0].action == "todo_add":
        todo_entity = entity_index.by_id.get(actions[0].todo_entity_id or "")
        if todo_entity is not None and actions[0].todo_text:
            return AssistLogicResult(
                response=build_todo_added_response(
                    actions[0].todo_text,
                    todo_entity.name,
                ),
                service_calls=service_calls,
            )
    return AssistLogicResult(
        response=ResponseText.ok(),
        service_calls=service_calls,
    )


def build_todo_added_response(item: str, list_name: str) -> str:
    normalized_list_name = list_name.strip()
    if normalized_list_name:
        normalized_list_name = (
                normalized_list_name[0].lower()
                + normalized_list_name[1:]
        )
    return f"Добавила {item} в {normalized_list_name}"


def build_service_calls(
        action: ParsedAction,
        entity_index: EntityIndex,
) -> tuple[list[dict[str, Any]], str | None]:
    if action.action == "todo_add":
        entity = entity_index.by_id.get(action.todo_entity_id or "")
        if entity is None or not action.todo_text:
            return [], ResponseText.ENTITY_NOT_FOUND
        service_call = device_command.build_service_call(
            entity=entity,
            action="add_todo",
            todo_item=action.todo_text,
        )
        return ([service_call] if service_call else []), None

    targets = resolve_action_targets(action, entity_index)
    if not targets:
        return [], ResponseText.ENTITY_NOT_FOUND
    if is_ambiguous_action_target(action, targets):
        return [], ResponseText.AMBIGUOUS_AREA

    service_calls: list[dict[str, Any]] = []
    for entity in targets:
        service_call = device_command.build_service_call(
            entity=entity,
            action=action.action,
            brightness_pct=action.brightness_percent,
            target_temperature=action.temperature,
            delay_seconds=action.delay_seconds,
        )
        if service_call is None:
            continue
        service_calls.append(service_call)
        reverse_call = device_command.build_reverse_service_call(
            entity=entity,
            action=action.action,
            delay_seconds=action.duration_seconds,
        )
        if reverse_call is not None:
            service_calls.append(reverse_call)

    if not service_calls:
        return [], ResponseText.ENTITY_NOT_FOUND
    return service_calls, None


def resolve_action_targets(
        action: ParsedAction,
        entity_index: EntityIndex,
) -> list[HaObject]:
    if action.target_entity_ids and not action.broad_target:
        candidates = [
            entity_index.by_id[entity_id]
            for entity_id in action.target_entity_ids
            if entity_id in entity_index.by_id
        ]
    else:
        candidates = [
            entity
            for domain in action.target_domains
            for entity in entity_index.by_domain.get(domain, ())
        ]
        candidates = filter_category_targets(candidates, action, entity_index)

    candidates = filter_action_compatible_targets(candidates, action)
    candidates = filter_action_location(candidates, action)
    candidates = [
        entity
        for entity in candidates
        if entity.area_id not in action.excluded_area_ids
           and entity.floor_id not in action.excluded_floor_ids
    ]
    return unique_entities(candidates)


def filter_category_targets(
        entities: list[HaObject],
        action: ParsedAction,
        entity_index: EntityIndex,
) -> list[HaObject]:
    if not action.category_words:
        return entities
    if action.category_words & broad_words_for_domains(action.target_domains):
        return entities
    if action.category_words & {"отопление", "обогрев", "подогрев"}:
        return [
            entity
            for entity in entities
            if entity_domain(entity) == "climate"
               and ("heat" in (entity.hvac_modes or []) or entity.state == "heat")
        ]

    matching = [
        entity
        for entity in entities
        if entity_index.name_words[entity.entity_id] & action.category_words
    ]
    return matching or entities


def filter_action_compatible_targets(
        entities: list[HaObject],
        action: ParsedAction,
) -> list[HaObject]:
    if action.action == "set_temperature":
        return [
            entity
            for entity in entities
            if entity_domain(entity) == "climate"
        ]
    if action.action in {"open", "close"}:
        return [
            entity
            for entity in entities
            if entity_domain(entity) == "cover"
        ]
    if action.action in {"turn_on", "turn_off"}:
        return [
            entity
            for entity in entities
            if device_command.is_turnable(entity)
               and entity_domain(entity) != "scene"
        ]
    return entities


def filter_action_location(
        entities: list[HaObject],
        action: ParsedAction,
) -> list[HaObject]:
    location_context = action.location_context
    if action.all_locations and not location_context.has_explicit_location:
        return entities
    if location_context.has_explicit_location:
        return [
            entity
            for entity in entities
            if location_resolver.entity_in_location(entity, location_context)
        ]
    if location_context.has_location and (action.broad_target or len(entities) > 1):
        room_entities = [
            entity
            for entity in entities
            if location_resolver.entity_in_location(entity, location_context)
        ]
        return room_entities
    return entities


def is_ambiguous_action_target(
        action: ParsedAction,
        entities: list[HaObject],
) -> bool:
    if len(entities) <= 1:
        return False
    if action.all_locations or action.location_context.has_explicit_location:
        return False
    if action.broad_target and action.location_context.has_location:
        return False
    if action.broad_target:
        area_ids = {entity.area_id for entity in entities if entity.area_id}
        return len(area_ids) > 1
    return True


def detect_location_context(
        command: NormalizedText,
        entities: list[HaObject],
        areas: list[Any],
        floors: list[Any],
        context: RequestContext,
) -> location_resolver.LocationContext:
    return location_resolver.detect_location_context(
        command=command,
        ha_objects=entities,
        areas=areas,
        floors=floors,
        source_area_id=context.source_area_id,
        source_area_name=context.source_area_name,
        source_floor_id=context.source_floor_id,
        source_floor_name=context.source_floor_name,
        generic_words=GENERIC_WORDS,
    )


def detect_location_error(
        command: NormalizedText,
        entities: list[HaObject],
        areas: list[Any],
        floors: list[Any],
) -> str | None:
    if location_resolver.has_unknown_floor(command, entities, floors, GENERIC_WORDS):
        return ResponseText.FLOOR_NOT_FOUND
    if location_resolver.has_unknown_location(
            command,
            entities,
            areas,
            floors,
            GENERIC_WORDS,
    ):
        return ResponseText.AREA_NOT_FOUND
    return None


def split_exclusion(
        command: NormalizedText,
) -> tuple[NormalizedText, NormalizedText | None]:
    parts = re.split(r"\bкроме\b", command.original_text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 1:
        return command, None
    return normalize(parts[0].strip()), normalize(parts[1].strip())


def is_all_locations_action(
        command: NormalizedText,
        location_context: location_resolver.LocationContext,
        exclude_command: NormalizedText | None,
) -> bool:
    words = normalized_words(command)
    if words & location_resolver.ALL_LOCATIONS_WORDS:
        return True
    return bool(
        words & location_resolver.ALL_WORDS
        and (
                exclude_command is not None
                or not location_context.has_explicit_location
        )
    )


def is_general_question(command: NormalizedText) -> bool:
    text = command.original_text.lower()
    words = normalized_words(command)
    if re.search(r"\bчто\s+(?:делать|сделать)\b", text, re.IGNORECASE):
        return True
    if "можно" in words and "ли" in words:
        return True
    if "если" in words:
        return True
    return bool(
        words
        & {"почему", "зачем", "кто", "когда", "где", "как", "чем", "каков", "какова"}
    )


def filter_by_source_room(
        entities: list[HaObject],
        entity_index: EntityIndex,
        context: RequestContext,
) -> list[HaObject]:
    if context.source_area_id:
        return [
            entity
            for entity in entities
            if entity.area_id == context.source_area_id
        ]
    if context.source_area_name:
        source_name = normalize(context.source_area_name).normalized_text
        return [
            entity
            for entity in entities
            if entity_index.normalized_area_names.get(entity.entity_id) == source_name
        ]
    return entities


def domain_words_in_request(
        command: NormalizedText,
        domains: set[str],
) -> set[str]:
    words = normalized_words(command)
    result: set[str] = set()
    for domain in domains:
        result.update(words & DOMAIN_REQUEST_WORDS.get(domain, set()))
    return result


def broad_words_for_domains(domains: set[str]) -> set[str]:
    words: set[str] = set()
    for domain in domains:
        words.update(BROAD_DOMAIN_WORDS.get(domain, set()))
    return words


def has_specific_target_words(
        command: NormalizedText,
        category_words: set[str],
        entity_index: EntityIndex,
) -> bool:
    request_words = set(command.normal_forms)
    remaining_words = (
            request_words
            - GENERIC_WORDS
            - category_words
            - entity_index.location_words
    )
    return any(not word.isdigit() for word in remaining_words)


def build_entity_index(entities: list[HaObject]) -> EntityIndex:
    by_id = {entity.entity_id: entity for entity in entities}
    domains: set[str] = set()
    by_domain_lists: dict[str, list[HaObject]] = {}
    normalized_names: dict[str, tuple[str, ...]] = {}
    raw_names: dict[str, tuple[str, ...]] = {}
    name_words: dict[str, frozenset[str]] = {}
    normalized_area_names: dict[str, str] = {}
    location_values: set[str] = set()

    for entity in entities:
        domain = entity_domain(entity)
        domains.add(domain)
        by_domain_lists.setdefault(domain, []).append(entity)

        entity_names = normalized_entity_names(entity)
        normalized_names[entity.entity_id] = entity_names
        raw_names[entity.entity_id] = raw_entity_names(entity)
        name_words[entity.entity_id] = frozenset(
            word
            for name in entity_names
            for word in name.split()
        )

        if entity.area_name:
            normalized_area_names[entity.entity_id] = normalize(
                entity.area_name,
            ).normalized_text
        location_values.update(
            value
            for value in (
                entity.area_id,
                entity.area_name,
                entity.floor_id,
                entity.floor_name,
            )
            if value
        )

    location_words = frozenset(
        word
        for value in location_values
        for word in normalized_words(normalize(value))
    )
    return EntityIndex(
        entities=entities,
        by_id=by_id,
        by_domain={
            domain: tuple(domain_entities)
            for domain, domain_entities in by_domain_lists.items()
        },
        domains=frozenset(domains),
        normalized_names=normalized_names,
        raw_names=raw_names,
        name_words=name_words,
        normalized_area_names=normalized_area_names,
        location_words=location_words,
    )


def normalized_entity_names(entity: HaObject) -> tuple[str, ...]:
    names: list[str] = []
    for name in [entity.name, *split_aliases(entity.aliases)]:
        normalized_name = normalize(name).normalized_text.strip()
        if (
                normalized_name
                and not normalized_name.startswith("computednametype")
                and normalized_name not in names
        ):
            names.append(normalized_name)
    return tuple(names)


def raw_entity_names(entity: HaObject) -> tuple[str, ...]:
    return tuple(
        name.strip().lower()
        for name in [entity.name, *split_aliases(entity.aliases)]
        if name.strip()
        and not name.strip().lower().startswith("computednametype")
    )


def entity_domain(entity: HaObject) -> str:
    return entity.entity_id.split(".", maxsplit=1)[0]


def contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text))


def unique_entities(entities: list[HaObject]) -> list[HaObject]:
    result: list[HaObject] = []
    seen: set[str] = set()
    for entity in entities:
        if entity.entity_id in seen:
            continue
        seen.add(entity.entity_id)
        result.append(entity)
    return result
