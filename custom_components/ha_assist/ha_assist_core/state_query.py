import re

from .ha_parser import HaObject
from .text_normalizer import NormalizedText, agree_adjective, get_text_normalizer

STATE_ONLY_DOMAINS = {"binary_sensor", "sensor", "todo", "weather"}

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


def is_state_query(command: NormalizedText) -> bool:
    # Вопросы состояния не должны превращаться в сервисные вызовы.
    text = command.original_text.strip().lower()
    words = set(command.normal_forms)

    if text.endswith("?"):
        return True
    if words & {"сколько", "какой", "какая", "какое", "что"}:
        return True
    return bool(
        re.search(
            r"\b(включ[её]н|включена|выключ[её]н|выключена|открыт|открыта|закрыт|закрыта)\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def build_state_answer(
        entity: HaObject,
        command: NormalizedText | None = None,
        normalized_words: set[str] | None = None,
) -> str:
    # Состояния Home Assistant переводим в короткий русский ответ для Assist.
    domain = entity.entity_id.split(".", maxsplit=1)[0]
    state = entity.state
    words = normalized_words or set()

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


def parse_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def temperature_text(value: int) -> str:
    if value < 0:
        return f"минус {abs(value)} {degree_word(value)}"
    return f"{value} {degree_word(value)}"


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
