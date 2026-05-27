import re

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
NUMBER_WORD_PATTERN = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
NUMBER_PATTERN = rf"\d{{1,4}}|(?:{NUMBER_WORD_PATTERN})(?:\s+(?:{NUMBER_WORD_PATTERN})){{0,3}}"
TIME_UNIT_PATTERN = r"минут[ауы]?|час(?:а|ов)?"
PERCENT_UNIT_PATTERN = r"%|процент(?:а|ов)?"
TEMPERATURE_UNIT_PATTERN = r"°|градус(?:а|ов)?"


def parse_russian_number(text: str) -> int | None:
    text = text.strip().lower()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    words = re.findall(r"[а-яё]+", text)
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


def parse_brightness_percent(text: str) -> int | None:
    value = parse_number_before_unit(text, PERCENT_UNIT_PATTERN)
    if value is None:
        return None
    return max(1, min(value, 100))


def parse_temperature(text: str) -> int | None:
    return parse_number_before_unit(text, TEMPERATURE_UNIT_PATTERN)


def parse_delay_seconds(text: str, marker: str = "через") -> int | None:
    pattern = rf"\b{marker}\s+(?P<duration>полчаса|(?P<number>{NUMBER_PATTERN})\s+(?P<unit>{TIME_UNIT_PATTERN}))\b"
    match = re.search(pattern, text, re.I)
    if match is None:
        return None
    return duration_match_to_seconds(match)


def parse_duration_seconds(text: str) -> int | None:
    if re.search(r"\bчерез\b", text, re.I):
        text = re.sub(r"\bчерез\b.*", "", text, flags=re.I)

    pattern = rf"\bна\s+(?P<duration>полчаса|(?P<number>{NUMBER_PATTERN})\s+(?P<unit>{TIME_UNIT_PATTERN}))\b"
    match = re.search(pattern, text, re.I)
    if match is None:
        return None
    return duration_match_to_seconds(match)


def parse_number_before_unit(text: str, unit_pattern: str) -> int | None:
    pattern = rf"\b(?P<number>{NUMBER_PATTERN})\s*(?:{unit_pattern})(?=$|\s|[,.!?])"
    match = re.search(pattern, text, re.I)
    if match is None:
        return None
    return parse_russian_number(match.group("number"))


def duration_match_to_seconds(match: re.Match[str]) -> int | None:
    duration = match.group("duration").lower()
    if duration == "полчаса":
        return 30 * 60

    amount_text = match.group("number")
    unit = match.group("unit")
    amount = parse_russian_number(amount_text)
    if amount is None:
        return None
    return duration_to_seconds(amount, unit)


def duration_to_seconds(amount: int, unit: str) -> int:
    unit = unit.lower()
    if unit.startswith("час"):
        return amount * 60 * 60
    return amount * 60
