#!/usr/bin/env python3
"""依來源優先序補齊 title/abstract，並可輸出來源 full metadata。

這支腳本會讀取 `reference_oracle.jsonl`，依序查詢多個來源，為每筆
reference 產生三類主要產物：

- `title_abstracts_metadata.jsonl`
- `title_abstracts_sources.jsonl`
- `title_abstracts_source_trace.jsonl`

當 `--include-full-metadata true` 時，會額外輸出：

- `title_abstracts_full_metadata.jsonl`

預設且一律不包含 Semantic Scholar 的 `embedding` 向量。

來源優先序：
`arxiv -> semantic_scholar -> dblp -> openalex -> crossref -> acl_anthology`
`-> lrec_conf -> rfc_editor -> bsi -> github -> huggingface -> keithito -> zenodo`

Examples
--------
```bash
python3 scripts/collect_title_abstracts_priority.py \
  --input-root bib/per_SR_cleaned \
  --output-root refs \
  --paper-name Chen2026_refs_from_pdf
```
"""

from __future__ import annotations

import argparse
import html
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

try:
    from src.utils.env import load_env_file  # type: ignore  # pragma: no cover
except Exception:  # pragma: no cover
    def load_env_file(dotenv_path: Path | str | None = None, *, override: bool = False) -> None:
        """Load environment variables from a local ``.env`` file in a minimal way."""
        path = Path(dotenv_path) if dotenv_path is not None else Path.cwd() / ".env"
        if not path.exists():
            return
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if override or key not in os.environ:
                os.environ[key] = value


try:
    from scripts.lib.title_normalizer import normalize_title  # type: ignore  # noqa: E402
    from scripts.lib.title_normalizer import split_words  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover
    from scripts.lib.title_normalizer import normalize_title  # type: ignore  # noqa: E402

    def split_words(text: str) -> list[str]:
        """Fallback tokenization for similarity matching."""
        normalized = normalize_title(text)
        return normalized.split() if normalized else []


ARXIV_ID_RE = re.compile(
    r"(?:arxiv\s*[: ]\s*)?(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+/\d{7})(?:v\d+)?)",
    re.IGNORECASE,
)

SOURCE_ORDER = [
    "arxiv",
    "semantic_scholar",
    "dblp",
    "openalex",
    "crossref",
    "acl_anthology",
    "lrec_conf",
    "rfc_editor",
    "bsi",
    "github",
    "huggingface",
    "keithito",
    "zenodo",
]

RATE_LIMITS = {
    "arxiv": 3.1,
    "semantic_scholar": 1.0,
    "dblp": 1.0,
    "openalex": 1.0,
    "crossref": 1.0,
    "acl_anthology": 1.0,
    "lrec_conf": 1.0,
    "rfc_editor": 1.0,
    "bsi": 1.0,
    "github": 6.0,
    "huggingface": 1.0,
    "keithito": 1.0,
    "zenodo": 1.0,
}

USER_AGENT = "autosr-sdse/collect-title-abstracts"
ARXIV_API_URL = "http://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_SEARCH_FIELDS = (
    "title,abstract,year,publicationDate,externalIds,venue,url,paperId,corpusId,authors,journal"
)
SEMANTIC_SCHOLAR_DETAIL_FIELDS_BASE = (
    "paperId,corpusId,title,abstract,year,publicationDate,publicationTypes,authors,venue,journal,url,"
    "externalIds,fieldsOfStudy,citationCount,referenceCount,influentialCitationCount,isOpenAccess,"
    "openAccessPdf,s2FieldsOfStudy,tldr"
)


@dataclass
class FetchResult:
    """Matched record from one source.

    Attributes
    ----------
    title:
        Canonical title selected by the source.
    abstract:
        Normalized abstract text used for downstream review.
    source:
        Source tag (e.g., `arxiv`, `semantic_scholar`).
    source_id:
        Source-specific stable identifier.
    match_status:
        Match type (`exact_title`, `fuzzy_title`, `exact_id`, ...).
    raw_metadata:
        Raw source payload (or best-effort full metadata) for traceability.
    """

    title: str
    abstract: str
    source: str
    source_id: str
    match_status: str
    raw_metadata: Dict[str, Any]


class RateLimiter:
    def __init__(self, min_intervals: Dict[str, float]) -> None:
        self._min_intervals = min_intervals
        self._last_call: Dict[str, float] = {}

    def wait(self, source: str) -> None:
        delay = self._min_intervals.get(source, 0.0)
        if delay <= 0:
            return
        now = time.monotonic()
        last = self._last_call.get(source)
        if last is not None:
            wait_time = delay - (now - last)
            if wait_time > 0:
                time.sleep(wait_time)
        self._last_call[source] = time.monotonic()


def parse_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    value = value.strip().lower()
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def _normalize_whitespace(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


def _strip_html(text: str) -> str:
    cleaned = html.unescape(text or "")
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    return _normalize_whitespace(cleaned)


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(split_words(left))
    right_tokens = set(split_words(right))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _prepare_title_query(title: str) -> str:
    cleaned = html.unescape(title or "")
    cleaned = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", cleaned)
    cleaned = cleaned.replace("{", "").replace("}", "")
    cleaned = cleaned.replace("\\", "")
    cleaned = cleaned.replace('"', " ")
    cleaned = re.sub(r"[\\s,]*(19|20)\\d{2}\\s*$", "", cleaned)
    return _normalize_whitespace(cleaned)


def _extract_arxiv_id(values: Iterable[str]) -> Optional[str]:
    for value in values:
        if not value:
            continue
        match = ARXIV_ID_RE.search(value)
        if match:
            return match.group("id")
    return None


def _request_json(
    session: requests.Session,
    url: str,
    *,
    source: str,
    limiter: RateLimiter,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, object]] = None,
    max_retries: int = 4,
) -> Dict[str, Any]:
    for attempt in range(max_retries):
        limiter.wait(source)
        response = session.get(url, headers=headers, params=params, timeout=30)
        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(float(retry_after))
            else:
                time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()
    return {}


