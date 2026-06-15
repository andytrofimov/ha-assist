import asyncio
import threading
from typing import Any

import pytest

from ha_assist_core import assistant_logic
from ha_assist_core.assistant_result import AssistLogicResult


def test_async_assist_result_builds_sync_logic_outside_event_loop(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_loop_thread_id = threading.get_ident()
    build_thread_id = None

    def fake_build_assist_result(*args: Any, **kwargs: Any) -> AssistLogicResult:
        nonlocal build_thread_id
        build_thread_id = threading.get_ident()
        return AssistLogicResult(response="готово")

    monkeypatch.setattr(
        assistant_logic,
        "build_assist_result",
        fake_build_assist_result,
    )

    result = asyncio.run(
        assistant_logic.build_assist_result_with_llm(
            text="включи свет",
            ha_objects=[],
        ),
    )

    assert result.response == "готово"
    assert build_thread_id is not None
    assert build_thread_id != event_loop_thread_id
