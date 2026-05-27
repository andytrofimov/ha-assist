from ha_assist_core.number_parser import (
    parse_brightness_percent,
    parse_delay_seconds,
    parse_duration_seconds,
    parse_russian_number,
    parse_temperature,
)


def test_parse_russian_number_supports_voice_forms() -> None:
    assert parse_russian_number("ноль") == 0
    assert parse_russian_number("одна") == 1
    assert parse_russian_number("две") == 2
    assert parse_russian_number("пятнадцать") == 15
    assert parse_russian_number("двадцать три") == 23
    assert parse_russian_number("сто один") == 101


def test_parse_brightness_percent_accepts_digits_and_words() -> None:
    assert parse_brightness_percent("включи свет на 15 процентов") == 15
    assert parse_brightness_percent("включи свет на пятнадцать процентов") == 15
    assert parse_brightness_percent("включи свет на ноль процентов") == 1
    assert parse_brightness_percent("включи свет на сто один процент") == 100


def test_parse_delay_seconds_accepts_digits_and_words() -> None:
    assert parse_delay_seconds("выключи свет через 15 минут") == 900
    assert parse_delay_seconds("выключи свет через пятнадцать минут") == 900
    assert parse_delay_seconds("выключи свет через две минуты") == 120
    assert parse_delay_seconds("выключи свет через один час") == 3600


def test_parse_duration_seconds_accepts_digits_and_words() -> None:
    assert parse_duration_seconds("включи свет на 30 минут") == 1800
    assert parse_duration_seconds("включи свет на тридцать минут") == 1800
    assert parse_duration_seconds("включи свет на два часа") == 7200
    assert parse_duration_seconds("включи свет на полчаса") == 1800


def test_parse_temperature_accepts_digits_and_words() -> None:
    assert parse_temperature("поставь кондиционер на 22 градуса") == 22
    assert parse_temperature("поставь кондиционер на двадцать два градуса") == 22