def _request_text(
    session: requests.Session,
    url: str,
    *,
    source: str,
    limiter: RateLimiter,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, object]] = None,
    max_retries: int = 4,
) -> str:
    for attempt in range(max_retries):
        limiter.wait(source)
        response = session.get(url, headers=headers, params=params, timeout=30)
        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(float(retry_after))
            else:
                time.sleep(2 ** attempt)
            continue
        response.raise_for_status()
        return response.text
    response.raise_for_status()
    return ""


def _extract_html_meta_tags(page_html: str) -> Dict[str, Any]:
    """Parse `<meta name=... content=...>` into a dict; duplicate names become list."""
    tag_pattern = re.compile(
        r'<meta[^>]+name="([^"]+)"[^>]+content="([^"]*)"[^>]*>',
        re.IGNORECASE,
    )
    parsed: Dict[str, Any] = {}
    for key, value in tag_pattern.findall(page_html):
        norm_key = _normalize_whitespace(key)
        norm_value = _normalize_whitespace(html.unescape(value))
        if not norm_key:
            continue
        if norm_key not in parsed:
            parsed[norm_key] = norm_value
            continue
        existing = parsed[norm_key]
        if isinstance(existing, list):
            existing.append(norm_value)
        else:
            parsed[norm_key] = [existing, norm_value]
    return parsed


def _strip_reference_arrays(value: Any) -> Any:
    """Recursively drop heavy reference arrays while keeping other metadata."""
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, sub_value in value.items():
            if key == "reference" and isinstance(sub_value, list):
                continue
            cleaned[key] = _strip_reference_arrays(sub_value)
        return cleaned
    if isinstance(value, list):
        return [_strip_reference_arrays(item) for item in value]
    return value


def _prune_heavy_source_fields(source: Optional[str], metadata: Any) -> Any:
    """Drop source-specific heavy fields from full metadata output."""
    cleaned = _strip_reference_arrays(metadata)
    if not isinstance(cleaned, dict):
        return cleaned

    heavy_fields_by_source = {
        "openalex": {"abstract_inverted_index", "referenced_works"},
        "crossref": {"assertion", "link", "license"},
    }
    fields_to_drop = heavy_fields_by_source.get(str(source or "").strip().lower(), set())
    if not fields_to_drop:
        return cleaned
    return {key: value for key, value in cleaned.items() if key not in fields_to_drop}


def _semantic_scholar_fetch_paper_metadata(
    session: requests.Session,
    limiter: RateLimiter,
    paper_id: str,
    *,
    api_key: Optional[str],
) -> Optional[Dict[str, Any]]:
    paper_id = _normalize_whitespace(paper_id)
    if not paper_id:
        return None
    fields = SEMANTIC_SCHOLAR_DETAIL_FIELDS_BASE
    payload = _request_json(
        session,
        f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}",
        source="semantic_scholar",
        limiter=limiter,
        headers=_semantic_headers(api_key),
        params={"fields": fields},
    )
    return payload if isinstance(payload, dict) and payload else None


def _extract_openalex_work_id(openalex_id: str) -> Optional[str]:
    openalex_id = _normalize_whitespace(openalex_id)
    if not openalex_id:
        return None
    if openalex_id.startswith("https://openalex.org/"):
        work_id = openalex_id.rstrip("/").rsplit("/", 1)[-1]
        return work_id if work_id else None
    if re.fullmatch(r"W\d+", openalex_id):
        return openalex_id
    return None


def _openalex_fetch_work_metadata(
    session: requests.Session,
    limiter: RateLimiter,
    openalex_id: str,
) -> Optional[Dict[str, Any]]:
    work_id = _extract_openalex_work_id(openalex_id)
    if not work_id:
        return None
    payload = _request_json(
        session,
        f"https://api.openalex.org/works/{work_id}",
        source="openalex",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    return payload if isinstance(payload, dict) and payload else None


def _select_best_match(
    title: str,
    candidates: list[Dict[str, Any]],
    *,
    title_key: str,
    allow_fuzzy: bool,
    min_similarity: float,
) -> Tuple[Optional[Dict[str, Any]], float, str]:
    target_norm = normalize_title(title)
    token_count = len(split_words(title))
    best: Optional[Dict[str, Any]] = None
    best_similarity = 0.0

    for item in candidates:
        candidate_title = str(item.get(title_key) or "")
        candidate_norm = normalize_title(candidate_title)
        if candidate_norm and candidate_norm == target_norm:
            return item, 1.0, "exact_title"
        similarity = _jaccard_similarity(candidate_title, title)
        if similarity > best_similarity:
            best = item
            best_similarity = similarity

    if best is None:
        return None, 0.0, ""
    if best_similarity < 1.0 and not allow_fuzzy:
        return None, best_similarity, ""
    if best_similarity < 1.0 and token_count < 7:
        return None, best_similarity, ""
    if best_similarity < min_similarity:
        return None, best_similarity, ""
    return best, best_similarity, "fuzzy_title"


def _load_reference_entries(path: Path) -> list[Dict[str, Any]]:
    entries: list[Dict[str, Any]] = []
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


# --- Source: arXiv ---

def _parse_arxiv_entry(entry: ET.Element, ns: Dict[str, str]) -> Dict[str, Any]:
    authors: list[Dict[str, Optional[str]]] = []
    for author in entry.findall("atom:author", ns):
        name = _normalize_whitespace(author.findtext("atom:name", default="", namespaces=ns))
        affiliation = _normalize_whitespace(
            author.findtext("arxiv:affiliation", default="", namespaces=ns)
        )
        authors.append(
            {
                "name": name or None,
                "affiliation": affiliation or None,
            }
        )

    categories: list[str] = []
    for category in entry.findall("atom:category", ns):
        term = _normalize_whitespace(str(category.attrib.get("term") or ""))
        if term:
            categories.append(term)

    links: list[Dict[str, str]] = []
    for link in entry.findall("atom:link", ns):
        link_payload = {
            "href": _normalize_whitespace(str(link.attrib.get("href") or "")),
            "rel": _normalize_whitespace(str(link.attrib.get("rel") or "")),
            "type": _normalize_whitespace(str(link.attrib.get("type") or "")),
            "title": _normalize_whitespace(str(link.attrib.get("title") or "")),
        }
        if any(link_payload.values()):
            links.append(link_payload)

    entry_id = _normalize_whitespace(entry.findtext("atom:id", default="", namespaces=ns))
    primary_category_node = entry.find("arxiv:primary_category", ns)
    return {
        "id": entry_id.rstrip("/").rsplit("/", 1)[-1],
        "entry_id_url": entry_id,
        "title": _normalize_whitespace(entry.findtext("atom:title", default="", namespaces=ns)),
        "summary": _normalize_whitespace(entry.findtext("atom:summary", default="", namespaces=ns)),
        "published": _normalize_whitespace(
            entry.findtext("atom:published", default="", namespaces=ns)
        ),
        "updated": _normalize_whitespace(entry.findtext("atom:updated", default="", namespaces=ns)),
        "doi": _normalize_whitespace(entry.findtext("arxiv:doi", default="", namespaces=ns)) or None,
        "comment": _normalize_whitespace(
            entry.findtext("arxiv:comment", default="", namespaces=ns)
        )
        or None,
        "journal_ref": _normalize_whitespace(
            entry.findtext("arxiv:journal_ref", default="", namespaces=ns)
        )
        or None,
        "primary_category": _normalize_whitespace(
            str((primary_category_node.attrib.get("term") if primary_category_node is not None else ""))
        )
        or None,
        "authors": authors,
        "categories": categories,
        "links": links,
    }


def _parse_arxiv_feed_entries(feed_xml: str) -> list[Dict[str, Any]]:
    root = ET.fromstring(feed_xml)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    return [_parse_arxiv_entry(entry, ns) for entry in root.findall("atom:entry", ns)]


def _fetch_arxiv_metadata_by_id(
    session: requests.Session,
    limiter: RateLimiter,
    arxiv_id: str,
) -> Optional[Dict[str, Any]]:
    candidate_id = _normalize_whitespace(arxiv_id)
    if not candidate_id:
        return None
    response = _request_text(
        session,
        ARXIV_API_URL,
        source="arxiv",
        limiter=limiter,
        params={"id_list": candidate_id},
        headers={"User-Agent": USER_AGENT},
    )
    entries = _parse_arxiv_feed_entries(response)
    if not entries:
        return None
    return entries[0]

def _search_arxiv_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    max_results: int,
) -> list[Dict[str, Any]]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return []
    params = {
        "search_query": f'ti:"{query_title}"',
        "start": 0,
        "max_results": max_results,
    }
    response = _request_text(
        session,
        ARXIV_API_URL,
        source="arxiv",
        limiter=limiter,
        params=params,
        headers={"User-Agent": USER_AGENT},
    )
    return _parse_arxiv_feed_entries(response)


