import re
from dataclasses import dataclass
from typing import Any

from .ha_parser import HaObject
from .number_parser import (
    parse_brightness_percent,
    parse_duration_seconds,
    parse_temperature,
)
from .text_matching import (
    expanded_words,
    normalize,
    normalized_words,
    raw_word_variants,
    split_aliases,
)
from .text_normalizer import NormalizedText

ALL_WORDS = {"весь", "все", "всё", "вся", "всей", "всю"}
ALL_LOCATIONS_WORDS = {"везде", "всюду", "повсюду"}


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


def detect_location_context(
        command: NormalizedText,
        ha_objects: list[HaObject],
        areas: list[Any],
        floors: list[Any],
        source_area_id: str | None,
        source_area_name: str | None,
        source_floor_id: str | None,
        source_floor_name: str | None,
        generic_words: set[str],
) -> LocationContext:
    area_ids = matched_location_ids(command, areas, "area_id", generic_words)
    floor_ids = matched_location_ids(command, floors, "floor_id", generic_words)
    if not area_ids:
        area_ids = matched_location_ids(command, entity_area_entries(ha_objects), "area_id", generic_words)
    if not floor_ids:
        floor_ids = matched_location_ids(command, entity_floor_entries(ha_objects), "floor_id", generic_words)

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
        generic_words: set[str],
) -> set[str]:
    matches: set[str] = set()
    request_words = normalized_words(command)
    for entry in entries:
        entry_id = get_value(entry, id_field)
        if not entry_id:
            continue
        for phrase in location_entry_phrases(entry):
            normalized = normalize(phrase)
            words = normalized_words(normalized) - expanded_words(generic_words)
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
        generic_words: set[str],
) -> bool:
    location_tail_words = prepositional_location_words(command)
    if not location_tail_words:
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
        generic_words=generic_words,
    )
    if context.has_explicit_location:
        return False
    known_location_words = all_location_words(areas, floors) | location_words(ha_objects)
    non_generic_words = location_tail_words - expanded_words(generic_words)
    return bool(non_generic_words - known_location_words)


def prepositional_location_words(command: NormalizedText) -> set[str]:
    matches = re.findall(
        r"\b(?:в|во|на)\s+([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\s-]*)",
        command.original_text,
        re.I,
    )
    words: set[str] = set()
    for match in matches:
        tail = re.split(
            r"\b(?:и|через|потом|после|кроме)\b",
            match,
            maxsplit=1,
            flags=re.I,
        )[0]
        if is_parameter_tail(tail):
            continue
        normalized = normalize(tail)
        words.update(normalized_words(normalized))
        words.update(raw_word_variants(tail))
    return words


def is_parameter_tail(text: str) -> bool:
    tail = text.strip(" .,!?")
    if not tail:
        return False
    normalized_tail = normalize(tail)
    return bool(
        parse_brightness_percent(normalized_tail) is not None
        or parse_temperature(normalized_tail) is not None
        or parse_duration_seconds(normalize(f"на {tail}")) is not None
    )


def has_unknown_floor(
        command: NormalizedText,
        ha_objects: list[HaObject],
        floors: list[Any],
        generic_words: set[str],
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
        generic_words=generic_words,
    )
    if context.explicit_floor:
        return False

    known_floor_words = floor_words(floors) | entity_floor_words(ha_objects)
    non_generic_words = request_words - expanded_words(generic_words)
    entity_words = all_entity_name_alias_words(ha_objects)
    return bool(non_generic_words - entity_words - known_floor_words)


def is_ambiguous_location(matches: list[Any], location_context: LocationContext) -> bool:
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


def is_all_locations_request(request_words: set[str]) -> bool:
    return bool(request_words & ALL_LOCATIONS_WORDS)


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


def all_entity_name_alias_words(ha_objects: list[HaObject]) -> set[str]:
    words: set[str] = set()
    for entity in ha_objects:
        words.update(normalized_words(normalize(entity.name)))
        words.update(raw_word_variants(entity.name))
        for alias in split_aliases(entity.aliases):
            words.update(normalized_words(normalize(alias)))
            words.update(raw_word_variants(alias))
    return {word for word in words if word}
