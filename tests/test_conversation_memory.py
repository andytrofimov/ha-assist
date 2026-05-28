from ha_assist_core.conversation_memory import (
    MAX_HISTORY_MESSAGES,
    build_llm_messages,
    clear_memory,
    get_previous_exchange,
    remember_exchange,
)


def test_llm_messages_include_conversation_history() -> None:
    clear_memory()
    remember_exchange("conversation-1", "расскажи про луну", "Луна - спутник Земли.")

    messages = build_llm_messages("conversation-1", "а какой у нее размер?")

    assert messages == [
        {
            "role": "user",
            "content": "расскажи про луну",
        },
        {
            "role": "assistant",
            "content": "Луна - спутник Земли.",
        },
        {
            "role": "user",
            "content": "а какой у нее размер?",
        },
    ]


def test_conversation_histories_do_not_mix() -> None:
    clear_memory()
    remember_exchange("conversation-1", "первый вопрос", "первый ответ")
    remember_exchange("conversation-2", "второй вопрос", "второй ответ")

    messages = build_llm_messages("conversation-1", "уточнение")

    assert messages == [
        {
            "role": "user",
            "content": "первый вопрос",
        },
        {
            "role": "assistant",
            "content": "первый ответ",
        },
        {
            "role": "user",
            "content": "уточнение",
        },
    ]


def test_default_conversation_history_is_shared_for_missing_ids() -> None:
    clear_memory()
    remember_exchange(None, "первый вопрос", "первый ответ")

    messages = build_llm_messages(None, "уточнение")

    assert messages == [
        {
            "role": "user",
            "content": "первый вопрос",
        },
        {
            "role": "assistant",
            "content": "первый ответ",
        },
        {
            "role": "user",
            "content": "уточнение",
        },
    ]


def test_previous_exchange_returns_last_user_and_assistant_messages() -> None:
    clear_memory()
    remember_exchange("conversation-1", "первый вопрос", "первый ответ")
    remember_exchange("conversation-1", "второй вопрос", "второй ответ")

    messages = get_previous_exchange("conversation-1")

    assert messages == [
        {
            "role": "user",
            "content": "второй вопрос",
        },
        {
            "role": "assistant",
            "content": "второй ответ",
        },
    ]


def test_conversation_history_is_capped() -> None:
    clear_memory()
    for index in range(10):
        remember_exchange("conversation-1", f"вопрос {index}", f"ответ {index}")

    messages = build_llm_messages("conversation-1", "новый вопрос")

    assert len(messages) == MAX_HISTORY_MESSAGES + 1
    assert messages[0] == {
        "role": "user",
        "content": "вопрос 4",
    }
    assert messages[-1] == {
        "role": "user",
        "content": "новый вопрос",
    }
