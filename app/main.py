import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI

from app.api_models import AssistRequest, AssistResponse
from app.assistant_logic import build_assist_result_with_llm
from app.conversation_memory import build_llm_messages, remember_exchange
from app.ha_parser import HaObject

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Последний запрос нужен только для локальной диагностики.
LAST_ASSIST_REQUEST_FILE = Path(__file__).resolve().parent.parent / "last_assist_request.json"

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/assist")
async def process_assist_request(request: AssistRequest) -> AssistResponse:
    logger.info("Assist request text: %s", request.text)
    await asyncio.to_thread(save_assist_request_snapshot, request)
    logger.info("Saved latest assist request snapshot")

    ha_objects = [
        HaObject.model_validate(entity.model_dump())
        for entity in request.entities
    ]
    result = await build_assist_result_with_llm(
        text=request.text,
        ha_objects=ha_objects,
        areas=[area.model_dump() for area in request.areas],
        floors=[floor.model_dump() for floor in request.floors],
        source_area_id=request.source_area_id,
        source_area_name=request.source_area_name,
        source_floor_id=request.source_floor_id,
        source_floor_name=request.source_floor_name,
        llm_messages=build_llm_messages(request.conversation_id, request.text),
    )
    response = AssistResponse(
        response=add_tts_trailing_period(result.response),
        service_calls=result.service_calls,
    )
    remember_exchange(
        conversation_id=request.conversation_id,
        user_text=request.text,
        assistant_text=response.response,
    )
    logger.info(
        "Assist response: %s; service_calls=%s",
        response.response,
        response.service_calls,
    )
    return response


def add_tts_trailing_period(text: str) -> str:
    stripped_text = text.rstrip()
    if not stripped_text or stripped_text.endswith("."):
        return stripped_text
    return f"{stripped_text}."


def save_assist_request_snapshot(request: AssistRequest) -> None:
    LAST_ASSIST_REQUEST_FILE.write_text(
        json.dumps(
            request.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
