import re

from .text_normalizer import NormalizedText

NUMBER_ONES = {
    "ноль": 0,
    "один": 1,
    "одна": 1,
    "одно": 1,
    "одну": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
}

NUMBER_TEENS = {
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
    "тринадцать": 13,
    "четырнадцать": 14,
    "пятнадцать": 15,
    "шестнадцать": 16,
    "семнадцать": 17,
    "восемнадцать": 18,
    "девятнадцать": 19,
}

NUMBER_TENS = {
    "двадцать": 20,
    "тридцать": 30,
    "сорок": 40,
    "пятьдесят": 50,
    "шестьдесят": 60,
    "семьдесят": 70,
    "восемьдесят": 80,
    "девяносто": 90,
}

NUMBER_HUNDREDS = {
    "сто": 100,
}

NUMBER_WORDS = set(NUMBER_ONES) | set(NUMBER_TEENS) | set(NUMBER_TENS) | set(NUMBER_HUNDREDS)
TIME_UNIT_SECONDS = {
    "секунда": 1,
    "минута": 60,
    "час": 60 * 60,
}
PERCENT_UNITS = {"%", "процент"}
TEMPERATURE_UNITS = {"°", "градус"}


def parse_russian_number(text: str) -> int | None:
    text = text.strip().lower()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    words = re.findall(r"[а-яё]+", text)
    return parse_russian_number_words(words)


def parse_russian_number_words(words: list[str]) -> int | None:
    if not words or any(word not in NUMBER_WORDS for word in words):
        return None
    if "ноль" in words and len(words) > 1:
        return None

    total = 0
    used_hundreds = False
    used_tens = False
    used_ones = False
    for word in words:
        if word in NUMBER_HUNDREDS:
            if total or used_hundreds:
                return None
            total += NUMBER_HUNDREDS[word]
            used_hundreds = True
            continue

        if word in NUMBER_TENS:
            if used_tens or used_ones or total % 100:
                return None
            total += NUMBER_TENS[word]
            used_tens = True
            continue

        if word in NUMBER_TEENS:
            if used_tens or used_ones or total % 100:
                return None
            total += NUMBER_TEENS[word]
            used_tens = True
            continue

        if word in NUMBER_ONES:
            if used_ones or (total % 100 and not used_tens):
                return None
            total += NUMBER_ONES[word]
            used_ones = True
            continue

    return total


def parse_brightness_percent(command: NormalizedText) -> int | None:
    value = parse_number_before_unit(command, PERCENT_UNITS)
    if value is None:
        return None
    return max(1, min(value, 100))


def parse_temperature(command: NormalizedText) -> int | None:
    return parse_number_before_unit(command, TEMPERATURE_UNITS)


def parse_delay_seconds(command: NormalizedText) -> int | None:
    for index, lemma in enumerate(command.normal_forms):
        if lemma != "через":
            continue
        return parse_duration_after_index(command, index + 1)
    return None


def parse_duration_seconds(command: NormalizedText) -> int | None:
    stop_index = next(
        (
            index
            for index, lemma in enumerate(command.normal_forms)
            if lemma == "через"
        ),
        len(command.normal_forms),
    )
    for index, lemma in enumerate(command.normal_forms[:stop_index]):
        if lemma != "на":
            continue
        duration_seconds = parse_duration_after_index(command, index + 1, stop_index=stop_index)
        if duration_seconds is not None:
            return duration_seconds
    return None


def parse_number_before_unit(command: NormalizedText, units: set[str]) -> int | None:
    for index, lemma in enumerate(command.normal_forms):
        if lemma not in units:
            continue
        value = parse_number_ending_at(command, index)
        if value is not None:
            return value
    return None


def parse_duration_after_index(
        command: NormalizedText,
        start_index: int,
        stop_index: int | None = None,
) -> int | None:
    stop_index = len(command.normal_forms) if stop_index is None else stop_index
    if start_index >= stop_index:
        return None
    if command.normal_forms[start_index] == "полчаса":
        return 30 * 60

    for unit_index in range(start_index + 1, stop_index):
        unit = command.normal_forms[unit_index]
        if unit not in TIME_UNIT_SECONDS:
            continue
        amount = parse_number_between(command, start_index, unit_index)
        if amount is None:
            return None
        return amount * TIME_UNIT_SECONDS[unit]
    return None


def parse_number_ending_at(command: NormalizedText, end_index: int) -> int | None:
    if end_index <= 0:
        return None
    previous_token = command.tokens[end_index - 1]
    if previous_token.isdigit():
        return int(previous_token)

    start_index = end_index
    while start_index > 0 and command.normal_forms[start_index - 1] in NUMBER_WORDS:
        start_index -= 1
    return parse_number_between(command, start_index, end_index)


def parse_number_between(command: NormalizedText, start_index: int, end_index: int) -> int | None:
    if start_index >= end_index:
        return None
    if end_index - start_index == 1 and command.tokens[start_index].isdigit():
        return int(command.tokens[start_index])
    words = command.normal_forms[start_index:end_index]
    return parse_russian_number_words(words)
