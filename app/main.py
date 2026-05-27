import logging

from fastapi import FastAPI

from app.api_models import AssistRequest, AssistResponse
from app.assistant_logic import build_assist_result
from app.ha_parser import HaObject

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/assist")
async def process_assist_request(request: AssistRequest) -> AssistResponse:
    logger.info("Assist request text: %s", request.text)

    ha_objects = [
        HaObject(
            entity_id=entity.entity_id,
            name=entity.name,
            state=entity.state,
            aliases=entity.aliases,
        )
        for entity in request.entities
    ]
    result = build_assist_result(request.text, ha_objects)
    response = AssistResponse(
        response=result.response,
        service_calls=result.service_calls,
    )
    logger.info(
        "Assist response: %s; service_calls=%s",
        response.response,
        response.service_calls,
    )
    return response
