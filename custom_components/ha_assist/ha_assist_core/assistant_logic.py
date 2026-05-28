import logging
import re
from dataclasses import dataclass
from typing import Any

from .assistant_result import (
    AssistLogicResult,
    ResponseText,
    llm_fallback_result,
    strip_trailing_period,
)
from .ha_parser import HaObject
from .llm_client import ChatMessage, generate_llm_response
from . import device_command, location_resolver, state_query
from .number_parser import (
    parse_brightness_percent,
    parse_temperature,
)
from .text_normalizer import NormalizedText, get_text_normalizer

logger = logging.getLogger(__name__)

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
    "добавить",
    "добавь",
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


@dataclass(frozen=True)
class EntityMatch:
    entity: HaObject
    score: int


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
        action = device_command.detect_action(command)
        timing = device_command.parse_timing(command.original_text)
        brightness_pct = parse_brightness_percent(command.original_text)
        target_temperature = parse_temperature(command.original_text)
        requested_domains = detect_requested_domains(command, ha_objects)
        location_context = location_resolver.detect_location_context(
            command=command,
            ha_objects=ha_objects,
            areas=areas or [],
            floors=floors or [],
            source_area_id=source_area_id,
            source_area_name=source_area_name,
            source_floor_id=source_floor_id,
            source_floor_name=source_floor_name,
            generic_words=GENERIC_WORDS,
        )

        bare_activation_result = build_bare_activation_result(
            command=command,
            ha_objects=ha_objects,
            location_context=location_context,
        )
        if bare_activation_result is not None:
            if bare_activation_result.service_calls:
                all_service_calls.extend(bare_activation_result.service_calls)
                found_smart_home_signal = True
                continue
            return bare_activation_result

        todo_matches = find_todo_item_matches(command, ha_objects)
        if todo_matches:
            action = "add_todo"
            matches = todo_matches
        else:
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

        if state_query.is_state_query(command):
            if not matches:
                if not found_smart_home_signal:
                    return llm_fallback_result()
                return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)
            state_answers.extend(
                state_query.build_state_answer(
                    match.entity,
                    command,
                    normalized_words(command),
                )
                for match in matches
            )
            continue

        if action != "add_todo" and device_command.is_invalid_device_command(command):
            if found_smart_home_signal:
                return AssistLogicResult(response=ResponseText.ACTION_NOT_FOUND)
            return llm_fallback_result()

        if action is None and device_command.has_unsupported_action(command):
            return llm_fallback_result()

        if action is None and is_general_question(command):
            return llm_fallback_result()

        if action is None and matches:
            if all(device_command.entity_domain(match.entity) in state_query.STATE_ONLY_DOMAINS for match in matches):
                state_answers.extend(
                    state_query.build_state_answer(
                        match.entity,
                        command,
                        normalized_words(command),
                    )
                    for match in matches
                )
                continue

        if action is None:
            if found_smart_home_signal:
                return AssistLogicResult(response=ResponseText.ACTION_NOT_FOUND)
            return llm_fallback_result()

        if action != "add_todo" and location_resolver.has_unknown_floor(command, ha_objects, floors or [],
                                                                        GENERIC_WORDS):
            return AssistLogicResult(response=ResponseText.FLOOR_NOT_FOUND)
        if action != "add_todo" and location_resolver.has_unknown_location(
                command,
                ha_objects,
                areas or [],
                floors or [],
                GENERIC_WORDS,
        ):
            return AssistLogicResult(response=ResponseText.AREA_NOT_FOUND)

        if not matches:
            return AssistLogicResult(response=ResponseText.ENTITY_NOT_FOUND)

        if location_resolver.is_ambiguous_location(matches, location_context):
            return AssistLogicResult(response=ResponseText.AMBIGUOUS_AREA)

        for match in matches:
            service_call = device_command.build_service_call(
                entity=match.entity,
                action=action,
                brightness_pct=brightness_pct,
                target_temperature=target_temperature,
                todo_item=(
                    device_command.parse_todo_item(
                        command,
                        match.entity,
                        raw_entity_phrases(match.entity),
                    )
                    if action == "add_todo" else None
                ),
                delay_seconds=timing.delay_seconds,
            )
            if service_call is None:
                continue

            all_service_calls.append(service_call)
            reverse_call = device_command.build_reverse_service_call(
                entity=match.entity,
                action=action,
                delay_seconds=timing.duration_seconds,
            )
            if reverse_call is not None:
                all_service_calls.append(reverse_call)

    if all_service_calls:
        return AssistLogicResult(
            response=ResponseText.ok(),
            service_calls=all_service_calls,
        )

    if state_answers:
        return AssistLogicResult(response="; ".join(state_answers))

    return llm_fallback_result()


