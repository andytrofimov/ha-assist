import logging
import time

from fastapi import FastAPI, HTTPException

from api_models import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseMessage,
    ChatCompletionUsage,
    ChatMessage,
)
from assistant_logic import build_assistant_response
from ha_parser import parse_ha_objects
from text_normalizer import get_text_normalizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


def requested_tool_names(request: ChatCompletionRequest) -> set[str]:
    names: set[str] = set()
    for tool in request.tools or []:
        function = tool.get("function")
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            names.add(function["name"])
    return names


def get_last_user_message(messages: list[ChatMessage]) -> ChatMessage | None:
    return next(
        (
            message
            for message in reversed(messages)
            if message.role == "user" and message.content
        ),
        None,
    )


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.post("/v1/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    logger.info(
        "Incoming chat completion request: %s",
        request.model_dump_json(),
    )

    user_message = get_last_user_message(request.messages)
    if user_message is None:
        raise HTTPException(status_code=400, detail="No user message found")

    user_text = user_message.content or ""
    normalized_request = get_text_normalizer().normalize(user_text)
    assistant_response = build_assistant_response(
        normalized_request=normalized_request,
        ha_objects=parse_ha_objects(request.messages),
        can_execute_services="execute_services" in requested_tool_names(request),
    )
    prompt_tokens = len(user_text.split())
    completion_tokens = len((assistant_response.content or "").split())

    return ChatCompletionResponse(
        id="chatcmpl-debug-natasha",
        created=int(time.time()),
        model=request.model,
        choices=[
            ChatCompletionChoice(
                message=ChatCompletionResponseMessage(
                    content=assistant_response.content,
                    tool_calls=assistant_response.tool_calls,
                ),
                finish_reason=assistant_response.finish_reason,
            ),
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
