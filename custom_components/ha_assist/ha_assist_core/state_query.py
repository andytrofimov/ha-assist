from .ha_parser import HaObject
from .text_normalizer import AgreementFeatures, NormalizedText, agree_adjective, get_text_normalizer

STATE_QUESTION_WORDS = {"сколько", "какой", "какая", "какое", "что"}
POWER_ON_WORDS = {"включить"}
POWER_OFF_WORDS = {"выключить"}
OPEN_WORDS = {"открыть"}
CLOSED_WORDS = {"закрыть"}
STATE_WORDS = POWER_ON_WORDS | POWER_OFF_WORDS | OPEN_WORDS | CLOSED_WORDS

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
    words = set(command.normal_forms) | set(command.tokens)

    if text.endswith("?"):
        return True
    if words & STATE_QUESTION_WORDS:
        return True
    return bool(state_predicate_words(command) & STATE_WORDS)


def build_state_answer(
        entity: HaObject,
        command: NormalizedText | None = None,
        normalized_words: set[str] | None = None,
) -> str:
    # Состояния Home Assistant переводим в короткий русский ответ для Assist.
    domain = entity.entity_id.split(".", maxsplit=1)[0]
    state = entity.state
    words = state_predicate_words(command, normalized_words)

    if domain == "binary_sensor":
        is_open = state == "on"
        features = get_text_normalizer().first_word_agreement(entity.name)
        if words & CLOSED_WORDS:
            return yes_no_state_answer(not is_open, features, is_open)
        if words & OPEN_WORDS:
            return yes_no_state_answer(is_open, features, is_open)
        return named_open_closed_state(features, is_open)

    if state in {"on", "off"}:
        is_on = state == "on"
        features = get_text_normalizer().first_word_agreement(entity.name)
        if words & POWER_ON_WORDS:
            return yes_no_power_state_answer(is_on, features, is_on)
        if words & POWER_OFF_WORDS:
            return yes_no_power_state_answer(not is_on, features, is_on)
        return named_power_state(features, is_on)

    if state in {"open", "closed"}:
        is_open = state == "open"
        features = get_text_normalizer().first_word_agreement(entity.name)
        if words & CLOSED_WORDS:
            return yes_no_state_answer(not is_open, features, is_open)
        if words & OPEN_WORDS:
            return yes_no_state_answer(is_open, features, is_open)
        return named_open_closed_state(features, is_open)

    if domain == "sensor" and entity.unit_of_measurement == "%":
        return format_percent_state(state)

    if domain == "sensor" and is_temperature_unit(entity.unit_of_measurement):
        return format_temperature_state(state)

    if domain == "weather":
        return build_weather_answer(entity)

    return state


def state_predicate_words(command: NormalizedText | None, normalized_words: set[str] | None = None) -> set[str]:
    if command is not None:
        return set(command.state_forms)
    return normalized_words or set()


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
        features: AgreementFeatures,
        actual_is_open: bool,
) -> str:
    return f"{'да' if is_expected_state else 'нет'}, {open_closed_state_text(features, actual_is_open)}"


def yes_no_power_state_answer(
        is_expected_state: bool,
        features: AgreementFeatures,
        actual_is_on: bool,
) -> str:
    return f"{'да' if is_expected_state else 'нет'}, {power_state_text(features, actual_is_on)}"


def named_power_state(features: AgreementFeatures, is_on: bool) -> str:
    return f"{features.word} {power_state_text(features, is_on)}"


def power_state_text(features: AgreementFeatures, is_on: bool) -> str:
    if is_on:
        return agree_adjective(features, "включен", "включена", "включено", "включены")
    return agree_adjective(features, "выключен", "выключена", "выключено", "выключены")


def named_open_closed_state(features: AgreementFeatures, is_open: bool) -> str:
    return f"{features.word} {open_closed_state_text(features, is_open)}"


def open_closed_state_text(features: AgreementFeatures, is_open: bool) -> str:
    if is_open:
        return agree_adjective(features, "открыт", "открыта", "открыто", "открыты")
    return agree_adjective(features, "закрыт", "закрыта", "закрыто", "закрыты")
