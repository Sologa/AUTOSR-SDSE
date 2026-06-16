#!/usr/bin/env python3
"""依來源優先序補齊 title/abstract。

這支腳本會讀取 `reference_oracle.jsonl`，依序查詢多個來源，為每筆
reference 產生三類主要產物：

- `title_abstracts_metadata.jsonl`
- `title_abstracts_sources.jsonl`
- `title_abstracts_source_trace.jsonl`

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
import subprocess
import tempfile
from collections import OrderedDict
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import quote, unquote, urljoin, urlparse

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
    try:
        from target_papers.scripts.title_normalization import normalize_title, split_words  # type: ignore  # noqa: E402
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
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\]\[\)\(<>\"',]+", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
HTTP_URL_RE = re.compile(r"https?://[^\s\"']+")
DOI_STRIP_CHARS = "[]{}()<>\"'`.,;:!?"
URL_TRAILING_PUNCTUATION = ".,;:!?)]}'\"`"
PREFERRED_PUBLICATION_DATE_KEYS = (
    "publicationDate",
    "publication_year",
    "publicationYear",
    "publication_date",
)

DEFAULT_SECONDARY_METADATA_CACHE_PATHS = (
    "paper_metadata_final.json",
    "verified_31_papers_metadata.json",
)

DATE_KEYS = (
    "publicationDate",
    "publication_year",
    "publicationYear",
    "publication_date",
    "published",
    "published-date",
    "date",
    "year",
    "issued",
    "created",
    "published-online",
    "published_print",
    "published-print",
    "created-date",
    "accepted",
    "submitted",
)
ABSTRACT_MIN_CHARS = 40
ABSTRACT_MIN_WORDS = 6
ABSTRACT_INVALID_VALUES = {
    "",
    ",",
    "n/a",
    "na",
    "none",
    "null",
    "undefined",
    "-",
    "proceedings",
}
ABSTRACT_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?$"
)
ABSTRACT_ISO_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
ABSTRACT_YEAR_MONTH_RE = re.compile(r"^\d{4}-\d{1,2}$")
ABSTRACT_YEAR_RE = re.compile(r"^\d{4}$")
ABSTRACT_SENTENCE_DELIMITERS = (".", "?", "!")
ABSTRACT_BANNED_PATTERNS = (
    re.compile(r"max\s+challenge\s+attempts\s+exceeded", re.IGNORECASE),
    re.compile(r"please\s+refresh\s+the\s+page", re.IGNORECASE),
    re.compile(r"markdown\s+content:", re.IGNORECASE),
    re.compile(r"^\s*title\s*:\s*url\s*source\b", re.IGNORECASE),
    re.compile(r"not\s+found|404\b", re.IGNORECASE),
    re.compile(r"\bproceedings\s+of\s+the\b", re.IGNORECASE),
    re.compile(r"\bhas\s+\d+\s+repositories\s+available\b", re.IGNORECASE),
    re.compile(r"\bfollow\s+(?:their|his|her)\s+code\s+on\s+github\b", re.IGNORECASE),
)
ABSTRACT_KEYWORD_HINTS = (
    "this paper",
    "we",
    "we propose",
    "we present",
    "we introduce",
    "this work",
    "this study",
    "in this paper",
    "our",
    "proposed",
    "propose",
    "present",
    "present a",
    "evaluat",
    "method",
    "approach",
)

ACL_DOI_PREFIX = "10.18653/v1/"
OPENALEX_DOI_PREFIX = "10.48550/"
Ieee_DOI_PREFIX = "10.1109/"
TITLE_NOISE_KEYWORDS = (
    "proceedings",
    "conference",
    "workshop",
    "journal",
    "review",
    "coling",
    "aaai",
    "acl",
    "emnlp",
    "icml",
    "ijcai",
    "acm",
    "dialogsum",
)

SOURCE_ORDER = [
    "arxiv",
    "semantic_scholar",
    "dblp",
    "openalex",
    "crossref",
    "google_books",
    "acl_anthology",
    "lrec_conf",
    "rfc_editor",
    "bsi",
    "github",
    "huggingface",
    "keithito",
    "zenodo",
]
SOURCE_RANK = {source: index for index, source in enumerate(SOURCE_ORDER)}
EARLY_STOP_SOURCES = { 
    "arxiv",
    "semantic_scholar",
    "openalex",
    "crossref",
    "google_books",
    "acl_anthology",
    "lrec_conf",
}

RATE_LIMITS = {
    "arxiv": 0.1,
    "semantic_scholar": 1.0,
    "dblp": 1.0,
    "openalex": 1.0,
    "crossref": 1.0,
    "google_books": 1.0,
    "acl_anthology": 1.0,
    "lrec_conf": 1.0,
    "rfc_editor": 1.0,
    "bsi": 1.0,
    "github": 6.0,
    "huggingface": 1.0,
    "keithito": 1.0,
    "zenodo": 1.0,
    "fallback": 1.0,
    "url_fallback": 1.0,
}

URL_REDIRECT_LIMIT = 3
JINA_MIRROR_PREFIX = "https://r.jina.ai/http://"
PDF_TO_TEXT_TIMEOUT = 25
PDF_TO_TEXT_MAX_CHARS = 120_000
REQUEST_TIMEOUT_SECONDS = (5.0, 15.0)
REQUEST_MAX_RETRIES = 2
MAX_RETRY_WAIT_SECONDS = 8.0

USER_AGENT = "autosr-sdse/collect-title-abstracts"
ARXIV_API_URL = "https://export.arxiv.org/api/query"
GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"
GOOGLE_BOOKS_MAX_QUERY_VARIANTS = 4
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
    match_score:
        Matching confidence between query title and source title.
    raw_metadata:
        Raw source payload (or best-effort full metadata) for traceability.
    """

    title: str
    abstract: str
    source: str
    source_id: str
    match_status: str
    match_score: float
    publication_date: Optional[str]
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


def _normalize_title_signature(text: str) -> str:
    """Return a compact, punctuation-safe signature for title-like comparison."""
    normalized = _normalize_latex_title(text)
    normalized = _normalize_whitespace(normalized.lower())
    normalized = re.sub(r"\b(proceedings|journal|conference|workshop|review|proceedings of)\b", "", normalized)
    normalized = re.sub(r"\W+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return _normalize_whitespace(normalized)


def _jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(split_words(left))
    right_tokens = set(split_words(right))
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _prepare_title_query(title: str) -> str:
    return _normalize_whitespace(_normalize_latex_title(title))


def _normalize_latex_title(text: str) -> str:
    cleaned = html.unescape(text or "")
    cleaned = cleaned.replace("\\_", " ")
    cleaned = cleaned.replace("_", " ")
    cleaned = re.sub(r"\\textbar|\\textemdash|\\textendash", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}",
        r"\\1",
        cleaned,
    )
    cleaned = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", cleaned)
    cleaned = cleaned.replace("{", "").replace("}", "")
    cleaned = cleaned.replace("\\", " ")
    cleaned = cleaned.replace('"', " ")
    cleaned = re.sub(r"[\\s,]*(19|20)\\d{2}\\s*$", "", cleaned)
    return _normalize_whitespace(cleaned)


def _is_likely_metadata_fragment(value: str) -> bool:
    value = _normalize_whitespace(value)
    if not value:
        return False
    lowered = value.lower()
    if re.search(r"\b(19|20)\d{2}\b", lowered):
        return True
    if len(value.split()) <= 6:
        return any(keyword in lowered for keyword in TITLE_NOISE_KEYWORDS)
    if value.isupper():
        return True
    return False


def _build_title_variants(title: str) -> list[str]:
    """Build a short list of robust query variants from a possibly LaTeX-escaped title."""
    base = _normalize_whitespace(_normalize_latex_title(title))
    if not base:
        return []

    variants: list[str] = [base]
    compact = re.sub(r"\s+", " ", base).strip()
    if compact and compact != base:
        variants.append(compact)

    def _append(value: str) -> None:
        value = _normalize_whitespace(value)
        if value and value not in variants:
            variants.append(value)

    # Direct separator splits.
    for sep in ("|", " - ", " -- ", "\\textbar"):
        if sep in compact:
            left, right = compact.split(sep, 1)
            _append(left)
            if not _is_likely_metadata_fragment(right):
                _append(right)

    if "@" in compact:
        left, right = compact.split("@", 1)
        _append(left)
        right = _normalize_whitespace(right)
        if right and ":" in right:
            right_lead, right_tail = right.rsplit(":", 1)
            right_lead = _normalize_whitespace(right_lead)
            if right_lead and _is_likely_metadata_fragment(right_lead):
                _append(right_tail)
            else:
                _append(right)
        else:
            _append(right)

    if ":" in compact:
        lead, tail = compact.split(":", 1)
        lead = _normalize_whitespace(lead)
        tail = _normalize_whitespace(tail)
        if lead:
            if not _is_likely_metadata_fragment(lead):
                _append(lead)
        if tail:
            if not _is_likely_metadata_fragment(tail):
                _append(tail)
        tail = _normalize_whitespace(compact.rsplit(":", 1)[-1])
        if tail:
            variants.append(tail)

    year_suffix_re = re.compile(r"\s*-\s*.*,\s*\d{4}\s*$")
    if year_suffix_re.search(compact):
        _append(year_suffix_re.sub("", compact))
    metadata_suffix_patterns = (
        r"\s+Proceedings\s+of\s+.*$",
        r"\s+Artificial\s+Intelligence\s+Review\s*$",
        r"\s+of\s+the\s+.*\s+Conference\s+on\s+.*$",
        r"\s+\|\s+Proceedings\s+.*$",
    )
    for pattern in metadata_suffix_patterns:
        metadata_re = re.compile(pattern, flags=re.IGNORECASE)
        if metadata_re.search(compact):
            cleaned = _normalize_whitespace(metadata_re.sub("", compact))
            if cleaned and len(cleaned.split()) >= 3:
                _append(cleaned)

    # Remove bracketed / parenthesized metadata blocks if present.
    compacted_parentheses = re.sub(r"\([^)]*\)", "", compact).strip()
    compacted_parentheses = re.sub(r"\s+", " ", compacted_parentheses)
    if compacted_parentheses:
        variants.append(compacted_parentheses)

    compacted_brackets = re.sub(r"\[[^\]]*\]", "", compact).strip()
    compacted_brackets = re.sub(r"\s+", " ", compacted_brackets)
    if compacted_brackets:
        variants.append(compacted_brackets)

    compacted_dual = _normalize_whitespace(compact.replace("&", "and"))
    if compacted_dual:
        variants.append(compacted_dual)

    deduped = _dedupe_values(_normalize_whitespace(v) for v in variants if v)
    return deduped


def _normalize_metadata_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return _normalize_whitespace(" ".join(str(item) for item in value if item is not None))
    if isinstance(value, dict):
        for key in ("normalized", "default", "name", "title", "text", "description", "value", "abstract", "summary"):
            if key in value:
                converted = _normalize_metadata_value(value.get(key))
                if converted:
                    return converted
        return _normalize_whitespace(" ".join(
            str(item) for item in value.values() if isinstance(item, (str, int, float))
        ))
    return _normalize_whitespace(str(value))


def _normalize_url(url: str) -> str:
    url = _normalize_whitespace(url)
    if not url:
        return ""
    url = _strip_bib_field_markers(url)
    url = url.rstrip("/")
    url = url.rstrip(URL_TRAILING_PUNCTUATION)
    url = url.strip()
    if (url.startswith("(") and url.endswith(")")) or (
        url.startswith("[") and url.endswith("]")
    ) or (url.startswith("{") and url.endswith("}")) or (
        url.startswith("<") and url.endswith(">")
    ):
        url = url[1:-1].strip()
    if url.startswith("/doi/"):
        return f"https://doi.org{url}"
    if url.startswith("doi:"):
        return _normalize_url(url.replace("doi:", "https://doi.org/"))
    return url


def _strip_bib_field_markers(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    value = value.strip("{}")
    value = re.sub(r"^\\(?:textasciitilde|textbar|textemdash)\{", "", value)
    return _normalize_whitespace(value)


def _dedupe_values(values: Iterable[str]) -> list[str]:
    ordered: OrderedDict[str, str] = OrderedDict()
    for value in values:
        if not value:
            continue
        normalized = _strip_bib_field_markers(_normalize_whitespace(value))
        if not normalized:
            continue
        ordered[normalized] = value.strip()
    return list(ordered.keys())


def _extract_arxiv_ids(values: Iterable[str]) -> list[str]:
    arxiv_ids: list[str] = []
    for value in values:
        if not value:
            continue
        arxiv_ids.extend(match.group("id") for match in ARXIV_ID_RE.finditer(value))
    return _dedupe_values(arxiv_ids)


def _extract_dois(values: Iterable[str]) -> list[str]:
    dois: list[str] = []
    for value in values:
        if not value:
            continue
        for match in DOI_RE.finditer(value):
            doi = _normalize_doi(match.group(0))
            if doi:
                dois.append(doi)
    return _dedupe_values(dois)


def _collect_dois_from_metadata(
    value: Any,
    *,
    max_depth: int = 6,
) -> list[str]:
    """Recursively collect DOI-like strings from arbitrary metadata objects."""

    found: list[str] = []
    if max_depth <= 0:
        return found

    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and any(token in key.lower() for token in ("doi", "crossref")):
                found.extend(_extract_dois([str(nested)] if nested is not None else []))
            if isinstance(nested, (str, dict, list, tuple, set)):
                found.extend(_collect_dois_from_metadata(nested, max_depth=max_depth - 1))
        return _dedupe_values(found)

    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, (str, dict, list, tuple, set)):
                found.extend(_collect_dois_from_metadata(item, max_depth=max_depth - 1))
        return _dedupe_values(found)

    if isinstance(value, str):
        found.extend(_extract_dois([value]))
    return _dedupe_values(found)