def build_bare_activation_result(
        command: NormalizedText,
        ha_objects: list[HaObject],
        location_context: location_resolver.LocationContext,
) -> AssistLogicResult | None:
    matches = exact_bare_activation_matches(command, ha_objects, location_context)
    if not matches:
        return None
    if len(matches) > 1:
        return AssistLogicResult(response=ResponseText.AMBIGUOUS_AREA)

    entity = matches[0].entity
    action = device_command.bare_activation_action(entity)
    if action is None:
        return None
    service_call = device_command.build_service_call(
        entity=entity,
        action=action,
        brightness_pct=None,
        target_temperature=None,
        todo_item=None,
        delay_seconds=None,
    )
    if service_call is None:
        return None
    return AssistLogicResult(
        response=ResponseText.ok(),
        service_calls=[service_call],
    )


def exact_bare_activation_matches(
        command: NormalizedText,
        ha_objects: list[HaObject],
        location_context: location_resolver.LocationContext,
) -> list[EntityMatch]:
    request_raw = command.original_text.strip(" .,!?").lower()
    request_normalized = command.normalized_text.strip()
    search_objects = location_resolver.filter_entities_by_location(ha_objects, location_context)
    matches: list[EntityMatch] = []
    for entity in search_objects:
        if not device_command.is_bare_activation_domain(entity):
            continue
        if request_normalized in entity_phrases(entity) or request_raw in raw_entity_phrases(entity):
            matches.append(EntityMatch(entity=entity, score=100))
    return matches


def find_todo_item_matches(command: NormalizedText, ha_objects: list[HaObject]) -> list[EntityMatch]:
    candidates: list[tuple[EntityMatch, bool]] = []
    for entity in ha_objects:
        if device_command.entity_domain(entity) != "todo":
            continue
        for phrase in sorted(raw_entity_phrases(entity), key=len, reverse=True):
            match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", command.original_text, re.I)
            if match is None:
                continue
            item = command.original_text[match.end():].strip(" .,!?")
            candidates.append((EntityMatch(entity=entity, score=100 + len(phrase.split())), bool(item)))
            break

    if not candidates:
        return []
    best_score = max(match.score for match, _ in candidates)
    return [
        match
        for match, has_item in candidates
        if match.score == best_score and has_item
    ]


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
        llm_api_key: str | None = None,
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
    llm_response = await generate_llm_response(messages, api_key=llm_api_key)
    if llm_response is None:
        logger.info("LLM fallback did not return a response")
        return result

    return AssistLogicResult(response=strip_trailing_period(llm_response))


def normalize(text: str) -> NormalizedText:
    return get_text_normalizer().normalize(text)


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


def is_general_question(command: NormalizedText) -> bool:
    return bool(
        set(command.normal_forms)
        & {"почему", "зачем", "кто", "когда", "где", "как", "каков", "какова"}
    )


