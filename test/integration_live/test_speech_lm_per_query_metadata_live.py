from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Sequence
from urllib.parse import quote_plus

import pytest
import requests

from src.utils.env import load_env_file
from src.utils.paper_downloaders import fetch_arxiv_metadata
from src.utils.paper_workflows import (
    extract_arxiv_id_from_record,
    search_arxiv_for_topic,
    search_semantic_scholar_for_topic,
)


TERMS_PAYLOAD = Path("test_artifacts/keyword_extractor_live/multi_20250929_114024.json")
OUTPUT_ROOT = Path("test_artifacts/metadata_harvest/speech_language_models_per_query")

MAX_RESULTS_PER_QUERY = 100
ANCHOR_TERM = "speech language models"
SEARCH_TERM = "superb"




def _load_single_terms(limit_per_category: int = 3) -> list[tuple[str, str]]:
    payload = json.loads(TERMS_PAYLOAD.read_text(encoding="utf-8"))
    anchors: Sequence[str] = payload.get("anchor_terms") or []
    if not anchors:
        raise RuntimeError("No anchor terms found in keyword extractor payload")

    search_terms_dict: Dict[str, Sequence[str]] = payload.get("search_terms") or {}
    flattened: List[str] = []
    for terms in search_terms_dict.values():
        for term in terms[:limit_per_category]:
            flattened.append(term)

    if not flattened:
        raise RuntimeError("No search terms found in keyword extractor payload")

    combos: list[tuple[str, str]] = []
    for anchor in anchors:
        for term in flattened:
            combos.append((anchor, term))
    return combos