def _fetch_arxiv_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
) -> Tuple[Optional[FetchResult], str]:
    candidates = _search_arxiv_by_title(session, limiter, title, max_results=max_results)
    matched, _, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match"
    abstract = _normalize_whitespace(matched.get("summary"))
    if not abstract:
        return None, "no_match_or_no_abstract"
    raw_metadata: Dict[str, Any] = dict(matched)
    arxiv_id = _normalize_whitespace(str(matched.get("id") or ""))
    if arxiv_id:
        try:
            full_metadata = _fetch_arxiv_metadata_by_id(session, limiter, arxiv_id)
            if isinstance(full_metadata, dict) and full_metadata:
                raw_metadata = full_metadata
        except Exception:  # noqa: BLE001
            pass
    result = FetchResult(
        title=_normalize_whitespace(str(raw_metadata.get("title") or matched.get("title") or "")),
        abstract=abstract,
        source="arxiv",
        source_id=arxiv_id,
        match_status=match_status,
        raw_metadata=raw_metadata,
    )
    return result, "match"


# --- Source: Semantic Scholar ---

def _semantic_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _search_semantic_scholar_by_title(
    session: requests.Session,
    limiter: RateLimiter,
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
        "fields": SEMANTIC_SCHOLAR_SEARCH_FIELDS,
    }
    payload = _request_json(
        session,
        "https://api.semanticscholar.org/graph/v1/paper/search",
        source="semantic_scholar",
        limiter=limiter,
        headers=_semantic_headers(api_key),
        params=params,
    )
    results = payload.get("data")
    if isinstance(results, list):
        return results
    return []


def _fetch_semantic_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    api_key: Optional[str],
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
) -> Tuple[Optional[FetchResult], str]:
    candidates = _search_semantic_scholar_by_title(
        session,
        limiter,
        title,
        api_key=api_key,
        max_results=max_results,
    )
    matched, _, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match"
    abstract = _normalize_whitespace(matched.get("abstract"))
    if not abstract:
        return None, "no_match_or_no_abstract"
    source_id = matched.get("paperId") or matched.get("corpusId") or ""
    raw_metadata: Dict[str, Any] = dict(matched)
    detailed_metadata = _semantic_scholar_fetch_paper_metadata(
        session,
        limiter,
        str(source_id),
        api_key=api_key,
    )
    if isinstance(detailed_metadata, dict):
        raw_metadata = detailed_metadata
        abstract_from_detail = _normalize_whitespace(str(detailed_metadata.get("abstract") or ""))
        if abstract_from_detail:
            abstract = abstract_from_detail
    result = FetchResult(
        title=_normalize_whitespace(str(raw_metadata.get("title") or matched.get("title") or "")),
        abstract=abstract,
        source="semantic_scholar",
        source_id=str(source_id),
        match_status=match_status,
        raw_metadata=raw_metadata,
    )
    return result, "match"


# --- Source: DBLP ---

def _search_dblp_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    max_results: int,
) -> list[Dict[str, Any]]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return []
    params = {"q": query_title, "format": "json"}
    payload = _request_json(
        session,
        "https://dblp.org/search/publ/api",
        source="dblp",
        limiter=limiter,
        params=params,
    )
    hits = payload.get("result", {}).get("hits", {}).get("hit", [])
    results: list[Dict[str, Any]] = []
    if isinstance(hits, list):
        for item in hits[:max_results]:
            info = item.get("info", {}) if isinstance(item, dict) else {}
            if info:
                results.append(info)
    return results


