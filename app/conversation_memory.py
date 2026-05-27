from collections import defaultdict

from app.llm_client import ChatMessage

# Храним только последние реплики, чтобы контекст не рос бесконечно.
MAX_HISTORY_MESSAGES = 12
DEFAULT_CONVERSATION_ID = "__default__"

_history_by_conversation: dict[str, list[ChatMessage]] = defaultdict(list)


def build_llm_messages(
    conversation_id: str | None,
    user_text: str,
) -> list[ChatMessage]:
    conversation_key = conversation_id or DEFAULT_CONVERSATION_ID
    return [
        *_history_by_conversation[conversation_key],
        {
            "role": "user",
            "content": user_text,
        },
    ]


def remember_exchange(
    conversation_id: str | None,
    user_text: str,
    assistant_text: str,
) -> None:
    conversation_key = conversation_id or DEFAULT_CONVERSATION_ID
    history = _history_by_conversation[conversation_key]
    history.extend(
        [
            {
                "role": "user",
                "content": user_text,
            },
            {
                "role": "assistant",
                "content": assistant_text,
            },
        ],
    )
    del history[:-MAX_HISTORY_MESSAGES]


def clear_memory() -> None:
    _history_by_conversation.clear()