def _normalize_doi(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = _normalize_whitespace(_normalize_metadata_value(value))
    if not normalized:
        return None
    normalized = normalized.lower()
    normalized = normalized.strip(DOI_STRIP_CHARS)
    normalized = re.sub(r"^doi:\s*", "", normalized)
    normalized = normalized.strip(DOI_STRIP_CHARS)
    return normalized


def _extract_urls(values: Iterable[str]) -> list[str]:
    urls: list[str] = []
    for value in values:
        if not value:
            continue
        for match in HTTP_URL_RE.finditer(value):
            url = _normalize_url(match.group(0))
            if url:
                urls.append(url)
    return _dedupe_values(urls)


def _extract_file_paths(values: Iterable[str]) -> list[str]:
    pattern = re.compile(r"(?i)(?:file://)?(?:[A-Za-z]:\\\\|/)?[^\\s\"'`<>\\[\\]]+\\.pdf\\b")
    paths: list[str] = []
    for value in values:
        if not value:
            continue
        cleaned = _normalize_whitespace(value)
        if not cleaned:
            continue
        paths.extend(match.group(0) for match in pattern.finditer(cleaned))
    return _dedupe_values(paths)


def _candidate_urls_from_doi(doi: Optional[str]) -> list[str]:
    doi = _normalize_doi(doi)
    if not doi:
        return []
    urls: list[str] = [_make_doi_url(doi)]
    if doi.lower().startswith(ACL_DOI_PREFIX):
        suffix = doi.split("/", 1)[-1]
        suffix = re.sub(r"^v\d+/", "", suffix)
        acl_suffixes = {suffix.lower(), suffix.upper()}
        for acl_suffix in acl_suffixes:
            urls.append(f"https://aclanthology.org/{acl_suffix}")
            urls.append(f"https://aclanthology.org/{acl_suffix}.pdf")
    if doi.lower().startswith(OPENALEX_DOI_PREFIX):
        suffix = doi.split("/", 1)[-1]
        urls.append(f"https://doi.org/{doi}")
    if doi.lower().startswith(Ieee_DOI_PREFIX):
        suffix = doi.split("/", 1)[-1]
        urls.append(f"https://ieeexplore.ieee.org/document/{suffix}")
        urls.append(f"https://www.semanticscholar.org/search?q={quote(doi)}")
    return _dedupe_values(urls)


def _normalize_fallback_url(url: str) -> list[str]:
    normalized = _normalize_url(url)
    if not normalized:
        return []
    if normalized.startswith("file://"):
        normalized = normalized.replace("file://", "", 1)
    candidates = [normalized]
    if normalized.startswith("http://"):
        candidates.append("https://" + normalized[len("http://") :])
    if normalized.startswith("https://"):
        candidates.append("http://" + normalized[len("https://") :])
    doi_match = DOI_RE.search(normalized)
    if doi_match:
        doi = _normalize_doi(doi_match.group(0))
        candidates.extend(_candidate_urls_from_doi(doi))
    return _dedupe_values(candidates)


def _url_redirect_candidates(url: str) -> list[str]:
    normalized_urls = _normalize_fallback_url(url)
    result: list[str] = []
    for candidate in normalized_urls:
        if not candidate:
            continue
        if candidate.startswith("http://") or candidate.startswith("https://"):
            result.append(candidate)
            mirror_candidate = candidate
            if mirror_candidate.startswith("https://"):
                mirror_candidate = mirror_candidate[len("https://") :]
            elif mirror_candidate.startswith("http://"):
                mirror_candidate = mirror_candidate[len("http://") :]
            for attempt in range(1, max(1, URL_REDIRECT_LIMIT + 1)):
                if attempt == 1:
                    result.append(f"{JINA_MIRROR_PREFIX}{mirror_candidate}")
                else:
                    # Keep one mirror per URL to avoid amplification.
                    break
            continue
        result.append(candidate)
    return _dedupe_values(result)


def _extract_year(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1000 <= value <= 2500 else None
    text = _normalize_metadata_value(value)
    if not text:
        return None
    match = YEAR_RE.search(text)
    if not match:
        return None
    year = int(match.group(0))
    return year if 1000 <= year <= 2500 else None


def _to_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        year = int(value)
        if 1000 <= year <= 2500:
            return f"{year:04d}-01-01"
        return None
    if isinstance(value, str):
        text = _normalize_metadata_value(value).replace("/", "-")
        if not text:
            return None
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
            return text
        if re.fullmatch(r"\d{4}-\d{1,2}", text):
            parts = text.split("-", 1)
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-01"
        if re.fullmatch(r"\d{4}", text):
            return f"{text}-01-01"
        if "T" in text and "Z" in text and "-" in text:
            text = text.replace("Z", "")
            text = text.replace("T", " ")
            text = text[:10]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                return text
        match = YEAR_RE.search(text)
        if match:
            year = int(match.group(0))
            return f"{year:04d}-01-01"
        return None
    if isinstance(value, dict):
        date_parts = value.get("date-parts")
        if isinstance(date_parts, list):
            first = date_parts[0] if date_parts else None
            if isinstance(first, list):
                year = _extract_year(first[0]) if first else None
                month = _extract_year(first[1]) if len(first) > 1 else None
                day = _extract_year(first[2]) if len(first) > 2 else None
                if year:
                    return f"{year:04d}-{(month or 1):02d}-{(day or 1):02d}"
        year = _extract_year(value.get("year"))
        if year:
            return f"{year:04d}-01-01"
    if isinstance(value, list):
        for item in value:
            parsed = _to_iso_date(item)
            if parsed:
                return parsed
    return None


def _extract_publication_date(metadata: Dict[str, Any]) -> Optional[str]:
    if not isinstance(metadata, dict):
        return None

    def _find_first_by_keys(keys: tuple[str, ...]) -> Optional[str]:
        normalized: Dict[str, Any] = {}
        for key, value in metadata.items():
            if not isinstance(key, str):
                continue
            lowered = _normalize_whitespace(key).lower()
            normalized[lowered] = value
            normalized[lowered.replace("_", "-")] = value
            normalized[lowered.replace("-", "_")] = value
            normalized[lowered.replace(":", "")] = value
            normalized[lowered.replace(":", "_")] = value
            normalized[lowered.replace(":", "-")] = value
            normalized[lowered.replace(".", "")] = value
        for key in keys:
            normalized_candidates = (key, key.replace("_", "-"), key.replace("-", "_"), key.replace(":", ""), key.replace(":", "_"), key.replace(":", "-"), key.replace(".", ""), key.replace(".", "_"))
            for candidate_key in normalized_candidates:
                if candidate_key in normalized:
                    parsed = _to_iso_date(normalized[candidate_key])
                    if parsed:
                        return parsed
        return None

    direct_key = _find_first_by_keys(
        (
            "publicationDate",
            "publication_year",
            "publicationYear",
            "publication_date",
            "published",
            "published-date",
            "date",
            "year",
            "issued",
            "created",
            "published-online",
            "published_print",
            "published-print",
            "created-date",
            "accepted",
            "submitted",
            "citation_publication_date",
            "citation_date",
            "dc.date",
            "dc.date.issued",
            "dc.date.created",
            "dcterms.issued",
            "dcterms.created",
            "prism.publicationDate",
            "prism.publication.date",
            "datepublished",
            "date_published",
            "og:article:published_time",
            "og:article:published-time",
            "pubdate",
            "publication-date",
        )
    )
    if direct_key:
        return direct_key

    # Crossref-like nested date objects.
    for key in ("published", "issued", "accepted", "created", "published_print", "published-online"):
        nested = metadata.get(key)
        if isinstance(nested, dict):
            for nested_key in ("date-parts", "date"):
                parsed = _to_iso_date(nested.get(nested_key))
                if parsed:
                    return parsed
        if isinstance(nested, list):
            parsed = _to_iso_date(nested)
            if parsed:
                return parsed
        if isinstance(nested, str):
            parsed = _to_iso_date(nested)
            if parsed:
                return parsed
    for key in ("published-online", "published-print"):
        nested = metadata.get(key)
        if isinstance(nested, dict):
            parsed = _extract_publication_date(nested)
            if parsed:
                return parsed
    for raw_key, value in metadata.items():
        if not isinstance(raw_key, str):
            continue
        normalized_key = _normalize_whitespace(raw_key).lower().replace("-", "").replace("_", "")
        if any(
            token in normalized_key
            for token in (
                "date",
                "year",
                "published",
                "issued",
                "created",
                "accepted",
                "submitted",
            )
        ):
            parsed = _to_iso_date(value)
            if parsed:
                return parsed
    return None


def _abstract_candidate_is_valid(
    abstract: str,
    *,
    min_chars: int = ABSTRACT_MIN_CHARS,
    min_words: int = ABSTRACT_MIN_WORDS,
) -> bool:
    text = _normalize_whitespace(abstract)
    if not text:
        return False
    lowered = text.lower()
    if lowered in ABSTRACT_INVALID_VALUES:
        return False
    if len(text) < min_chars:
        return False
    if ABSTRACT_DATETIME_RE.fullmatch(text):
        return False
    if ABSTRACT_ISO_DATE_RE.fullmatch(text):
        return False
    if ABSTRACT_YEAR_MONTH_RE.fullmatch(text):
        return False
    if ABSTRACT_YEAR_RE.fullmatch(text):
        return False
    alphabetic_words = re.findall(r"[A-Za-z]{3,}", text)
    if len(alphabetic_words) < min_words:
        return False
    alpha_chars = sum(ch.isalpha() for ch in text)
    if not text:
        return False
    if alpha_chars / len(text) < 0.1:
        return False
    if lowered.startswith(("proceedings", "accessibility", "copyright")):
        return False
    if any(pattern.search(text) for pattern in ABSTRACT_BANNED_PATTERNS):
        return False
    return True


def _is_title_like_text(text: str, *, title: str) -> bool:
    """Return True when `text` appears to be just the paper title.

    This is used to avoid carrying title-only strings into abstract fields,
    especially when local cache contains malformed records.
    """
    if not text or not title:
        return False
    if normalize_title(text) == normalize_title(title):
        return True

    text_signature = _normalize_title_signature(text)
    title_signature = _normalize_title_signature(title)
    if not text_signature or not title_signature:
        return False
    if text_signature == title_signature:
        return True
    text_tokens = set(text_signature.split())
    title_tokens = set(title_signature.split())
    if not text_tokens or not title_tokens:
        return False

    overlap = len(text_tokens & title_tokens)
    if overlap == 0:
        return False
    # If almost all tokens overlap with very small extras, treat as title noise.
    base_len = min(len(text_tokens), len(title_tokens))
    if base_len <= 2:
        return False
    if overlap / base_len >= 0.90:
        # Keep long abstracts (often starting with a phrase sharing many title tokens)
        # even when overlap is high; only treat short/near-title strings as title-noise.
        # This avoids suppressing valid abstracts from cached records where the first
        # sentence reuses a lot of title words.
        if len(text_signature) <= len(title_signature) + 20:
            return True
        if len(text_signature.split()) <= 24 and len(text_signature) <= 240:
            return True
        return False
    if len(text_signature) >= len(title_signature) and (len(text_signature) - len(title_signature)) <= 20:
        return True
    return False


def _extract_abstract(
    metadata: Dict[str, Any],
    source: str = "",
    *,
    title: Optional[str] = None,
    strict: bool = False,
) -> str:
    source = str(source or "").strip().lower()
    normalized_title = normalize_title(title or "") if title else ""
    raw_title = _normalize_whitespace(title)
    if not isinstance(metadata, dict):
        return ""

    non_abstract_values = {
        normalize_title(raw_title),
        _normalize_whitespace(raw_title).lower(),
        _normalize_whitespace(str(metadata.get("title") or "")).lower(),
        _normalize_whitespace(str(metadata.get("display_name") or "")).lower(),
        _normalize_whitespace(str(metadata.get("DOI") or "")).lower(),
    }
    for raw_key in ("container-title", "container_title", "publisher", "issue", "journal-title", "short-container-title", "event", "source"):
        value = metadata.get(raw_key)
        if isinstance(value, str):
            non_abstract_values.add(_normalize_whitespace(value).lower())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    non_abstract_values.add(_normalize_whitespace(item).lower())

    def _is_valid_candidate(text: str) -> bool:
        normalized = _normalize_whitespace(text)
        if not normalized:
            return False
        if normalized_title and normalize_title(normalized) == normalized_title:
            return False
        lowered = normalized.lower()
        if lowered in non_abstract_values:
            return False
        if not _abstract_candidate_is_valid(normalized):
            return False

        has_sentence_mark = any(ch in normalized for ch in ABSTRACT_SENTENCE_DELIMITERS)
        if not has_sentence_mark and not any(keyword in lowered for keyword in ABSTRACT_KEYWORD_HINTS):
            # If no sentence markers, only allow values that look abstract-like by phrase.
            return False
        return True

    def _first_text(payload: Any) -> str:
        text = _normalize_metadata_value(payload)
        if text and "<" in text and ">" in text:
            text = _strip_html(text)
        return _normalize_whitespace(text)

    candidates = (
        "abstract",
        "summary",
        "description",
        "bodyText",
        "text",
        "message.abstract",
        "message.description",
        "message.summary",
    )
    if source in {"openalex"}:
        candidates = ("abstract_inverted_index", "abstract", "summary", "description")
    elif source in {"semantic_scholar"}:
        candidates = (
            "abstract",
            "tldr",
            "tldr.text",
            "summary",
            "description",
            "bodyText",
            "text",
            "message.abstract",
        )
    if source in {
        "local",
        "rfc_editor",
        "bsi",
        "acl_anthology",
        "lrec_conf",
        "github",
        "huggingface",
        "zenodo",
    }:
        candidates = (
            "abstract",
            "summary",
            "description",
            "note",
            "text",
            "bodyText",
            "message.abstract",
            "message.description",
            "message.summary",
        )
        for candidate in _extract_abstract_candidates_from_nested(
            metadata,
            "local",
            ("abstract", "summary", "description", "note", "text", "bodyText"),
        ):
            if _abstract_candidate_is_valid(candidate):
                return candidate
    for key in candidates:
        if key == "abstract_inverted_index":
            text = _openalex_inverted_to_text(metadata.get("abstract_inverted_index"))
            if _is_valid_candidate(text):
                return _normalize_whitespace(text)
            continue
        if "." in key:
            root_key, nested_key = key.split(".", 1)
            root = metadata.get(root_key)
            if isinstance(root, dict):
                text = _first_text(root.get(nested_key))
            else:
                text = ""
        else:
            text = _first_text(metadata.get(key))
        if _is_valid_candidate(text):
            return text
    for candidate in _extract_abstract_text_candidates(metadata, strict=strict):
        normalized = _normalize_whitespace(candidate)
        if _is_valid_candidate(normalized):
            return normalized
    return ""


def _sanitize_fetch_result(result: Optional[FetchResult], title: str) -> Optional[FetchResult]:
    """Normalize and validate fetch result values before ranking/saving."""

    if result is None:
        return None

    normalized_abstract = _normalize_whitespace(result.abstract or "")
    title_for_compare = _normalize_whitespace(title)
    if normalized_abstract and _is_title_like_text(normalized_abstract, title=title_for_compare):
        normalized_abstract = ""
    if normalized_abstract and result.title and _is_title_like_text(normalized_abstract, title=result.title):
        normalized_abstract = ""
    if not normalized_abstract or not _abstract_candidate_is_valid(
        normalized_abstract,
        min_words=max(4, ABSTRACT_MIN_WORDS),
    ):
        normalized_abstract = ""

    normalized_title = _normalize_whitespace(result.title)
    if normalized_title:
        normalized_title = normalize_title(normalized_title)

    if normalized_title and _normalize_whitespace(title):
        candidate_title = normalize_title(title)
        if normalized_title == candidate_title:
            normalized_title = _normalize_whitespace(result.title)

    publication_date = result.publication_date
    if publication_date:
        publication_date = _to_iso_date(publication_date)

    if not publication_date and isinstance(result.raw_metadata, dict):
        publication_date = _extract_publication_date(result.raw_metadata)

    if not normalized_abstract and not publication_date and result.source in {"rfc_editor", "bsi", "github", "huggingface", "keithito", "zenodo"}:
        # Do not keep non-semantic snippets from non-paper sources.
        return FetchResult(
            title=result.title,
            abstract="",
            source=result.source,
            source_id=result.source_id,
            match_status=result.match_status,
            match_score=result.match_score,
            publication_date=None,
            raw_metadata=result.raw_metadata,
        )

    return FetchResult(
        title=normalized_title,
        abstract=normalized_abstract,
        source=result.source,
        source_id=result.source_id,
        match_status=result.match_status,
        match_score=result.match_score,
        publication_date=publication_date,
        raw_metadata=result.raw_metadata,
    )


def _pick_first_valid_abstract(
    metadata: Dict[str, Any],
    title: str,
    *,
    source: str = "",
) -> str:
    title = title or ""
    candidates: list[str] = []
    for _, value in metadata.items():
        if not isinstance(value, (str, int, float, dict, list)):
            continue
        candidates.append(_normalize_metadata_value(value))

    for candidate in candidates:
        if not candidate:
            continue
        if _is_title_like_text(candidate, title=title):
            continue
        if not _abstract_candidate_is_valid(candidate):
            continue
        if source in {"local", "rfc_editor", "bsi", "github", "huggingface", "keithito", "zenodo"} and _is_title_like_text(candidate, title=title):
            continue
        return candidate
    return ""


def _extract_abstract_candidates_from_nested(
    metadata: Dict[str, Any],
    parent_key: str,
    keys: tuple[str, ...],
) -> list[str]:
    parent = metadata.get(parent_key)
    if not isinstance(parent, dict):
        return []
    values: list[str] = []
    for key in keys:
        value = _normalize_metadata_value(parent.get(key))
        if value:
            values.append(value)
    return values


def _extract_abstract_text_candidates(
    payload: Any,
    *,
    max_depth: int = 6,
    strict: bool = False,
) -> list[str]:
    if max_depth <= 0:
        return []
    key_hints = {
        "abstract",
        "summary",
        "description",
        "tldr",
        "bodytext",
        "text",
    }
    recurse_hints = {
        "message",
        "metadata",
        "response",
        "result",
        "data",
        "record",
        "records",
        "item",
        "items",
    }
    candidates: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if not key:
                continue
            normalized_key = str(key).lower().replace("_", "").replace("-", "")
            if any(hint in normalized_key for hint in key_hints):
                text = _normalize_metadata_value(value)
                if text:
                    candidates.append(text)
            if not strict or any(hint in normalized_key for hint in recurse_hints):
                candidates.extend(_extract_abstract_text_candidates(value, max_depth=max_depth - 1, strict=strict))
    elif isinstance(payload, list):
        for item in payload:
            candidates.extend(_extract_abstract_text_candidates(item, max_depth=max_depth - 1, strict=strict))
    elif isinstance(payload, str):
        text = _normalize_whitespace(payload)
        if text and len(text) >= 20:
            candidates.append(text)
    return _dedupe_values([_normalize_metadata_value(item) for item in candidates if _normalize_metadata_value(item)])


def _match_score(
    title: str,
    candidate_title: str,
    *,
    expected_year: Optional[int],
    candidate_year: Optional[int],
) -> tuple[str, str, float]:
    candidate_norm = normalize_title(candidate_title)
    target_norm = normalize_title(title)
    if candidate_norm and candidate_norm == target_norm:
        status = "exact_title"
        return candidate_title, status, 1.0

    similarity = _jaccard_similarity(candidate_title, title)
    confidence = similarity
    if expected_year is not None and candidate_year is not None:
        if candidate_year == expected_year:
            confidence += 0.12
        elif abs(candidate_year - expected_year) == 1:
            confidence += 0.05
    confidence = min(confidence, 1.0)
    if confidence >= 1.0:
        status = "exact_title"
    else:
        status = "fuzzy_title"
    return candidate_title, status, confidence


def _extract_first_arxiv_id(values: Iterable[str]) -> Optional[str]:
    for value in values:
        if not value:
            continue
        match = ARXIV_ID_RE.search(value)
        if match:
            return match.group("id")
    return None


def _request_response(
    session: requests.Session,
    url: str,
    *,
    source: str,
    limiter: RateLimiter,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, object]] = None,
    max_retries: int = REQUEST_MAX_RETRIES,
) -> requests.Response:
    for attempt in range(max_retries):
        limiter.wait(source)
        try:
            response = session.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception:  # noqa: BLE001
            delay = 2**attempt
            if delay > MAX_RETRY_WAIT_SECONDS:
                delay = MAX_RETRY_WAIT_SECONDS
            time.sleep(delay)
            if attempt == max_retries - 1:
                raise
            continue

        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            parsed_retry_after = None
            if retry_after:
                try:
                    parsed_retry_after = float(retry_after)
                except (TypeError, ValueError):
                    parsed_retry_after = None
            if parsed_retry_after is not None:
                delay = parsed_retry_after
                if delay > MAX_RETRY_WAIT_SECONDS:
                    delay = MAX_RETRY_WAIT_SECONDS
                if delay > 0:
                    time.sleep(delay)
            else:
                delay = 2 ** attempt
                if delay > MAX_RETRY_WAIT_SECONDS:
                    delay = MAX_RETRY_WAIT_SECONDS
                time.sleep(delay)
            continue
        response.raise_for_status()
        return response
    response.raise_for_status()
    return response


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
    response = _request_response(
        session,
        url,
        source=source,
        limiter=limiter,
        headers=headers,
        params=params,
        max_retries=max_retries,
    )
    return response.json()


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
    response = _request_response(
        session,
        url,
        source=source,
        limiter=limiter,
        headers=headers,
        params=params,
        max_retries=max_retries,
    )
    return response.text


