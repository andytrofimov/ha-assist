import json
import random
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from ha_parser import HaObject
from text_normalizer import NormalizedText, get_text_normalizer

OK_RESPONSES = ("окей", "готово", "сделано")
ERROR_NOT_SMART_HOME = "Не поняла, как это связано с умным домом."
ERROR_ENTITY_NOT_FOUND = "Не нашла такое устройство."
ERROR_ACTION_NOT_FOUND = "Не поняла, что сделать."

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

STATE_ONLY_DOMAINS = {"binary_sensor", "sensor"}

DOMAIN_WORDS = {
    "light": {"свет", "лампа", "лампочка", "люстра", "подсветка", "торшер"},
    "climate": {"кондиционер", "кондей", "климат"},
    "cover": {"штора", "шторы", "занавеска", "ворота", "рольставни"},
    "switch": {"выключатель", "розетка", "массаж", "чайник", "комп", "компьютер"},
    "input_boolean": {"режим"},
    "scene": {"режим", "сцена"},
    "media_player": {"телевизор", "телек", "тв", "колонка", "плеер"},
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
    "процент",
    "процентов",
    "включить",
    "выключить",
    "открыть",
    "закрыть",
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
}

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
    response: str
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


def build_assist_result(
    text: str,
    ha_objects: list[HaObject],
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
        matches = find_entity_matches(command, ha_objects)

        found_smart_home_signal = (
            found_smart_home_signal
            or action is not None
            or is_state_query(command)
            or bool(matches)
            or bool(detect_requested_domains(command))
        )

        if is_state_query(command):
            if not matches:
                return AssistLogicResult(response=ERROR_ENTITY_NOT_FOUND)
            state_answers.extend(build_state_answer(match.entity) for match in matches)
            continue

        if action is None and matches:
            action = "turn_on" if all(is_turnable(match.entity) for match in matches) else None

        if action is None:
            if found_smart_home_signal:
                return AssistLogicResult(response=ERROR_ACTION_NOT_FOUND)
            return AssistLogicResult(
                response=ERROR_NOT_SMART_HOME,
                fallback_to_llm=True,
            )

        if not matches:
            return AssistLogicResult(response=ERROR_ENTITY_NOT_FOUND)

        for match in matches:
            service_call = build_service_call(
                entity=match.entity,
                action=action,
                brightness_pct=brightness_pct,
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

    return AssistLogicResult(
        response=ERROR_NOT_SMART_HOME,
        fallback_to_llm=True,
    )


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


def split_compound_commands(text: str) -> list[str]:
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
    return None


def is_state_query(command: NormalizedText) -> bool:
    text = command.original_text.strip().lower()
    words = set(command.normal_forms)

    if text.endswith("?"):
        return True
    if words & {"сколько", "какой", "какая", "какое", "что"}:
        return True
    if (words & {"включить", "открыть", "закрыть"}) and not (
        words & (TURN_ON_WORDS | TURN_OFF_WORDS | OPEN_WORDS | CLOSE_WORDS)
    ):
        return True
    return bool(
        re.search(
            r"\b(включ[её]н|включена|открыт|открыта|закрыт|закрыта)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def find_entity_matches(
    command: NormalizedText,
    ha_objects: list[HaObject],
) -> list[EntityMatch]:
    request_words = set(command.normal_forms)
    requested_domains = detect_requested_domains(command)
    scored_matches = [
        match
        for entity in ha_objects
        if (match := score_entity_match(entity, command, request_words, requested_domains))
        is not None
    ]

    if not scored_matches:
        broad_matches = broad_domain_matches(command, ha_objects, requested_domains)
        if broad_matches:
            return broad_matches
        return []

    best_score = max(match.score for match in scored_matches)
    if best_score >= 100:
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

    return [match for match in scored_matches if match.score == best_score]


def score_entity_match(
    entity: HaObject,
    command: NormalizedText,
    request_words: set[str],
    requested_domains: set[str],
) -> EntityMatch | None:
    entity_domain = entity.entity_id.split(".", maxsplit=1)[0]
    phrases = entity_phrases(entity)

    for phrase in phrases:
        if phrase and phrase in command.normalized_text:
            return EntityMatch(entity=entity, score=100 + len(phrase.split()))

    if requested_domains and entity_domain not in requested_domains:
        return None

    phrase_scores = [
        score_phrase_words(phrase_words, request_words, entity_domain)
        for phrase_words in entity_phrase_word_sets(entity)
    ]
    phrase_scores = [score for score in phrase_scores if score is not None]
    if requested_domains and phrase_scores:
        return EntityMatch(entity=entity, score=max(phrase_scores))

    entity_words = entity_search_words(entity)
    specific_words = entity_words - generic_entity_words(entity_domain)
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
    if not matched_specific_words:
        return None

    unmatched_specific_words = specific_words - request_words
    return 50 + (10 * len(matched_specific_words)) - len(unmatched_specific_words)


def broad_domain_matches(
    command: NormalizedText,
    ha_objects: list[HaObject],
    requested_domains: set[str],
) -> list[EntityMatch]:
    if not requested_domains:
        return []

    request_words = set(command.normal_forms)
    domain_generic_words = set(GENERIC_WORDS)
    for domain in requested_domains:
        domain_generic_words.update(DOMAIN_WORDS.get(domain, set()))

    if request_words - domain_generic_words:
        return []

    return [
        EntityMatch(entity=entity, score=30)
        for entity in ha_objects
        if entity.entity_id.split(".", maxsplit=1)[0] in requested_domains
    ]


def detect_requested_domains(command: NormalizedText) -> set[str]:
    request_words = set(command.normal_forms)
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
    raw_phrases = [entity.name, *split_aliases(entity.aliases)]
    phrases: list[str] = []
    for phrase in raw_phrases:
        normalized = normalize(phrase).normalized_text.strip()
        if normalized and not normalized.startswith("computednametype"):
            phrases.append(normalized)
    return phrases


def split_aliases(aliases: str) -> list[str]:
    return [
        alias.strip()
        for alias in aliases.replace(",", "/").split("/")
        if alias.strip() and not alias.strip().startswith("ComputedNameType.")
    ]


def entity_search_words(entity: HaObject) -> set[str]:
    words = set(normalize(entity.name).normal_forms)
    for alias in split_aliases(entity.aliases):
        words.update(normalize(alias).normal_forms)
    return {word for word in words if word and word not in GENERIC_WORDS}


def entity_phrase_word_sets(entity: HaObject) -> list[set[str]]:
    return [
        set(normalize(phrase).normal_forms)
        for phrase in [entity.name, *split_aliases(entity.aliases)]
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
) -> dict[str, Any] | None:
    domain = entity.entity_id.split(".", maxsplit=1)[0]
    service = service_for_action(domain, action)
    if service is None:
        return None

    service_data: dict[str, Any] = {"entity_id": entity.entity_id}
    if domain == "light" and service == "turn_on" and brightness_pct is not None:
        service_data["brightness_pct"] = brightness_pct

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

    return None


def parse_brightness_percent(text: str) -> int | None:
    match = re.search(r"\b(?:на\s+)?(\d{1,3})\s*%|\bна\s+(\d{1,3})\s+процент", text, re.I)
    if match is None:
        return None

    value = int(next(group for group in match.groups() if group is not None))
    return max(1, min(value, 100))


def parse_timing(text: str) -> ParsedTiming:
    delay_seconds = parse_seconds_after_marker(text, "через")
    duration_seconds = parse_duration_seconds(text)
    return ParsedTiming(delay_seconds=delay_seconds, duration_seconds=duration_seconds)


def parse_seconds_after_marker(text: str, marker: str) -> int | None:
    pattern = rf"\b{marker}\s+((?:пол)?\s*\d*|пол)?\s*(минут[уы]?|час(?:а|ов)?|полчаса)\b"
    match = re.search(pattern, text, re.I)
    if match is None:
        return None
    return duration_to_seconds(match.group(1), match.group(2))


def parse_duration_seconds(text: str) -> int | None:
    if re.search(r"\bчерез\b", text, re.I):
        text = re.sub(r"\bчерез\b.*", "", text, flags=re.I)

    match = re.search(r"\bна\s+(полчаса|\d+\s+минут[уы]?|\d+\s+час(?:а|ов)?)\b", text, re.I)
    if match is None:
        return None

    duration = match.group(1)
    duration_match = re.match(r"(\d+)?\s*(минут[уы]?|час(?:а|ов)?|полчаса)", duration, re.I)
    if duration_match is None:
        return None
    return duration_to_seconds(duration_match.group(1), duration_match.group(2))


def duration_to_seconds(amount_text: str | None, unit: str) -> int:
    unit = unit.lower()
    if unit == "полчаса" or (amount_text and amount_text.strip().lower() == "пол"):
        return 30 * 60

    amount = int(amount_text.strip()) if amount_text and amount_text.strip().isdigit() else 1
    if unit.startswith("час"):
        return amount * 60 * 60
    return amount * 60


def build_state_answer(entity: HaObject) -> str:
    domain = entity.entity_id.split(".", maxsplit=1)[0]
    name = entity.name
    state = entity.state

    if domain == "binary_sensor":
        if state == "on":
            return f"{name}: открыто"
        if state == "off":
            return f"{name}: закрыто"

    if state in {"on", "off"}:
        return f"{name}: {'включено' if state == 'on' else 'выключено'}"

    if state in {"open", "closed"}:
        return f"{name}: {'открыто' if state == 'open' else 'закрыто'}"

    if domain == "sensor" and looks_like_percent_sensor(entity):
        return f"{name}: {state}%"

    return f"{name}: {state}"


def looks_like_percent_sensor(entity: HaObject) -> bool:
    words = entity_search_words(entity)
    return bool(words & {"потеря", "пакет", "пакетов", "процент", "процентов"})
