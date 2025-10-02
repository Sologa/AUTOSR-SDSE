from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from src.utils.env import load_env_file
from src.utils.llm import LLMResult, OpenAIProvider


def _require_api_key() -> str:
    load_env_file()
    key = os.environ.get("OPENAI_API_KEY")
    assert key, "OPENAI_API_KEY is required for live OpenAI tests."
    return key


MODEL = os.environ.get("AUTOSR_OPENAI_MODEL", "gpt-4o-mini")


def _assert_result_shape(result: LLMResult, *, mode: str) -> None:
    assert isinstance(result.content, str) and result.content.strip()
    assert result.usage.provider == "openai"
    assert result.usage.model == MODEL
    assert result.usage.mode == mode
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens >= 0


def _load_small_pdfs(limit: int = 1) -> Iterable[Path]:
    root = Path("resources/datasets/arxiv_papers")
    paths: list[Path] = []
    for candidate in sorted(root.rglob("*.pdf")):
        try:
            if candidate.stat().st_size <= 4 * 1024 * 1024:
                paths.append(candidate)
        except FileNotFoundError:
            continue
        if len(paths) >= limit:
            break
    assert paths, f"No suitable PDFs found under {root}"
    return paths


def test_openai_chat_sync_live() -> None:
    _require_api_key()
    provider = OpenAIProvider()
    prompt = "Summarize the importance of benchmarking for multimodal language models in one sentence."

    result = provider.chat(
        MODEL,
        prompt,
        temperature=0.2,
        max_output_tokens=256,
    )

    _assert_result_shape(result, mode="sync")


def test_openai_chat_batch_live() -> None:
    _require_api_key()
    provider = OpenAIProvider()
    prompts = [
        "List two open challenges for applying large language models to speech processing.",
        "Give two risks of using LLMs in healthcare decision support.",
    ]

    results = provider.chat_batch(
        MODEL,
        prompts,
        temperature=0.3,
        max_output_tokens=200,
        metadata={"suite": "live_batch"},
    )

    assert len(results) == len(prompts)
    for idx, result in enumerate(results):
        _assert_result_shape(result, mode="batch")
        assert result.usage.metadata.get("batch_index") == idx


def test_openai_chat_async_live() -> None:
    _require_api_key()
    provider = OpenAIProvider()
    prompts = [[{"role": "user", "content": text}] for text in [
        "Explain why context window length matters for survey analysis.",
        "Name two datasets commonly used for dialogue summarization.",
    ]]

    results = asyncio.run(
        provider.chat_async(
            MODEL,
            prompts,
            concurrency=2,
            temperature=0.15,
            max_output_tokens=180,
        )
    )

    assert len(results) == len(prompts)
    for idx, result in enumerate(results):
        _assert_result_shape(result, mode="async")
        assert result.usage.metadata.get("async_index") == idx


def test_openai_pdf_read_live(tmp_path: Path) -> None:
    _require_api_key()
    provider = OpenAIProvider()
    pdf_paths = list(_load_small_pdfs(limit=1))

    results = provider.read_pdf_batch(
        MODEL,
        pdf_paths,
        instructions="Extract the main topic of this survey.",
        metadata={"suite": "live_pdf"},
        max_output_tokens=500,
    )

    assert len(results) == 1
    artifact_dir = Path("test_artifacts/openai_live")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifact_path = artifact_dir / f"pdf_read_{timestamp}.json"
    artifact_path.write_text(results[0].content, encoding="utf-8")

    for result in results:
        _assert_result_shape(result, mode="pdf")
        assert result.usage.metadata.get("batch_index") == 0
