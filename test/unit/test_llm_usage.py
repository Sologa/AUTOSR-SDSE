from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import pytest

from src.utils.llm import (
    BaseLLMProvider,
    DEFAULT_PRICING,
    LLMResult,
    LLMService,
    LLMUsage,
    LLMUsageTracker,
    ModelPriceRegistry,
    ModelPricing,
)


@dataclass
class _Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class _FakeResponse:
    usage: _Usage
    output_text: str


class _StubProvider(BaseLLMProvider):
    provider_name = "stub"

    def __init__(self, *, response: _FakeResponse, fail_times: int = 0) -> None:
        pricing = ModelPriceRegistry({"stub": {"stub-model": ModelPricing(120.0, 240.0)}})
        super().__init__(pricing=pricing)
        self._response = response
        self._fail_times = fail_times
        self._call_count = 0

    def _chat_request(self, *, model: str, messages: Sequence[dict[str, Any]], **kwargs: Any) -> Any:
        self._call_count += 1
        if self._call_count <= self._fail_times:
            raise RuntimeError("retry me")
        return self._response

    async def _chat_request_async(self, *, model: str, messages: Sequence[dict[str, Any]], **kwargs: Any) -> Any:
        self._call_count += 1
        if self._call_count <= self._fail_times:
            raise RuntimeError("retry async")
        await asyncio.sleep(0)
        return self._response

    def _pdf_request(self, *, model: str, pdf_path: Path, instructions: str, **kwargs: Any) -> Any:
        return self._response

    def _extract_usage(self, response: _FakeResponse) -> tuple[int, int]:
        return response.usage.input_tokens, response.usage.output_tokens

    def _extract_content(self, response: _FakeResponse) -> str:
        return response.output_text

    @property
    def call_count(self) -> int:
        return self._call_count

    # Mark RuntimeError as retryable for testing purposes.
    retryable_exceptions = (RuntimeError,)


@pytest.fixture()
def sample_response() -> _FakeResponse:
    return _FakeResponse(usage=_Usage(input_tokens=100, output_tokens=50), output_text="ok")


def test_chat_records_usage(sample_response: _FakeResponse) -> None:
    provider = _StubProvider(response=sample_response)
    result = provider.chat("stub-model", "hello world")
    assert isinstance(result, LLMResult)
    assert result.usage.input_tokens == 100
    expected_cost = ((100 / 1_000_000) * 120.0) + ((50 / 1_000_000) * 240.0)
    assert pytest.approx(result.usage.cost, rel=1e-6) == expected_cost
    assert provider.usage_tracker.records[0].mode == "sync"


def test_batch_application_of_discount(sample_response: _FakeResponse) -> None:
    provider = _StubProvider(response=sample_response)
    outputs = provider.chat_batch("stub-model", ["msg1", "msg2"])
    assert len(outputs) == 2
    # Discount should halve the computed cost per call.
    expected_cost = (
        ((100 / 1_000_000) * 120.0) + ((50 / 1_000_000) * 240.0)
    ) * provider.batch_discount
    assert all(pytest.approx(out.usage.cost, rel=1e-6) == expected_cost for out in outputs)


def test_async_retry_and_usage(sample_response: _FakeResponse) -> None:
    provider = _StubProvider(response=sample_response, fail_times=1)
    results = asyncio.run(provider.chat_async("stub-model", ["async message"]))
    assert len(results) == 1
    assert provider.call_count == 2  # one failure + one success
    assert provider.usage_tracker.records[0].mode == "async"


def test_read_pdf_requires_existing_file(tmp_path: Path, sample_response: _FakeResponse) -> None:
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%\xff\xff\xff\xff\n")
    provider = _StubProvider(response=sample_response)
    result = provider.read_pdf("stub-model", pdf_file, instructions="Summarize")
    assert isinstance(result, LLMResult)
    assert provider.usage_tracker.records[-1].mode == "pdf"


def test_read_pdf_batch_applies_discount(tmp_path: Path, sample_response: _FakeResponse) -> None:
    pdf_files = []
    for idx in range(2):
        pdf_path = tmp_path / f"sample_{idx}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")
        pdf_files.append(pdf_path)

    provider = _StubProvider(response=sample_response)
    results = provider.read_pdf_batch("stub-model", pdf_files, instructions="Summarize")
    assert len(results) == 2
    expected_cost = (
        ((100 / 1_000_000) * 120.0) + ((50 / 1_000_000) * 240.0)
    ) * provider.batch_discount
    for result in results:
        assert pytest.approx(result.usage.cost, rel=1e-6) == expected_cost
    assert provider.usage_tracker.records[-1].metadata["batch_index"] == 1


def test_usage_tracker_summary(sample_response: _FakeResponse) -> None:
    tracker = LLMUsageTracker()
    usage = LLMUsage(
        provider="stub",
        model="stub-model",
        mode="sync",
        input_tokens=10,
        output_tokens=5,
        cost=0.25,
    )
    tracker.add_record(usage)
    summary = tracker.summarize()
    assert summary[("stub", "stub-model")]["total_input_tokens"] == 10
    assert summary[("stub", "stub-model")]["total_cost"] == 0.25


def test_llm_service_routes_to_provider(sample_response: _FakeResponse) -> None:
    provider = _StubProvider(response=sample_response)
    service = LLMService({"stub": provider})
    result = service.chat("stub", "stub-model", "hello there")
    assert result.content == "ok"
    assert service.usage_tracker.records[0].provider == "stub"


def test_default_pricing_matches_published_tables() -> None:
    pricing_expectations = {
        ("openai", "gpt-5-nano"): (0.05, 0.4),
        ("openai", "gpt-4o"): (2.5, 10.0),
        ("openai", "gpt-4.1-mini"): (0.4, 1.6),
        ("openai", "o1-pro"): (150.0, 600.0),
        ("openai", "o3-deep-research"): (10.0, 40.0),
        ("openai", "o3-mini"): (1.1, 4.4),
        ("anthropic", "claude-sonnet-4"): (3.0, 15.0),
        ("gemini", "gemini-2.5-flash"): (0.30, 2.5),
    }

    for (provider, model), (expected_input, expected_output) in pricing_expectations.items():
        pricing = DEFAULT_PRICING.get(provider, model)
        assert pytest.approx(pricing.input_cost_per_1m, rel=1e-6) == expected_input
        assert pytest.approx(pricing.output_cost_per_1m, rel=1e-6) == expected_output