def _fetch_dblp_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
) -> Tuple[Optional[str], str]:
    candidates = _search_dblp_by_title(session, limiter, title, max_results=max_results)
    matched, _, _ = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match"
    doi = matched.get("doi")
    if isinstance(doi, str) and doi:
        return doi, "match"
    return None, "match_no_abstract"


# --- Source: OpenAlex ---

def _openalex_inverted_to_text(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    pairs = []
    for token, positions in index.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                pairs.append((pos, token))
    if not pairs:
        return ""
    pairs.sort(key=lambda item: item[0])
    return " ".join(token for _, token in pairs)


def _search_openalex_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    max_results: int,
) -> list[Dict[str, Any]]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return []
    params = {
        "search": query_title,
        "per-page": max_results,
        "select": "id,display_name,title,abstract_inverted_index,doi,primary_location",
    }
    payload = _request_json(
        session,
        "https://api.openalex.org/works",
        source="openalex",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
        params=params,
    )
    results = payload.get("results")
    if isinstance(results, list):
        return results
    return []


def _fetch_openalex_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
) -> Tuple[Optional[FetchResult], str, Optional[str], Optional[str]]:
    candidates = _search_openalex_by_title(session, limiter, title, max_results=max_results)
    matched, _, match_status = _select_best_match(
        title,
        candidates,
        title_key="display_name",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match", None, None
    raw_metadata = dict(matched)
    detailed_metadata = _openalex_fetch_work_metadata(
        session,
        limiter,
        str(matched.get("id") or ""),
    )
    if isinstance(detailed_metadata, dict):
        raw_metadata = detailed_metadata
    abstract = ""
    if raw_metadata.get("abstract_inverted_index"):
        abstract = _openalex_inverted_to_text(raw_metadata.get("abstract_inverted_index"))
    if not abstract:
        return (
            None,
            "no_match_or_no_abstract",
            raw_metadata.get("doi"),
            _openalex_landing_url(raw_metadata),
        )
    result = FetchResult(
        title=_normalize_whitespace(raw_metadata.get("display_name") or raw_metadata.get("title")),
        abstract=_normalize_whitespace(abstract),
        source="openalex",
        source_id=str(raw_metadata.get("id") or matched.get("id") or ""),
        match_status=match_status,
        raw_metadata=raw_metadata,
    )
    return result, "match", raw_metadata.get("doi"), _openalex_landing_url(raw_metadata)


def _openalex_landing_url(record: Dict[str, Any]) -> Optional[str]:
    location = record.get("primary_location")
    if not isinstance(location, dict):
        return None
    url = location.get("landing_page_url")
    if isinstance(url, str):
        return url
    return None


# --- Source: Crossref ---

def _search_crossref_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    max_results: int,
) -> list[Dict[str, Any]]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return []
    params = {"query.title": query_title, "rows": max_results}
    payload = _request_json(
        session,
        "https://api.crossref.org/works",
        source="crossref",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
        params=params,
    )
    items = payload.get("message", {}).get("items")
    if isinstance(items, list):
        return items
    return []


def _fetch_crossref_by_doi(
    session: requests.Session,
    limiter: RateLimiter,
    doi: str,
) -> Optional[Dict[str, Any]]:
    if not doi:
        return None
    payload = _request_json(
        session,
        f"https://api.crossref.org/works/{doi}",
        source="crossref",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    item = payload.get("message")
    if isinstance(item, dict):
        return item
    return None


def _fetch_crossref_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
    candidate_doi: Optional[str],
) -> Tuple[Optional[FetchResult], str]:
    item = None
    if candidate_doi:
        item = _fetch_crossref_by_doi(session, limiter, candidate_doi)
    if item is None:
        raw_candidates = _search_crossref_by_title(session, limiter, title, max_results=max_results)
        candidates: list[Dict[str, Any]] = []
        for raw in raw_candidates:
            titles = raw.get("title")
            if isinstance(titles, list) and titles:
                title_value = titles[0]
            elif isinstance(titles, str):
                title_value = titles
            else:
                title_value = ""
            candidates.append({"title": title_value, "raw": raw})
        matched, _, match_status = _select_best_match(
            title,
            candidates,
            title_key="title",
            allow_fuzzy=allow_fuzzy,
            min_similarity=min_similarity,
        )
        if not matched:
            return None, "no_match"
        item = matched.get("raw")
        if not isinstance(item, dict):
            return None, "no_match"
    else:
        match_status = "exact_title"

    if isinstance(item, dict):
        item_doi = _normalize_whitespace(str(item.get("DOI") or ""))
        if item_doi:
            detailed_item = _fetch_crossref_by_doi(session, limiter, item_doi)
            if isinstance(detailed_item, dict):
                item = detailed_item

    abstract = _normalize_whitespace(_strip_html(item.get("abstract") or ""))
    if not abstract:
        return None, "no_match_or_no_abstract"

    titles = item.get("title")
    title_value = titles[0] if isinstance(titles, list) and titles else ""
    source_id = item.get("DOI") or candidate_doi or ""

    result = FetchResult(
        title=_normalize_whitespace(title_value),
        abstract=abstract,
        source="crossref",
        source_id=str(source_id),
        match_status=match_status,
        raw_metadata=item,
    )
    return result, "match"


# --- Source: ACL Anthology ---

