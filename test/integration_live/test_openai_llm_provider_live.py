from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import pytest

from src.utils.env import load_env_file
from src.utils.llm import LLMResult, LLMUsage, OpenAIProvider


load_env_file()


OPENAI_SKIP_REASON = "Set OPENAI_API_KEY to run live OpenAI provider tests."
REQUIRED_MODEL = "gpt-5-nano"
ARTIFACT_DIR = Path("test_artifacts/llm")
PDF_SOURCE_ROOT = Path("resources/datasets/arxiv_papers")


def _serialize_usage(usage: LLMUsage) -> dict:
    return {
        "provider": usage.provider,
        "model": usage.model,
        "mode": usage.mode,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost": usage.cost,
        "metadata": usage.metadata,
    }


def _serialize_result(result: LLMResult) -> dict:
    return {
        "content": result.content,
        "usage": _serialize_usage(result.usage),
    }


def _write_artifact(prefix: str, payload: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = ARTIFACT_DIR / f"{prefix}_{timestamp}_{uuid4().hex[:8]}.json"
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return file_path

CHALLENGE_DOMAINS = [
    "biomedical literature review",
    "clinical decision support",
    "legal document analysis",
    "materials science discovery",
    "climate science modeling",
    "education technology research",
    "cybersecurity threat intelligence",
    "financial risk assessment",
    "social science survey analysis",
    "robotics planning and control",
]


def _assert_reasonable_text(text: str) -> None:
    lowered = text.strip().lower()
    assert lowered, "Response text is empty"
    disallowed = [
        "i can't access",
        "i cannot access",
        "i can’t access",
        "unable to access",
        "cannot access",
    ]
    assert not any(fragment in lowered for fragment in disallowed), f"Response indicates access failure: {text!r}"


def _gather_pdf_samples(limit: int) -> list[Path]:
    pdf_paths: list[Path] = []
    for path in sorted(PDF_SOURCE_ROOT.rglob("*.pdf")):
        if path.stat().st_size <= 10 * 1024 * 1024:  # OpenAI file upload limit
            pdf_paths.append(path)
        if len(pdf_paths) >= limit:
            break
    if len(pdf_paths) < limit:
        raise AssertionError(
            f"Expected at least {limit} PDFs under {PDF_SOURCE_ROOT} smaller than 10MB, found {len(pdf_paths)}"
        )
    return pdf_paths


def _build_prompt_list() -> list[str]:
    return [
        f"List three current challenges when applying large language models to {domain}."
        for domain in CHALLENGE_DOMAINS
    ]


def _messages_from_prompts(prompts: Iterable[str]) -> list[list[dict[str, str]]]:
    return [[{"role": "user", "content": prompt}] for prompt in prompts]


@pytest.fixture()
def openai_provider() -> OpenAIProvider:
    return OpenAIProvider()


def _ensure_api_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


@pytest.mark.skipif(not _ensure_api_key(), reason=OPENAI_SKIP_REASON)
def test_openai_chat_sync_10_samples(openai_provider: OpenAIProvider) -> None:
    prompts = _build_prompt_list()
    results: list[LLMResult] = []
    for idx, prompt in enumerate(prompts):
        result = openai_provider.chat(REQUIRED_MODEL, prompt)
        _assert_reasonable_text(result.content)
        assert result.usage.input_tokens > 0
        assert result.usage.mode == "sync"
        results.append(result)

    artifact = {
        "mode": "sync",
        "model": REQUIRED_MODEL,
        "prompts": prompts,
        "results": [_serialize_result(res) for res in results],
    }
    _write_artifact("chat_sync_openai", artifact)


@pytest.mark.skipif(not _ensure_api_key(), reason=OPENAI_SKIP_REASON)
def test_openai_chat_batch_10_samples(openai_provider: OpenAIProvider) -> None:
    prompts = _build_prompt_list()
    results = openai_provider.chat_batch(REQUIRED_MODEL, prompts)
    assert len(results) == 10
    for idx, result in enumerate(results):
        assert isinstance(result, LLMResult)
        _assert_reasonable_text(result.content)
        assert result.usage.input_tokens > 0
        assert result.usage.output_tokens >= 0
        assert result.usage.mode == "batch"

    artifact = {
        "mode": "batch",
        "model": REQUIRED_MODEL,
        "prompts": prompts,
        "results": [_serialize_result(res) for res in results],
    }
    _write_artifact("chat_batch_openai", artifact)


@pytest.mark.skipif(not _ensure_api_key(), reason=OPENAI_SKIP_REASON)
def test_openai_chat_async_10_samples(openai_provider: OpenAIProvider) -> None:
    prompts = _build_prompt_list()
    message_batches = _messages_from_prompts(prompts)
    results = asyncio.run(openai_provider.chat_async(REQUIRED_MODEL, message_batches, concurrency=3))
    assert len(results) == 10
    for result in results:
        _assert_reasonable_text(result.content)
        assert result.usage.input_tokens > 0
        assert result.usage.mode == "async"

    artifact = {
        "mode": "async",
        "model": REQUIRED_MODEL,
        "prompts": prompts,
        "results": [_serialize_result(res) for res in results],
    }
    _write_artifact("chat_async_openai", artifact)


@pytest.mark.skipif(not _ensure_api_key(), reason=OPENAI_SKIP_REASON)
def test_openai_pdf_reading_10_samples(openai_provider: OpenAIProvider) -> None:
    instructions = "Summarize the attached research snippet in one sentence."
    pdf_paths = _gather_pdf_samples(10)

    results = openai_provider.read_pdf_batch(
        REQUIRED_MODEL,
        pdf_paths,
        instructions=instructions,
        metadata={"sample_set": "arxiv"},
    )

    assert len(results) == 10
    for idx, result in enumerate(results):
        _assert_reasonable_text(result.content)
        assert result.usage.input_tokens > 0
        assert result.usage.mode == "pdf"
        assert result.usage.metadata.get("batch_index") == idx

    pdf_records = [record for record in openai_provider.usage_tracker.records if record.mode == "pdf"]
    assert len(pdf_records) >= 10

    artifact = {
        "model": REQUIRED_MODEL,
        "instructions": instructions,
        "pdf_samples": [str(path) for path in pdf_paths],
        "results": [_serialize_result(res) for res in results],
    }
    _write_artifact("pdf_read_openai", artifact)
