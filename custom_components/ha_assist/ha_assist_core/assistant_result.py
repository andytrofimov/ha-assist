import random
from typing import Any

from pydantic import BaseModel, Field


class AssistLogicResult(BaseModel):
    response: str = ""
    service_calls: list[dict[str, Any]] = Field(default_factory=list)
    fallback_to_llm: bool = False


class ResponseText:
    OK_RESPONSES = ("окей", "готово", "сделано")
    ENTITY_NOT_FOUND = "Не нашла такое устройство"
    ACTION_NOT_FOUND = "Не поняла, что сделать"
    AREA_NOT_FOUND = "Не нашла такую комнату"
    FLOOR_NOT_FOUND = "Не нашла такой этаж"
    AMBIGUOUS_AREA = "В какой комнате?"

    @classmethod
    def ok(cls) -> str:
        return random.choice(cls.OK_RESPONSES)


def llm_fallback_result() -> AssistLogicResult:
    return AssistLogicResult(fallback_to_llm=True)


def strip_trailing_period(text: str) -> str:
    return text.rstrip().removesuffix(".").rstrip()