def _extract_html_meta_tags(page_html: str) -> Dict[str, Any]:
    """Parse `<meta ...>` tags with name/property/itemprop and content."""
    tag_pattern = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
    key_pattern = re.compile(
        r"\b(?:name|property|itemprop|http-equiv)\s*=\s*['\"]([^'\"]+)['\"]",
        re.IGNORECASE,
    )
    content_pattern = re.compile(
        r"\bcontent\s*=\s*['\"]([^'\"]*)['\"]",
        re.IGNORECASE,
    )
    parsed: Dict[str, Any] = {}
    for tag in tag_pattern.findall(page_html):
        if not tag:
            continue
        key_match = key_pattern.search(tag)
        if not key_match:
            continue
        norm_key = _normalize_whitespace(key_match.group(1))
        content_match = content_pattern.search(tag)
        value = content_match.group(1) if content_match else ""
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


def _extract_jsonld_abstract(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        text = _normalize_metadata_value(payload)
        if text and "<" not in text and ">" not in text:
            return text
        return _strip_html(text)
    if isinstance(payload, list):
        for item in payload:
            text = _extract_jsonld_abstract(item)
            if text:
                return text
        return ""
    if isinstance(payload, dict):
        for key in (
            "description",
            "abstract",
            "articleBody",
            "text",
            "summary",
        ):
            text = _extract_jsonld_abstract(payload.get(key))
            if text:
                return text
        for key in ("author", "publisher", "creator", "@context", "@type", "@graph"):
            if key in payload:
                text = _extract_jsonld_abstract(payload.get(key))
                if text:
                    return text
    return ""


def _extract_embedded_urls(payload: Any) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, str):
        return _extract_urls([payload]) + _extract_urls([payload.replace("'", "\"")]) + _extract_urls([payload.replace("`", "\"")])
    if isinstance(payload, list):
        results: list[str] = []
        for item in payload:
            results.extend(_extract_embedded_urls(item))
        return _dedupe_values(results)
    if isinstance(payload, dict):
        results: list[str] = []
        for value in payload.values():
            results.extend(_extract_embedded_urls(value))
        return _dedupe_values(results)
    return []


def _extract_id_urls_from_mapping(identifier_name: str, identifier_value: Any) -> list[str]:
    """Build URLs from known scholarly identifier keys."""
    urls: list[str] = []
    if not identifier_name:
        return urls
    if isinstance(identifier_value, (list, tuple, set)):
        for item in identifier_value:
            urls.extend(_extract_id_urls_from_mapping(identifier_name, item))
        return _dedupe_values(urls)

    value = _normalize_whitespace(_normalize_metadata_value(identifier_value))
    if not value:
        return urls

    key = str(identifier_name).lower().replace("_", "").replace("-", "")
    lower_value = value.lower()

    if key in {"doi", "crossref", "crossreftopic"}:
        doi = _normalize_doi(value)
        if doi:
            urls.extend(_candidate_urls_from_doi(doi))
            doi_url = _make_doi_url(doi)
            if doi_url:
                urls.append(doi_url)
    elif key in {"acldoi", "acl", "aclanthology", "aclpaperid", "acl_id", "aclid"}:
        if "10.18653/v1/" in lower_value:
            urls.extend(_candidate_urls_from_doi(value))
        else:
            suffix = lower_value.lstrip("acl-")
            if suffix:
                urls.extend([f"https://aclanthology.org/{suffix}", f"https://aclanthology.org/{suffix}.pdf"])
    elif key in {"dblp", "dblpid", "dblp_id", "dblpid"}:
        if lower_value.startswith("http"):
            if lower_value.startswith("http://"):
                urls.append("https://" + lower_value[len("http://"):])
            else:
                urls.append(lower_value)
        elif lower_value.startswith("conf/") or lower_value.startswith("journals/"):
            urls.append(f"https://dblp.org/rec/{lower_value}")
            urls.append(f"https://dblp.org/rec/{lower_value}.html")
    elif key in {"pmid", "pubmed"}:
        urls.append(f"https://pubmed.ncbi.nlm.nih.gov/{value}/")
    elif key in {"pmcid", "pmc"}:
        urls.append(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{value}")
    elif key in {"arxiv", "arxivid", "arxivid", "eprint"}:
        if "/" in lower_value and "." in lower_value:
            urls.extend([f"https://arxiv.org/abs/{value}", f"https://arxiv.org/pdf/{value}.pdf"])
    elif key in {"openalex", "openalexid", "openalex_id", "openalexid"}:
        if value.startswith("https://openalex.org/"):
            urls.append(value)
        elif re.fullmatch(r"W\\d+", value):
            urls.append(f"https://openalex.org/{value}")
    elif key in {"github", "githuburl", "repository"}:
        if value.startswith("http://") or value.startswith("https://"):
            urls.append(value)
    elif key in {"url", "website", "homepage"} and value.startswith("http"):
        urls.append(value)

    return _dedupe_values(urls)


def _extract_text_from_pdf_payload(payload: bytes) -> str:
    if not payload:
        return ""
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(payload)
            tmp_path = tmp_file.name
        process = subprocess.run(
            ["pdftotext", "-layout", "-nopgbrk", tmp_path, "-"],
            capture_output=True,
            text=True,
            timeout=PDF_TO_TEXT_TIMEOUT,
            check=False,
        )
        text = process.stdout if process.returncode == 0 else ""
        if not text:
            return ""
        return _normalize_whitespace(text)[:PDF_TO_TEXT_MAX_CHARS]
    except FileNotFoundError:
        return ""
    except Exception:
        return ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _extract_text_from_pdf_file(file_path: str) -> str:
    if not file_path:
        return ""
    normalized = os.path.expanduser(os.path.expandvars(_normalize_whitespace(_strip_bib_field_markers(file_path))))
    if normalized.startswith("file://"):
        normalized = normalized.replace("file://", "", 1)
    if not normalized:
        return ""
    candidate_path = Path(normalized)
    if not candidate_path.exists() or not candidate_path.is_file():
        return ""
    if candidate_path.suffix.lower() != ".pdf":
        return ""
    try:
        with candidate_path.open("rb") as handle:
            payload = handle.read()
        return _extract_text_from_pdf_payload(payload)
    except FileNotFoundError:
        return ""
    except Exception:
        return ""


def _extract_year_from_text_snippet(raw_text: str) -> Optional[str]:
    if not raw_text:
        return None
    first_lines = "\n".join(raw_text.splitlines()[:40])
    match = re.search(r"(?:(19|20)\d{2})", first_lines)
    if not match:
        return None
    year = int(match.group(0))
    return f"{year:04d}-01-01" if 1000 <= year <= 2500 else None


def _extract_abstract_from_pdf_text(pdf_text: str) -> str:
    if not pdf_text:
        return ""
    raw_lines = [line.strip() for line in re.split(r"[\r\n]+", pdf_text)]
    start = None
    for index, line in enumerate(raw_lines):
        if re.match(r"(?i)^abstract\b", line):
            start = index + 1
            break
    if start is None:
        return ""
    stop_markers = (
        r"(?i)^\d*\s*introduction\b",
        r"(?i)^keywords?\b",
        r"(?i)^1\.?\s*introduction\b",
        r"(?i)^references?\b",
        r"(?i)^bibliography\b",
        r"(?i)^index terms\b",
        r"(?i)^background\b",
    )
    collected: list[str] = []
    for line in raw_lines[start:]:
        if any(re.match(marker, line) for marker in stop_markers):
            break
        if line:
            collected.append(line)
    candidate = " ".join(collected).strip()
    return candidate if len(candidate) >= 40 else ""


def _extract_abstract_from_markdown(raw_text: str) -> str:
    if not raw_text:
        return ""
    lines = raw_text.splitlines()
    if not lines:
        return ""

    heading_pattern = re.compile(r"^\s*(#{1,6}\s*)?(abstract|摘要)\s*[:：]?\s*$", re.IGNORECASE)
    inline_pattern = re.compile(r"^\s*(abstract|abstracts?)\s*[:：]\s*(.+)$", re.IGNORECASE)
    markdown_heading_line = re.compile(r"^\s*#{1,6}\s*")
    end_section_pattern = re.compile(r"^\s*#{1,6}\s*[A-Za-z]")

    for idx, line in enumerate(lines):
        line_strip = line.strip()
        inline_match = inline_pattern.search(line_strip)
        if inline_match:
            candidate = _normalize_whitespace(inline_match.group(2))
            if candidate and _abstract_candidate_is_valid(candidate):
                return candidate
        if not heading_pattern.search(line_strip):
            continue
        collected: list[str] = []
        for follow in lines[idx + 1 :]:
            follow_strip = follow.strip()
            if not follow_strip:
                if collected:
                    break
                continue
            if markdown_heading_line.search(follow_strip) and end_section_pattern.search(follow_strip):
                break
            collected.append(follow_strip)
        candidate = _normalize_whitespace(" ".join(collected))
        if candidate and _abstract_candidate_is_valid(candidate):
            return candidate

    return ""


def _extract_abstract_from_plain_text(raw_text: str, title: str) -> str:
    """Extract abstract-like text from structured plain text (post-html stripped)."""
    if not raw_text:
        return ""

    normalized_title = _normalize_title_signature(title)
    lines = [line.strip() for line in re.split(r"[\r\n]+", raw_text)]
    if not lines:
        return ""

    lower_title = normalized_title.lower() if normalized_title else ""
    abstract_lines: list[str] = []

    for index, line in enumerate(lines):
        if not line:
            continue
        if re.match(r"(?i)^(abstract|摘要)\s*[:：]?\s*$", line):
            for follow in lines[index + 1 :]:
                if not follow:
                    if abstract_lines:
                        break
                    continue
                if re.match(
                    r"(?i)^(introduction|keywords?|references?|bibliography|index terms|background|method|approach)\b",
                    follow,
                ):
                    break
                if re.match(r"^\d*\.?\s*(introduction|keywords?|background|references?|bibliography)\b", follow, re.IGNORECASE):
                    break
                abstract_lines.append(follow)
            break

        if re.match(r"(?i)^abstract\s*[:：]\s*(.+)$", line):
            candidate = _normalize_whitespace(re.sub(r"(?i)^abstract\s*[:：]\s*", "", line))
            if candidate:
                abstract_lines = [candidate]
            break

    if not abstract_lines and lower_title and lines:
        for index, line in enumerate(lines):
            normalized_line = _normalize_title_signature(line)
            if not normalized_line:
                continue
            if lower_title == normalized_line.lower():
                for follow in lines[index + 1 :]:
                    if not follow:
                        if abstract_lines:
                            break
                        continue
                    if re.match(
                        r"(?i)^introduction|^\d*\.?\s*introduction|^keywords?|^references?|^bibliography|^abstract",
                        follow,
                    ):
                        break
                    abstract_lines.append(follow)
                break

    if not abstract_lines:
        return ""
    return _normalize_whitespace(" ".join(abstract_lines))


def _extract_abstract_from_source_text(
    raw_text: str,
    source: str = "",
    *,
    title: str = "",
) -> tuple[str, str]:
    if not raw_text:
        return "", "empty"

    if source == "pdf":
        return _extract_abstract_from_pdf_text(raw_text), "pdf-abstract"

    if source == "html":
        markdown_abstract = _extract_abstract_from_markdown(raw_text)
        if markdown_abstract:
            return markdown_abstract, "markdown-abstract"

    abstract, abstract_source = _extract_abstract_from_html(raw_text)
    if abstract:
        return abstract, abstract_source

    text = _strip_html(raw_text)
    if text and len(text) >= 40:
        plain_abstract = _extract_abstract_from_plain_text(
            text,
            title=_normalize_whitespace(title),
        )
        if plain_abstract:
            return plain_abstract, "plain-text"
        # Keep only explicitly extracted abstract-like blocks from structured HTML fields.
        return "", "none"
    return "", "none"


def _read_source_text(
    session: requests.Session,
    limiter: RateLimiter,
    url: str,
    *,
    trace_steps: list[str],
) -> tuple[str, bool]:
    for candidate_url in _url_redirect_candidates(url):
        if not candidate_url:
            continue
        if candidate_url.startswith("file://"):
            candidate_url = candidate_url.replace("file://", "", 1)
        lower = candidate_url.lower()
        if lower.startswith("http://") or lower.startswith("https://"):
            try:
                response = _request_response(
                    session,
                    candidate_url,
                    source="url_fallback",
                    limiter=limiter,
                    headers={"User-Agent": USER_AGENT},
                )
                content_type = str(response.headers.get("content-type", "")).lower()
                if "application/pdf" in content_type or lower.endswith(".pdf"):
                    text = _extract_text_from_pdf_payload(response.content)
                    if text:
                        trace_steps.append(f"url_fallback:pdf:{candidate_url}")
                        return text, True
                    trace_steps.append(f"url_fallback:pdf_empty:{candidate_url}")
                else:
                    text = response.text
                    if text:
                        trace_steps.append(f"url_fallback:html:{candidate_url}")
                        return text, False
            except Exception:
                continue
        if "://" not in candidate_url and candidate_url:
            page_text = _extract_text_from_pdf_file(candidate_url)
            if page_text:
                trace_steps.append(f"url_fallback:pdf:{candidate_url}")
                return page_text, True
    return "", False


def _first_non_empty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _normalize_whitespace(_strip_html(value))
    if isinstance(value, list):
        for item in value:
            text = _first_non_empty(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for item in value.values():
            text = _first_non_empty(item)
            if text:
                return text
        return ""
    return ""


def _extract_abstract_from_html(page_html: str) -> tuple[str, str]:
    if not page_html:
        return "", ""

    html_abstract_patterns = (
        r"<(?:section|div|p|blockquote)\b[^>]*\bclass=['\"]?[^'\"]*\bacl-abstract\b[^'\"]*['\"]?[^>]*>(.*?)</(?:section|div|p|blockquote)>",
        r"<(?:section|div|p|blockquote)\b[^>]*\bclass=['\"]?[^'\"]*\babstract\b[^'\"]*['\"]?[^>]*>(.*?)</(?:section|div|p|blockquote)>",
        r"<(?:section|div|p|blockquote)\b[^>]*\bid=['\"]?abstract['\"]?[^>]*>(.*?)</(?:section|div|p|blockquote)>",
        r"<(?:section|div|p|blockquote)\b[^>]*\bclass=['\"]?[^'\"]*\babstracts?\b[^'\"]*['\"]?[^>]*>(.*?)</(?:section|div|p|blockquote)>",
    )
    for pattern in html_abstract_patterns:
        match = re.search(pattern, page_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            text = _normalize_whitespace(_strip_html(match.group(1)))
            if text and _abstract_candidate_is_valid(text):
                return text, "html:class"

    meta_tags = _extract_html_meta_tags(page_html)
    for meta_key in (
        "description",
        "og:description",
        "twitter:description",
        "dc.description",
        "citation_abstract",
        "abstract",
    ):
        text = _first_non_empty(meta_tags.get(meta_key))
        if text and _abstract_candidate_is_valid(text):
            return text, f"meta:{meta_key}"

    for json_match in re.finditer(
        r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raw = html.unescape(json_match.group(1) or "")
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        text = _extract_jsonld_abstract(payload)
        if text:
            return _normalize_whitespace(text), "json-ld"

    return "", ""


def _make_doi_url(doi: str) -> str:
    normalized = _normalize_doi(doi)
    if not normalized:
        return ""
    return f"https://doi.org/{quote(normalized, safe=':/')}"


def _extract_candidate_urls(
    entry: Dict[str, Any],
    result: Optional[FetchResult] = None,
) -> list[str]:
    candidates: list[str] = []
    if not isinstance(entry, dict):
        return []
    base = _entry_candidates(entry) if entry else {}
    candidates.extend(base.get("urls") or [])
    fallback_keys = (
        "note",
        "howpublished",
        "url",
        "doi",
        "eprint",
        "pmid",
        "pmcid",
        "file",
        "booktitle",
        "journal",
    )

    raw_local = entry.get("raw", {}).get("local", {})
    if isinstance(raw_local, dict):
        for source_key in fallback_keys:
            value = raw_local.get(source_key)
            if value and isinstance(value, str):
                if source_key == "pmid":
                    candidates.append(f"https://pubmed.ncbi.nlm.nih.gov/{value.strip()}/")
                elif source_key == "pmcid":
                    candidates.append(f"https://www.ncbi.nlm.nih.gov/pmc/articles/{value.strip()}")
                elif source_key == "eprint" and raw_local.get("eprinttype", "").lower() == "jstor":
                    candidates.append(f"https://www.jstor.org/stable/{value.strip()}")
                elif source_key == "file":
                    candidates.extend(_extract_file_paths((value,)))
                elif source_key == "doi":
                    candidates.extend(_candidate_urls_from_doi(value))
                else:
                    candidates.append(value)
                if source_key in {"doi", "note", "url", "howpublished"}:
                    candidates.extend(_extract_urls((value,)))
                    candidates.extend(_extract_embedded_urls(value))
            if source_key == "file":
                candidates.extend(_extract_file_paths([value] if isinstance(value, str) else []))
            if source_key == "eprint":
                candidates.extend(_extract_id_urls_from_mapping("eprint", value))

        for identifier_key in ("archiveprefix", "eprinttype", "type", "primaryclass"):
            candidate_value = raw_local.get(identifier_key)
            if isinstance(candidate_value, str):
                candidates.extend(_extract_id_urls_from_mapping(identifier_key, candidate_value))

    candidate_dois = base.get("dois") if base else []
    for doi in candidate_dois:
        doi_url = _make_doi_url(doi)
        if doi_url:
            candidates.append(doi_url)
        candidates.extend(_candidate_urls_from_doi(doi))
    for raw_key in ("doi", "url", "howpublished", "note", "file", "pmid", "pmcid", "eprint", "arxiv"):
        raw_value = entry.get("raw", {}).get(raw_key)
        candidates.extend(_extract_urls((raw_value,)) if isinstance(raw_value, str) else [])
        candidates.extend(_extract_id_urls_from_mapping(raw_key, raw_value))

    raw_metadata = entry.get("raw", {})
    if isinstance(raw_metadata, dict):
        for raw_key in ("doi", "url", "arxivid", "abstract", "note", "pages"):
            raw_value = raw_metadata.get(raw_key)
            if raw_value:
                if isinstance(raw_value, str):
                    candidates.extend(_extract_urls((raw_value,)))
                candidates.extend(_extract_id_urls_from_mapping(raw_key, raw_value))

    if result is not None:
        result_metadata = result.raw_metadata if isinstance(result.raw_metadata, dict) else {}
        direct_url_keys = (
            "url",
            "ids",
            "openAccessPdf",
            "open_access",
            "openaccess",
            "landing_page_url",
            "landingPage",
            "landing_page",
            "landingPageUrl",
            "canonicalUrl",
            "paperUrl",
            "paperURL",
            "pdfUrl",
            "pdf_url",
            "homepage",
            "source",
            "repository",
            "pdf",
            "url_source",
            "primary_url",
            "official_url",
            "primary_location",
        )
        for key in direct_url_keys:
            value = result_metadata.get(key)
            if isinstance(value, str):
                candidates.extend(_extract_urls((value,)))
            elif isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, str):
                        candidates.extend(_extract_urls((nested,)))
                        candidates.extend(_extract_id_urls_from_mapping(key, nested))
                    elif isinstance(nested, (list, tuple, set)):
                        for nested_item in nested:
                            if isinstance(nested_item, str):
                                candidates.extend(_extract_urls((nested_item,)))
                                candidates.extend(_extract_id_urls_from_mapping(key, nested_item))
            elif isinstance(value, (list, tuple, set)):
                for nested in value:
                    if isinstance(nested, str):
                        candidates.extend(_extract_urls((nested,)))
                        if key in {"ids", "externalIds", "external_ids", "openalex_id", "openalexId"}:
                            candidates.extend(_extract_id_urls_from_mapping(key, nested))
                    elif isinstance(nested, dict):
                        for nested_key, nested_value in nested.items():
                            candidates.extend(_extract_id_urls_from_mapping(str(nested_key), nested_value))

            if isinstance(value, dict):
                if key in {"primary_location", "source", "open_access"}:
                    for nested_key, nested_value in value.items():
                        if nested_key in {"landing_page_url", "landingPageUrl", "pdf_url", "pdfUrl", "url", "canonical_url", "canonicalUrl"}:
                            candidates.extend(_extract_urls((nested_value,)) if isinstance(nested_value, str) else [])
                        candidates.extend(_extract_id_urls_from_mapping(str(nested_key), nested_value))

        candidates.extend(_extract_embedded_urls(result_metadata))
        for key in ("ids", "externalIds", "external_ids", "id", "openalex_id", "openalexId"):
            mapping = result_metadata.get(key) if isinstance(result_metadata, dict) else None
            if isinstance(mapping, dict):
                for nested_key, nested_value in mapping.items():
                    candidates.extend(_extract_id_urls_from_mapping(str(nested_key), nested_value))
            elif isinstance(mapping, list):
                for nested in mapping:
                    if isinstance(nested, str):
                        candidates.extend(_extract_id_urls_from_mapping(key, nested))
                    elif isinstance(nested, dict):
                        for nested_key, nested_value in nested.items():
                            candidates.extend(_extract_id_urls_from_mapping(str(nested_key), nested_value))
        source_specific_ids = {
            "pubmedId": result_metadata.get("pmid"),
            "pubmed_central_id": result_metadata.get("pmcid"),
            "acmId": result_metadata.get("acmid"),
            "arxivId": result_metadata.get("arxivId"),
            "arxiv_id": result_metadata.get("arxiv_id"),
        }
        for key, value in source_specific_ids.items():
            if value:
                candidates.extend(_extract_id_urls_from_mapping(key, value))

    return _dedupe_values(_strip_bib_field_markers(v) for v in candidates if isinstance(v, str))


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


def _search_google_books_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    expected_year: Optional[int],
    max_results: int,
) -> list[Dict[str, Any]]:
    query_titles = _build_title_variants(title)
    if not query_titles:
        return []
    results: list[Dict[str, Any]] = []
    seen: set[str] = set()
    max_per_query = max(1, max_results)
    for query_title in query_titles[: min(len(query_titles), GOOGLE_BOOKS_MAX_QUERY_VARIANTS)]:
        query = _normalize_whitespace(query_title)
        if not query:
            continue
        if expected_year:
            query = f"{query} {expected_year}"
        payload = _request_json(
            session,
            GOOGLE_BOOKS_API_URL,
            source="google_books",
            limiter=limiter,
            headers={"User-Agent": USER_AGENT},
            params={"q": query, "maxResults": max_per_query, "printType": "books"},
        )
        items = payload.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if not isinstance(item.get("volumeInfo"), dict):
                continue
            volume = item.get("volumeInfo") or {}
            title_value = _normalize_whitespace(str(volume.get("title") or ""))
            subtitle = _normalize_whitespace(str(volume.get("subtitle") or ""))
            candidate_title = _normalize_whitespace(
                f"{title_value}: {subtitle}" if subtitle else title_value
            )
            if not candidate_title:
                continue
            key = _normalize_whitespace(item.get("id") or candidate_title).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "title": candidate_title,
                    "raw": volume,
                    "year": _extract_year(volume.get("publishedDate")),
                    "publishedDate": volume.get("publishedDate"),
                    "source_id": _normalize_whitespace(item.get("id") or ""),
                    "infoLink": _normalize_whitespace(volume.get("infoLink") or ""),
                }
            )
            if len(results) >= max_per_query:
                return results
    return results