def find_entity_matches(
        command: NormalizedText,
        ha_objects: list[HaObject],
        location_context: location_resolver.LocationContext | None = None,
) -> list[EntityMatch]:
    request_words = normalized_words(command)
    requested_domains = detect_requested_domains(command, ha_objects)
    search_objects = location_resolver.filter_entities_by_location(ha_objects, location_context)
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
            if location_resolver.entity_in_location(match.entity, location_context)
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

    broad_matches = broad_domain_matches(
        command,
        search_objects,
        requested_domains,
        location_context,
    )
    if broad_matches:
        return broad_matches

    best_score = max(match.score for match in scored_matches)
    if best_score >= 100:
        # При точном совпадении не подтягиваем похожие entity, кроме явных списков через "и".
        allow_related_matches = "и" in command.normal_forms
        if not allow_related_matches:
            return [match for match in scored_matches if match.score == best_score]
        exact_domains = {
            match.entity.entity_id.split(".", maxsplit=1)[0]
            for match in scored_matches
            if match.score >= 100
        }
        return [
            match
            for match in scored_matches
            if match.score == best_score
               or (
                       allow_related_matches
                       and
                       50 <= match.score < 100
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
        score_phrase_words(phrase_words, request_words)
        for phrase_words in entity_phrase_word_sets(entity)
    ]
    climate_metadata_score = score_climate_metadata(entity, request_words, requested_domains)
    if climate_metadata_score is not None:
        phrase_scores.append(climate_metadata_score)
    phrase_scores = [score for score in phrase_scores if score is not None]
    if requested_domains and phrase_scores:
        return EntityMatch(entity=entity, score=max(phrase_scores))

    entity_words = entity_search_words(entity)
    specific_words = entity_words - GENERIC_WORDS
    if entity_domain in state_query.STATE_ONLY_DOMAINS and not requested_domains:
        return None
    if requested_domains and not specific_words and entity_domain in requested_domains:
        return EntityMatch(entity=entity, score=30)

    if not requested_domains and specific_words and specific_words <= request_words:
        return EntityMatch(entity=entity, score=40 + len(specific_words))

    return None


def score_phrase_words(
        phrase_words: set[str],
        request_words: set[str],
) -> int | None:
    specific_words = phrase_words - GENERIC_WORDS
    matched_specific_words = request_words & specific_words
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
        location_context: location_resolver.LocationContext | None = None,
) -> list[EntityMatch]:
    if location_context and location_context.has_location:
        ha_objects = [
            entity
            for entity in ha_objects
            if location_resolver.entity_in_location(entity, location_context)
        ]

    # Широкие команды без комнаты ниже отсекаются как неоднозначные, если есть разные комнаты.
    request_words = normalized_words(command)
    if not requested_domains:
        if not location_resolver.is_all_devices_request(request_words, location_context):
            return []
        return [
            EntityMatch(entity=entity, score=30)
            for entity in ha_objects
            if device_command.is_turnable(entity) and entity.entity_id.split(".", maxsplit=1)[0] != "scene"
        ]

    if location_resolver.is_all_devices_request(request_words, location_context):
        return [
            EntityMatch(entity=entity, score=30)
            for entity in ha_objects
            if device_command.is_turnable(entity) and entity.entity_id.split(".", maxsplit=1)[0] != "scene"
        ]

    if requested_domains == {"light"} and (request_words & location_resolver.ALL_WORDS):
        return [
            EntityMatch(entity=entity, score=30)
            for entity in ha_objects
            if entity.entity_id.split(".", maxsplit=1)[0] == "light"
        ]

    domain_generic_words = set(GENERIC_WORDS)
    domain_generic_words.update(category_words_for_domains(ha_objects, requested_domains))
    domain_generic_words.update(location_resolver.location_words(ha_objects))

    if request_words - domain_generic_words:
        return []

    return [
        EntityMatch(entity=entity, score=30)
        for entity in ha_objects
        if entity.entity_id.split(".", maxsplit=1)[0] in requested_domains
    ]


def detect_requested_domains(command: NormalizedText, ha_objects: list[HaObject]) -> set[str]:
    request_words = normalized_words(command)
    domains: set[str] = set()
    for entity in ha_objects:
        domain = entity.entity_id.split(".", maxsplit=1)[0]
        entity_words = entity_name_alias_words(entity) - GENERIC_WORDS
        if request_words & entity_words:
            domains.add(domain)

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


def entity_name_alias_words(entity: HaObject) -> set[str]:
    words = normalized_words(normalize(entity.name))
    words.update(raw_word_variants(entity.name))
    for alias in split_aliases(entity.aliases):
        words.update(normalized_words(normalize(alias)))
        words.update(raw_word_variants(alias))
    return {word for word in words if word}


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


def category_words_for_domains(ha_objects: list[HaObject], domains: set[str]) -> set[str]:
    word_counts: dict[tuple[str, str], int] = {}
    for entity in ha_objects:
        domain = device_command.entity_domain(entity)
        if domain not in domains:
            continue
        for word in entity_name_alias_words(entity) - GENERIC_WORDS:
            key = (domain, word)
            word_counts[key] = word_counts.get(key, 0) + 1
    return {
        word
        for (domain, word), count in word_counts.items()
        if domain in domains and count > 1
    }
