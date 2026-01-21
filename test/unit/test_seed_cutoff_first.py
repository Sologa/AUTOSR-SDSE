from __future__ import annotations

from datetime import date

import pytest

from src.pipelines.topic_pipeline import (
    _build_seed_query_from_tokens,
    _clean_seed_rewrite_phrases,
    _collect_cutoff_candidates,
    _filter_seed_records_by_cutoff,
    _normalize_title_for_match,
    _select_cutoff_candidate,
    _tokenize_seed_phrase_for_query,
)


def test_normalize_title_for_match_latex_and_punct() -> None:
    title = "Discrete Audio Tokens: More Than a Survey!"
    assert _normalize_title_for_match(title) == "discrete audio tokens more than a survey"

    latex_title = r"Deep $\\mathbf{RL}$ for \\text{Robotics}"
    assert _normalize_title_for_match(latex_title) == "deep rl for robotics"


def test_collect_cutoff_candidates_exact_title() -> None:
    records = [
        {
            "id": "http://arxiv.org/abs/2401.00001",
            "title": "Exact Match Title",
            "published": "2024-01-02T00:00:00Z",
        },
        {
            "id": "http://arxiv.org/abs/2401.00002",
            "title": "Different Title",
            "published": "2024-01-03T00:00:00Z",
        },
    ]
    title_norm = _normalize_title_for_match("Exact Match Title")
    candidates = _collect_cutoff_candidates(records, title_norm=title_norm, date_field="published")
    assert len(candidates) == 1
    assert candidates[0]["arxiv_id"] == "2401.00001"


def test_cutoff_tie_break_earliest_then_id() -> None:
    candidates = [
        {"arxiv_id": "2401.00002", "date_parsed": date(2024, 1, 2)},
        {"arxiv_id": "2401.00001", "date_parsed": date(2024, 1, 2)},
        {"arxiv_id": "2301.00001", "date_parsed": date(2023, 1, 1)},
    ]
    selected = _select_cutoff_candidate(candidates, date_field="published")
    assert selected is not None
    assert selected["arxiv_id"] == "2301.00001"

    candidates = [
        {"arxiv_id": "2401.00002", "date_parsed": date(2024, 1, 2)},
        {"arxiv_id": "2401.00001", "date_parsed": date(2024, 1, 2)},
    ]
    selected = _select_cutoff_candidate(candidates, date_field="published")
    assert selected is not None
    assert selected["arxiv_id"] == "2401.00001"


def test_clean_seed_rewrite_phrases_blacklist_and_english() -> None:
    phrases = ["survey of discrete audio tokens", "discrete audio tokens", "\u97f3\u9891 tokens"]
    cleaned, english_only, blacklist = _clean_seed_rewrite_phrases(phrases, blacklist_mode="clean")

    assert "discrete audio tokens" in cleaned
    assert all("survey" not in phrase for phrase in cleaned)
    assert english_only["dropped"]
    assert blacklist["hits"]


def test_clean_seed_rewrite_phrases_fail_mode() -> None:
    phrases = ["comprehensive review of speech models"]
    with pytest.raises(ValueError, match="blacklisted"):
        _clean_seed_rewrite_phrases(phrases, blacklist_mode="fail")


def test_query_builder_and_filter() -> None:
    tokens, info = _tokenize_seed_phrase_for_query("Audio-tokenization for speech", max_tokens=32)
    assert tokens == ["audio", "tokenization", "for", "speech"]
    assert info["truncated"] is False

    query = _build_seed_query_from_tokens(tokens)
    assert query == "(audio OR tokenization OR for OR speech) AND (survey OR review OR overview)"

    records = [
        {
            "id": "http://arxiv.org/abs/2401.00001",
            "title": "Cutoff",
            "published": "2024-01-02T00:00:00Z",
        },
        {
            "id": "http://arxiv.org/abs/2401.00002",
            "title": "Keep",
            "published": "2024-01-10T00:00:00Z",
        },
        {
            "id": "http://arxiv.org/abs/2401.00003",
            "title": "After",
            "published": "2024-02-01T00:00:00Z",
        },
        {
            "id": "http://arxiv.org/abs/2401.00004",
            "title": "Missing",
            "published": "",
        },
    ]
    kept, stats = _filter_seed_records_by_cutoff(
        records,
        cutoff_id="2401.00001",
        cutoff_date=date(2024, 1, 15),
        date_field="published",
    )
    assert [item["arxiv_id"] for item in kept] == ["2401.00002"]
    assert stats["excluded_cutoff_id"] == 1
    assert stats["excluded_after_cutoff"] == 1
    assert stats["excluded_missing_date"] == 1
    assert stats["kept"] == 1


def test_filter_seed_records_without_cutoff() -> None:
    records = [
        {
            "id": "http://arxiv.org/abs/2401.00001",
            "title": "Cutoff",
            "published": "2024-01-02T00:00:00Z",
        },
        {
            "id": "http://arxiv.org/abs/2401.00002",
            "title": "Keep",
            "published": "2024-01-10T00:00:00Z",
        },
        {
            "id": "http://arxiv.org/abs/2401.00003",
            "title": "After",
            "published": "2024-02-01T00:00:00Z",
        },
        {
            "id": "http://arxiv.org/abs/2401.00004",
            "title": "Missing",
            "published": "",
        },
    ]
    kept, stats = _filter_seed_records_by_cutoff(
        records,
        cutoff_id=None,
        cutoff_date=None,
        date_field="published",
    )
    assert [item["arxiv_id"] for item in kept] == [
        "2401.00001",
        "2401.00002",
        "2401.00003",
        "2401.00004",
    ]
    assert stats["excluded_cutoff_id"] == 0
    assert stats["excluded_after_cutoff"] == 0
    assert stats["excluded_missing_date"] == 0
    assert stats["kept"] == 4