def _fetch_google_books_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
    expected_year: Optional[int] = None,
) -> Tuple[Optional[FetchResult], str]:
    candidates = _search_google_books_by_title(
        session,
        limiter,
        title,
        expected_year=expected_year,
        max_results=max_results,
    )
    if not candidates:
        return None, "no_match"
    matched, match_score, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
        expected_year=expected_year,
    )
    if not matched:
        return None, "no_match"

    raw_metadata = matched.get("raw")
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}
    abstract = _extract_abstract(raw_metadata, source="google_books", title=title, strict=True)
    publication_date = _extract_publication_date(raw_metadata)
    if not abstract and not publication_date:
        return None, "no_match_or_no_abstract"
    return FetchResult(
        title=_normalize_whitespace(raw_metadata.get("title") or matched.get("title") or ""),
        abstract=abstract,
        source="google_books",
        source_id=str(matched.get("source_id") or ""),
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=raw_metadata,
    ), "match" if abstract else "match_no_abstract"


def _select_best_match(
    title: str,
    candidates: list[Dict[str, Any]],
    *,
    title_key: str,
    allow_fuzzy: bool,
    min_similarity: float,
    expected_year: Optional[int] = None,
) -> Tuple[Optional[Dict[str, Any]], float, str]:
    def _title_signature_list(value: str) -> list[str]:
        signatures: list[str] = []
        for variant in (value,):
            normalized = normalize_title(variant)
            if normalized:
                signatures.append(normalized)
            compact = _normalize_title_signature(variant)
            if compact:
                signatures.append(compact)
        for variant in _build_title_variants(value):
            normalized = normalize_title(variant)
            if normalized:
                signatures.append(normalized)
            compact = _normalize_title_signature(variant)
            if compact:
                signatures.append(compact)
        return _dedupe_values(signatures)

    target_signatures = _title_signature_list(_normalize_whitespace(title))
    target_signature_set = set(target_signatures)

    token_count = len(split_words(title))
    best: Optional[Dict[str, Any]] = None
    best_similarity = 0.0
    best_status = ""

    for item in candidates:
        candidate_title = str(item.get(title_key) or "")
        candidate_signatures = _title_signature_list(candidate_title)
        for signature in candidate_signatures:
            if signature in target_signature_set:
                return item, 1.0, "exact_title"

        candidate_similarities = [
            _jaccard_similarity(target_signature, candidate_signature)
            for target_signature in target_signatures
            for candidate_signature in candidate_signatures
            if target_signature and candidate_signature
        ]
        similarity = max(candidate_similarities) if candidate_similarities else 0.0

        if similarity < best_similarity:
            continue
        candidate_year = _extract_year(
            item.get("year")
            or item.get("publication_year")
            or item.get("publicationYear")
            or item.get("published")
            or item.get("publicationDate")
        )
        _, status, _ = _match_score(
            title,
            candidate_title,
            expected_year=expected_year,
            candidate_year=candidate_year,
        )

        if similarity > best_similarity or (similarity == best_similarity and candidate_similarities):
            best = item
            best_similarity = similarity
            best_status = status

    if best is None:
        return None, 0.0, ""
    if best_similarity < 1.0 and not allow_fuzzy:
        return None, best_similarity, ""
    if best_similarity < min_similarity:
        return None, best_similarity, ""
    if best_similarity < 1.0 and token_count < 4:
        return None, best_similarity, ""
    if best_similarity < 1.0 and not best_status:
        best_status = "fuzzy_title"
    if not best_status:
        best_status = "fuzzy_title"
    return best, best_similarity, best_status


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
        for key in (
            "title",
            "journal",
            "booktitle",
            "publisher",
            "abstract",
            "note",
            "howpublished",
            "url",
            "doi",
            "eprint",
            "eprinttype",
            "urldate",
            "pmid",
            "pmcid",
            "file",
            "note",
            "year",
            "month",
        ):
            value = raw_local.get(key)
            if isinstance(value, str):
                values.append(value)
        if raw_local.get("note"):
            values.append(_normalize_metadata_value(raw_local.get("note")))
        if raw_local.get("howpublished"):
            values.append(_normalize_metadata_value(raw_local.get("howpublished")))
        if raw_local.get("abstract"):
            values.append(_normalize_metadata_value(raw_local.get("abstract")))
    raw_top = entry.get("raw", {})
    if isinstance(raw_top, dict):
        for key in ("title", "journal", "booktitle", "publisher", "note", "howpublished", "url", "doi", "year", "month", "date", "abstract", "summary", "description"):
            value = raw_top.get(key)
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        values.append(item)
    return values




def _resolve_expected_year(entry: Dict[str, Any]) -> Optional[int]:
    raw_local = entry.get("raw", {}).get("local", {})
    for candidate in (
        entry.get("year"),
        entry.get("query_year"),
        raw_local.get("year") if isinstance(raw_local, dict) else None,
        raw_local.get("date") if isinstance(raw_local, dict) else None,
        raw_local.get("published") if isinstance(raw_local, dict) else None,
        raw_local.get("published-online") if isinstance(raw_local, dict) else None,
        raw_local.get("published_print") if isinstance(raw_local, dict) else None,
    ):
        year = _extract_year(candidate)
        if year:
            return year
    return None


def _entry_candidates(entry: Dict[str, Any]) -> Dict[str, Any]:
    values = _candidate_strings(entry)
    title = _title_from_entry(entry)
    query_title = _strip_bib_field_markers(_normalize_whitespace(_prepare_title_query(title)))
    key_value = entry.get("key")
    if isinstance(key_value, str):
        values.append(key_value)
    raw = entry.get("raw", {})
    raw_local = raw.get("local", {})
    if isinstance(raw, dict) and raw.get("title"):
        values.append(_normalize_metadata_value(raw.get("title")))
    if isinstance(raw_local, dict):
        for candidate_key in ("title", "booktitle", "journal", "publisher", "school", "institution"):
            candidate_title = raw_local.get(candidate_key)
            if isinstance(candidate_title, str):
                values.append(candidate_title)
        for candidate_key in ("note", "howpublished", "url", "doi", "eprint", "eprinttype", "pmid", "pmcid", "file", "month", "year"):
            candidate_value = raw_local.get(candidate_key)
            if isinstance(candidate_value, str):
                values.append(candidate_value)
            elif isinstance(candidate_value, list):
                for item in candidate_value:
                    if isinstance(item, str):
                        values.append(item)

    return {
        "titles": _dedupe_values(values + [title, query_title]),
        "arxiv_ids": _extract_arxiv_ids(values),
        "dois": _dedupe_values(_extract_dois(values)),
        "urls": _extract_urls(values),
        "expected_year": _resolve_expected_year(entry),
    }


def _build_date_from_local(entry: Dict[str, Any]) -> Optional[str]:
    raw_local = entry.get("raw", {}).get("local", {})
    if not isinstance(raw_local, dict):
        return None
    publication_date = _extract_publication_date(raw_local)
    if publication_date:
        return publication_date
    year = _extract_year(raw_local.get("year") or raw_local.get("date"))
    if year:
        return f"{year:04d}-01-01"
    return None


