import pytest
from urllib import error

from ha_assist_core import llm_client


def test_llm_api_key_is_read_from_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key_file = tmp_path / "llm_api_key.txt"
    api_key_file.write_text("test-key\n", encoding="utf-8")
    monkeypatch.setattr(llm_client, "LLM_API_KEY_FILE", api_key_file)

    assert llm_client.read_api_key() == "test-key"


def test_llm_payload_includes_full_message_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_payload = {}

    def fake_post_chat_completion(payload, api_key, api_url):
        captured_payload.update(payload)
        assert api_key == "test-key"
        assert api_url == llm_client.DEFAULT_LLM_API_URL
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
    assert captured_payload["max_completion_tokens"] == llm_client.AI_MAX_TOKENS
    assert "max_tokens" not in captured_payload


def test_llm_api_key_can_be_passed_directly(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_api_key = None

    def fake_post_chat_completion(payload, api_key, api_url):
        nonlocal captured_api_key
        captured_api_key = api_key
        return {
            "choices": [
                {
                    "message": {
                        "content": "ответ",
                    },
                },
            ],
        }

    monkeypatch.setattr(llm_client, "read_api_key", lambda: None)
    monkeypatch.setattr(llm_client, "post_chat_completion", fake_post_chat_completion)

    response = llm_client.generate_llm_response_sync(
        [
            {
                "role": "user",
                "content": "расскажи про луну",
            },
        ],
        api_key="direct-key",
    )

    assert response == "ответ"
    assert captured_api_key == "direct-key"


def test_llm_api_url_can_be_passed_directly(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_api_url = None

    def fake_post_chat_completion(payload, api_key, api_url):
        nonlocal captured_api_url
        captured_api_url = api_url
        return {
            "choices": [
                {
                    "message": {
                        "content": "ответ",
                    },
                },
            ],
        }

    monkeypatch.setattr(llm_client, "post_chat_completion", fake_post_chat_completion)

    response = llm_client.generate_llm_response_sync(
        [
            {
                "role": "user",
                "content": "расскажи про луну",
            },
        ],
        api_key="direct-key",
        api_url="https://llm.example.test/v1/",
    )

    assert response == "ответ"
    assert captured_api_url == "https://llm.example.test/v1"


@pytest.mark.parametrize(
    ("api_url", "expected"),
    [
        (
                "https://llm.example.test/v1",
                "https://llm.example.test/v1/chat/completions",
        ),
        (
                "https://llm.example.test/v1/chat/completions",
                "https://llm.example.test/v1/chat/completions",
        ),
    ],
)
def test_chat_completions_url_accepts_base_or_endpoint(
        api_url: str,
        expected: str,
) -> None:
    assert llm_client.chat_completions_url(api_url) == expected


def test_llm_request_is_skipped_without_api_key(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_post_chat_completion(payload, api_key, api_url):
        raise AssertionError("post_chat_completion should not be called")

    monkeypatch.setattr(llm_client, "read_api_key", lambda: None)
    monkeypatch.setattr(llm_client, "post_chat_completion", fail_post_chat_completion)

    response = llm_client.generate_llm_response_sync(
        [
            {
                "role": "user",
                "content": "расскажи про луну",
            },
        ],
    )

    assert response is None


@pytest.mark.parametrize(
    "response_data",
    [
        {},
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"message": None}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": 42}}]},
    ],
)
def test_extract_chat_completion_text_rejects_malformed_responses(response_data) -> None:
    assert llm_client.extract_chat_completion_text(response_data) is None


def test_llm_network_errors_return_none(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post_chat_completion(payload, api_key, api_url):
        raise error.URLError("network unavailable")

    monkeypatch.setattr(llm_client, "read_api_key", lambda: "test-key")
    monkeypatch.setattr(llm_client, "post_chat_completion", fake_post_chat_completion)

    response = llm_client.generate_llm_response_sync(
        [
            {
                "role": "user",
                "content": "расскажи про луну",
            },
        ],
    )

    assert response is None
