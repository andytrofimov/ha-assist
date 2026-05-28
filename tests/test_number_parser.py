import pytest

from ha_assist_core.number_parser import (
    parse_brightness_percent,
    parse_delay_seconds,
    parse_duration_seconds,
    parse_russian_number,
    parse_temperature,
)
from ha_assist_core.text_matching import normalize


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ноль", 0),
        ("одна", 1),
        ("две", 2),
        ("пятнадцать", 15),
        ("двадцать три", 23),
        ("сто один", 101),
    ],
)
def test_parse_russian_number_supports_voice_forms(text: str, expected: int) -> None:
    assert parse_russian_number(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("включи свет на 15 процентов", 15),
        ("включи свет на пятнадцать процентов", 15),
        ("включи свет на ноль процентов", 1),
        ("включи свет на сто один процент", 100),
    ],
)
def test_parse_brightness_percent_accepts_digits_and_words(text: str, expected: int) -> None:
    assert parse_brightness_percent(normalize(text)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("выключи свет через 15 минут", 900),
        ("выключи свет через пятнадцать минут", 900),
        ("выключи свет через две минуты", 120),
        ("выключи свет через десять секунд", 10),
        ("выключи свет через один час", 3600),
    ],
)
def test_parse_delay_seconds_accepts_digits_and_words(text: str, expected: int) -> None:
    assert parse_delay_seconds(normalize(text)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("включи свет на 30 минут", 1800),
        ("включи свет на тридцать минут", 1800),
        ("включи свет на десять секунд", 10),
        ("включи свет на два часа", 7200),
        ("включи свет на полчаса", 1800),
    ],
)
def test_parse_duration_seconds_accepts_digits_and_words(text: str, expected: int) -> None:
    assert parse_duration_seconds(normalize(text)) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("поставь кондиционер на 22 градуса", 22),
        ("поставь кондиционер на двадцать два градуса", 22),
    ],
)
def test_parse_temperature_accepts_digits_and_words(text: str, expected: int) -> None:
    assert parse_temperature(normalize(text)) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "ноль один",
        "один два",
        "двадцать десять",
        "сто сто",
        "пять попугаев",
    ],
)
def test_parse_russian_number_rejects_invalid_phrases(text: str) -> None:
    assert parse_russian_number(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "включи свет на процентов",
        "выключи свет через минут",
        "поставь кондиционер на градусов",
    ],
)
def test_number_parsers_reject_missing_values(text: str) -> None:
    command = normalize(text)

    assert parse_brightness_percent(command) is None
    assert parse_delay_seconds(command) is None
    assert parse_temperature(command) is None


def test_normalized_text_keeps_digits_for_number_parsing() -> None:
    command = normalize("включи свет через 15 секунд")

    assert "15" in command.tokens
    assert parse_delay_seconds(command) == 15