def _build_candidate_result_from_entry(entry: Dict[str, Any]) -> Optional[FetchResult]:
    candidates = _entry_candidates(entry)
    title = _title_from_entry(entry)
    if not title:
        title = candidates.get("titles", [""])[0]
    local_metadata = entry.get("raw", {})
    local_raw = entry.get("raw", {}).get("local", {})
    abstract = _extract_abstract(local_metadata, source="local", title=title, strict=True)
    if not abstract and isinstance(local_metadata, dict):
        local_candidates = {k: local_metadata.get(k) for k in ("abstract", "summary", "description", "note")}
        if isinstance(local_raw, dict):
            for key in ("abstract", "summary", "description", "note"):
                local_candidates[f"local_{key}"] = local_raw.get(key)
        for candidate in local_candidates.values():
            if not candidate:
                continue
            normalized = _normalize_metadata_value(candidate)
            if not normalized:
                continue
            if _is_title_like_text(normalized, title=title):
                continue
            if not _abstract_candidate_is_valid(
                normalized,
                min_words=max(4, ABSTRACT_MIN_WORDS),
            ):
                continue
            abstract = normalized
            break

    if not abstract:
        abstract = _pick_first_valid_abstract(
            local_metadata if isinstance(local_metadata, dict) else {},
            title=title,
            source="local",
        )
    abstract = _normalize_whitespace(abstract)
    publication_date = _build_date_from_local(entry)

    if not abstract and not publication_date:
        return None

    return FetchResult(
        title=title,
        abstract=abstract,
        source="local",
        source_id="",
        match_status="exact_title" if title else "match",
        match_score=1.0,
        publication_date=publication_date,
        raw_metadata=entry.get("raw", {}),
    )


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
    query_titles = _build_title_variants(title)
    if not query_titles:
        return []
    seen: set[str] = set()
    results: list[Dict[str, Any]] = []
    max_per_query = max(1, max_results)

    for query_title in query_titles[:3]:
        response = _request_text(
            session,
            ARXIV_API_URL,
            source="arxiv",
            limiter=limiter,
            params={"search_query": f'ti:"{query_title}"', "start": 0, "max_results": max_per_query},
            headers={"User-Agent": USER_AGENT},
        )
        for entry in _parse_arxiv_feed_entries(response):
            entry_id = _normalize_whitespace(str(entry.get("entry_id_url") or entry.get("id") or ""))
            if entry_id and entry_id in seen:
                continue
            seen.add(entry_id)
            results.append(entry)
            if len(results) >= max_per_query:
                return results
    return results


def _fetch_arxiv_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
    expected_year: Optional[int] = None,
) -> Tuple[Optional[FetchResult], str]:
    candidates = _search_arxiv_by_title(session, limiter, title, max_results=max_results)
    matched, match_score, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
        expected_year=expected_year,
    )
    if not matched:
        return None, "no_match"
    abstract = _extract_abstract(matched, source="arxiv", title=title, strict=True)
    publication_date = _extract_publication_date(matched)
    raw_metadata: Dict[str, Any] = dict(matched)
    arxiv_id = _normalize_whitespace(str(matched.get("id") or ""))
    if arxiv_id:
        try:
            full_metadata = _fetch_arxiv_metadata_by_id(session, limiter, arxiv_id)
            if isinstance(full_metadata, dict) and full_metadata:
                raw_metadata = full_metadata
        except Exception:  # noqa: BLE001
            pass
    if not abstract and not publication_date:
        return None, "no_match_or_no_abstract"
    result = FetchResult(
        title=_normalize_whitespace(str(raw_metadata.get("title") or matched.get("title") or "")),
        abstract=abstract,
        source="arxiv",
        source_id=arxiv_id,
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=raw_metadata,
    )
    return result, "match" if abstract else "match_no_abstract"


# --- Source: Semantic Scholar ---

def _semantic_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _semantic_scholar_fetch_by_doi(
    session: requests.Session,
    limiter: RateLimiter,
    doi: str,
    *,
    api_key: Optional[str],
) -> Optional[Dict[str, Any]]:
    doi = _normalize_doi(doi)
    if not doi:
        return None
    payload = _request_json(
        session,
        f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}",
        source="semantic_scholar",
        limiter=limiter,
        headers=_semantic_headers(api_key),
        params={"fields": SEMANTIC_SCHOLAR_DETAIL_FIELDS_BASE},
    )
    return payload if isinstance(payload, dict) and payload else None


def _search_semantic_scholar_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    api_key: Optional[str],
    max_results: int,
) -> list[Dict[str, object]]:
    query_titles = _build_title_variants(title)
    if not query_titles:
        return []
    results: list[Dict[str, object]] = []
    seen: set[str] = set()
    headers = _semantic_headers(api_key)
    for query_title in query_titles[:4]:
        params = {
            "query": query_title,
            "limit": max(1, max_results),
            "fields": SEMANTIC_SCHOLAR_SEARCH_FIELDS,
        }
        payload = _request_json(
            session,
            "https://api.semanticscholar.org/graph/v1/paper/search",
            source="semantic_scholar",
            limiter=limiter,
            headers=headers,
            params=params,
        )
        items = payload.get("data")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("paperId") or item.get("corpusId") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            results.append(item)
            if len(results) >= max(1, max_results):
                break
        if len(results) >= max(1, max_results):
            break
    if results:
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
    expected_year: Optional[int] = None,
    candidate_doi: Optional[str] = None,
) -> Tuple[Optional[FetchResult], str]:
    fallback_result: Optional[FetchResult] = None

    if candidate_doi:
        direct_metadata = _semantic_scholar_fetch_by_doi(
            session,
            limiter,
            candidate_doi,
            api_key=api_key,
        )
        if isinstance(direct_metadata, dict) and direct_metadata:
            abstract = _extract_abstract(direct_metadata, source="semantic_scholar", title=title, strict=True)
            publication_date = _extract_publication_date(direct_metadata)
            source_id = direct_metadata.get("paperId") or direct_metadata.get("corpusId") or ""
            if abstract:
                result = FetchResult(
                    title=_normalize_whitespace(str(direct_metadata.get("title") or title)),
                    abstract=abstract,
                    source="semantic_scholar",
                    source_id=str(source_id),
                    match_status="exact_id",
                    match_score=1.0,
                    publication_date=publication_date,
                    raw_metadata=direct_metadata,
                )
                return result, "match"
            if publication_date:
                fallback_result = FetchResult(
                    title=_normalize_whitespace(str(direct_metadata.get("title") or title)),
                    abstract="",
                    source="semantic_scholar",
                    source_id=str(source_id),
                    match_status="match_no_abstract",
                    match_score=1.0,
                    publication_date=publication_date,
                    raw_metadata=direct_metadata,
                )

    candidates = _search_semantic_scholar_by_title(
        session,
        limiter,
        title,
        api_key=api_key,
        max_results=max_results,
    )
    matched, match_score, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
        expected_year=expected_year,
    )
    if not matched:
        return None, "no_match"

    source_id = matched.get("paperId") or matched.get("corpusId") or ""
    detailed_metadata = _semantic_scholar_fetch_paper_metadata(
        session,
        limiter,
        str(source_id),
        api_key=api_key,
    )
    if isinstance(detailed_metadata, dict):
        raw_metadata = detailed_metadata
    else:
        raw_metadata = dict(matched)

    abstract = _extract_abstract(raw_metadata, source="semantic_scholar", title=title, strict=True)
    publication_date = _extract_publication_date(raw_metadata)

    if abstract:
        result = FetchResult(
            title=_normalize_whitespace(str(raw_metadata.get("title") or matched.get("title") or "")),
            abstract=abstract,
            source="semantic_scholar",
            source_id=str(source_id),
            match_status=match_status,
            match_score=match_score,
            publication_date=publication_date,
            raw_metadata=raw_metadata,
        )
        return result, "match"

    if publication_date and fallback_result:
        return fallback_result, "match_no_abstract"

    if not abstract and publication_date:
        return FetchResult(
            title=_normalize_whitespace(str(raw_metadata.get("title") or matched.get("title") or "")),
            abstract="",
            source="semantic_scholar",
            source_id=str(source_id),
            match_status=match_status,
            match_score=match_score,
            publication_date=publication_date,
            raw_metadata=raw_metadata,
        ), "match_no_abstract"

    # Retry with a more relaxed match threshold when only title search returned low-confidence date-only hits.
    relaxed_candidates = _search_semantic_scholar_by_title(
        session,
        limiter,
        title,
        api_key=api_key,
        max_results=max(1, max_results * 3),
    )
    relaxed_matched, relaxed_score, relaxed_status = _select_best_match(
        title,
        relaxed_candidates,
        title_key="title",
        allow_fuzzy=True,
        min_similarity=max(0.5, min_similarity - 0.35),
        expected_year=expected_year,
    )
    if relaxed_matched:
        relaxed_source_id = relaxed_matched.get("paperId") or relaxed_matched.get("corpusId") or ""
        detailed_relaxed_metadata = _semantic_scholar_fetch_paper_metadata(
            session,
            limiter,
            str(relaxed_source_id),
            api_key=api_key,
        )
        if isinstance(detailed_relaxed_metadata, dict):
            relaxed_raw = detailed_relaxed_metadata
        else:
            relaxed_raw = dict(relaxed_matched)
        relaxed_abstract = _extract_abstract(
            relaxed_raw,
            source="semantic_scholar",
            title=title,
            strict=True,
        )
        relaxed_publication_date = _extract_publication_date(relaxed_raw)
        if relaxed_abstract:
            return FetchResult(
                title=_normalize_whitespace(
                    str(relaxed_raw.get("title") or relaxed_matched.get("title") or "")
                ),
                abstract=relaxed_abstract,
                source="semantic_scholar",
                source_id=str(relaxed_source_id),
                match_status=relaxed_status or match_status,
                match_score=max(relaxed_score, match_score),
                publication_date=relaxed_publication_date or publication_date,
                raw_metadata=relaxed_raw,
            ), "match"
        if relaxed_publication_date:
            return FetchResult(
                title=_normalize_whitespace(
                    str(relaxed_raw.get("title") or relaxed_matched.get("title") or "")
                ),
                abstract="",
                source="semantic_scholar",
                source_id=str(relaxed_source_id),
                match_status=relaxed_status or match_status,
                match_score=max(relaxed_score, match_score),
                publication_date=relaxed_publication_date,
                raw_metadata=relaxed_raw,
            ), "match_no_abstract"

    result = FetchResult(
        title=_normalize_whitespace(str(raw_metadata.get("title") or matched.get("title") or "")),
        abstract=abstract,
        source="semantic_scholar",
        source_id=str(source_id),
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=raw_metadata,
    )
    return result, "match" if abstract else "match_no_abstract"


# --- Source: DBLP ---

def _search_dblp_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    max_results: int,
) -> list[Dict[str, Any]]:
    query_titles = _build_title_variants(title)
    if not query_titles:
        return []
    results: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for query_title in query_titles[:3]:
        params = {"q": query_title, "format": "json"}
        payload = _request_json(
            session,
            "https://dblp.org/search/publ/api",
            source="dblp",
            limiter=limiter,
            params=params,
        )
        hits = payload.get("result", {}).get("hits", {}).get("hit", [])
        if isinstance(hits, list):
            for item in hits[:max_results]:
                if not isinstance(item, dict):
                    continue
                info = item.get("info", {})
                if not isinstance(info, dict):
                    continue
                key = _normalize_whitespace(
                    str(info.get("title") or info.get("doi") or info.get("url") or "")
                )
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                results.append(info)
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break
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
    query_titles = _build_title_variants(title)
    if not query_titles:
        return []
    results: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for query_title in query_titles[:4]:
        params = {
            "search": query_title,
            "per-page": max(1, max_results),
            "select": "id,display_name,title,abstract_inverted_index,doi,primary_location",
        }
        try:
            payload = _request_json(
                session,
                "https://api.openalex.org/works",
                source="openalex",
                limiter=limiter,
                headers={"User-Agent": USER_AGENT},
                params=params,
                max_retries=1,
            )
        except Exception:
            continue
        payload_results = payload.get("results")
        if not isinstance(payload_results, list):
            continue
        for item in payload_results:
            if not isinstance(item, dict):
                continue
            key = _normalize_whitespace(item.get("id") or item.get("doi") or str(item.get("title") or ""))
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            results.append(item)
            if len(results) >= max(1, max_results):
                break
        if len(results) >= max(1, max_results):
            break
    return results


def _fetch_openalex_by_doi(
    session: requests.Session,
    limiter: RateLimiter,
    doi: str,
) -> Optional[Dict[str, Any]]:
    doi = _normalize_whitespace(doi)
    if not doi:
        return None
    payload = _request_json(
        session,
        "https://api.openalex.org/works",
        source="openalex",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
        params={"filter": f"doi:{doi}", "per-page": 1},
    )
    results = payload.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            return first
    return None


def _fetch_openalex_by_doi_direct(
    session: requests.Session,
    limiter: RateLimiter,
    doi: str,
) -> Optional[Dict[str, Any]]:
    doi = _normalize_doi(doi)
    if not doi:
        return None
    payload = _request_json(
        session,
        f"https://api.openalex.org/works/doi:{quote(doi, safe='')}",
        source="openalex",
        limiter=limiter,
        headers={"User-Agent": USER_AGENT},
    )
    if isinstance(payload, dict) and payload:
        return payload
    return None


def _fetch_openalex_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    max_results: int,
    candidate_doi: Optional[str] = None,
    expected_year: Optional[int] = None,
) -> Tuple[Optional[FetchResult], str, Optional[str], Optional[str]]:
    matched: Optional[Dict[str, Any]] = None
    raw_metadata: Optional[Dict[str, Any]] = None
    match_score = 1.0
    if candidate_doi:
        matched_doi = _fetch_openalex_by_doi_direct(session, limiter, candidate_doi)
        if isinstance(matched_doi, dict):
            raw_metadata = matched_doi
            match_status = "exact_id"
        else:
            match_status = ""
    else:
        match_status = ""

    if raw_metadata is None:
        candidates = _search_openalex_by_title(session, limiter, title, max_results=max_results)
        matched, match_score, match_status = _select_best_match(
            title,
            candidates,
            title_key="display_name",
            allow_fuzzy=allow_fuzzy,
            min_similarity=min_similarity,
            expected_year=expected_year,
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
    else:
        matched = raw_metadata
        match_score = 1.0

    if not raw_metadata:
        return None, "no_match", None, None

    abstract = _normalize_whitespace(_extract_abstract(raw_metadata, source="openalex", title=title, strict=True))
    publication_date = _extract_publication_date(raw_metadata)
    if not abstract and not publication_date:
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
        source_id=str(raw_metadata.get("id") or (matched or {}).get("id") or ""),
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=raw_metadata,
    )
    return (
        result,
        "match" if abstract else "match_no_abstract",
        raw_metadata.get("doi"),
        _openalex_landing_url(raw_metadata),
    )


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
    expected_year: Optional[int] = None,
) -> list[Dict[str, Any]]:
    query_titles = _build_title_variants(title)
    if not query_titles:
        return []
    year_filters: list[Optional[str]] = [None]
    if expected_year is not None:
        year_filters = [
            f"from-pub-date:{expected_year:04d}-01-01,until-pub-date:{expected_year:04d}-12-31",
            f"from-pub-date:{max(expected_year - 1, 1900):04d}-01-01,until-pub-date:{min(expected_year + 1, 2500):04d}-12-31",
            None,
        ]
    results: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for query_title in query_titles[:5]:
        for query_mode in ("query.title", "query.bibliographic"):
            for filter_value in year_filters:
                params: Dict[str, object] = {query_mode: query_title, "rows": max_results}
                if filter_value:
                    params["filter"] = filter_value
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
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        doi = _normalize_whitespace(item.get("DOI") or "")
                        title_candidates = item.get("title")
                        candidate_title = ""
                        if isinstance(title_candidates, list) and title_candidates:
                            candidate_title = _normalize_whitespace(title_candidates[0])
                        elif isinstance(title_candidates, str):
                            candidate_title = _normalize_whitespace(title_candidates)
                        key = f"{doi}::{candidate_title}".lower()
                        if key and key in seen:
                            continue
                        if key:
                            seen.add(key)
                        results.append(item)
                if len(results) >= max_results:
                    return results
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break
    return results


def _fetch_crossref_by_doi(
    session: requests.Session,
    limiter: RateLimiter,
    doi: str,
) -> Optional[Dict[str, Any]]:
    if not doi:
        return None
    doi = _normalize_whitespace(doi)
    if not doi:
        return None
    encoded_doi = quote(doi, safe="")
    payload = _request_json(
        session,
        f"https://api.crossref.org/works/{encoded_doi}",
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
    expected_year: Optional[int] = None,
) -> Tuple[Optional[FetchResult], str]:
    item = None
    match_score = 1.0
    match_status = "match"
    if candidate_doi:
        item = _fetch_crossref_by_doi(session, limiter, candidate_doi)
        if item is not None:
            match_status = "exact_id"
    if item is None:
        raw_candidates = _search_crossref_by_title(
            session,
            limiter,
            title,
            max_results=max_results,
            expected_year=expected_year,
        )
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
        matched, match_score, match_status = _select_best_match(
            title,
            candidates,
            title_key="title",
            allow_fuzzy=allow_fuzzy,
            min_similarity=min_similarity,
            expected_year=expected_year,
        )
        if not matched:
            return None, "no_match"
        item = matched.get("raw")
        if not isinstance(item, dict):
            return None, "no_match"
    if not isinstance(item, dict):
        return None, "no_match_or_no_abstract"

    if isinstance(item, dict):
        item_doi = _normalize_whitespace(str(item.get("DOI") or ""))
        if item_doi:
            detailed_item = _fetch_crossref_by_doi(session, limiter, item_doi)
            if isinstance(detailed_item, dict):
                item = detailed_item
        else:
            item_doi = candidate_doi

    abstract = _extract_abstract(item, source="crossref", title=title, strict=True)
    publication_date = _extract_publication_date(item)
    if not abstract and not publication_date:
        return None, "no_match_or_no_abstract"

    titles = item.get("title")
    title_value = titles[0] if isinstance(titles, list) and titles else ""
    source_id = item.get("DOI") or item_doi or candidate_doi or ""

    result = FetchResult(
        title=_normalize_whitespace(title_value),
        abstract=abstract,
        source="crossref",
        source_id=str(source_id),
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=item,
    )
    return result, "match" if abstract else "match_no_abstract"


