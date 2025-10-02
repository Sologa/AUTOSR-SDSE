from __future__ import annotations

import json
import os
from datetime import date, datetime
from itertools import product
from pathlib import Path
from typing import Dict, List, Sequence
from urllib.parse import quote_plus

import pytest
import requests

from src.utils.env import load_env_file
from src.utils.paper_downloaders import fetch_arxiv_metadata
from src.utils.paper_workflows import (
    build_semantic_scholar_query,
    extract_arxiv_id_from_record,
    respect_semantic_scholar_rate_limit,
    search_arxiv_for_topic,
    search_semantic_scholar_for_topic,
    trim_arxiv_id,
)


TERMS_PAYLOAD = Path("test_artifacts/keyword_extractor_live/multi_20250929_114024.json")
OUTPUT_ROOT = Path("test_artifacts/metadata_harvest/speech_language_models")
SINGLE_QUERY_ROOT = Path("test_artifacts/metadata_harvest/speech_language_models_single_query")

SINGLE_QUERY_MODE = bool(int(os.environ.get("SPEECH_LM_SINGLE_QUERY_MODE", "0")))

MAX_TERMS_PER_CATEGORY = 3
TOP_K_RESULTS = 100
ARXIV_MAX_RESULTS = TOP_K_RESULTS
SEMANTIC_LIMIT = TOP_K_RESULTS

START_DATE = date(2019, 1, 1)
END_DATE = date(2025, 9, 30)


def _load_terms(limit_per_category: int, *, single_mode: bool = False) -> tuple[list[str], list[str]]:
    payload = json.loads(TERMS_PAYLOAD.read_text(encoding="utf-8"))
    anchors = payload.get("anchor_terms") or []
    search_terms_dict: Dict[str, Sequence[str]] = payload.get("search_terms") or {}

    flattened: List[str] = []
    for terms in search_terms_dict.values():
        for term in terms[:limit_per_category]:
            if term not in flattened:
                flattened.append(term)

    if single_mode:
        anchors = anchors[:1]
        flattened = flattened[:1]

    return anchors, flattened


def _head_ok(session: requests.Session, url: str, *, timeout: int = 15) -> bool:
    try:
        response = session.head(url, allow_redirects=True, timeout=timeout)
    except requests.RequestException:
        return False
    return 200 <= response.status_code < 400


def _parse_arxiv_date(value: str | None) -> date | None:
    if not value:
        return None
    sanitized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(sanitized)
    except ValueError:
        try:
            dt = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    return dt.date()


def _within_window_arxiv(published: str | None) -> bool:
    published_date = _parse_arxiv_date(published)
    if not published_date:
        return False
    return START_DATE <= published_date <= END_DATE


def _within_window_semantic(year_value: object) -> bool:
    try:
        year = int(year_value)
    except (TypeError, ValueError):
        return False

    if year < START_DATE.year or year > END_DATE.year:
        return False

    if year == START_DATE.year:
        return True
    if year == END_DATE.year:
        return True
    return True


