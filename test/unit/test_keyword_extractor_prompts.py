from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from src.utils.keyword_extractor import (
    ExtractParams,
    _write_usage_log,
    build_aggregate_instructions,
    build_generate_instructions,
    extract_search_terms_from_surveys,
)
from src.utils.keyword_extractor import _parse_json_content  # type: ignore[attr-defined]
from src.utils.llm import LLMResult, LLMService, LLMUsage


def test_build_generate_instructions_defaults_use_standard_categories() -> None:
    params = ExtractParams()
    instructions = build_generate_instructions(params)

    assert "<<" not in instructions and ">>" not in instructions
    assert "include_ethics: true" in instructions
    assert "max_queries: 50" in instructions
    assert "topic_hint: not provided" in instructions
    assert "custom_categories: not provided" in instructions
    assert "anchor_terms: infer 2–4 anchors grounded in the PDFs" in instructions
    category_line = next(
        line.strip()
        for line in instructions.splitlines()
        if "For each paper, extract candidate terms" in line
    )
    assert "core_concepts" in category_line and "ethics" in category_line


def test_build_generate_instructions_custom_categories_override_defaults() -> None:
    params = ExtractParams(
        include_ethics=False,
        custom_categories=["datasets", "evaluation_metrics"],
        seed_anchors=["dialogue systems"],
        exclude_terms=["speech recognition"],
        max_queries=12,
        topic="dialogue summarization",
        anchor_variants=["dialogue summarization", "dialog summarization"],
    )
    instructions = build_generate_instructions(params)

    assert "include_ethics: false" in instructions
    assert "max_queries: 12" in instructions
    assert "seed_anchors: dialogue systems" in instructions
    assert "exclude_terms: speech recognition" in instructions
    assert "use exactly these topic-aligned variants: dialogue summarization | dialog summarization; do not introduce unrelated anchor terms" in instructions

    category_line = next(
        line.strip()
        for line in instructions.splitlines()
        if "For each paper, extract candidate terms" in line
    )
    assert "datasets" in category_line
    assert "evaluation_metrics" in category_line
    assert "core_concepts" not in category_line

    topic_line = next(
        line.strip()
        for line in instructions.splitlines()
        if line.strip().startswith("\"topic\":")
    )
    assert re.search(r"dialogue summarization", topic_line)


def test_build_aggregate_instructions_replaces_tokens() -> None:
    partials = ["{\"anchor_terms\": []}"]
    instructions = build_aggregate_instructions(
        partials,
        max_queries=7,
        topic="spoken language models",
        anchor_variants=["spoken language models", "speech language models"],
    )

    assert "<<" not in instructions and ">>" not in instructions
    assert "7" in instructions
    assert partials[0] in instructions
    assert "Topic focus: spoken language models" in instructions
    assert "speech language models" in instructions


def test_write_usage_log(tmp_path) -> None:
    usage = LLMUsage(
        provider="openai",
        model="gpt-5-nano",
        mode="pdf",
        input_tokens=123,
        output_tokens=45,
        cost=0.00123,
    )
    result = LLMResult(content="{}", usage=usage, raw_response=None)

    output_path = tmp_path / "usage.json"
    _write_usage_log(output_path, [result])

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["total"]["input_tokens"] == 123
    assert data["total"]["output_tokens"] == 45
    assert data["total"]["cost"] == 0.00123
    assert data["records"][0]["provider"] == "openai"


def test_build_generate_instructions_with_custom_prompt_path() -> None:
    params = ExtractParams(
        topic="spoken language models",
        custom_categories=["language", "structure"],
        anchor_variants=["speech language models"],
        prompt_path="resources/LLM/prompts/keyword_extractor/cads_search_terms.md",
    )
    instructions = build_generate_instructions(params)

    assert "Speech-language model search strategist" in instructions
    assert "anchor_terms: use exactly these topic-aligned variants" in instructions
    assert "categories: language, structure" in instructions


def test_build_generate_instructions_with_topic_enforces_variants() -> None:
    params = ExtractParams(topic="spoken language models", include_ethics=False)
    instructions = build_generate_instructions(params)

    assert "anchor_terms: use exactly these topic-aligned variants" in instructions
    assert "speech language models" in instructions


def _dummy_usage() -> LLMUsage:
    return LLMUsage(
        provider="test",
        model="stub",
        mode="pdf",
        input_tokens=1,
        output_tokens=1,
        cost=0.0,
    )


def _dummy_result(content: str) -> LLMResult:
    return LLMResult(content=content, usage=_dummy_usage(), raw_response=None)

def test_extract_search_terms_empty_pdf_paths_raises() -> None:
    with pytest.raises(ValueError):
        extract_search_terms_from_surveys([])


def test_parse_json_strips_case_insensitive_fences() -> None:
    result = _dummy_result("```JSON\n{\n  \"x\": 1\n}\n```")
    parsed = _parse_json_content(result)

    assert parsed == {"x": 1}


def test_usage_log_written_even_when_llm_output_invalid(tmp_path) -> None:
    bad = _dummy_result("not json")
    log_path = tmp_path / "usage.json"

    with pytest.raises(ValueError):
        extract_search_terms_from_surveys(
            ["dummy.pdf"],
            service=_mock_service(return_value=bad),
            usage_log_path=log_path,
        )

    assert log_path.exists(), "usage log should still be recorded"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["total"]["input_tokens"] == 1
    assert payload["total"]["output_tokens"] == 1


def test_default_usage_log_created(monkeypatch) -> None:
    good = _dummy_result("{}")
    service = _mock_service(return_value=good)

    log_dir = Path("test_artifacts/llm")
    existing = set(log_dir.glob("keyword_extractor_usage_*.json"))

    result = extract_search_terms_from_surveys(
        ["dummy.pdf"],
        service=service,
        params=ExtractParams(topic="spoken language models", include_ethics=False),
    )

    assert isinstance(result, dict)
    created = set(log_dir.glob("keyword_extractor_usage_*.json")) - existing
    try:
        assert created, "Expected a new default usage log to be written"
    finally:
        for path in created:
            path.unlink(missing_ok=True)


def _mock_service(*, return_value: LLMResult) -> LLMService:
    service = cast(LLMService, Mock(spec=LLMService))
    service.read_pdfs.return_value = return_value  # type: ignore[attr-defined]
    return service
