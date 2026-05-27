import pytest

from app import llm_client


def test_llm_api_key_is_read_from_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key_file = tmp_path / "deepseek_api_key.txt"
    api_key_file.write_text("test-key\n", encoding="utf-8")
    monkeypatch.setattr(llm_client, "AI_API_KEY_FILE", api_key_file)

    assert llm_client.read_api_key() == "test-key"


def test_llm_payload_includes_full_message_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payload = {}

    def fake_post_chat_completion(payload, api_key):
        captured_payload.update(payload)
        assert api_key == "test-key"
        return {
            "choices": [
                {
                    "message": {
                        "content": "ответ",
                    },
                },
            ],
        }

    monkeypatch.setattr(llm_client, "read_api_key", lambda: "test-key")
    monkeypatch.setattr(llm_client, "post_chat_completion", fake_post_chat_completion)

    response = llm_client.generate_llm_response_sync(
        [
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
        ],
    )

    assert response == "ответ"
    assert captured_payload["messages"] == [
        {
            "role": "system",
            "content": llm_client.SYSTEM_PROMPT,
        },
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
