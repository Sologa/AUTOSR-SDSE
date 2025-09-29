from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest

from src.utils.keyword_extractor import (
    ExtractParams,
    PaperMetadataRecord,
    _write_usage_log,
    build_aggregate_instructions,
    build_generate_instructions,
    extract_search_terms_from_surveys,
)
from src.utils.keyword_extractor import _parse_json_content  # type: ignore[attr-defined]
from src.utils.llm import LLMResult, LLMService, LLMUsage
from src.utils.latte_review_configs import TitleAbstractReviewerProfile


def test_build_generate_instructions_defaults_encourage_category_inference() -> None:
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
    assert "自行歸納 4–6 個具描述性的" in category_line
    assert "推導多個主題分類" in instructions
    assert "不足 3 個術語" in instructions
    assert "never output full sentences or tokens with underscores" in instructions
    assert "目標總數大約 48 個或依據證據調整" in instructions


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
        category_target=3,
    )

    assert "<<" not in instructions and ">>" not in instructions
    assert partials[0] in instructions
    assert "Topic focus: spoken language models" in instructions
    assert "speech language models" in instructions
    assert (
        "每個分類至少維持 3 個術語，保留模型推導出的分類並避免超過 7 個總量；若某分類不足 3 個術語請併入相關分類"
        in instructions
    )
    assert "Ensure resulting search terms stay concise" in instructions


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


def _dummy_chat_result(content: str) -> LLMResult:
    usage = LLMUsage(
        provider="test",
        model="stub",
        mode="sync",
        input_tokens=1,
        output_tokens=1,
        cost=0.0,
    )
    return LLMResult(content=content, usage=usage, raw_response=None)


