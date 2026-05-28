from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .assistant_result import AssistLogicResult, ResponseText
from .llm_client import ChatMessage
from .text_normalizer import NormalizedText, normalize

BUG_REPORT_TODO_ENTITY_ID = "todo.spisok_dorabotok"


@dataclass(frozen=True)
class CustomIntent:
    name: str
    phrases: tuple[str, ...]
    handler: Callable[[NormalizedText, list[ChatMessage]], AssistLogicResult]

    @property
    def normalized_phrases(self) -> set[str]:
        return {normalize(phrase).normalized_text.strip() for phrase in self.phrases}


def handle_custom_intent(
        command: NormalizedText,
        previous_exchange: list[ChatMessage] | None = None,
) -> AssistLogicResult | None:
    request_normalized = command.normalized_text.strip()
    for intent in CUSTOM_INTENTS:
        if request_normalized in intent.normalized_phrases:
            return intent.handler(command, previous_exchange or [])
    return None


def handle_time_query(
        command: NormalizedText,
        previous_exchange: list[ChatMessage],
) -> AssistLogicResult:
    return AssistLogicResult(response=f"Сейчас {datetime.now().strftime('%H:%M')}")


def handle_bug_report(
        command: NormalizedText,
        previous_exchange: list[ChatMessage],
) -> AssistLogicResult:
    previous_user_text = ""
    previous_assistant_text = ""
    for message in previous_exchange:
        if message["role"] == "user":
            previous_user_text = message["content"]
        if message["role"] == "assistant":
            previous_assistant_text = message["content"]

    if not previous_user_text and not previous_assistant_text:
        return AssistLogicResult(response="Не нашла предыдущий запрос")

    item = " ".join(
        part
        for part in (
            f"Запрос: {previous_user_text}" if previous_user_text else "",
            f"Ответ: {previous_assistant_text}" if previous_assistant_text else "",
        )
        if part
    )
    return AssistLogicResult(
        response=ResponseText.ok(),
        service_calls=[
            {
                "domain": "todo",
                "service": "add_item",
                "service_data": {
                    "entity_id": BUG_REPORT_TODO_ENTITY_ID,
                    "item": item,
                },
            },
        ],
    )


CUSTOM_INTENTS = (
    CustomIntent(
        name="time_query",
        phrases=(
            "сколько времени",
            "сколько сейчас времени",
            "который час",
            "подскажи время",
            "скажи время",
        ),
        handler=handle_time_query,
    ),
    CustomIntent(
        name="bug_report",
        phrases=(
            "это была ошибка",
            "это был баг",
        ),
        handler=handle_bug_report,
    ),
)