# --- Source: ACL Anthology ---

def _fetch_acl_anthology_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    allow_fuzzy: bool,
    min_similarity: float,
    expected_year: Optional[int],
    candidate_urls: Optional[list[str]] = None,
) -> Tuple[Optional[FetchResult], str]:
    query_titles = _build_title_variants(title)
    if not query_titles:
        return None, "no_match"
    search_url = "https://aclanthology.org/search/"
    explicit_links = [
        _normalize_whitespace(url)
        for url in (candidate_urls or [])
        if isinstance(url, str) and "aclanthology.org" in url
    ]
    links = _dedupe_values(explicit_links)
    if not links:
        for query_title in query_titles:
            text = _request_text(
                session,
                search_url,
                source="acl_anthology",
                limiter=limiter,
                params={"q": query_title},
                headers={"User-Agent": USER_AGENT},
            )
            for match in re.finditer(
                r"<a\b[^>]*href=(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))",
                text,
                flags=re.IGNORECASE,
            ):
                href = match.group(1) or match.group(2) or match.group(3)
                if not href:
                    continue
                if not href.startswith("http") and not href.startswith("/"):
                    continue
                if href.startswith("http://") or href.startswith("https://"):
                    path = re.sub(r"^https?://aclanthology\.org", "", href, flags=re.IGNORECASE)
                    if path:
                        href = path
                    else:
                        href = "/"
                if "/search/" in href or "aclanthology.org/search" in href:
                    continue
                links.append(href.rstrip("/"))
            if links:
                break
    if not links:
        return None, "no_match"

    candidates: list[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    for link in links[:10]:
        paper_url = link
        if not paper_url.startswith("http"):
            paper_url = f"https://aclanthology.org{link}"
        if paper_url in seen_urls:
            continue
        seen_urls.add(paper_url)
        page_meta: dict[str, Any] = {}
        candidate_title = ""
        abstract = ""
        publication_date = None
        if paper_url.lower().endswith(".pdf"):
            response = _request_response(
                session,
                paper_url,
                source="acl_anthology",
                limiter=limiter,
                headers={"User-Agent": USER_AGENT},
            )
            paper_text = _extract_text_from_pdf_payload(response.content)
            if paper_text:
                candidate_title = _extract_abstract_from_pdf_text(paper_text)
                publication_date = _extract_year_from_text_snippet(paper_text)
                abstract = _extract_abstract_from_pdf_text(paper_text)
        else:
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
            publication_date = _extract_publication_date(page_meta)
        candidates.append(
            {
                "title": candidate_title,
                "abstract": abstract,
                "publication_date": publication_date,
                "url": paper_url,
                "source_id": paper_url.rstrip("/").rsplit("/", 1)[-1],
                "raw": {
                    "url": paper_url,
                    "page_meta": page_meta,
                    "title": candidate_title,
                    "abstract": abstract,
                },
            }
        )

    matched, match_score, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
        expected_year=expected_year,
    )
    if not matched:
        return None, "no_match"
    abstract = _normalize_whitespace(_extract_abstract(matched, source="acl_anthology", title=title, strict=True))
    publication_date = _extract_publication_date(matched.get("raw", {}))
    if not abstract and not publication_date:
        return None, "match_no_abstract"

    result = FetchResult(
        title=_normalize_whitespace(matched.get("title") or title),
        abstract=abstract,
        source="acl_anthology",
        source_id=matched.get("source_id") or "",
        match_status=match_status,
        match_score=1.0 if match_status == "exact_title" else 0.9,
        publication_date=publication_date,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else {},
    )
    return result, "match" if abstract else "match_no_abstract"


# --- Source: LREC ---

def _fetch_lrec_summary(
    session: requests.Session,
    limiter: RateLimiter,
    landing_urls: list[str],
    title: str,
    *,
    expected_year: Optional[int] = None,
) -> Tuple[Optional[FetchResult], str]:
    if not landing_urls:
        return None, "no_match"
    candidates = []
    for landing_url in landing_urls:
        if not landing_url or "lrec-conf.org/proceedings" not in landing_url:
            continue
        page = _request_text(
            session,
            landing_url,
            source="lrec_conf",
            limiter=limiter,
            headers={"User-Agent": USER_AGENT},
        )
        title_match = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
        page_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else ""
        page_meta = _extract_html_meta_tags(page)
        abstract_match = re.search(r"<div[^>]*class=\"abstract\"[^>]*>(.*?)</div>", page, re.IGNORECASE | re.DOTALL)
        abstract = ""
        if abstract_match:
            abstract = _normalize_whitespace(_strip_html(abstract_match.group(1)))
        if not abstract:
            meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", page)
            if meta_desc:
                abstract = _normalize_whitespace(meta_desc.group(1))
        candidates.append(
            {
                "title": page_title,
                "abstract": abstract,
                "url": landing_url,
                "publication_date": _extract_publication_date(page_meta),
                "raw": {
                    "url": landing_url,
                    "page_meta": page_meta,
                    "title": page_title,
                    "abstract": abstract,
                },
            }
        )

    if not candidates:
        return None, "no_match"

    matched, _, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=True,
        min_similarity=0.0,
        expected_year=expected_year,
    )
    if not matched:
        return None, "no_match"
    abstract = _normalize_whitespace(_extract_abstract(matched, source="lrec_conf", title=title, strict=True))
    publication_date = _extract_publication_date(matched.get("raw", {}))
    if not abstract and not publication_date:
        return None, "match_no_abstract"
    landing_url = matched.get("url") or ""
    lrec_id_match = re.search(r"/lrec(\d{4})/summaries/(\d+)", landing_url)
    source_id = landing_url
    if lrec_id_match:
        source_id = f"lrec{lrec_id_match.group(1)}:{lrec_id_match.group(2)}"
    result = FetchResult(
        title=_normalize_whitespace(matched.get("title") or title),
        abstract=abstract,
        source="lrec_conf",
        source_id=source_id,
        match_status=match_status,
        match_score=1.0 if match_status == "exact_title" else 0.8,
        publication_date=publication_date,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else {},
    )
    return result, "match" if abstract else "match_no_abstract"


# --- Source: RFC Editor ---

def _fetch_rfc_editor_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    candidate_urls: Optional[list[str]] = None,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    normalized_candidates = _dedupe_values(
        [
            _normalize_whitespace(url)
            for url in (candidate_urls or [])
            if isinstance(url, str) and "rfc-editor.org/rfc/" in url
        ]
    )

    for rfc_url in normalized_candidates:
        if not rfc_url:
            continue
        if not rfc_url.startswith("http"):
            rfc_url = f"https://{rfc_url.lstrip('/')}"
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
        abstract = _normalize_whitespace(
            _extract_abstract(page_meta, source="rfc_editor", title=title, strict=True)
        )
        if abstract_match:
            abstract = _normalize_whitespace(_strip_html(abstract_match.group(1)))
        if not abstract:
            meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", page)
            if meta_desc:
                abstract = _normalize_whitespace(meta_desc.group(1))
        title_match = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
        doc_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
        publication_date = _extract_publication_date(page_meta)
        if abstract or publication_date:
            return FetchResult(
                title=doc_title,
                abstract=abstract,
                source="rfc_editor",
                source_id=rfc_url.rstrip("/").rsplit("/", 1)[-1],
                match_status="exact_id",
                match_score=1.0,
                publication_date=publication_date,
                raw_metadata={
                    "url": rfc_url,
                    "page_meta": page_meta,
                    "title": doc_title,
                    "abstract": abstract,
                },
            ), "match" if abstract else "match_no_abstract"

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
    page_meta = _extract_html_meta_tags(page)
    abstract = _normalize_whitespace(
        _extract_abstract(page_meta, source="rfc_editor", title=title, strict=True)
    )
    abstract_match = re.search(
        r"<section[^>]*id=\"abstract\"[^>]*>(.*?)</section>",
        page,
        re.IGNORECASE | re.DOTALL,
    )
    if abstract_match:
        abstract = _normalize_whitespace(_strip_html(abstract_match.group(1)))
    if not abstract:
        meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", page)
        if meta_desc:
            abstract = _normalize_whitespace(meta_desc.group(1))
    title_match = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    doc_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
    publication_date = _extract_publication_date(page_meta)
    if not abstract and not publication_date:
        return None, "no_match_or_no_abstract"
    result = FetchResult(
        title=doc_title,
        abstract=abstract,
        source="rfc_editor",
        source_id=f"RFC{rfc_id}",
        match_status="exact_title",
        match_score=1.0,
        publication_date=publication_date,
        raw_metadata={
            "url": rfc_url,
            "page_meta": page_meta,
            "title": doc_title,
            "abstract": abstract,
        },
    )
    return result, "match" if abstract else "match_no_abstract"


# --- Source: BSI ---

def _fetch_bsi_by_title(
    session: requests.Session,
    limiter: RateLimiter,
    title: str,
    *,
    candidate_urls: Optional[list[str]] = None,
) -> Tuple[Optional[FetchResult], str]:
    query_title = _prepare_title_query(title)
    normalized_candidates = _dedupe_values(
        [
            _normalize_whitespace(url)
            for url in (candidate_urls or [])
            if isinstance(url, str) and "knowledge.bsigroup.com/products/" in url
        ]
    )
    for product_url in normalized_candidates:
        if not product_url:
            continue
        if not product_url.startswith("http"):
            product_url = f"https://{product_url.lstrip('/')}"
        product_page = _request_text(
            session,
            product_url,
            source="bsi",
            limiter=limiter,
            headers={"User-Agent": USER_AGENT},
        )
        page_meta = _extract_html_meta_tags(product_page)
        abstract = _normalize_whitespace(_extract_abstract(page_meta, source="bsi", title=title, strict=True))
        if not abstract:
            meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", product_page)
            if meta_desc:
                abstract = _normalize_whitespace(meta_desc.group(1))
        publication_date = _extract_publication_date(page_meta)
        if abstract or publication_date:
            title_match = re.search(r"<title>(.*?)</title>", product_page, re.IGNORECASE | re.DOTALL)
            product_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
            return FetchResult(
                title=product_title,
                abstract=abstract,
                source="bsi",
                source_id=product_url,
                match_status="exact_id",
                match_score=1.0,
                publication_date=publication_date,
                raw_metadata={
                    "url": product_url,
                    "page_meta": page_meta,
                    "title": product_title,
                    "abstract": abstract,
                },
            ), "match" if abstract else "match_no_abstract"

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
    page_meta = _extract_html_meta_tags(product_page)
    abstract = _normalize_whitespace(_extract_abstract(page_meta, source="bsi", title=title, strict=True))
    if not abstract:
        meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", product_page)
        abstract = _normalize_whitespace(meta_desc.group(1)) if meta_desc else ""
    publication_date = _extract_publication_date(page_meta)
    if not abstract and not publication_date:
        return None, "no_match_or_no_abstract"
    title_match = re.search(r"<title>(.*?)</title>", product_page, re.IGNORECASE | re.DOTALL)
    product_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
    result = FetchResult(
        title=product_title,
        abstract=abstract,
        source="bsi",
        source_id=product_url,
        match_status="exact_title",
        match_score=1.0,
        publication_date=publication_date,
        raw_metadata={
            "url": product_url,
            "page_meta": page_meta,
            "title": product_title,
            "abstract": abstract,
        },
    )
    return result, "match" if abstract else "match_no_abstract"


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

    matched, match_score, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
        expected_year=None,
    )
    if not matched:
        return None, "no_match"

    abstract = _normalize_whitespace(_extract_abstract(matched, source="github", title=title, strict=True))
    publication_date = _extract_publication_date(matched.get("raw", {}))
    if not abstract and not publication_date:
        return None, "no_match_or_no_description"
    source_title = _normalize_whitespace(matched.get("title") or title)
    result = FetchResult(
        title=source_title,
        abstract=abstract,
        source="github",
        source_id=_normalize_whitespace(matched.get("full_name")),
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else matched,
    )
    return result, "match" if abstract else "match_no_description"


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

    matched, match_score, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
        expected_year=None,
    )
    if not matched:
        return None, "no_match"
    abstract = _normalize_whitespace(_extract_abstract(matched, source="huggingface", title=title, strict=True))
    publication_date = _extract_publication_date(matched.get("raw", {}))
    if not abstract and not publication_date:
        return None, "no_match_or_no_description"

    result = FetchResult(
        title=_normalize_whitespace(matched.get("title")),
        abstract=abstract,
        source="huggingface",
        source_id=_normalize_whitespace(matched.get("id")),
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else matched,
    )
    return result, "match" if abstract else "match_no_description"


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
    page_meta = _extract_html_meta_tags(page)
    abstract = _normalize_whitespace(
        _extract_abstract(page_meta, source="keithito", title=title, strict=True)
    )
    if not abstract:
        meta_desc = re.search(r"name=\"description\" content=\"([^\"]+)\"", page)
        abstract = _normalize_whitespace(meta_desc.group(1)) if meta_desc else ""
    publication_date = _extract_publication_date(page_meta)
    if not abstract and not publication_date:
        return None, "no_match_or_no_description"
    title_match = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    dataset_title = _normalize_whitespace(_strip_html(title_match.group(1))) if title_match else title
    result = FetchResult(
        title=dataset_title,
        abstract=abstract,
        source="keithito",
        source_id=url,
        match_status="exact_title",
        match_score=1.0,
        publication_date=publication_date,
        raw_metadata={
            "url": url,
            "page_meta": page_meta,
            "title": dataset_title,
            "abstract": abstract,
        },
    )
    return result, "match" if abstract else "match_no_description"


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

    matched, match_score, match_status = _select_best_match(
        title,
        candidates,
        title_key="title",
        allow_fuzzy=allow_fuzzy,
        min_similarity=min_similarity,
    )
    if not matched:
        return None, "no_match"

    abstract = _normalize_whitespace(_extract_abstract(matched, source="zenodo", title=title, strict=True))
    publication_date = _extract_publication_date(matched.get("raw", {}))
    if not abstract and not publication_date:
        return None, "no_match_or_no_description"

    result = FetchResult(
        title=_normalize_whitespace(matched.get("title")),
        abstract=abstract,
        source="zenodo",
        source_id=str(matched.get("id")),
        match_status=match_status,
        match_score=match_score,
        publication_date=publication_date,
        raw_metadata=matched.get("raw") if isinstance(matched.get("raw"), dict) else matched,
    )
    return result, "match" if abstract else "match_no_description"


def _build_metadata_record(
    entry: Dict[str, Any],
    result: Optional[FetchResult],
    expected_year: Optional[int],
) -> Dict[str, Any]:
    title = entry.get("query_title") or entry.get("title")
    result = _sanitize_fetch_result(result, _normalize_whitespace(title))
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
                "match_score": 0.0,
                "publication_date": None,
                "abstract_present": False,
                "publication_date_present": False,
                "resolved": False,
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
            "match_score": result.match_score,
            "publication_date": result.publication_date,
            "abstract_present": bool(result.abstract),
            "publication_date_present": bool(result.publication_date),
            "resolved": _is_resolved(result),
            "missing_reason": _resolve_missing_reason(result, expected_year),
        }
    )
    return record


def _build_sources_record(
    entry: Dict[str, Any],
    result: Optional[FetchResult],
    expected_year: Optional[int],
) -> Dict[str, Any]:
    title = entry.get("query_title") or entry.get("title")
    result = _sanitize_fetch_result(result, _normalize_whitespace(title))
    if result is None:
        return {
            "key": entry.get("key"),
            "title": entry.get("query_title"),
            "source": None,
            "source_id": None,
            "match_status": "missing",
            "match_score": 0.0,
            "publication_date": None,
        "publication_date_present": False,
        "abstract_present": False,
        "resolved": False,
        "abstract_source": "missing",
        "abstract_source_reason": "missing:abstract_unavailable",
        "missing_reason": "no_match",
    }

    return {
        "key": entry.get("key"),
        "title": result.title,
        "source": result.source,
        "source_id": result.source_id,
        "match_status": result.match_status,
        "match_score": result.match_score,
        "publication_date": result.publication_date,
        "publication_date_present": bool(result.publication_date),
        "abstract_present": bool(result.abstract),
        "resolved": _is_resolved(result),
        "abstract_source": result.source,
        "abstract_source_reason": f"{result.source}:{result.match_status}",
        "missing_reason": _resolve_missing_reason(result, expected_year),
    }