def _stub_profile() -> TitleAbstractReviewerProfile:
    return TitleAbstractReviewerProfile(
        key="stub",
        review_topic="Stub topic",
        inclusion_criteria="Stub include",
        exclusion_criteria="Stub exclude",
        backstory="Stub backstory",
        reasoning="brief",
        additional_context="Stub context",
        examples=["Example A"],
        provider_model="stub-model",
        provider_model_args={},
        keywords=["stub"],
        search_terms={"core_concepts": ["stub"]},
    )

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

    def _collect(paths):
        return [
            PaperMetadataRecord(
                arxiv_id="2504.08528",
                title="Stub Title",
                abstract="Stub Abstract",
                year="2025",
                url="https://arxiv.org/abs/2504.08528",
                pdf_path=Path(path),
            )
            for path in paths
        ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.utils.keyword_extractor._collect_paper_metadata", _collect)
        mp.setattr(
            "src.utils.keyword_extractor.get_title_abstract_profile",
            lambda topic: _stub_profile(),
        )

        result = extract_search_terms_from_surveys(
            ["2504.08528.pdf"],
            service=_mock_service(return_value=bad),
            usage_log_path=log_path,
        )

    assert log_path.exists(), "usage log should still be recorded"
    assert isinstance(result, dict)
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["total"]["input_tokens"] >= 1
    assert payload["total"]["output_tokens"] >= 1


def test_default_usage_log_created(monkeypatch) -> None:
    title = "Stub Title"
    abstract = "Stub Abstract"

    def _collect(paths):
        return [
            PaperMetadataRecord(
                arxiv_id="2504.08528",
                title=title,
                abstract=abstract,
                year="2025",
                url="https://arxiv.org/abs/2504.08528",
                pdf_path=Path(path),
            )
            for path in paths
        ]

    monkeypatch.setattr("src.utils.keyword_extractor._collect_paper_metadata", _collect)
    monkeypatch.setattr(
        "src.utils.keyword_extractor.get_title_abstract_profile",
        lambda topic: _stub_profile(),
    )

    good_payload = {
        "topic": "stub",
        "anchor_terms": ["stub"],
        "search_terms": {"core_concepts": ["stub"]},
        "papers": [
            {
                "id": "stub-0",
                "source_id": "arXiv:2504.08528",
                "title": title,
                "abstract": abstract,
                "year": "2025",
                "source_url": "https://arxiv.org/abs/2504.08528",
                "detected_keywords": [],
            }
        ],
        "reviewer_profile": {
            "review_topic": "Stub topic",
            "inclusion_criteria": "Stub include",
            "exclusion_criteria": "Stub exclude",
            "backstory": "Stub backstory",
            "reasoning": "brief",
            "additional_context": "Stub context",
            "examples": ["Example A"],
            "provider": {"model": "stub-model", "model_args": {}},
        },
    }

    good = _dummy_result(json.dumps(good_payload))
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


def test_two_step_fallback_merges_per_paper_payloads(monkeypatch, tmp_path: Path) -> None:
    metadata = [
        PaperMetadataRecord(
            arxiv_id="1234.5678",
            title="Paper One",
            abstract="Abstract One",
            year="2024",
            url="https://arxiv.org/abs/1234.5678",
            pdf_path=Path("paper1.pdf"),
        ),
        PaperMetadataRecord(
            arxiv_id="9876.5432",
            title="Paper Two",
            abstract="Abstract Two",
            year="2023",
            url="https://arxiv.org/abs/9876.5432",
            pdf_path=Path("paper2.pdf"),
        ),
    ]

    per_payloads = [
        {
            "topic": "sample topic",
            "anchor_terms": ["paper one anchors"],
            "search_terms": {"core_concepts": ["term_a", "term_b"]},
            "papers": [
                {
                    "id": "p1",
                    "source_id": "arXiv:1234.5678",
                    "title": "Paper One",
                    "abstract": "Abstract One",
                    "year": "2024",
                    "source_url": "https://arxiv.org/abs/1234.5678",
                    "detected_keywords": [
                        {
                            "term": "term_a",
                            "category": "core_concepts",
                            "evidence": {"quote": "quote", "page": "1"},
                            "confidence": 0.5,
                        }
                    ],
                }
            ],
            "reviewer_profile": {
                "review_topic": "Stub topic",
                "inclusion_criteria": "Stub include",
                "exclusion_criteria": "Stub exclude",
                "backstory": "Stub backstory",
                "reasoning": "brief",
                "additional_context": "Context one",
                "examples": ["Example"],
                "provider": {"model": "stub-model", "model_args": {}},
            },
        },
        {
            "topic": "sample topic",
            "anchor_terms": ["paper two anchors"],
            "search_terms": {"core_concepts": ["term_c"]},
            "papers": [
                {
                    "id": "p2",
                    "source_id": "arXiv:9876.5432",
                    "title": "Paper Two",
                    "abstract": "Abstract Two",
                    "year": "2023",
                    "source_url": "https://arxiv.org/abs/9876.5432",
                    "detected_keywords": [],
                }
            ],
            "reviewer_profile": {
                "review_topic": "Stub topic",
                "inclusion_criteria": "Stub include",
                "exclusion_criteria": "Stub exclude",
                "backstory": "Stub backstory",
                "reasoning": "brief",
                "additional_context": "Context two",
                "examples": ["Example"],
                "provider": {"model": "stub-model", "model_args": {}},
            },
        },
    ]

    monkeypatch.setattr(
        "src.utils.keyword_extractor._collect_paper_metadata", lambda _paths: metadata
    )
    monkeypatch.setattr(
        "src.utils.keyword_extractor.get_title_abstract_profile",
        lambda topic: _stub_profile(),
    )

    per_results = [_dummy_result(json.dumps(payload)) for payload in per_payloads]
    service = cast(LLMService, Mock(spec=LLMService))
    service.read_pdf.side_effect = per_results  # type: ignore[attr-defined]
    service.chat.return_value = _dummy_chat_result("not json")  # type: ignore[attr-defined]
    service.get_provider.return_value = Mock()

    output = extract_search_terms_from_surveys(
        ["paper1.pdf", "paper2.pdf"],
        service=service,
        params=ExtractParams(topic="sample topic", include_ethics=False),
        usage_log_path=tmp_path / "fallback_usage.json",
    )

    assert {paper["source_id"] for paper in output["papers"]} == {
        record.source_id for record in metadata
    }
    assert "latte_inputs" not in output
    assert "term c" in output["search_terms"]["core_concepts"]
    assert "queries" not in output
    assert "synonyms" not in output
    reviewer_profile = output.get("reviewer_profile")
    assert isinstance(reviewer_profile, dict)
    assert reviewer_profile.get("review_topic")


def _mock_service(*, return_value: LLMResult) -> LLMService:
    service = cast(LLMService, Mock(spec=LLMService))
    service.read_pdf.return_value = return_value  # type: ignore[attr-defined]
    service.chat.return_value = return_value  # type: ignore[attr-defined]
    return service
