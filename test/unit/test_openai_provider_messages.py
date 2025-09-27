from __future__ import annotations

from src.utils.llm import OpenAIProvider


class _StubResponses:
    def create(self, *args, **kwargs):  # pragma: no cover - sanity stub
        raise RuntimeError("responses.create should not be called in this test")


class _StubFiles:
    def create(self, *args, **kwargs):  # pragma: no cover - sanity stub
        raise RuntimeError("files.create should not be called in this test")

    def delete(self, *args, **kwargs):  # pragma: no cover - sanity stub
        raise RuntimeError("files.delete should not be called in this test")


class _StubAsyncResponses:
    async def create(self, *args, **kwargs):  # pragma: no cover - sanity stub
        raise RuntimeError("async responses.create should not be called in this test")


class _StubClient:
    def __init__(self) -> None:
        self.responses = _StubResponses()
        self.files = _StubFiles()


class _StubAsyncClient:
    def __init__(self) -> None:
        self.responses = _StubAsyncResponses()


def _make_provider() -> OpenAIProvider:
    return OpenAIProvider(client=_StubClient(), async_client=_StubAsyncClient())


def test_normalize_assistant_history_uses_input_text() -> None:
    provider = _make_provider()
    history = [
        {"role": "system", "content": "stay concise"},
        {"role": "assistant", "content": "Of course."},
        {"role": "user", "content": "Next question?"},
    ]

    normalized = provider._normalize_messages(history)

    assert normalized[1]["role"] == "assistant"
    assert normalized[1]["content"][0]["type"] == "input_text"
    assert normalized[1]["content"][0]["text"] == "Of course."


def test_prepare_messages_promotes_string_to_message() -> None:
    provider = _make_provider()

    prepared = provider._prepare_messages("hello there")

    assert prepared == [{"role": "user", "content": "hello there"}]


def test_build_chat_kwargs_preserves_max_output_tokens() -> None:
    provider = _make_provider()

    kwargs = provider._build_chat_kwargs("gpt-5-nano", {"max_output_tokens": 256})

    assert kwargs["max_output_tokens"] == 256
    assert "max_tokens" not in kwargs


def test_build_chat_kwargs_promotes_legacy_max_tokens() -> None:
    provider = _make_provider()

    kwargs = provider._build_chat_kwargs("gpt-4.1-mini", {"max_tokens": 512})

    assert kwargs["max_output_tokens"] == 512
    assert "max_tokens" not in kwargs


def test_temperature_removed_for_reasoning_models() -> None:
    provider = _make_provider()

    kwargs = provider._build_chat_kwargs("gpt-5-nano", {"temperature": 0.2})

    assert "temperature" not in kwargs


def test_temperature_retained_for_non_reasoning_models() -> None:
    provider = _make_provider()

    kwargs = provider._build_chat_kwargs("gpt-4.1-mini", {"temperature": 0.7})

    assert kwargs["temperature"] == 0.7


def test_exact_reasoning_model_id_blocks_temperature() -> None:
    provider = _make_provider()

    kwargs = provider._build_chat_kwargs("gpt-5", {"temperature": 0.1})

    assert "temperature" not in kwargs


def test_reasoning_prefixes_disable_temperature() -> None:
    provider = _make_provider()

    kwargs = provider._build_chat_kwargs("o1-preview-2024-12-17", {"temperature": 0.3})

    assert "temperature" not in kwargs