def _build_full_metadata_record(
    entry: Dict[str, Any],
    result: Optional[FetchResult],
    expected_year: Optional[int],
) -> Dict[str, Any]:
    title = entry.get("query_title") or entry.get("title")
    result = _sanitize_fetch_result(result, _normalize_whitespace(title))
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
        "publication_date": result.publication_date,
        "abstract_present": bool(result.abstract),
        "publication_date_present": bool(result.publication_date),
        "resolved": _is_resolved(result),
        "missing_reason": _resolve_missing_reason(result, expected_year),
        "match_score": result.match_score,
        "source_metadata": _prune_heavy_source_fields(result.source, result.raw_metadata),
    }

def _enrich_with_url_abstract(
    session: requests.Session,
    limiter: RateLimiter,
    result: Optional[FetchResult],
    *,
    fallback_urls: list[str],
    trace_steps: list[str],
) -> Optional[FetchResult]:
    if result is None:
        return None
    if result.abstract and result.publication_date:
        return result

    fallback_urls = _dedupe_values(fallback_urls or [])
    for fallback_url in fallback_urls[:8]:
        if not fallback_url:
            continue
        page_text, is_pdf = _read_source_text(
            session,
            limiter,
            fallback_url,
            trace_steps=trace_steps,
        )
        if not page_text:
            continue

        source_type = "pdf" if is_pdf else "html"
        page_meta: dict[str, Any] = {}
        page_title: str = ""
        page_date: Optional[str] = None
        if is_pdf:
            page_title = _normalize_whitespace(_extract_abstract_from_pdf_text(page_text))
            page_date = _extract_year_from_text_snippet(page_text)
        else:
            page_meta = _extract_html_meta_tags(page_text)
            page_title = _normalize_whitespace(
                _first_non_empty(
                    [
                        page_meta.get("og:title"),
                        page_meta.get("citation_title"),
                        page_meta.get("dc.title"),
                        page_meta.get("title"),
                    ]
                )
            )
            page_date = _extract_publication_date(page_meta)

        abstract, abstract_source = _extract_abstract_from_source_text(
            page_text,
            source_type,
            title=result.title,
        )
        if not abstract and not page_text:
            continue
        if source_type == "pdf":
            abstract_source = f"{abstract_source}:{fallback_url}"

        needs_abstract = not result.abstract
        needs_date = not result.publication_date

        if needs_abstract and not _abstract_candidate_is_valid(abstract):
            continue
        if needs_abstract and _is_title_like_text(abstract, title=result.title):
            continue

        if needs_abstract and needs_date and not page_date:
            trace_steps.append(f"url_fallback:date_missing:{fallback_url}")
            continue
        if needs_abstract:
            if not _abstract_candidate_is_valid(abstract):
                continue
            trace_steps.append(f"url_fallback:{abstract_source}:{fallback_url}")
            return FetchResult(
                title=result.title or page_title or _normalize_whitespace(result.title),
                abstract=abstract,
                source=result.source,
                source_id=result.source_id or fallback_url,
                match_status=(
                    result.match_status
                    if result.match_status != "match_no_abstract"
                    else "match_no_abstract+url_fallback"
                ),
                match_score=result.match_score,
                publication_date=result.publication_date or page_date,
                raw_metadata={
                    **(result.raw_metadata or {}),
                    "abstract_fallback": {
                        "url": fallback_url,
                        "abstract_source": abstract_source,
                        "source": "url_fallback",
                    },
                    "abstract_fallback_source_page_metadata": page_meta,
                },
            )

        if needs_date:
            if not page_date:
                trace_steps.append(f"url_fallback:date_missing:{fallback_url}")
                continue
            return FetchResult(
                title=result.title or page_title or _normalize_whitespace(result.title),
                abstract=result.abstract,
                source=result.source,
                source_id=result.source_id or fallback_url,
                match_status=(
                    result.match_status
                    if result.match_status != "match_no_abstract"
                    else "match_no_abstract+url_fallback"
                ),
                match_score=result.match_score,
                publication_date=page_date,
                raw_metadata={
                    **(result.raw_metadata or {}),
                    "abstract_fallback": {
                        "url": fallback_url,
                        "abstract_source": "date_only",
                        "source": "url_fallback",
                    },
                    "abstract_fallback_source_page_metadata": page_meta,
                },
            )

    if not fallback_urls:
        trace_steps.append("url_fallback:skipped_no_urls")
    else:
        trace_steps.append("url_fallback:all_failed")
    return result


def _publication_year_from_value(value: Optional[str]) -> Optional[int]:
    return _extract_year(value)


def _is_resolved(result: Optional[FetchResult]) -> bool:
    if result is None:
        return False
    return bool(result.abstract and result.publication_date)


def _resolve_missing_reason(result: Optional[FetchResult], expected_year: Optional[int]) -> Optional[str]:
    if result is None:
        return "no_match"
    has_abstract = bool(result.abstract)
    has_date = bool(result.publication_date)
    if has_date and expected_year:
        detected_year = _publication_year_from_value(result.publication_date)
        if detected_year and abs(detected_year - expected_year) > 1:
            return "date_abstract_mismatch" if has_abstract else "date_ambiguous"
    if has_abstract and has_date:
        return None
    if has_abstract and not has_date:
        return "date_missing"
    if has_date and not has_abstract:
        return "abstract_missing"
    return "abstract_and_date_missing"


def _apply_expected_year_fallback(
    result: Optional[FetchResult],
    expected_year: Optional[int],
) -> Optional[FetchResult]:
    if result is None:
        return None
    if result.publication_date:
        return result
    if not expected_year:
        return result
    expected_year = int(expected_year)
    if expected_year < 1000 or expected_year > 2500:
        return result
    fallback_date = f"{expected_year:04d}-01-01"
    return FetchResult(
        title=result.title,
        abstract=result.abstract,
        source=result.source,
        source_id=result.source_id,
        match_status=result.match_status,
        match_score=result.match_score,
        publication_date=fallback_date,
        raw_metadata=result.raw_metadata,
    )


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


def _load_local_cache(path: Path) -> list[Dict[str, Any]]:
    """Load cached title metadata (e.g., `arxiv_metadata.json`) into a record list."""
    if not path.exists():
        return []

    payload: Any
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    records: list[Dict[str, Any]] = []
    if isinstance(payload, list):
        iterable = payload
    elif isinstance(payload, dict):
        if "items" in payload and isinstance(payload["items"], list):
            iterable = payload["items"]
        elif "records" in payload and isinstance(payload["records"], list):
            iterable = payload["records"]
        else:
            iterable = [payload]
    else:
        return records

    for item in iterable:
        if not isinstance(item, dict):
            continue
        records.append(item)
    return records


def _normalize_cache_key(value: Any) -> str:
    text = _normalize_metadata_value(value)
    if not text:
        return ""
    return text.lower()


