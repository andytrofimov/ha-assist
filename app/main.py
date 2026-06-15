import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI

from app.api_models import AssistRequest, AssistResponse
from ha_assist_core.assist_processor import process_assist_payload

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

    result = await process_assist_payload(
        text=request.text,
        entities=[entity.model_dump() for entity in request.entities],
        areas=[area.model_dump() for area in request.areas],
        floors=[floor.model_dump() for floor in request.floors],
        conversation_id=request.conversation_id,
        source_area_id=request.source_area_id,
        source_area_name=request.source_area_name,
        source_floor_id=request.source_floor_id,
        source_floor_name=request.source_floor_name,
    )
    response = AssistResponse(
        response=result["response"],
        service_calls=result["service_calls"],
    )
    logger.info(
        "Assist response: %s; service_calls=%s",
        response.response,
        response.service_calls,
    )
    return response


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