def _fetch_semantic_metadata(
    session: requests.Session,
    paper_id: str,
    *,
    api_key: str | None,
    timeout: int = 30,
) -> Dict[str, object]:
    headers = {"x-api-key": api_key} if api_key else {}
    params = {
        "fields": (
            "title,abstract,year,publicationDate,publicationVenue,venue,isOpenAccess,openAccessPdf,"
            "externalIds,url,alternateUrls,pdfUrls,referenceCount,citationCount,influentialCitationCount,"
            "fieldsOfStudy,s2FieldsOfStudy,tldr,journal,journalPages,journalVolume,isPublisherLicensed,"
            "embedding,publicationTypes,publicationPlace,issn,isbn,volume,issue,pages,doi,corpusId,"
            "keywords,relations,affiliations,"
            "authors.name,authors.aliases,authors.externalIds,authors.url,authors.profile,"
            "authors.affiliations,authors.homepage"
        ),
    }
    url = f"https://api.semanticscholar.org/graph/v1/paper/{quote_plus(paper_id)}"

    respect_semantic_scholar_rate_limit(api_key_present=bool(api_key))
    response = session.get(url, headers=headers, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _merge_sources(
    arxiv_items: Sequence[Dict[str, object]],
    semantic_items: Sequence[Dict[str, object]],
) -> List[Dict[str, object]]:
    by_key: Dict[str, Dict[str, object]] = {}

    def _normalise_arxiv_id(identifier: object) -> str | None:
        if not isinstance(identifier, str):
            return None
        return trim_arxiv_id(identifier) or identifier

    for item in arxiv_items:
        metadata = item.get("metadata") if isinstance(item, dict) else {}
        arxiv_id = _normalise_arxiv_id(
            metadata.get("arxiv_id")
            or item.get("arxiv_id")
        )
        if not arxiv_id:
            continue
        by_key[arxiv_id] = {
            "identifier": arxiv_id,
            "sources": ["arxiv"],
            **item,
        }

    for item in semantic_items:
        metadata = item.get("metadata") if isinstance(item, dict) else {}
        paper_id = item.get("paper_id") or metadata.get("paper_id")
        if isinstance(paper_id, str) and paper_id.startswith("arXiv:"):
            arxiv_part = trim_arxiv_id(paper_id.split(":", 1)[-1])
        else:
            external_ids = metadata.get("externalIds") if isinstance(metadata, dict) else {}
            arxiv_part = trim_arxiv_id(external_ids.get("ArXiv")) if isinstance(external_ids, dict) and external_ids.get("ArXiv") else None
        key = arxiv_part or str(paper_id)
        if not key:
            continue

        existing = by_key.get(key)
        record = {
            "identifier": key,
            "sources": sorted(set((existing.get("sources", []) if existing else []) + ["semantic_scholar"])),
        }
        if existing:
            record.update(existing)
        record.update(item)
        by_key[key] = record

    return sorted(by_key.values(), key=lambda entry: entry["identifier"])


class TestSpeechLMMetadataHarvest:
    @classmethod
    def setup_class(cls) -> None:
        load_env_file()
        cls.session = requests.Session()
        cls.api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        cls.anchor_terms, cls.search_terms = _load_terms(
            MAX_TERMS_PER_CATEGORY,
            single_mode=SINGLE_QUERY_MODE,
        )
        if not cls.anchor_terms:
            raise RuntimeError("No anchor terms available in keyword extractor payload")
        if not cls.search_terms:
            raise RuntimeError("No search terms available in keyword extractor payload")

        (SINGLE_QUERY_ROOT if SINGLE_QUERY_MODE else OUTPUT_ROOT).mkdir(parents=True, exist_ok=True)

    @classmethod
    def teardown_class(cls) -> None:
        cls.session.close()

    def test_arxiv_metadata_for_pdf_accessible_records(self) -> None:
        output_root = SINGLE_QUERY_ROOT if SINGLE_QUERY_MODE else OUTPUT_ROOT
        combined_records: List[Dict[str, object]] = []
        for anchor, modifier in product(self.anchor_terms, self.search_terms):
            try:
                partial_records = search_arxiv_for_topic(
                    self.session,
                    [anchor],
                    [modifier],
                    max_results=ARXIV_MAX_RESULTS,
                    scope="all",
                    boolean_operator="OR",
                )
            except requests.RequestException:
                continue
            combined_records.extend(partial_records)
        records = combined_records
        assert records, "Expected at least one record aggregated from arXiv queries"

        accessible: List[Dict[str, object]] = []
        seen_arxiv: set[str] = set()
        for record in records:
            arxiv_id = extract_arxiv_id_from_record(record)
            if not arxiv_id or arxiv_id in seen_arxiv:
                continue
            seen_arxiv.add(arxiv_id)
            try:
                metadata = fetch_arxiv_metadata(arxiv_id, session=self.session)
            except requests.RequestException:
                continue
            if not _within_window_arxiv(metadata.get("published")):
                continue
            pdf_url = metadata.get("pdf_url")
            if not pdf_url or not _head_ok(self.session, str(pdf_url)):
                continue
            accessible.append({
                "arxiv_id": arxiv_id,
                "anchor": anchor,
                "search_term": modifier,
                "search_record": record,
                "metadata": metadata,
            })

        output_path = output_root / ("arxiv_single_query_metadata.json" if SINGLE_QUERY_MODE else "arxiv_metadata.json")
        output_path.write_text(
            json.dumps(accessible, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        assert accessible, "Expected at least one arXiv record with accessible PDF metadata"

    def test_semantic_scholar_metadata_records(self) -> None:
        output_root = SINGLE_QUERY_ROOT if SINGLE_QUERY_MODE else OUTPUT_ROOT
        combined_records: List[Dict[str, object]] = []
        for anchor, modifier in product(self.anchor_terms, self.search_terms):
            try:
                records = search_semantic_scholar_for_topic(
                    self.session,
                    [anchor],
                    [modifier],
                    api_key=self.api_key,
                    limit=SEMANTIC_LIMIT,
                    custom_query=f"{anchor} {modifier}",
                )
            except requests.RequestException:
                continue
            combined_records.extend(records)

        if not combined_records:
            pytest.skip("Semantic Scholar searches produced no records")

        accessible: List[Dict[str, object]] = []
        seen_semantic: set[str] = set()
        for record in combined_records:
            paper_id = record.get("paperId") or record.get("paper_id")
            if not paper_id or paper_id in seen_semantic:
                continue
            seen_semantic.add(str(paper_id))
            try:
                metadata = _fetch_semantic_metadata(
                    self.session,
                    str(paper_id),
                    api_key=self.api_key,
                )
            except requests.RequestException:
                continue

            if not _within_window_semantic(metadata.get("year")):
                continue

            accessible.append({
                "paper_id": paper_id,
                "anchor": anchor,
                "search_term": modifier,
                "search_record": record,
                "metadata": metadata,
            })

        if not accessible:
            pytest.skip("Semantic Scholar metadata unavailable for current search window")

        output_path = output_root / ("semantic_scholar_single_query_metadata.json" if SINGLE_QUERY_MODE else "semantic_scholar_metadata.json")
        output_path.write_text(
            json.dumps(accessible, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_merge_metadata_across_sources(self) -> None:
        output_root = SINGLE_QUERY_ROOT if SINGLE_QUERY_MODE else OUTPUT_ROOT

        arxiv_path = output_root / ("arxiv_single_query_metadata.json" if SINGLE_QUERY_MODE else "arxiv_metadata.json")
        semantic_path = output_root / ("semantic_scholar_single_query_metadata.json" if SINGLE_QUERY_MODE else "semantic_scholar_metadata.json")

        if not arxiv_path.exists():
            pytest.skip("arXiv metadata not available")
        if not semantic_path.exists():
            pytest.skip("Semantic Scholar metadata not available")

        arxiv_items = json.loads(arxiv_path.read_text(encoding="utf-8"))
        semantic_items = json.loads(semantic_path.read_text(encoding="utf-8"))

        merged = _merge_sources(arxiv_items, semantic_items)

        merged_path = output_root / ("single_query_merged_metadata.json" if SINGLE_QUERY_MODE else "merged_metadata.json")
        merged_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        identifiers = [entry["identifier"] for entry in merged]
        assert len(identifiers) == len(set(identifiers)), "Merged metadata contains duplicate identifiers"
