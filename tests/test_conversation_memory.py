from ha_assist_core.conversation_memory import (
    build_llm_messages,
    clear_memory,
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
