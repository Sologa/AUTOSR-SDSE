#!/usr/bin/env python3
"""Collect title + abstract metadata for reference oracle entries."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.utils.env import load_env_file

sys.path.insert(0, "target_papers/scripts")
from title_normalization import normalize_title, split_words  # noqa: E402


ARXIV_ID_RE = re.compile(
    r"(?:arxiv\s*[: ]\s*)?(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+/\d{7})(?:v\d+)?)",
    re.IGNORECASE,
)


def _normalize_whitespace(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


def _extract_arxiv_id(values: Iterable[str]) -> Optional[str]:
    for value in values:
        if not value:
            continue
        match = ARXIV_ID_RE.search(value)
        if match:
            return match.group("id")
    return None


def _load_reference_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


def _title_from_entry(entry: Dict[str, Any]) -> str:
    return (
        entry.get("query_title")
        or entry.get("raw", {}).get("local", {}).get("title")
        or ""
    )


def _candidate_strings(entry: Dict[str, Any]) -> list[str]:
    values: list[str] = []
    raw_local = entry.get("raw", {}).get("local", {})
    if isinstance(raw_local, dict):
        for key in ("journal", "note", "howpublished", "url", "doi"):
            value = raw_local.get(key)
            if isinstance(value, str):
                values.append(value)
    return values


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(split_words(left))
    right_tokens = set(split_words(right))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _prepare_title_query(title: str) -> str:
    cleaned = re.sub(r"[{}]", " ", title)
    cleaned = cleaned.replace("\\", " ")
    cleaned = cleaned.replace('"', " ")
    cleaned = _normalize_whitespace(cleaned)
    return cleaned


def _arxiv_id_from_entry_id(entry_id: str) -> str:
    if not entry_id:
        return ""
    return entry_id.rstrip("/").rsplit("/", 1)[-1]


def _search_arxiv_by_title(
    session: requests.Session,
    title: str,
    *,
    max_results: int,
) -> list[Dict[str, str]]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return []
    params = {
        "search_query": f'ti:"{query_title}"',
        "start": 0,
        "max_results": max_results,
    }
    response = session.get("https://export.arxiv.org/api/query", params=params, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results: list[Dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        entry_id = entry.findtext("atom:id", default="", namespaces=ns)
        results.append(
            {
                "id": _arxiv_id_from_entry_id(entry_id),
                "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip(),
                "summary": (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip(),
            }
        )
    return results


def _select_arxiv_match(
    entries: list[Dict[str, str]],
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
) -> tuple[Optional[Dict[str, str]], float]:
    target_norm = normalize_title(title)
    best: Optional[Dict[str, str]] = None
    best_similarity = 0.0

    for item in entries:
        candidate_title = item.get("title", "")
        candidate_norm = normalize_title(candidate_title)
        if candidate_norm and candidate_norm == target_norm:
            return item, 1.0
        similarity = _jaccard_similarity(candidate_title, title)
        if similarity > best_similarity:
            best = item
            best_similarity = similarity

    if best is None:
        return None, 0.0

    if best_similarity < 1.0 and not allow_fuzzy:
        return None, best_similarity
    if best_similarity < min_similarity:
        return None, best_similarity
    return best, best_similarity


def _semantic_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"User-Agent": "autosr-sdse/collect_title_abstracts"}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _semantic_request(
    session: requests.Session,
    url: str,
    *,
    headers: Dict[str, str],
    params: Dict[str, object],
    max_retries: int = 6,
) -> Dict[str, object]:
    for attempt in range(max_retries):
        response = session.get(url, headers=headers, params=params, timeout=30)
        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(float(retry_after))
            else:
                time.sleep(5 + (2 ** attempt))
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()
    return {}


def _search_semantic_scholar_by_title(
    session: requests.Session,
    title: str,
    *,
    api_key: Optional[str],
    max_results: int,
) -> list[Dict[str, object]]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return []
    params = {
        "query": query_title,
        "limit": max_results,
        "fields": "title,abstract,year,publicationDate,externalIds,venue,url,paperId,corpusId",
    }
    payload = _semantic_request(
        session,
        "https://api.semanticscholar.org/graph/v1/paper/search",
        headers=_semantic_headers(api_key),
        params=params,
    )
    results = payload.get("data")
    if isinstance(results, list):
        return results
    return []


def _select_semantic_match(
    entries: list[Dict[str, object]],
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
) -> Tuple[Optional[Dict[str, object]], float]:
    target_norm = normalize_title(title)
    best: Optional[Dict[str, object]] = None
    best_similarity = 0.0

    for item in entries:
        candidate_title = str(item.get("title") or "")
        candidate_norm = normalize_title(candidate_title)
        if candidate_norm and candidate_norm == target_norm:
            return item, 1.0
        similarity = _jaccard_similarity(candidate_title, title)
        if similarity > best_similarity:
            best = item
            best_similarity = similarity

    if best is None:
        return None, 0.0
    if best_similarity < 1.0 and not allow_fuzzy:
        return None, best_similarity
    if best_similarity < min_similarity:
        return None, best_similarity
    return best, best_similarity


@dataclass
class FetchResult:
    title: str
    abstract: str
    source: str
    source_id: str
    match_status: str
    raw_metadata: Dict[str, Any]


def _fetch_arxiv_metadata(session: requests.Session, arxiv_id: str) -> Optional[FetchResult]:
    from src.utils.paper_downloaders import fetch_arxiv_metadata

    metadata = fetch_arxiv_metadata(arxiv_id, session=session)
    title = _normalize_whitespace(metadata.get("title"))
    abstract = _normalize_whitespace(metadata.get("summary"))
    if not title:
        return None
    return FetchResult(
        title=title,
        abstract=abstract,
        source="arxiv",
        source_id=arxiv_id,
        match_status="exact_id",
        raw_metadata=metadata,
    )


def _fetch_arxiv_by_title(
    session: requests.Session,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
) -> Optional[FetchResult]:
    entries = _search_arxiv_by_title(session, title, max_results=max_results)
    matched, similarity = _select_arxiv_match(
        entries,
        title,
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None

    match_status = "exact_title" if similarity == 1.0 else "fuzzy_title"
    return FetchResult(
        title=_normalize_whitespace(matched.get("title")),
        abstract=_normalize_whitespace(matched.get("summary")),
        source="arxiv",
        source_id=matched.get("id") or "",
        match_status=match_status,
        raw_metadata=matched,
    )


def _fetch_semantic_scholar_by_title(
    session: requests.Session,
    title: str,
    *,
    api_key: Optional[str],
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
) -> Optional[FetchResult]:
    entries = _search_semantic_scholar_by_title(
        session,
        title,
        api_key=api_key,
        max_results=max_results,
    )
    matched, similarity = _select_semantic_match(
        entries,
        title,
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None

    match_status = "exact_title" if similarity == 1.0 else "fuzzy_title"
    source_id = matched.get("paperId") or matched.get("corpusId") or ""
    return FetchResult(
        title=_normalize_whitespace(matched.get("title")),
        abstract=_normalize_whitespace(matched.get("abstract")),
        source="semantic_scholar",
        source_id=str(source_id),
        match_status=match_status,
        raw_metadata=matched,
    )


def _build_record(
    entry: Dict[str, Any],
    result: Optional[FetchResult],
    *,
    missing_reason: Optional[str],
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "key": entry.get("key"),
        "query_title": entry.get("query_title"),
        "normalized_title": entry.get("normalized_title"),
    }
    if result is None:
        record.update(
            {
                "title": None,
                "abstract": None,
                "source": None,
                "source_id": None,
                "match_status": "missing",
                "missing_reason": missing_reason,
            }
        )
        return record

    record.update(
        {
            "title": result.title or None,
            "abstract": result.abstract or None,
            "source": result.source,
            "source_id": result.source_id,
            "match_status": result.match_status,
            "missing_reason": None,
        }
    )
    return record


def _load_existing(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    existing: Dict[str, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            key = item.get("key")
            if key:
                existing[str(key)] = item
    return existing


def _write_records(
    output_path: Path,
    entries: list[dict[str, Any]],
    records_by_key: Dict[str, Dict[str, Any]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            key = str(entry.get("key"))
            record = records_by_key.get(key)
            if record is None:
                continue
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=str,
        default="target_papers/discrete_audio_tokens_more_than_a_survey/reference_oracle.jsonl",
        help="Reference oracle JSONL file.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="workspaces/discrete_audio_tokens_more_than_a_survey/title_abstracts.jsonl",
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.25,
        help="Sleep seconds between external requests.",
    )
    parser.add_argument(
        "--allow-fuzzy",
        action="store_true",
        help="Allow fuzzy title matches from arXiv.",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.9,
        help="Minimum Jaccard similarity for fuzzy arXiv matches.",
    )
    parser.add_argument(
        "--arxiv-max-results",
        type=int,
        default=5,
        help="Max arXiv search results to consider per title.",
    )
    parser.add_argument(
        "--use-semantic-scholar",
        action="store_true",
        help="Use Semantic Scholar search for missing entries.",
    )
    parser.add_argument(
        "--semantic-scholar-api-key",
        type=str,
        default=None,
        help="Semantic Scholar API key (or set SEMANTIC_SCHOLAR_API_KEY).",
    )
    parser.add_argument(
        "--semantic-max-results",
        type=int,
        default=5,
        help="Max Semantic Scholar search results to consider per title.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of entries to process.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=1,
        help="Rewrite output after this many updates (default: 1).",
    )
    args = parser.parse_args()

    load_env_file()
    semantic_api_key = args.semantic_scholar_api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")

    input_path = Path(args.input)
    output_path = Path(args.output)
    entries = _load_reference_entries(input_path)
    if args.limit:
        entries = entries[: args.limit]

    records_by_key = _load_existing(output_path)

    session = requests.Session()

    for entry in entries:
        key = str(entry.get("key"))
        if key in records_by_key and records_by_key[key].get("match_status") != "missing":
            continue

        title = _title_from_entry(entry)
        arxiv_id = entry.get("arxiv") or _extract_arxiv_id(_candidate_strings(entry))

        result = None
        missing_reason = None
        if arxiv_id:
            try:
                result = _fetch_arxiv_metadata(session, arxiv_id)
            except Exception as exc:
                missing_reason = f"arxiv_error:{type(exc).__name__}"
            time.sleep(args.sleep)

        if result is None and title:
            try:
                result = _fetch_arxiv_by_title(
                    session,
                    title,
                    allow_fuzzy=args.allow_fuzzy,
                    min_similarity=args.min_similarity,
                    max_results=args.arxiv_max_results,
                )
            except Exception as exc:
                missing_reason = f"arxiv_search_error:{type(exc).__name__}"
            time.sleep(args.sleep)

        if result is None and title and args.use_semantic_scholar:
            try:
                result = _fetch_semantic_scholar_by_title(
                    session,
                    title,
                    api_key=semantic_api_key,
                    allow_fuzzy=args.allow_fuzzy,
                    min_similarity=args.min_similarity,
                    max_results=args.semantic_max_results,
                )
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                missing_reason = f"semantic_scholar_error:{status or type(exc).__name__}"
            except Exception as exc:
                missing_reason = f"semantic_scholar_error:{type(exc).__name__}"
            time.sleep(args.sleep)

        if result is None and not missing_reason:
            missing_reason = "not_found"

        record = _build_record(entry, result, missing_reason=missing_reason)
        records_by_key[key] = record
        if args.checkpoint_every > 0 and (len(records_by_key) % args.checkpoint_every == 0):
            _write_records(output_path, entries, records_by_key)

    _write_records(output_path, entries, records_by_key)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
