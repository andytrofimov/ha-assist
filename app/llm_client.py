import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Literal, TypedDict
from urllib import error, request

logger = logging.getLogger(__name__)

# DeepSeek работает через совместимый с OpenAI адрес API.
AI_BASE_URL = "https://api.deepseek.com"
AI_MODEL = "deepseek-v4-flash"
AI_TIMEOUT = 20
AI_MAX_TOKENS = 300

# Ключ хранится отдельно от кода и игнорируется git.
AI_API_KEY_FILE = Path(__file__).resolve().parent.parent / "deepseek_api_key.txt"

SYSTEM_PROMPT = """Ты русскоязычный голосовой ассистент.
Отвечай кратко, буквально парой предложений чтобы TTS не занимал слишком много времени. Стиль разговорный, не очень формальный.
Если надо пользователь задаст уточняющие вопросы.
Не используй в ответе никакую разметку, ответ потом зачитывается TTS.
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


async def generate_llm_response(messages: list[ChatMessage]) -> str | None:
    return await asyncio.to_thread(generate_llm_response_sync, messages)


def generate_llm_response_sync(messages: list[ChatMessage]) -> str | None:
    api_key = read_api_key()
    if not api_key:
        logger.info("LLM request skipped: DeepSeek API key file is missing or empty")
        return None

    logger.info("Calling DeepSeek LLM; messages=%s", len(messages))
    payload = {
        "model": AI_MODEL,
        "messages": [system_message(), *messages],
        "temperature": 0.7,
        "max_tokens": AI_MAX_TOKENS,
    }

    try:
        response_data = post_chat_completion(payload, api_key)
    except (OSError, TimeoutError, error.URLError, error.HTTPError, ValueError):
        logger.exception("DeepSeek LLM request failed")
        return None

    return extract_chat_completion_text(response_data)


def post_chat_completion(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url=f"{AI_BASE_URL}/chat/completions",
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
        api_key = AI_API_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return api_key or None


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