def _fetch_acl_anthology_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return None, "no_match"
    search_url = "https://aclanthology.org/search/"
    text = _request_text(
        session,
        search_url,
        source="acl_anthology",
        limiter=limiter,
        params={"q": query_title},
        headers={"User-Agent": USER_AGENT},
    )
    links = re.findall(r"href=\"(/[^\"]+/)\"", text)
    if not links:
        return None, "no_match"

    # Prefer the first search hit.
    paper_url = f"https://aclanthology.org{links[0]}"
    paper_html = _request_text(
        session,
        paper_url,
        source="acl_anthology",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    title_match = re.search(r"name=\"citation_title\" content=\"([^\"]+)\"", paper_html)
    abstract_match = re.search(
        r"name=\"citation_abstract\" content=\"([^\"]+)\"",
        paper_html,
    )
    page_meta = _extract_html_meta_tags(paper_html)
    candidate_title = _normalize_whitespace(title_match.group(1)) if title_match else ""
    abstract = _normalize_whitespace(abstract_match.group(1)) if abstract_match else ""

    if candidate_title:
        _, similarity, match_status = _select_best_match(
            title,
            [{"title": candidate_title}],
            title_key="title",
            allow_fuzzy=allow_fuzzy,
            min_similarity=min_similarity,
        )
        if similarity == 0.0:
            return None, "no_match"
    else:
        return None, "no_match"

    if not abstract:
        return None, "match_no_abstract"

    result = FetchResult(
        title=candidate_title,
        abstract=abstract,
        source="acl_anthology",
        source_id=paper_url.rstrip("/").rsplit("/", 1)[-1],
        match_status=match_status,
        raw_metadata={
            "url": paper_url,
            "page_meta": page_meta,
            "title": candidate_title,
            "abstract": abstract,
        },
    )
    return result, "match"


# --- Source: LREC ---

def _fetch_lrec_summary(
    session: requests.Session,
    limiter: RateLimiter,
    landing_url: Optional[str],
) -> Tuple[Optional[FetchResult], str]:
    if not landing_url or "lrec-conf.org/proceedings" not in landing_url:
        return None, "no_match"
    page = _request_text(
        session,
        landing_url,
        source="lrec_conf",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    title_match = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else ""
    page_meta = _extract_html_meta_tags(page)
    abstract_match = re.search(r"<div[^>]*class=\"abstract\"[^>]*>(.*?)</div>", page, re.IGNORECASE | re.DOTALL)
    abstract = ""
    if abstract_match:
        abstract = _normalize_whitespace(_strip_html(abstract_match.group(1)))
    if not abstract:
        meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", page)
        if meta_desc:
            abstract = _normalize_whitespace(meta_desc.group(1))
    if not title or not abstract:
        return None, "match_no_abstract"

    lrec_id_match = re.search(r"/lrec(\d{4})/summaries/(\d+)", landing_url)
    source_id = landing_url
    if lrec_id_match:
        source_id = f"lrec{lrec_id_match.group(1)}:{lrec_id_match.group(2)}"

    result = FetchResult(
        title=title,
        abstract=abstract,
        source="lrec_conf",
        source_id=source_id,
        match_status="exact_title",
        raw_metadata={
            "url": landing_url,
            "page_meta": page_meta,
            "title": title,
            "abstract": abstract,
        },
    )
    return result, "summary_page"


# --- Source: RFC Editor ---

def _fetch_rfc_editor_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return None, "no_match"
    search_url = "https://www.rfc-editor.org/search/rfc_search_detail.php"
    text = _request_text(
        session,
        search_url,
        source="rfc_editor",
        limiter=limiter,
        params={"title": query_title},
        headers={"User-Agent": USER_AGENT},
    )
    rfc_match = re.search(r"RFC\s*(\d{3,5})", text)
    if not rfc_match:
        return None, "no_match"
    rfc_id = rfc_match.group(1)
    rfc_url = f"https://www.rfc-editor.org/rfc/rfc{rfc_id}"
    page = _request_text(
        session,
        rfc_url,
        source="rfc_editor",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    abstract_match = re.search(
        r"<section[^>]*id=\"abstract\"[^>]*>(.*?)</section>",
        page,
        re.IGNORECASE | re.DOTALL,
    )
    page_meta = _extract_html_meta_tags(page)
    abstract = ""
    if abstract_match:
        abstract = _normalize_whitespace(_strip_html(abstract_match.group(1)))
    title_match = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    doc_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
    if not abstract:
        return None, "no_match_or_no_abstract"
    result = FetchResult(
        title=doc_title,
        abstract=abstract,
        source="rfc_editor",
        source_id=f"RFC{rfc_id}",
        match_status="exact_title",
        raw_metadata={
            "url": rfc_url,
            "page_meta": page_meta,
            "title": doc_title,
            "abstract": abstract,
        },
    )
    return result, "match"


# --- Source: BSI ---

def _fetch_bsi_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return None, "no_match"
    search_url = "https://knowledge.bsigroup.com/search"
    page = _request_text(
        session,
        search_url,
        source="bsi",
        limiter=limiter,
        params={"text": query_title},
        headers={"User-Agent": USER_AGENT},
    )
    match = re.search(r"https://knowledge\.bsigroup\.com/products/[^\"\s]+", page)
    if not match:
        return None, "no_match"
    product_url = match.group(0)
    product_page = _request_text(
        session,
        product_url,
        source="bsi",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", product_page)
    page_meta = _extract_html_meta_tags(product_page)
    abstract = _normalize_whitespace(meta_desc.group(1)) if meta_desc else ""
    if not abstract:
        return None, "no_match_or_no_abstract"
    title_match = re.search(r"<title>(.*?)</title>", product_page, re.IGNORECASE | re.DOTALL)
    product_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
    result = FetchResult(
        title=product_title,
        abstract=abstract,
        source="bsi",
        source_id=product_url,
        match_status="exact_title",
        raw_metadata={
            "url": product_url,
            "page_meta": page_meta,
            "title": product_title,
            "abstract": abstract,
        },
    )
    return result, "match"


# --- Source: GitHub ---

def _fetch_github_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    github_token: Optional[str],
    allow_fuzzy: bool,
    min_similarity: float,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return None, "no_match"
    headers = {"User-Agent": USER_AGENT}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    params = {"q": query_title, "per_page": 5}
    payload = _request_json(
        session,
        "https://api.github.com/search/repositories",
        source="github",
        limiter=limiter,
        headers=headers,
        params=params,
    )
    items = payload.get("items")
    if not isinstance(items, list):
        return None, "no_match"

    candidates = []
    for item in items:
        if not isinstance(item, dict):
            continue
        candidates.append(
            {
                "title": item.get("name") or "",
                "description": item.get("description") or "",
                "full_name": item.get("full_name") or "",
                "raw": item,
            }
        )

    matched, _, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match"

    abstract = _normalize_whitespace(matched.get("description"))
    if not abstract:
        return None, "no_match_or_no_description"

    result = FetchResult(
        title=_normalize_whitespace(matched.get("title")),
        abstract=abstract,
        source="github",
        source_id=_normalize_whitespace(matched.get("full_name")),
        match_status=match_status,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else matched,
    )
    return result, "match"


# --- Source: Hugging Face ---

def _fetch_huggingface_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return None, "no_match"
    payload = _request_json(
        session,
        "https://huggingface.co/api/datasets",
        source="huggingface",
        limiter=limiter,
        params={"search": query_title},
        headers={"User-Agent": USER_AGENT},
    )
    if not isinstance(payload, list):
        return None, "no_match"

    candidates = []
    for item in payload[:5]:
        if not isinstance(item, dict):
            continue
        candidates.append(
            {
                "title": item.get("id") or "",
                "description": item.get("description") or "",
                "id": item.get("id") or "",
                "raw": item,
            }
        )

    matched, _, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match"
    abstract = _normalize_whitespace(matched.get("description"))
    if not abstract:
        return None, "no_match_or_no_description"

    result = FetchResult(
        title=_normalize_whitespace(matched.get("title")),
        abstract=abstract,
        source="huggingface",
        source_id=_normalize_whitespace(matched.get("id")),
        match_status=match_status,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else matched,
    )
    return result, "match"


# --- Source: Keithito ---

def _fetch_keithito_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
) -> Tuple[Optional[FetchResult], str]:
    if "lj speech" not in normalize_title(title):
        return None, "no_match"
    url = "https://keithito.com/LJ-Speech-Dataset/"
    page = _request_text(
        session,
        url,
        source="keithito",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", page)
    page_meta = _extract_html_meta_tags(page)
    abstract = _normalize_whitespace(meta_desc.group(1)) if meta_desc else ""
    if not abstract:
        return None, "no_match_or_no_description"
    title_match = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    dataset_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
    result = FetchResult(
        title=dataset_title,
        abstract=abstract,
        source="keithito",
        source_id=url,
        match_status="exact_title",
        raw_metadata={
            "url": url,
            "page_meta": page_meta,
            "title": dataset_title,
            "abstract": abstract,
        },
    )
    return result, "match"


# --- Source: Zenodo ---

def _fetch_zenodo_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    if not query_title:
        return None, "no_match"
    params = {"q": f'title:"{query_title}"', "size": 5}
    payload = _request_json(
        session,
        "https://zenodo.org/api/records/",
        source="zenodo",
        limiter=limiter,
        params=params,
        headers={"User-Agent": USER_AGENT},
    )
    hits = payload.get("hits", {}).get("hits")
    if not isinstance(hits, list):
        return None, "no_match"

    candidates = []
    for item in hits:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") or {}
        candidates.append(
            {
                "title": metadata.get("title") or "",
                "description": metadata.get("description") or "",
                "id": item.get("id") or "",
                "raw": item,
            }
        )

    matched, _, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match"

    abstract = _normalize_whitespace(_strip_html(matched.get("description")))
    if not abstract:
        return None, "no_match_or_no_description"

    result = FetchResult(
        title=_normalize_whitespace(matched.get("title")),
        abstract=abstract,
        source="zenodo",
        source_id=str(matched.get("id")),
        match_status=match_status,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else matched,
    )
    return result, "match"


def _build_metadata_record(entry: Dict[str, Any], result: Optional[FetchResult]) -> Dict[str, Any]:
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
                "source": "missing",
                "source_id": None,
                "match_status": "missing",
                "missing_reason": "not_found",
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


def _build_sources_record(entry: Dict[str, Any], result: Optional[FetchResult]) -> Dict[str, Any]:
    if result is None:
        return {
            "key": entry.get("key"),
            "title": entry.get("query_title"),
            "source": None,
            "source_id": None,
            "match_status": "missing",
            "abstract_present": False,
            "abstract_source": "missing",
            "abstract_source_reason": "missing:abstract_unavailable",
        }

    return {
        "key": entry.get("key"),
        "title": result.title,
        "source": result.source,
        "source_id": result.source_id,
        "match_status": result.match_status,
        "abstract_present": True,
        "abstract_source": result.source,
        "abstract_source_reason": f"{result.source}:{result.match_status}",
    }


def _build_full_metadata_record(entry: Dict[str, Any], result: Optional[FetchResult]) -> Dict[str, Any]:
    if result is None:
        return {
            "key": entry.get("key"),
            "title": entry.get("query_title"),
            "source": None,
            "source_id": None,
            "match_status": "missing",
            "source_metadata": None,
        }
    return {
        "key": entry.get("key"),
        "title": result.title,
        "source": result.source,
        "source_id": result.source_id,
        "match_status": result.match_status,
        "source_metadata": _prune_heavy_source_fields(result.source, result.raw_metadata),
    }


def _load_records_by_key(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    records: Dict[str, Dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            key = item.get("key")
            if key:
                records[str(key)] = item
    return records


def _write_jsonl(path: Path, records: list[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            if record is None:
                continue
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _collect_single_input(
    input_path: Path,
    output_dir: Path,
    *,
    limit: Optional[int],
    allow_fuzzy: bool,
    min_similarity: float,
    arxiv_max_results: int,
    semantic_max_results: int,
    dblp_max_results: int,
    openalex_max_results: int,
    crossref_max_results: int,
    include_full_metadata: bool,
    checkpoint_every: int,
    resume: bool,
) -> tuple[int, int, int, float]:
    """Collect title/abstract metadata for a single reference_oracle input."""
    metadata_path = output_dir / "title_abstracts_metadata.jsonl"
    sources_path = output_dir / "title_abstracts_sources.jsonl"
    trace_path = output_dir / "title_abstracts_source_trace.jsonl"
    full_metadata_path = output_dir / "title_abstracts_full_metadata.jsonl"

    entries = _load_reference_entries(input_path)
    if limit:
        entries = entries[:limit]

    existing_metadata = _load_records_by_key(metadata_path) if resume else {}
    existing_sources = _load_records_by_key(sources_path) if resume else {}
    existing_traces = _load_records_by_key(trace_path) if resume else {}
    existing_full_metadata = (
        _load_records_by_key(full_metadata_path)
        if resume and include_full_metadata
        else {}
    )

    semantic_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")

    limiter = RateLimiter(RATE_LIMITS)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    metadata_records: Dict[str, Dict[str, Any]] = {}
    sources_records: Dict[str, Dict[str, Any]] = {}
    trace_records: Dict[str, Dict[str, Any]] = {}
    full_metadata_records: Dict[str, Dict[str, Any]] = {}

    start = time.perf_counter()
    processed = 0
    total = len(entries)

    for idx, entry in enumerate(entries, start=1):
        key = str(entry.get("key"))
        if not key:
            continue

        if resume and key in existing_metadata:
            existing = existing_metadata[key]
            has_full_metadata = key in existing_full_metadata
            can_skip = existing.get("match_status") != "missing"
            if include_full_metadata and not has_full_metadata:
                can_skip = False
            if can_skip:
                metadata_records[key] = existing
                if key in existing_sources:
                    sources_records[key] = existing_sources[key]
                if key in existing_traces:
                    trace_records[key] = existing_traces[key]
                if include_full_metadata and key in existing_full_metadata:
                    full_metadata_records[key] = existing_full_metadata[key]
                continue

        title = _title_from_entry(entry)
        candidate_arxiv = _extract_arxiv_id([title] + _candidate_strings(entry))
        trace_steps: list[str] = []
        result: Optional[FetchResult] = None
        candidate_doi: Optional[str] = None
        openalex_landing_url: Optional[str] = None

        # 1) arXiv
        try:
            if candidate_arxiv:
                metadata = _fetch_arxiv_metadata_by_id(session, limiter, candidate_arxiv) or {}
                abstract = _normalize_whitespace(metadata.get("summary"))
                if abstract:
                    result = FetchResult(
                        title=_normalize_whitespace(metadata.get("title")),
                        abstract=abstract,
                        source="arxiv",
                        source_id=candidate_arxiv,
                        match_status="exact_id",
                        raw_metadata=metadata,
                    )
                    trace_steps.append("arxiv:match")
                else:
                    trace_steps.append("arxiv:no_match_or_no_abstract")
            else:
                result, status = _fetch_arxiv_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=arxiv_max_results,
                )
                trace_steps.append(f"arxiv:{status}")
        except Exception as exc:  # noqa: BLE001
            trace_steps.append(f"arxiv:error_{type(exc).__name__}")
            result = None

        # 2) Semantic Scholar
        if result is None:
            try:
                result, status = _fetch_semantic_by_title(
                    session,
                    limiter,
                    title,
                    api_key=semantic_api_key,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=semantic_max_results,
                )
                trace_steps.append(f"semantic_scholar:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"semantic_scholar:error_{type(exc).__name__}")
                result = None

        # 3) DBLP (for DOI hint)
        if result is None:
            try:
                candidate_doi, status = _fetch_dblp_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=dblp_max_results,
                )
                trace_steps.append(f"dblp:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"dblp:error_{type(exc).__name__}")
                candidate_doi = None

        # 4) OpenAlex
        if result is None:
            try:
                result, status, openalex_doi, landing_url = _fetch_openalex_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=openalex_max_results,
                )
                trace_steps.append(f"openalex:{status}")
                if openalex_doi and not candidate_doi:
                    candidate_doi = openalex_doi
                if landing_url:
                    openalex_landing_url = landing_url
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"openalex:error_{type(exc).__name__}")
                result = None

        # 5) Crossref
        if result is None:
            try:
                result, status = _fetch_crossref_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=crossref_max_results,
                    candidate_doi=candidate_doi,
                )
                trace_steps.append(f"crossref:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"crossref:error_{type(exc).__name__}")
                result = None

        # 6) ACL Anthology
        if result is None:
            try:
                result, status = _fetch_acl_anthology_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                )
                trace_steps.append(f"acl_anthology:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"acl_anthology:error_{type(exc).__name__}")
                result = None

        # 7) LREC summary (using OpenAlex landing page)
        if result is None:
            try:
                result, status = _fetch_lrec_summary(
                    session,
                    limiter,
                    openalex_landing_url,
                )
                trace_steps.append(f"lrec_conf:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"lrec_conf:error_{type(exc).__name__}")
                result = None

        # 8) RFC Editor
        if result is None:
            try:
                result, status = _fetch_rfc_editor_by_title(
                    session,
                    limiter,
                    title,
                )
                trace_steps.append(f"rfc_editor:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"rfc_editor:error_{type(exc).__name__}")
                result = None

        # 9) BSI
        if result is None:
            try:
                result, status = _fetch_bsi_by_title(
                    session,
                    limiter,
                    title,
                )
                trace_steps.append(f"bsi:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"bsi:error_{type(exc).__name__}")
                result = None

        # 10) GitHub
        if result is None:
            try:
                result, status = _fetch_github_by_title(
                    session,
                    limiter,
                    title,
                    github_token=github_token,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                )
                trace_steps.append(f"github:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"github:error_{type(exc).__name__}")
                result = None

        # 11) Hugging Face
        if result is None:
            try:
                result, status = _fetch_huggingface_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                )
                trace_steps.append(f"huggingface:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"huggingface:error_{type(exc).__name__}")
                result = None

        # 12) Keithito
        if result is None:
            try:
                result, status = _fetch_keithito_by_title(
                    session,
                    limiter,
                    title,
                )
                trace_steps.append(f"keithito:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"keithito:error_{type(exc).__name__}")
                result = None

        # 13) Zenodo
        if result is None:
            try:
                result, status = _fetch_zenodo_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                )
                trace_steps.append(f"zenodo:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"zenodo:error_{type(exc).__name__}")
                result = None

        metadata_records[key] = _build_metadata_record(entry, result)
        sources_records[key] = _build_sources_record(entry, result)
        trace_records[key] = {"key": key, "lookup_steps": trace_steps}
        if include_full_metadata:
            full_metadata_records[key] = _build_full_metadata_record(entry, result)

        processed += 1
        if checkpoint_every > 0 and processed % checkpoint_every == 0:
            ordered_keys = [str(e.get("key")) for e in entries if e.get("key")]
            _write_jsonl(
                metadata_path,
                [metadata_records.get(k) for k in ordered_keys],
            )
            _write_jsonl(
                sources_path,
                [sources_records.get(k) for k in ordered_keys],
            )
            _write_jsonl(
                trace_path,
                [trace_records.get(k) for k in ordered_keys],
            )
            if include_full_metadata:
                _write_jsonl(
                    full_metadata_path,
                    [full_metadata_records.get(k) for k in ordered_keys],
                )

        if idx % 10 == 0 or idx == total:
            print(f"[{idx}/{total}] processed: {key}")

    ordered_keys = [str(e.get("key")) for e in entries if e.get("key")]
    _write_jsonl(
        metadata_path,
        [metadata_records.get(k) for k in ordered_keys],
    )
    _write_jsonl(
        sources_path,
        [sources_records.get(k) for k in ordered_keys],
    )
    _write_jsonl(
        trace_path,
        [trace_records.get(k) for k in ordered_keys],
    )
    if include_full_metadata:
        _write_jsonl(
            full_metadata_path,
            [full_metadata_records.get(k) for k in ordered_keys],
        )

    matched = sum(
        1
        for record in metadata_records.values()
        if record.get("match_status") != "missing"
    )
    missing = max(len(ordered_keys) - matched, 0)
    elapsed = time.perf_counter() - start
    return processed, matched, missing, elapsed


def _collect_all_reference_oracles(
    input_root: Path,
    output_root: Path,
    paper_name: Optional[str],
    *,
    limit: Optional[int],
    allow_fuzzy: bool,
    min_similarity: float,
    arxiv_max_results: int,
    semantic_max_results: int,
    dblp_max_results: int,
    openalex_max_results: int,
    crossref_max_results: int,
    include_full_metadata: bool,
    checkpoint_every: int,
    resume: bool,
) -> list[tuple[str, int, int, int, float]]:
    """Run collection for one or more ``reference_oracle.jsonl`` files."""
    if not input_root.exists():
        raise FileNotFoundError(f"Input root not found: {input_root}")
    if not input_root.is_dir():
        raise NotADirectoryError(f"Input root is not a directory: {input_root}")

    files = [input_root / paper_name / "reference_oracle.jsonl"] if paper_name else sorted(input_root.glob("*/reference_oracle.jsonl"))
    if paper_name and not files[0].exists():
        raise FileNotFoundError(f"Reference file not found: {files[0]}")

    summaries: list[tuple[str, int, int, int, float]] = []
    for file_path in files:
        if not file_path.exists():
            raise FileNotFoundError(f"Reference file not found: {file_path}")

        paper_dir = file_path.parent
        target_output_dir = output_root / paper_dir.name / "metadata"
        print(f"[start] {paper_dir.name} -> {target_output_dir}")
        processed, matched, missing, elapsed = _collect_single_input(
            file_path,
            target_output_dir,
            limit=limit,
            allow_fuzzy=allow_fuzzy,
            min_similarity=min_similarity,
            arxiv_max_results=arxiv_max_results,
            semantic_max_results=semantic_max_results,
            dblp_max_results=dblp_max_results,
            openalex_max_results=openalex_max_results,
            crossref_max_results=crossref_max_results,
            include_full_metadata=include_full_metadata,
            checkpoint_every=checkpoint_every,
            resume=resume,
        )
        summaries.append((paper_dir.name, processed, matched, missing, elapsed))
        print(
            "[done] {paper}: entries={entries}, matched={matched}, missing={missing}, elapsed={elapsed:.2f}s".format(
                paper=paper_dir.name,
                entries=processed,
                matched=matched,
                missing=missing,
                elapsed=elapsed,
            )
        )
    return summaries


def main() -> int:
    """CLI entrypoint for title/abstract harvesting."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=str,
        default="bib/per_SR_cleaned",
        help="Directory containing per-paper reference_oracle.jsonl inputs.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="refs",
        help="Root directory for metadata outputs.",
    )
    parser.add_argument(
        "--paper-name",
        type=str,
        default=None,
        help="Optional paper folder name under input-root to process a single paper.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional max entries.")
    parser.add_argument(
        "--allow-fuzzy",
        type=parse_bool,
        default=True,
        help="Allow fuzzy title matches (default: true).",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.9,
        help="Minimum Jaccard similarity for fuzzy matches.",
    )
    parser.add_argument("--arxiv-max-results", type=int, default=5)
    parser.add_argument("--semantic-max-results", type=int, default=5)
    parser.add_argument("--openalex-max-results", type=int, default=5)
    parser.add_argument("--crossref-max-results", type=int, default=5)
    parser.add_argument("--dblp-max-results", type=int, default=5)
    parser.add_argument(
        "--resume",
        type=parse_bool,
        default=False,
        help="Reuse existing outputs and skip matched entries.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=1,
        help="Rewrite outputs after this many processed entries.",
    )
    parser.add_argument(
        "--include-full-metadata",
        type=parse_bool,
        default=True,
        help="Export source full metadata to title_abstracts_full_metadata.jsonl.",
    )
    args = parser.parse_args()

    load_env_file()

    start = time.perf_counter()

    totals = _collect_all_reference_oracles(
        Path(args.input_root),
        Path(args.output_root),
        args.paper_name,
        limit=args.limit,
        allow_fuzzy=args.allow_fuzzy,
        min_similarity=args.min_similarity,
        arxiv_max_results=args.arxiv_max_results,
        semantic_max_results=args.semantic_max_results,
        dblp_max_results=args.dblp_max_results,
        openalex_max_results=args.openalex_max_results,
        crossref_max_results=args.crossref_max_results,
        include_full_metadata=args.include_full_metadata,
        checkpoint_every=args.checkpoint_every,
        resume=args.resume,
    )
    elapsed = time.perf_counter() - start
    total_processed = sum(item[1] for item in totals)
    total_matched = sum(item[2] for item in totals)
    total_missing = sum(item[3] for item in totals)
    print(
        f"Completed: papers={len(totals)}, entries={total_processed}, matched={total_matched}, missing={total_missing}, elapsed={elapsed:.2f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
