import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib import error, request

logger = logging.getLogger(__name__)

DEFAULT_LLM_API_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "chat-latest"
AI_TIMEOUT = 20
AI_MAX_TOKENS = 4000

# Ключ API-сервиса хранится отдельно от кода и игнорируется git.
LLM_API_KEY_FILE = Path(__file__).resolve().parents[3] / "deepseek_api_key.txt"

SYSTEM_PROMPT = """Ты русскоязычный голосовой ассистент женского пола.
Отвечай кратко, буквально парой предложений чтобы TTS не занимал слишком много времени, если только не пользователь попросил об обратном.
Стиль разговорный (обращайся на ты), дружелюбный, не очень формальный.
Если надо пользователь задаст уточняющие вопросы.
Не используй в ответе никакую разметку кроме той, которая требуется в этом промте, ответ потом зачитывается TTS
Ставь ударение с помощью знака + перед гласной в неоднозначных словах (и только в них!) (например, "каменный з+амок")
Каждое предложение начинай на новой строке. Точку в последнем предложении не ставь.
Римские цифры пиши русскими числительными.
Запросы которые приходят к тебе предварительно фильтруются,
и если там команда по управлению умным домом, то она обрабатывается локально, но ты будешь видеть её в истории.
Не управляй умным домом и не выдумывай выполненные действия."""


class ChatMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


def system_message() -> dict[str, str]:
    return {
        "role": "system",
        "content": SYSTEM_PROMPT,
    }


async def generate_llm_response(
        messages: list[ChatMessage],
        api_key: str | None = None,
        api_url: str | None = None,
) -> str | None:
    return await asyncio.to_thread(
        generate_llm_response_sync,
        messages,
        api_key,
        api_url,
    )


def generate_llm_response_sync(
        messages: list[ChatMessage],
        api_key: str | None = None,
        api_url: str | None = None,
) -> str | None:
    api_key = api_key or read_api_key()
    if not api_key:
        logger.info("LLM request skipped: API key file is missing or empty")
        return None

    api_url = normalized_api_url(api_url)
    logger.info("Calling LLM API at %s; messages=%s", api_url, len(messages))
    payload = {
        "model": DEFAULT_LLM_MODEL,
        "messages": [system_message(), *messages],
        # "temperature": 0.7,
        # "max_completion_tokens": AI_MAX_TOKENS,
    }

    try:
        response_data = post_chat_completion(payload, api_key, api_url)
    except (OSError, TimeoutError, error.URLError, error.HTTPError, ValueError):
        logger.exception("LLM request failed")
        return None

    return extract_chat_completion_text(response_data)


def post_chat_completion(
        payload: dict[str, Any],
        api_key: str,
        api_url: str,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url=chat_completions_url(api_url),
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with request.urlopen(http_request, timeout=AI_TIMEOUT) as http_response:
        response_body = http_response.read().decode("utf-8")

    response_data = json.loads(response_body)
    if not isinstance(response_data, dict):
        raise ValueError("LLM response must be a JSON object")
    return response_data


def read_api_key() -> str | None:
    try:
        api_key = LLM_API_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return api_key or None


def normalized_api_url(api_url: str | None) -> str:
    if isinstance(api_url, str) and api_url.strip():
        return api_url.strip().rstrip("/")
    return DEFAULT_LLM_API_URL.rstrip("/")


def chat_completions_url(api_url: str) -> str:
    if api_url.endswith("/chat/completions"):
        return api_url
    return f"{api_url}/chat/completions"


def extract_chat_completion_text(response_data: dict[str, Any]) -> str | None:
    choices = response_data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if not isinstance(content, str):
        return None

    content = content.strip()
    return content or None