def _head_ok(session: requests.Session, url: str, *, timeout: int = 15) -> bool:
    try:
        response = session.head(url, allow_redirects=True, timeout=timeout)
    except requests.RequestException:
        return False
    return 200 <= response.status_code < 400


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
    response = session.get(url, headers=headers, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


class TestSpeechLMPerQueryMetadata:
    @classmethod
    def setup_class(cls) -> None:
        load_env_file()
        cls.session = requests.Session()
        cls.api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        cls.query_pairs = [(ANCHOR_TERM, SEARCH_TERM)]
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def teardown_class(cls) -> None:
        cls.session.close()

    def _find_successful_query(
        self,
        extractor: callable,
        reducer: callable,
        *,
        source: str,
    ) -> tuple[str, str, List[Dict[str, object]]]:
        for anchor, term in self.query_pairs:
            try:
                records = extractor(anchor, term)
            except requests.RequestException:
                continue
            if not records:
                continue
            accessible = reducer(anchor, term, records)
            if accessible:
                return anchor, term, accessible
        # breakpoint()
        pytest.skip(f"No {source} query produced accessible results")

    def test_single_query_arxiv_metadata(self) -> None:
        def _extract(anchor: str, term: str) -> list[Dict[str, object]]:
            return search_arxiv_for_topic(
                self.session,
                [anchor],
                [term],
                max_results=MAX_RESULTS_PER_QUERY,
                scope="all",
                boolean_operator="OR",
            )

        def _reduce(anchor: str, term: str, records: list[Dict[str, object]]) -> List[Dict[str, object]]:
            accessible: List[Dict[str, object]] = []
            seen_ids: set[str] = set()
            for record in records:
                arxiv_id = extract_arxiv_id_from_record(record)
                if not arxiv_id or arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)
                try:
                    metadata = fetch_arxiv_metadata(arxiv_id, session=self.session)
                except requests.RequestException:
                    continue
                pdf_url = metadata.get("pdf_url")
                if not pdf_url or not _head_ok(self.session, str(pdf_url)):
                    continue
                accessible.append(
                    {
                        "anchor": anchor,
                        "search_term": term,
                        "search_record": record,
                        "metadata": metadata,
                    }
                )
            return accessible

        anchor, term, accessible = self._find_successful_query(_extract, _reduce, source="arXiv")
        # breakpoint()

        output_path = OUTPUT_ROOT / "arxiv_per_query_metadata.json"
        output_path.write_text(json.dumps(accessible, ensure_ascii=False, indent=2), encoding="utf-8")

        assert accessible[0]["metadata"].get("summary"), "ArXiv metadata missing abstract"

    def test_single_query_semantic_scholar_metadata(self) -> None:
        def _extract(anchor: str, term: str) -> list[Dict[str, object]]:
            # Assuming respect_semantic_scholar_rate_limit is defined elsewhere or will be added.
            # For now, we'll just pass the api_key if it's available.
            return search_semantic_scholar_for_topic(
                self.session,
                [anchor],
                [term],
                api_key=self.api_key,
                limit=MAX_RESULTS_PER_QUERY,
                custom_query=f"{anchor} {term}",
            )

        def _reduce(anchor: str, term: str, records: list[Dict[str, object]]) -> List[Dict[str, object]]:
            accessible: List[Dict[str, object]] = []
            seen_ids: set[str] = set()
            for record in records:
                paper_id = record.get("paperId") or record.get("paper_id")
                if not paper_id or paper_id in seen_ids:
                    continue
                seen_ids.add(str(paper_id))
                try:
                    metadata = _fetch_semantic_metadata(
                        self.session,
                        str(paper_id),
                        api_key=self.api_key,
                    )
                except requests.RequestException:
                    continue

                accessible.append(
                    {
                        "anchor": anchor,
                        "search_term": term,
                        "search_record": record,
                        "metadata": metadata,
                    }
                )
            return accessible

        anchor, term, accessible = self._find_successful_query(_extract, _reduce, source="Semantic Scholar")
        # breakpoint()

        output_path = OUTPUT_ROOT / "semantic_scholar_per_query_metadata.json"
        output_path.write_text(json.dumps(accessible, ensure_ascii=False, indent=2), encoding="utf-8")

        # Semantic Scholar abstracts are optional; ensure metadata carries text fields for inspection.
        assert isinstance(accessible[0]["metadata"].get("abstract"), str) or accessible[0]["metadata"].get("tldr"), "Semantic Scholar metadata missing abstract/tldr"

    def test_single_query_merge(self) -> None:
        arxiv_path = OUTPUT_ROOT / "arxiv_per_query_metadata.json"
        semantic_path = OUTPUT_ROOT / "semantic_scholar_per_query_metadata.json"

        if not arxiv_path.exists() or not semantic_path.exists():
            pytest.skip("Required single query metadata files not available")

        arxiv_items = json.loads(arxiv_path.read_text(encoding="utf-8"))
        semantic_items = json.loads(semantic_path.read_text(encoding="utf-8"))

        merged: Dict[str, Dict[str, object]] = {}

        for entry in arxiv_items:
            arxiv_id = entry["metadata"].get("arxiv_id")
            if not arxiv_id:
                continue
            merged[arxiv_id] = {
                "identifier": arxiv_id,
                "sources": ["arxiv"],
                **entry,
            }

        for entry in semantic_items:
            paper_id = entry["metadata"].get("externalIds", {}).get("ArXiv") if isinstance(entry["metadata"].get("externalIds"), dict) else None
            key = paper_id or entry["search_record"].get("paperId")
            if not key:
                continue

            existing = merged.get(key)
            sources = set(existing.get("sources", []) if existing else [])
            sources.add("semantic_scholar")
            payload = {
                "identifier": key,
                "sources": sorted(sources),
                **entry,
            }
            if existing:
                payload.update(existing)
            merged[key] = payload

        merged_path = OUTPUT_ROOT / "per_query_merged_metadata.json"
        merged_path.write_text(
            json.dumps(list(merged.values()), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        identifiers = [item["identifier"] for item in merged.values()]
        assert len(identifiers) == len(set(identifiers)), "Merged single-query metadata contains duplicates"