def _cache_key_terms(item: Dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    if not isinstance(item, dict):
        return terms

    for raw_value in (
        item.get("key"),
        item.get("query"),
        item.get("query_title"),
        item.get("title"),
        item.get("normalized_title"),
        item.get("doi"),
        item.get("source"),
        item.get("source_id"),
        item.get("id"),
        item.get("source_url"),
        item.get("url"),
        item.get("file_path"),
    ):
        normalized = _normalize_cache_key(raw_value)
        if normalized:
            terms.add(normalized)
            terms.update(_extract_urls((normalized,)))
            terms.update(_extract_dois((normalized,)))

    raw_metadata = item.get("metadata")
    if isinstance(raw_metadata, dict):
        terms.update(_normalize_cache_key(raw_metadata.get(k)) for k in ("doi", "source_url", "url", "id") if _normalize_cache_key(raw_metadata.get(k)))
        terms.update(_extract_urls(_normalize_metadata_value(v) for v in raw_metadata.values() if isinstance(v, str)))
        terms.update(_extract_dois(_normalize_metadata_value(v) for v in raw_metadata.values() if isinstance(v, str)))

    for title_value in (item.get("title"), item.get("query"), item.get("query_title"), item.get("normalized_title")):
        normalized_title = _normalize_whitespace(title_value or "")
        if not normalized_title:
            continue
        terms.add(_normalize_title_signature(normalized_title))
        terms.add(normalize_title(normalized_title))

    return terms


def _entry_cache_terms(entry: Dict[str, Any], candidate_titles: list[str]) -> set[str]:
    terms: set[str] = set()
    key = _normalize_cache_key(entry.get("key"))
    if key:
        terms.add(key)

    for title in candidate_titles:
        normalized_title = _normalize_whitespace(title)
        if not normalized_title:
            continue
        terms.add(_normalize_cache_key(normalized_title))
        terms.add(_normalize_title_signature(normalized_title))
        terms.add(normalize_title(normalized_title))

    terms.update(_extract_dois(candidate_titles))
    terms.update(_extract_urls(candidate_titles))

    raw = entry.get("raw", {})
    if isinstance(raw, dict):
        raw_local = raw.get("local", {})
        if isinstance(raw_local, dict):
            terms.update(_extract_dois(_normalize_metadata_value(v) for v in raw_local.values() if isinstance(v, str)))
            terms.update(_extract_urls(_normalize_metadata_value(v) for v in raw_local.values() if isinstance(v, str)))
            for value in (raw_local.get("doi"), raw_local.get("url"), raw_local.get("howpublished"), raw_local.get("note")):
                normalized = _normalize_cache_key(value)
                if normalized:
                    terms.add(normalized)
        for value in (raw.get("doi"), raw.get("url"), raw.get("howpublished"), raw.get("note"), raw.get("source_url")):
            normalized = _normalize_cache_key(value)
            if normalized:
                terms.add(normalized)
            terms.update(_extract_urls((normalized,)))
            terms.update(_extract_dois((normalized,)))

    return terms


def _select_cache_match(
    entry: Dict[str, Any],
    cache: list[Dict[str, Any]],
    entry_title: str,
    candidate_titles: list[str],
    expected_year: Optional[int],
) -> Optional[Tuple[Dict[str, Any], float, str]]:
    if not cache:
        return None

    entry_terms = _entry_cache_terms(entry, candidate_titles)
    best: Optional[Tuple[Dict[str, Any], float, str]] = None
    best_with_abstract: Optional[Tuple[Dict[str, Any], float, str]] = None
    entry_title_norm = normalize_title(entry_title) if entry_title else ""
    for item in cache:
        if not isinstance(item, dict):
            continue

        cache_terms = _cache_key_terms(item)
        overlap = len(entry_terms & cache_terms)
        if overlap == 0 and not entry_title_norm:
            continue

        candidate_title = _normalize_whitespace(
            item.get("title")
            or item.get("query")
            or item.get("query_title")
            or item.get("normalized_title")
            or item.get("key")
            or ""
        )
        candidate_title_norm = normalize_title(candidate_title) if candidate_title else ""
        title_similarity = _jaccard_similarity(candidate_title, entry_title) if candidate_title else 0.0
        if not overlap and title_similarity < 0.6:
            continue

        key_exact = 1 if _normalize_cache_key(item.get("key")) in entry_terms else 0
        doi_overlap = 0
        raw_dois = set(
            _extract_dois(
                (
                    _normalize_metadata_value(item.get("doi")),
                    _normalize_metadata_value(item.get("source_id")),
                )
            )
        )
        entry_dois = set(_extract_dois(tuple(candidate_titles)))
        if raw_dois & entry_dois:
            doi_overlap = 1
        if not doi_overlap:
            raw_url_terms = set(
                _extract_urls(
                    (
                        _normalize_metadata_value(item.get("source_url")),
                        _normalize_metadata_value(item.get("url")),
                        _normalize_metadata_value(item.get("file_path")),
                    )
                )
            )
            if raw_url_terms & entry_terms:
                url_overlap = 1
            else:
                url_overlap = 0
        else:
            url_overlap = 0

        candidate_year = _extract_year(
            item.get("publication_year")
            or item.get("year")
            or item.get("publicationYear")
            or item.get("publication_date")
        )
        year_bonus = 0.0
        if expected_year and candidate_year:
            if candidate_year == expected_year:
                year_bonus = 0.3
            elif abs(expected_year - candidate_year) == 1:
                year_bonus = 0.15

        score = (
            6.0 * key_exact
            + 4.0 * doi_overlap
            + 2.0 * url_overlap
            + title_similarity * 3.0
            + (1.0 if overlap else 0.0)
            + year_bonus
        )
        match_title = _normalize_whitespace(
            item.get("title")
            or item.get("query")
            or item.get("query_title")
            or item.get("normalized_title")
            or item.get("key")
            or ""
        )
        cached_abstract = _extract_cached_item_abstract(item, match_title or entry_title)
        if cached_abstract:
            # Prefer cache records that truly provide an abstract.
            score += 4.0
            has_abstract = True
        elif item.get("abstract") or item.get("summary") or item.get("description") or item.get("note"):
            # Penalize cache hits that only carry title-like/noise abstract fields.
            score -= 1.0
            has_abstract = False
        else:
            has_abstract = False
        if _extract_publication_date(item):
            score += 0.4

        match_status = "exact_id" if key_exact or doi_overlap or url_overlap else "fuzzy_title"

        if has_abstract:
            if best_with_abstract is None or score > best_with_abstract[1]:
                best_with_abstract = (item, score, match_status)
        elif best is None or score > best[1]:
            best = (item, score, match_status)

    return best_with_abstract or best


def _extract_cache_publication_date(item: Dict[str, Any]) -> Optional[str]:
    publication_date = _extract_publication_date(item)
    if publication_date:
        return publication_date

    fallback_keys = (
        "publication_year",
        "year",
        "published",
        "publicationYear",
        "yearPublished",
        "year_published",
    )
    for key in fallback_keys:
        date_value = _to_iso_date(item.get(key))
        if date_value:
            return date_value

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        return _extract_publication_date(metadata)
    return None


def _extract_cached_item_abstract(item: Dict[str, Any], title: str) -> str:
    """Extract usable abstract from a cache record."""
    title = _normalize_whitespace(title)
    source_hint = str(item.get("source") or "crossref")
    raw_metadata = item.get("metadata")

    if isinstance(raw_metadata, dict):
        abstract = _extract_abstract(raw_metadata, source=source_hint, title=title, strict=True)
    else:
        abstract = ""
    if not abstract:
        abstract = _extract_abstract(item, source=source_hint, title=title, strict=True)
    if not abstract:
        for value in (
            item.get("abstract"),
            item.get("summary"),
            item.get("description"),
            item.get("note"),
        ):
            if not value:
                continue
            candidate = _normalize_metadata_value(value)
            if not candidate or _is_title_like_text(candidate, title=title):
                continue
            if not _abstract_candidate_is_valid(candidate):
                continue
            abstract = candidate
            break
    if not abstract:
        abstract = _pick_first_valid_abstract(
            item,
            title=title,
            source=source_hint,
        )
    return _normalize_whitespace(abstract)


def _fetch_from_metadata_cache(entry: Dict[str, Any], cache: list[Dict[str, Any]]) -> Optional[FetchResult]:
    """Create a FetchResult directly from the local cache when available."""
    candidates = _entry_candidates(entry)
    title = _title_from_entry(entry)
    if not title:
        title = candidates.get("titles", [""])[0] if candidates.get("titles") else ""
    selected = _select_cache_match(
        entry,
        cache,
        title,
        candidates.get("titles") or [],
        candidates.get("expected_year"),
    )
    if selected is None:
        return None

    item, _match_score, match_status = selected
    title = _normalize_whitespace(
        _title_from_entry(item)
        or item.get("title")
        or item.get("query")
        or item.get("query_title")
        or item.get("normalized_title")
        or item.get("key")
        or ""
    )
    source_hint = str(item.get("source") or "crossref")
    raw_metadata = item.get("metadata")
    abstract = _extract_cached_item_abstract(item, title)

    publication_date = _extract_cache_publication_date(item)
    if not publication_date and isinstance(raw_metadata, dict):
        publication_date = _extract_cache_publication_date(raw_metadata)

    if not publication_date and isinstance(item.get("metadata"), dict):
        publication_date = _extract_cache_publication_date(item.get("metadata"))

    source_id = str(item.get("source_id") or item.get("id") or item.get("doi") or "")
    result = FetchResult(
        title=title,
        abstract=abstract,
        source=source_hint,
        source_id=source_id,
        match_status=match_status,
        match_score=float(_match_score),
        publication_date=publication_date,
        raw_metadata=raw_metadata if isinstance(raw_metadata, dict) else dict(item),
    )
    if not result.abstract and not result.publication_date:
        return None
    return result



def _metadata_cache_paths(output_dir: Path) -> list[Path]:
    """Collect metadata cache candidate files to improve offline matching coverage."""
    paths: list[Path] = []
    seen: set[str] = set()
    base_dirs: list[Path] = []
    env_cache_dirs = [
        Path(raw_path).expanduser().resolve()
        for raw_path in os.getenv("AUTO_SR_METADATA_CACHE_DIRS", "").split(os.pathsep)
        if raw_path.strip()
    ]
    for base_dir in (output_dir, Path.cwd(), REPO_ROOT):
        base_dir = base_dir.resolve()
        base_dirs.append(base_dir)
        base_dirs.extend(base_dir.parents)

    deduped_base_dirs: list[Path] = []
    for base_dir in base_dirs:
        if base_dir not in deduped_base_dirs:
            deduped_base_dirs.append(base_dir)

    cache_roots: list[Path] = list(deduped_base_dirs)
    cache_roots.extend(env_cache_dirs)
    # Try sibling workspace-style folders that often host pre-collected metadata caches.
    for base_dir in deduped_base_dirs:
        candidate_roots = [base_dir / "find_pdf"]
        if base_dir.parent:
            candidate_roots.append(base_dir.parent / "find_pdf")
        for cache_root in candidate_roots:
            if cache_root.exists():
                cache_roots.append(cache_root)

    deduped_cache_roots: list[Path] = []
    for root in cache_roots:
        if root not in deduped_cache_roots:
            deduped_cache_roots.append(root)

    cache_names = ("arxiv_metadata.json", *DEFAULT_SECONDARY_METADATA_CACHE_PATHS)
    for base_dir in deduped_cache_roots:
        for cache_name in cache_names:
            candidate = Path(base_dir) / cache_name
            if not candidate.exists():
                continue
            resolved = str(candidate.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(candidate)
    return paths


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
    start_index: int,
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
    use_url_fallback: bool,
    use_zenodo: bool,
    skip_non_scholar_sources: bool,
    skip_dblp: bool,
    skip_google_books: bool,
) -> tuple[int, int, int, float]:
    """Collect title/abstract metadata for a single reference_oracle input."""
    metadata_path = output_dir / "title_abstracts_metadata.jsonl"
    sources_path = output_dir / "title_abstracts_sources.jsonl"
    trace_path = output_dir / "title_abstracts_source_trace.jsonl"
    full_metadata_path = output_dir / "title_abstracts_full_metadata.jsonl"

    all_entries = _load_reference_entries(input_path)
    entries = list(all_entries)
    if start_index < 0:
        start_index = 0
    if start_index:
        entries = entries[start_index:]
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
    metadata_cache_paths = _metadata_cache_paths(output_dir)
    metadata_cache: list[Dict[str, Any]] = []
    for cache_path in metadata_cache_paths:
        metadata_cache.extend(_load_local_cache(cache_path))

    semantic_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")

    limiter = RateLimiter(RATE_LIMITS)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    metadata_records: Dict[str, Dict[str, Any]] = dict(existing_metadata)
    sources_records: Dict[str, Dict[str, Any]] = dict(existing_sources)
    trace_records: Dict[str, Dict[str, Any]] = dict(existing_traces)
    full_metadata_records: Dict[str, Dict[str, Any]] = dict(existing_full_metadata)
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
            existing_resolved = existing.get("resolved")
            if isinstance(existing_resolved, bool):
                can_skip = existing_resolved
            else:
                # Backward-compatible fallback: older outputs used only match_status.
                can_skip = (
                    existing.get("match_status") not in {"missing", "match_no_abstract", "match_no_description", "match_no_abstract+url_fallback"}
                )
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

        candidates = _entry_candidates(entry)
        candidate_titles = candidates.get("titles") or []
        title = _title_from_entry(entry)
        if not title:
            title = candidate_titles[0] if candidate_titles else ""
            if not title:
                title = ""
        else:
            # Keep metadata-derived title variants for downstream matching, but do not let entry keys override the query title.
            title = _normalize_whitespace(_prepare_title_query(title))
        expected_year = candidates.get("expected_year")
        candidate_arxiv_ids = candidates.get("arxiv_ids") or []
        candidate_doi_list = candidates.get("dois") or []
        candidate_urls = _extract_candidate_urls(entry)
        candidate_arxiv = candidate_arxiv_ids[0] if candidate_arxiv_ids else None
        trace_steps: list[str] = []
        best_result: Optional[FetchResult] = None
        candidate_doi: Optional[str] = None
        openalex_landing_url: Optional[str] = None
        fallback_urls: list[str] = list(candidate_urls)
        best_priority: tuple[int, float, int, int, int, int] = (
            -1,
            -1.0,
            -1,
            -1,
            -1,
            -1,
        )
        stop_early = False

        if candidate_doi_list:
            candidate_doi = _normalize_doi(candidate_doi_list[0])

        def _collect_fallback_urls(candidate_result: Optional[FetchResult]) -> None:
            if candidate_result is None:
                return
            fallback_urls.extend(_extract_candidate_urls(entry, candidate_result))

        def _priority(result_to_score: FetchResult) -> tuple[int, float, int, int, int]:
            has_abstract = 1 if bool(result_to_score.abstract) else 0
            has_date = 1 if bool(result_to_score.publication_date) else 0
            non_local = 0 if result_to_score.source == "local" else 1
            source_score = SOURCE_RANK.get(result_to_score.source, len(SOURCE_ORDER))
            return (
                1 if has_abstract and has_date else 0,
                result_to_score.match_score,
                has_abstract,
                has_date,
                -source_score,
                non_local,
            )

        def _consider(candidate_result: Optional[FetchResult], source_status: str) -> bool:
            nonlocal best_result, best_priority
            if candidate_result is None:
                return False
            candidate_result = _sanitize_fetch_result(candidate_result, title)
            if candidate_result is None:
                trace_steps.append(f"{source_status}:discarded")
                return False

            _collect_fallback_urls(candidate_result)
            priority = _priority(candidate_result)
            if priority > best_priority:
                best_result = candidate_result
                best_priority = priority
                if (
                    _is_resolved(candidate_result)
                    and candidate_result.source in EARLY_STOP_SOURCES
                    and candidate_result.match_score >= min_similarity
                ):
                    trace_steps.append(f"early_stop:{source_status}")
                    return True
            return False

        # 0) local metadata fallback
        cache_result = _fetch_from_metadata_cache(entry, metadata_cache)
        if cache_result:
            trace_steps.append("arxiv_metadata:cache_hit")
            stop_early = _consider(cache_result, "arxiv_metadata:cache_hit")

        # 1) local metadata fallback
        if not stop_early:
            local_result = _build_candidate_result_from_entry(entry)
            if local_result:
                stop_early = _consider(local_result, "local")

        # 2) arXiv
        if not stop_early:
            try:
                if candidate_arxiv:
                    metadata = _fetch_arxiv_metadata_by_id(session, limiter, candidate_arxiv) or {}
                    abstract = _extract_abstract(metadata, source="arxiv", title=title, strict=True)
                    publication_date = _extract_publication_date(metadata)
                    if abstract:
                        result = FetchResult(
                            title=_normalize_whitespace(metadata.get("title")),
                            abstract=abstract,
                            source="arxiv",
                            source_id=candidate_arxiv,
                            match_status="exact_id" if _normalize_whitespace(metadata.get("title")) else "match",
                            match_score=1.0,
                            publication_date=publication_date,
                            raw_metadata=metadata,
                        )
                        trace_steps.append("arxiv:match")
                        stop_early = _consider(result, "arxiv:match")
                    else:
                        if publication_date:
                            result = FetchResult(
                                title=_normalize_whitespace(metadata.get("title")),
                                abstract="",
                                source="arxiv",
                                source_id=candidate_arxiv,
                                match_status="match_no_abstract",
                                match_score=0.85,
                                publication_date=publication_date,
                                raw_metadata=metadata,
                            )
                            trace_steps.append("arxiv:match_no_abstract")
                            stop_early = _consider(result, "arxiv:match_no_abstract")
                        else:
                            trace_steps.append("arxiv:no_match_or_no_abstract")
                elif arxiv_max_results > 0:
                    result, status = _fetch_arxiv_by_title(
                        session,
                        limiter,
                        title,
                        allow_fuzzy=allow_fuzzy,
                        min_similarity=min_similarity,
                        max_results=arxiv_max_results,
                        expected_year=expected_year,
                    )
                    trace_steps.append(f"arxiv:{status}")
                    stop_early = _consider(result, f"arxiv:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"arxiv:error_{type(exc).__name__}")
                result = None

        # 3) Semantic Scholar
        if not stop_early:
            try:
                result, status = _fetch_semantic_by_title(
                    session,
                    limiter,
                    title,
                    api_key=semantic_api_key,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=semantic_max_results,
                    expected_year=expected_year,
                    candidate_doi=candidate_doi,
                )
                trace_steps.append(f"semantic_scholar:{status}")
                stop_early = _consider(result, f"semantic_scholar:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"semantic_scholar:error_{type(exc).__name__}")
                pass

        # 4) DBLP (for DOI hint)
        if dblp_max_results > 0 and not skip_dblp:
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
                if candidate_doi and not candidate_doi_list:
                    candidate_doi = _normalize_doi(candidate_doi)
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"dblp:error_{type(exc).__name__}")
                candidate_doi = None
                pass

        # 5) OpenAlex
        if openalex_max_results > 0:
            try:
                result, status, openalex_doi, landing_url = _fetch_openalex_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=openalex_max_results,
                    candidate_doi=candidate_doi,
                    expected_year=expected_year,
                )
                trace_steps.append(f"openalex:{status}")
                stop_early = _consider(result, f"openalex:{status}")
                if openalex_doi and not candidate_doi:
                    candidate_doi = openalex_doi
                if landing_url:
                    openalex_landing_url = landing_url
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"openalex:error_{type(exc).__name__}")
                pass

        # 6) Crossref
        try:
            result, status = _fetch_crossref_by_title(
                session,
                limiter,
                title,
                allow_fuzzy=allow_fuzzy,
                min_similarity=min_similarity,
                max_results=crossref_max_results,
                candidate_doi=candidate_doi,
                expected_year=expected_year,
            )
            trace_steps.append(f"crossref:{status}")
            stop_early = _consider(result, f"crossref:{status}")
        except Exception as exc:  # noqa: BLE001
            trace_steps.append(f"crossref:error_{type(exc).__name__}")
            pass

        # 6) Google Books (fallback for older books/proceedings without strict APIs)
        if not stop_early and not skip_google_books:
            try:
                result, status = _fetch_google_books_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    max_results=crossref_max_results,
                    expected_year=expected_year,
                )
                trace_steps.append(f"google_books:{status}")
                stop_early = _consider(result, f"google_books:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"google_books:error_{type(exc).__name__}")
                pass

        # 7) ACL Anthology
        if not stop_early and not skip_non_scholar_sources:
            try:
                result, status = _fetch_acl_anthology_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                    expected_year=expected_year,
                    candidate_urls=candidate_urls,
                )
                trace_steps.append(f"acl_anthology:{status}")
                stop_early = _consider(result, f"acl_anthology:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"acl_anthology:error_{type(exc).__name__}")
                pass

        # 8) LREC summary (using OpenAlex landing page)
        if not stop_early and not skip_non_scholar_sources:
            try:
                lrec_urls = _dedupe_values([url for url in candidate_urls if "lrec-conf.org/proceedings" in url])
                if openalex_landing_url:
                    lrec_urls.append(openalex_landing_url)
                    lrec_urls = _dedupe_values(lrec_urls)
                result, status = _fetch_lrec_summary(
                    session,
                    limiter,
                    lrec_urls,
                    title,
                    expected_year=expected_year,
                )
                trace_steps.append(f"lrec_conf:{status}")
                stop_early = _consider(result, f"lrec_conf:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"lrec_conf:error_{type(exc).__name__}")
                pass

        # 9) RFC Editor
        if not stop_early and not skip_non_scholar_sources:
            try:
                result, status = _fetch_rfc_editor_by_title(
                    session,
                    limiter,
                    title,
                    candidate_urls=candidate_urls,
                )
                trace_steps.append(f"rfc_editor:{status}")
                stop_early = _consider(result, f"rfc_editor:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"rfc_editor:error_{type(exc).__name__}")
                pass

        # 10) BSI
        if not stop_early and not skip_non_scholar_sources:
            try:
                result, status = _fetch_bsi_by_title(
                    session,
                    limiter,
                    title,
                    candidate_urls=candidate_urls,
                )
                trace_steps.append(f"bsi:{status}")
                stop_early = _consider(result, f"bsi:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"bsi:error_{type(exc).__name__}")
                pass

        # 11) GitHub
        if not stop_early and not skip_non_scholar_sources:
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
                stop_early = _consider(result, f"github:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"github:error_{type(exc).__name__}")
                pass

        # 12) Hugging Face
        if not stop_early and not skip_non_scholar_sources:
            try:
                result, status = _fetch_huggingface_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                )
                trace_steps.append(f"huggingface:{status}")
                stop_early = _consider(result, f"huggingface:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"huggingface:error_{type(exc).__name__}")
                pass

        # 13) Keithito
        if not stop_early and not skip_non_scholar_sources:
            try:
                result, status = _fetch_keithito_by_title(
                    session,
                    limiter,
                    title,
                )
                trace_steps.append(f"keithito:{status}")
                stop_early = _consider(result, f"keithito:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"keithito:error_{type(exc).__name__}")
                pass

        # 14) Zenodo
        if not stop_early and use_zenodo:
            try:
                result, status = _fetch_zenodo_by_title(
                    session,
                    limiter,
                    title,
                    allow_fuzzy=allow_fuzzy,
                    min_similarity=min_similarity,
                )
                trace_steps.append(f"zenodo:{status}")
                stop_early = _consider(result, f"zenodo:{status}")
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"zenodo:error_{type(exc).__name__}")
                pass

        fallback_urls = _dedupe_values(fallback_urls)
        if use_url_fallback and best_result is not None and (
            not best_result.abstract or not best_result.publication_date
        ):
            try:
                best_result = _enrich_with_url_abstract(
                    session,
                    limiter,
                    best_result,
                    fallback_urls=fallback_urls,
                    trace_steps=trace_steps,
                )
            except Exception as exc:  # noqa: BLE001
                trace_steps.append(f"url_fallback:error_{type(exc).__name__}")
        best_result = _apply_expected_year_fallback(best_result, expected_year)

        metadata_records[key] = _build_metadata_record(entry, best_result, expected_year)
        sources_records[key] = _build_sources_record(entry, best_result, expected_year)
        trace_records[key] = {"key": key, "lookup_steps": trace_steps}
        if include_full_metadata:
            full_metadata_records[key] = _build_full_metadata_record(
                entry,
                best_result,
                expected_year,
            )

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

    if resume:
        ordered_keys = [
            str(e.get("key"))
            for e in all_entries
            if e.get("key") and str(e.get("key")) in metadata_records
        ]
    else:
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
        if record.get("resolved")
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
    start_index: int,
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
    use_url_fallback: bool,
    use_zenodo: bool,
    skip_non_scholar_sources: bool,
    skip_dblp: bool,
    skip_google_books: bool,
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
        if paper_name:
            target_output_dir = output_root
        else:
            target_output_dir = output_root / paper_dir.name / "metadata"
        print(f"[start] {paper_dir.name} -> {target_output_dir}")
        processed, matched, missing, elapsed = _collect_single_input(
            file_path,
            target_output_dir,
            limit=limit,
            start_index=start_index,
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
            use_url_fallback=use_url_fallback,
            use_zenodo=use_zenodo,
            skip_non_scholar_sources=skip_non_scholar_sources,
            skip_dblp=skip_dblp,
            skip_google_books=skip_google_books,
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
        "--start-index",
        type=int,
        default=0,
        help="Optional zero-based start index to skip entries before processing.",
    )
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
    parser.add_argument(
        "--use-url-fallback",
        type=parse_bool,
        default=True,
        help="Attempt URL fallback scraping when title/source match lacks abstract or date.",
    )
    parser.add_argument(
        "--use-zenodo",
        type=parse_bool,
        default=False,
        help="Query Zenodo as a fallback source.",
    )
    parser.add_argument(
        "--skip-non-scholar-sources",
        type=parse_bool,
        default=False,
        help="Skip RFC/BSI/GitHub/HuggingFace/Keithito fallback sources.",
    )
    parser.add_argument(
        "--skip-dblp",
        type=parse_bool,
        default=False,
        help="Skip DBLP lookup (often slow/hanging in restrictive networks).",
    )
    parser.add_argument(
        "--skip-google-books",
        type=parse_bool,
        default=False,
        help="Skip Google Books lookup (often slow or blocked in restrictive networks).",
    )
    args = parser.parse_args()

    load_env_file()

    start = time.perf_counter()

    totals = _collect_all_reference_oracles(
        Path(args.input_root),
        Path(args.output_root),
        args.paper_name,
        limit=args.limit,
        start_index=args.start_index,
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
        use_url_fallback=args.use_url_fallback,
        use_zenodo=args.use_zenodo,
        skip_non_scholar_sources=args.skip_non_scholar_sources,
        skip_dblp=args.skip_dblp,
        skip_google_books=args.skip_google_books,
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
