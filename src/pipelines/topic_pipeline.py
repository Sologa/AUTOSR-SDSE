"""Topic-driven end-to-end pipeline orchestration.

This module connects existing utilities in ``src/utils`` into a single,
parameterised workflow that can be driven by a CLI.

Design goals
------------
- Treat a single ``topic`` string as the primary input.
- Write all artefacts into a deterministic workspace directory so the user does
  not need to manually hunt through ``test_artifacts/``.
- Reuse existing, tested utilities (paper search, downloaders, keyword
  extraction, structured web search) without modifying protected files.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import sys
import time
import types
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

import requests

from src.utils.env import load_env_file
from src.utils.keyword_extractor import ExtractParams, extract_search_terms_from_surveys
from src.utils.llm import LLMResult, LLMService, ProviderCallError
from src.utils.openai_web_search import WebSearchOptions, create_web_search_service
from src.utils.paper_downloaders import fetch_arxiv_metadata
from src.utils.paper_workflows import (
    download_records_to_pdfs,
    extract_arxiv_id_from_record,
    search_arxiv_for_topic,
    search_dblp_for_topic,
    search_semantic_scholar_for_topic,
    trim_arxiv_id,
)
from src.utils.structured_web_search_pipeline import (
    CriteriaPipelineConfig,
    FormatterStageConfig,
    SearchStageConfig,
    run_structured_criteria_pipeline,
)


def slugify_topic(text: str) -> str:
    """Create a filesystem-friendly slug for a topic string."""

    base = "".join(
        "_"
        if not (ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        else ch
        for ch in text.strip()
    )
    base = "_".join(filter(None, base.split("_")))
    return base.lower() or "topic"


def _ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if missing, then return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    """Write JSON to disk with UTF-8 encoding."""
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    """Read JSON content from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file if it exists."""
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _update_registry_criteria_hash(registry_path: Path, criteria_hash: str) -> None:
    """Update criteria_hash in the registry JSON when it changes."""
    if not criteria_hash or not registry_path.exists():
        return
    payload = _read_json(registry_path)
    if not isinstance(payload, dict):
        return
    if payload.get("criteria_hash") == criteria_hash:
        return
    payload["criteria_hash"] = criteria_hash
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(registry_path, payload)


def _now_utc_stamp() -> str:
    """Return a compact UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def _parse_date_bound(raw: Optional[str], *, label: str) -> Optional[date]:
    """Parse a date bound from multiple supported string formats."""
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None
    if value.isdigit() and len(value) == 4:
        return date(int(value), 1, 1)
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError as exc:
        raise ValueError(f"Unable to parse {label}: {raw}") from exc


def _extract_publication_date(metadata: Dict[str, object]) -> Optional[date]:
    """Extract a publication date from common metadata fields."""
    for key in ("published", "published_date", "publication_date", "date", "year"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            return _parse_date_bound(str(raw), label=key)
        except ValueError:
            continue
    return None


def _load_cutoff_artifact(workspace: TopicWorkspace) -> Optional[Dict[str, object]]:
    """Load the cutoff artifact if it exists and is well-formed."""
    if not workspace.cutoff_path.exists():
        return None
    data = _read_json(workspace.cutoff_path)
    if isinstance(data, dict):
        return data
    return None


def _extract_candidate_cutoff_date(
    candidate: Dict[str, object],
    *,
    session: Optional[requests.Session] = None,
) -> Tuple[Optional[date], Optional[str]]:
    published_raw = candidate.get("published_date") or candidate.get("published")
    if isinstance(published_raw, str) and published_raw.strip():
        try:
            return _parse_date_bound(published_raw, label="published_date"), published_raw
        except ValueError:
            pass
    arxiv_id = candidate.get("arxiv_id")
    if isinstance(arxiv_id, str) and arxiv_id.strip() and session is not None:
        try:
            metadata = fetch_arxiv_metadata(arxiv_id.strip(), session=session)
        except requests.RequestException:
            metadata = {}
        published_raw = metadata.get("published") if isinstance(metadata, dict) else None
        extracted = _extract_publication_date(metadata) if isinstance(metadata, dict) else None
        if extracted:
            return extracted, str(published_raw or extracted.isoformat())
    return None, None


def _resolve_cutoff_from_selection(
    workspace: TopicWorkspace,
    selection_report: Dict[str, object],
    *,
    session: Optional[requests.Session] = None,
) -> Optional[Dict[str, object]]:
    """Resolve a cutoff candidate from seed selection without user input."""
    topic_norm = _normalize_title_for_match(workspace.topic)
    if not topic_norm:
        return None

    candidates: List[Dict[str, object]] = []
    cutoff_candidate = selection_report.get("cutoff_candidate")
    if isinstance(cutoff_candidate, dict):
        candidates.append(cutoff_candidate)
    listed_candidates = selection_report.get("candidates")
    if isinstance(listed_candidates, list):
        for candidate in listed_candidates:
            if isinstance(candidate, dict):
                candidates.append(candidate)

    matched: Optional[Dict[str, object]] = None
    for candidate in candidates:
        title = str(candidate.get("title") or "").strip()
        if title and _normalize_title_for_match(title) == topic_norm:
            matched = candidate
            break

    if matched is None:
        return None

    cutoff_date, published_raw = _extract_candidate_cutoff_date(matched, session=session)
    if cutoff_date is None:
        raise RuntimeError(
            "cutoff candidate found but missing published date; cannot proceed safely."
        )

    arxiv_id = matched.get("arxiv_id")
    source = "arxiv" if isinstance(arxiv_id, str) and arxiv_id.strip() else "unknown"
    title = str(matched.get("title") or "").strip()

    return {
        "topic_title": workspace.topic,
        "topic_title_normalized": topic_norm,
        "target_paper": {
            "source": source,
            "id": str(arxiv_id or ""),
            "title": title,
            "published_date": cutoff_date.isoformat(),
            "published_raw": str(published_raw or ""),
        },
        "cutoff_date": cutoff_date.isoformat(),
        "policy": {
            "exclude_same_title": True,
            "exclude_on_or_after_cutoff_date": True,
        },
        "derived_from": "seed_selection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _ensure_cutoff_artifact(
    workspace: TopicWorkspace,
    selection_report: Dict[str, object],
    *,
    session: Optional[requests.Session] = None,
) -> Optional[Dict[str, object]]:
    """Persist cutoff metadata derived from seed selection if available."""
    existing = _load_cutoff_artifact(workspace)
    if existing is not None:
        return existing
    cutoff_payload = _resolve_cutoff_from_selection(workspace, selection_report, session=session)
    if cutoff_payload is None:
        return None
    _write_json(workspace.cutoff_path, cutoff_payload)
    return cutoff_payload


def _get_cutoff_info(
    workspace: TopicWorkspace,
    *,
    session: Optional[requests.Session] = None,
) -> Optional[Dict[str, object]]:
    """Load cutoff info, deriving it from seed selection if needed."""
    existing = _load_cutoff_artifact(workspace)
    if existing is not None:
        return existing
    selection_path = workspace.seed_queries_dir / "seed_selection.json"
    if not selection_path.exists():
        return None
    selection_report = _read_json(selection_path)
    if not isinstance(selection_report, dict):
        return None
    return _ensure_cutoff_artifact(workspace, selection_report, session=session)


def _subtract_years(value: date, years: int) -> date:
    """Subtract years from a date while handling leap-day edge cases."""
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, month=2, day=28)


def _infer_criteria_cutoff_constraints(workspace: TopicWorkspace) -> Tuple[Optional[str], Optional[str]]:
    """Infer exclude_title and cutoff date based on seed selection."""
    selection_path = workspace.seed_queries_dir / "seed_selection.json"
    if not selection_path.exists():
        return None, None

    data = _read_json(selection_path)
    if data.get("cutoff_reason") != "similar_title_threshold_met":
        return None, None

    candidate = data.get("cutoff_candidate") or {}
    title = candidate.get("title")
    if not isinstance(title, str) or not title.strip():
        return None, None

    topic_value = data.get("topic")
    topic_matches = False
    if isinstance(topic_value, str) and topic_value.strip():
        topic_matches = topic_value.strip().casefold() == title.strip().casefold()
    if not topic_matches and workspace.topic.strip().casefold() != title.strip().casefold():
        return None, None

    published_raw = candidate.get("published_date") or candidate.get("published")
    cutoff_date: Optional[date] = None
    if published_raw:
        try:
            cutoff_date = _parse_date_bound(str(published_raw), label="cutoff_candidate.published_date")
        except ValueError:
            cutoff_date = None

    return title.strip(), cutoff_date.isoformat() if cutoff_date else None


def _infer_topic_publication_date(
    workspace: TopicWorkspace,
    *,
    session: Optional[requests.Session] = None,
) -> Optional[date]:
    """Infer a topic's publication date from seed selection or arXiv search."""
    cutoff_payload = _load_cutoff_artifact(workspace)
    if cutoff_payload:
        cutoff_value = cutoff_payload.get("cutoff_date")
        if isinstance(cutoff_value, str) and cutoff_value.strip():
            try:
                return _parse_date_bound(cutoff_value.strip(), label="cutoff_date")
            except ValueError:
                pass

    selection_path = workspace.seed_queries_dir / "seed_selection.json"
    if not selection_path.exists():
        return None
    data = _read_json(selection_path)
    if not isinstance(data, dict):
        return None

    def _title_matches_topic(candidate_title: str) -> bool:
        return candidate_title.strip().casefold() == workspace.topic.strip().casefold()

    def _parse_candidate_date(candidate: Dict[str, object]) -> Optional[date]:
        published_raw = candidate.get("published_date") or candidate.get("published")
        if not published_raw:
            return None
        try:
            return _parse_date_bound(str(published_raw), label="published_date")
        except ValueError:
            return None

    cutoff_candidate = data.get("cutoff_candidate")
    if isinstance(cutoff_candidate, dict):
        title = str(cutoff_candidate.get("title") or "")
        if title and _title_matches_topic(title):
            return _parse_candidate_date(cutoff_candidate)

    candidates = data.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            title = str(candidate.get("title") or "")
            if title and _title_matches_topic(title):
                candidate_date = _parse_candidate_date(candidate)
                if candidate_date:
                    return candidate_date
    if session is None:
        return None

    try:
        query = _build_arxiv_phrase_clause([workspace.topic], "ti")
        if not query:
            return None
        records = _search_arxiv_with_query(session, query=query, max_results=5)
    except requests.RequestException:
        return None

    for record in records:
        if not isinstance(record, dict):
            continue
        title = str(record.get("title") or "")
        if not title or not _title_matches_topic(title):
            continue
        published_raw = record.get("published")
        if not published_raw:
            continue
        try:
            return _parse_date_bound(str(published_raw), label="published")
        except ValueError:
            continue
    return None


_DATE_TOKEN_RE = re.compile(r"\b(?P<year>\d{4})[/-](?P<month>\d{2})[/-](?P<day>\d{2})\b")
_JSONLD_DATE_KEYS = ("datePublished", "dateCreated", "dateModified", "date")
_META_DATE_KEYS = (
    "citation_publication_date",
    "citation_date",
    "dc.date",
    "dc.date.issued",
    "date",
    "pubdate",
    "publish-date",
    "article:published_time",
    "article:modified_time",
)


def _parse_explicit_date(value: str) -> Optional[date]:
    """Extract an explicit YYYY-MM-DD date token from a string."""
    match = _DATE_TOKEN_RE.search(value)
    if not match:
        return None
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None


def _extract_arxiv_id_from_url(url: str) -> Optional[str]:
    """Extract an arXiv identifier from an arxiv.org URL."""
    parsed = urlparse(url)
    if "arxiv.org" not in parsed.netloc:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None
    if parts[0] in {"abs", "pdf"} and len(parts) >= 2:
        arxiv_id = parts[1]
    else:
        arxiv_id = parts[-1]
    arxiv_id = arxiv_id.replace(".pdf", "")
    return trim_arxiv_id(arxiv_id) or arxiv_id


def _extract_date_from_html(html: str) -> Optional[date]:
    """Best-effort extraction of a publication date from HTML."""
    for key in _JSONLD_DATE_KEYS:
        match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', html)
        if match:
            candidate = _parse_explicit_date(match.group(1))
            if candidate:
                return candidate

    for key in _META_DATE_KEYS:
        pattern_a = rf'(?:name|property)\s*=\s*["\']?{re.escape(key)}["\']?\s+content\s*=\s*["\']([^"\']+)["\']'
        pattern_b = rf'content\s*=\s*["\']([^"\']+)["\']\s+(?:name|property)\s*=\s*["\']?{re.escape(key)}["\']?'
        for pattern in (pattern_a, pattern_b):
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if match:
                candidate = _parse_explicit_date(match.group(1))
                if candidate:
                    return candidate

    for key in ("cdate", "pdate", "mdate"):
        match = re.search(rf'"{key}"\s*:\s*(\d{{13}})', html)
        if match:
            try:
                ts = int(match.group(1)) / 1000
            except ValueError:
                continue
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()

    match = _DATE_TOKEN_RE.search(html)
    if match:
        return _parse_explicit_date(match.group(0))
    return None


def _fetch_source_date(source: str, session: requests.Session) -> Optional[date]:
    """Fetch a source URL and extract its publication date."""
    arxiv_id = _extract_arxiv_id_from_url(source)
    if arxiv_id:
        try:
            metadata = fetch_arxiv_metadata(arxiv_id, session=session)
        except requests.RequestException:
            return None
        published = metadata.get("published")
        if published:
            return _parse_explicit_date(str(published)) or _parse_date_bound(
                str(published), label="published"
            )
        return None

    try:
        response = session.get(
            source,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0"},
        )
    except requests.RequestException:
        return None
    if response.status_code >= 400:
        return None
    return _extract_date_from_html(response.text)


def _collect_criteria_sources(structured_payload: Dict[str, object]) -> Set[str]:
    """Collect all source URLs referenced in structured criteria."""
    sources: Set[str] = set()

    def _add(value: Optional[str]) -> None:
        if not isinstance(value, str):
            return
        cleaned = value.strip()
        if not cleaned:
            return
        sources.add(cleaned)

    for value in structured_payload.get("sources", []) or []:
        _add(value)

    inclusion = structured_payload.get("inclusion_criteria", {}) or {}
    for item in inclusion.get("required", []) or []:
        if isinstance(item, dict):
            _add(item.get("source"))
    for group in inclusion.get("any_of", []) or []:
        if isinstance(group, dict):
            for option in group.get("options", []) or []:
                if isinstance(option, dict):
                    _add(option.get("source"))

    for item in structured_payload.get("exclusion_criteria", []) or []:
        if isinstance(item, dict):
            _add(item.get("source"))

    return sources


_TEMPORAL_KEYWORDS = (
    "發表日期",
    "出版日期",
    "出版年",
    "時間範圍",
    "早於",
    "晚於",
    "之前",
    "之後",
    "以後",
    "以前",
    "截止",
    "cutoff",
    "publication date",
    "published before",
    "published after",
)
_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _is_temporal_criterion(text: str) -> bool:
    """Detect whether a criterion string encodes a date constraint."""
    if not text:
        return False
    if _DATE_PATTERN.search(text):
        return True
    lowered = text.lower()
    return any(keyword in lowered for keyword in _TEMPORAL_KEYWORDS)


def _strip_temporal_criteria(structured_payload: Dict[str, object]) -> Dict[str, object]:
    """Remove temporal criteria and normalize the sources list."""
    if not isinstance(structured_payload, dict):
        return structured_payload

    payload = json.loads(json.dumps(structured_payload, ensure_ascii=False))
    payload.pop("time_range", None)

    inclusion = payload.get("inclusion_criteria")
    if isinstance(inclusion, dict):
        required = []
        for item in inclusion.get("required", []) or []:
            if not isinstance(item, dict):
                continue
            criterion = str(item.get("criterion") or "")
            if _is_temporal_criterion(criterion):
                continue
            required.append(item)
        inclusion["required"] = required

        any_of_groups = []
        for group in inclusion.get("any_of", []) or []:
            if not isinstance(group, dict):
                continue
            options = []
            for opt in group.get("options", []) or []:
                if not isinstance(opt, dict):
                    continue
                criterion = str(opt.get("criterion") or "")
                if _is_temporal_criterion(criterion):
                    continue
                options.append(opt)
            if options:
                group["options"] = options
                any_of_groups.append(group)
        inclusion["any_of"] = any_of_groups

    exclusion = []
    for item in payload.get("exclusion_criteria", []) or []:
        if not isinstance(item, dict):
            continue
        criterion = str(item.get("criterion") or "")
        if _is_temporal_criterion(criterion):
            continue
        exclusion.append(item)
    payload["exclusion_criteria"] = exclusion

    sources: Set[str] = set()

    def _add_source(value: Optional[str]) -> None:
        if not isinstance(value, str):
            return
        cleaned = value.strip()
        if not cleaned or not cleaned.startswith("https"):
            return
        sources.add(cleaned)

    inclusion = payload.get("inclusion_criteria", {}) or {}
    for item in inclusion.get("required", []) or []:
        if isinstance(item, dict):
            _add_source(item.get("source"))
    for group in inclusion.get("any_of", []) or []:
        if isinstance(group, dict):
            for option in group.get("options", []) or []:
                if isinstance(option, dict):
                    _add_source(option.get("source"))
    for item in payload.get("exclusion_criteria", []) or []:
        if isinstance(item, dict):
            _add_source(item.get("source"))
    payload["sources"] = sorted(sources)
    return payload


def _validate_criteria_sources(
    structured_payload: Dict[str, object],
    *,
    cutoff_before_date: Optional[str],
    session: requests.Session,
    min_https_sources: int = 3,
) -> Dict[str, object]:
    """Validate criteria sources against date and HTTPS requirements."""
    cutoff_date = _parse_date_bound(cutoff_before_date, label="cutoff_before_date") if cutoff_before_date else None
    sources = sorted(_collect_criteria_sources(structured_payload))
    invalid: List[Dict[str, str]] = []
    checked: List[Dict[str, Optional[str]]] = []
    valid_https_sources: List[str] = []

    for source in sources:
        if source.lower() == "internal":
            continue
        if not source.startswith("https://"):
            invalid.append({"source": source, "reason": "non_https"})
            continue
        source_date = _fetch_source_date(source, session)
        checked.append({"source": source, "date": source_date.isoformat() if source_date else None})
        if not source_date:
            invalid.append({"source": source, "reason": "missing_date"})
            continue
        if cutoff_date and source_date >= cutoff_date:
            invalid.append(
                {"source": source, "reason": f"after_cutoff:{source_date.isoformat()}"}
            )
            continue
        valid_https_sources.append(source)

    if min_https_sources and len(valid_https_sources) < min_https_sources:
        invalid.append(
            {"source": "__sources__", "reason": f"insufficient_https_sources:{len(valid_https_sources)}"}
        )

    return {
        "ok": not invalid,
        "checked_sources": checked,
        "invalid_sources": invalid,
        "valid_https_sources": valid_https_sources,
        "cutoff_before_date": cutoff_before_date,
    }


def _head_ok(session: requests.Session, url: str, *, timeout: int = 15) -> bool:
    """Return True if the URL responds successfully to a HEAD request."""
    try:
        response = session.head(url, allow_redirects=True, timeout=timeout)
    except requests.RequestException:
        return False
    return 200 <= response.status_code < 400


@dataclass(frozen=True)
class TopicWorkspace:
    """Directory layout for a topic run."""

    topic: str
    root: Path

    @property
    def slug(self) -> str:
        """Filesystem-friendly slug derived from the topic."""
        return slugify_topic(self.topic)

    @property
    def config_path(self) -> Path:
        """Path to the workspace config JSON."""
        return self.root / "config.json"

    @property
    def seed_dir(self) -> Path:
        """Root directory for seed artifacts."""
        return self.root / "seed"

    @property
    def seed_queries_dir(self) -> Path:
        """Directory for seed query cache and selection reports."""
        return self.seed_dir / "queries"

    @property
    def seed_downloads_dir(self) -> Path:
        """Directory for seed downloads (PDF/BibTeX)."""
        return self.seed_dir / "downloads"

    @property
    def seed_downloads_raw_dir(self) -> Path:
        """Directory holding unfiltered seed PDFs."""
        return self.seed_downloads_dir / "arxiv_raw"

    @property
    def seed_arxiv_pdf_dir(self) -> Path:
        """Directory holding filtered seed PDFs for downstream stages."""
        return self.seed_downloads_dir / "arxiv"

    @property
    def seed_filters_dir(self) -> Path:
        """Directory for filter-seed outputs."""
        return self.seed_dir / "filters"

    @property
    def keywords_dir(self) -> Path:
        """Directory for keyword extractor outputs."""
        return self.root / "keywords"

    @property
    def keywords_path(self) -> Path:
        """Path to the keywords.json output."""
        return self.keywords_dir / "keywords.json"

    @property
    def harvest_dir(self) -> Path:
        """Directory for harvested metadata outputs."""
        return self.root / "harvest"

    @property
    def arxiv_metadata_path(self) -> Path:
        """Path to the harvested arXiv metadata JSON."""
        return self.harvest_dir / "arxiv_metadata.json"

    @property
    def criteria_dir(self) -> Path:
        """Directory for structured criteria outputs."""
        return self.root / "criteria"

    @property
    def criteria_path(self) -> Path:
        """Path to the criteria.json output."""
        return self.criteria_dir / "criteria.json"

    @property
    def cutoff_dir(self) -> Path:
        """Directory for cutoff metadata artifacts."""
        return self.root / "cutoff"

    @property
    def cutoff_path(self) -> Path:
        """Path to the cutoff.json artifact."""
        return self.cutoff_dir / "cutoff.json"

    @property
    def review_dir(self) -> Path:
        """Directory for LatteReview outputs."""
        return self.root / "review"

    @property
    def review_results_path(self) -> Path:
        """Path to LatteReview results JSON."""
        return self.review_dir / "latte_review_results.json"

    @property
    def asreview_dir(self) -> Path:
        """Legacy directory for ASReview outputs."""
        return self.root / "asreview"

    @property
    def snowball_rounds_dir(self) -> Path:
        """Directory containing iterative snowball rounds."""
        return self.root / "snowball_rounds"

    def snowball_round_dir(self, round_index: int) -> Path:
        """Return the directory path for a specific snowball round."""
        return self.snowball_rounds_dir / f"round_{round_index:02d}"

    @property
    def snowball_registry_path(self) -> Path:
        """Path to the snowball review registry JSON."""
        return self.snowball_rounds_dir / "review_registry.json"

    def ensure_layout(self) -> None:
        """Create the workspace folder structure on disk."""
        for path in (
            self.root,
            self.seed_queries_dir,
            self.seed_downloads_dir,
            self.seed_downloads_raw_dir,
            self.seed_arxiv_pdf_dir,
            self.seed_filters_dir,
            self.keywords_dir,
            self.harvest_dir,
            self.criteria_dir,
            self.review_dir,
            self.asreview_dir,
            self.snowball_rounds_dir,
        ):
            _ensure_dir(path)

    def write_config(self, payload: Dict[str, object]) -> None:
        """Persist a workspace config payload to config.json."""
        data = {"topic": self.topic, **payload}
        _write_json(self.config_path, data)


def resolve_workspace(*, topic: str, workspace_root: Path) -> TopicWorkspace:
    """Resolve and create a workspace directory for ``topic``."""

    slug = slugify_topic(topic)
    ws = TopicWorkspace(topic=topic, root=Path(workspace_root) / slug)
    ws.ensure_layout()
    ws.write_config({"updated_at": datetime.now(timezone.utc).isoformat()})
    return ws


def default_seed_survey_terms() -> List[str]:
    """Default survey discovery modifiers for seed PDF collection."""

    return [
        "survey",
        "review",
        "overview",
        "systematic review",
        "systematic literature review",
        "scoping review",
        "mapping study",
        "tutorial",
    ]


def default_topic_variants(topic: str) -> List[str]:
    """Generate lightweight topic variants for search/similarity matching."""

    normalized = " ".join(topic.split())
    if not normalized:
        return []

    variants: List[str] = []

    def _looks_like_title(text: str) -> bool:
        lowered = text.lower()
        if any(marker in text for marker in (":", "!", "?", "—", "–")):
            return True
        tokens = [tok for tok in lowered.split() if tok]
        if len(tokens) >= 6:
            return True
        if any(
            phrase in lowered
            for phrase in (
                "survey",
                "review",
                "overview",
                "systematic review",
                "systematic literature review",
                "scoping review",
                "mapping study",
                "tutorial",
            )
        ):
            return True
        return False

    def _add_variant(text: str) -> None:
        candidate = " ".join(str(text).split())
        if candidate:
            variants.append(candidate)

    lower = normalized.lower()
    _add_variant(normalized)
    _add_variant(lower)
    _add_variant(normalized.title())

    clean = _normalize_similarity_text(normalized)
    if clean and clean != lower:
        _add_variant(clean)

    title_like = _looks_like_title(normalized)
    prefix = None
    for marker in (":", " - ", " — ", " – "):
        if marker in normalized:
            prefix = normalized.split(marker, 1)[0].strip()
            break
    if prefix:
        _add_variant(prefix)
        if prefix.lower() != lower:
            _add_variant(prefix.lower())

    if "spoken" in lower:
        _add_variant(lower.replace("spoken", "speech"))
    if "speech" in lower:
        _add_variant(lower.replace("speech", "spoken"))

    tokens = _normalize_similarity_text(normalized).split()
    if tokens:
        last = tokens[-1]
        if last.endswith("s") and len(last) > 1:
            singular_tokens = tokens[:-1] + [last[:-1]]
            _add_variant(" ".join(singular_tokens))
        elif len(last) > 1:
            plural_tokens = tokens[:-1] + [last + "s"]
            _add_variant(" ".join(plural_tokens))

    if not title_like and len(tokens) >= 2:
        acronym = "".join(token[0] for token in tokens if token)
        if acronym:
            _add_variant(acronym.upper())
            _add_variant(acronym.upper() + "s")

    seen: set[str] = set()
    deduped: List[str] = []
    for value in variants:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _normalize_similarity_text(value: str) -> str:
    """Normalize text for similarity scoring (lowercase, alnum, spaces)."""
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\\u4e00-\\u9fff\\s]+", " ", text)
    return " ".join(text.split())


_TITLE_TEX_COMMAND_RE = re.compile(r"\\\\[A-Za-z]+\\*?")
_TITLE_NON_ALNUM_RE = re.compile(r"[^0-9A-Za-z\\s]+")


def _normalize_title_for_match(value: str) -> str:
    """Normalize a title for exact-match comparisons across pipeline stages."""
    text = str(value or "")
    text = _TITLE_TEX_COMMAND_RE.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ")
    text = _TITLE_NON_ALNUM_RE.sub(" ", text)
    return " ".join(text.lower().split())


def _titles_match_topic(topic: str, title: str) -> bool:
    """Return True when a title matches the topic under normalization."""
    return _normalize_title_for_match(topic) == _normalize_title_for_match(title)


def _quote_term(term: str) -> str:
    """Escape and quote a query term for arXiv search clauses."""
    escaped = term.replace("\\", r"\\").replace('"', r"\"")
    return f'"{escaped}"'


def _tokenize_query_phrase(text: str) -> List[str]:
    """Split a phrase into unique normalized tokens for token-AND queries."""
    normalized = _normalize_similarity_text(text)
    if not normalized:
        return []
    tokens = [tok for tok in normalized.split() if tok]
    seen: set[str] = set()
    deduped: List[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _build_arxiv_phrase_clause(terms: Sequence[str], field: str) -> str:
    """Build an OR clause for quoted arXiv field searches."""
    prefix = field.strip() or "all"
    return " OR ".join(f"{prefix}:{_quote_term(term)}" for term in terms if str(term).strip())


def _build_arxiv_token_and_clause(terms: Sequence[str], field: str) -> str:
    """Build an OR clause where each term is tokenized with AND."""
    prefix = field.strip() or "all"
    clauses: List[str] = []
    for term in terms:
        tokens = _tokenize_query_phrase(str(term))
        if not tokens:
            continue
        if len(tokens) == 1:
            clauses.append(f"{prefix}:{_quote_term(tokens[0])}")
        else:
            joined = " AND ".join(_quote_term(token) for token in tokens)
            clauses.append(f"{prefix}:({joined})")
    return " OR ".join(clauses)


def _search_arxiv_with_query(
    session: requests.Session,
    *,
    query: str,
    max_results: int,
) -> List[Dict[str, object]]:
    """Run an arXiv API query and return basic entry dictionaries."""
    params = {"search_query": query, "start": 0, "max_results": max_results}
    response = session.get("https://export.arxiv.org/api/query", params=params, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    records: List[Dict[str, object]] = []
    for entry in root.findall("atom:entry", ns):
        records.append(
            {
                "id": entry.findtext("atom:id", default="", namespaces=ns),
                "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip(),
                "summary": (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip(),
                "published": entry.findtext("atom:published", default="", namespaces=ns),
            }
        )
    return records


def _stem_token(token: str) -> str:
    """Apply a minimal stem for plural tokens."""
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _token_set(text: str) -> set[str]:
    """Convert normalized text into a set of tokens for similarity checks."""
    normalized = _normalize_similarity_text(text)
    if not normalized:
        return set()
    tokens = {_stem_token(tok) for tok in normalized.split() if tok}
    tokens |= set(re.findall(r"[\\u4e00-\\u9fff]", normalized))
    return {tok for tok in tokens if tok}


def _title_contains_any_keyword(title: str, keywords: Sequence[str]) -> bool:
    """Return True when title includes any of the required keywords."""
    if not keywords:
        return True
    lowered = (title or "").lower()
    return any(keyword in lowered for keyword in keywords if keyword)


def _similarity_score(topic: str, title: str, *, variants: Sequence[str]) -> Tuple[float, Dict[str, object]]:
    """Return a similarity score in [0, 1] for (topic, title).

    Score is computed as the best match among topic variants, using the max of:
    - SequenceMatcher ratio on normalised strings
    - token containment ratio (topic tokens contained in title tokens)
    """

    title_norm = _normalize_similarity_text(title)
    title_tokens = _token_set(title_norm)
    best = 0.0
    best_detail: Dict[str, object] = {"best_variant": "", "sequence_ratio": 0.0, "token_containment": 0.0}

    for variant in variants:
        topic_norm = _normalize_similarity_text(variant)
        if not topic_norm or not title_norm:
            continue
        topic_tokens = _token_set(topic_norm)
        if topic_tokens:
            containment = len(topic_tokens & title_tokens) / len(topic_tokens)
        else:
            containment = 0.0
        sequence_ratio = SequenceMatcher(None, topic_norm, title_norm).ratio()
        score = max(sequence_ratio, containment)
        if score > best:
            best = score
            best_detail = {
                "best_variant": variant,
                "sequence_ratio": sequence_ratio,
                "token_containment": containment,
            }

    best_detail["topic"] = topic
    best_detail["title"] = title
    best_detail["score"] = best
    return best, best_detail


def _select_seed_arxiv_records(
    records: Sequence[Dict[str, object]],
    *,
    topic: str,
    download_top_k: int,
    cutoff_by_similar_title: bool,
    similarity_threshold: float,
    title_required_keywords: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """Filter and select seed survey records with similarity cutoff handling."""
    topic_variants = default_topic_variants(topic)
    topic_norm = _normalize_title_for_match(topic)
    required_keywords = [kw.lower() for kw in (title_required_keywords or []) if str(kw).strip()]
    original_records = list(records)
    if required_keywords:
        records = [
            record
            for record in original_records
            if isinstance(record, dict)
            and _title_contains_any_keyword(str(record.get("title") or ""), required_keywords)
        ]
    else:
        records = original_records
    candidates: List[Dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        title = str(record.get("title") or "").strip()
        published_raw = str(record.get("published") or "").strip()
        arxiv_id = extract_arxiv_id_from_record(record) or ""
        try:
            published_date = _parse_date_bound(published_raw, label="published") if published_raw else None
        except ValueError:
            published_date = None

        score, detail = _similarity_score(topic, title, variants=topic_variants)
        candidates.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "published": published_raw,
                "published_date": published_date.isoformat() if published_date else None,
                "similarity": detail,
            }
        )

    cutoff_candidate: Optional[Dict[str, object]] = None
    cutoff_date: Optional[date] = None
    cutoff_reason: str = "disabled"

    if candidates:
        exact_match = None
        for candidate in candidates:
            title = str(candidate.get("title") or "").strip()
            if title and _titles_match_topic(topic, title):
                exact_match = candidate
                break
        if exact_match is not None:
            cutoff_candidate = exact_match
            cutoff_date_str = cutoff_candidate.get("published_date")
            if isinstance(cutoff_date_str, str) and cutoff_date_str:
                cutoff_date = _parse_date_bound(cutoff_date_str, label="published_date")
                cutoff_reason = "exact_title_match"
            else:
                cutoff_reason = "exact_title_but_missing_date"
        elif cutoff_by_similar_title:
            comparable = [
                candidate
                for candidate in candidates
                if isinstance(candidate.get("similarity"), dict)
                and float(candidate["similarity"].get("score") or 0.0) >= similarity_threshold
            ]
            if comparable:
                def _date_key(value: Optional[str]) -> date:
                    if not value:
                        return date.min
                    try:
                        return _parse_date_bound(value, label="published_date") or date.min
                    except ValueError:
                        return date.min

                cutoff_candidate = max(
                    comparable,
                    key=lambda item: (
                        float(item.get("similarity", {}).get("score") or 0.0),
                        _date_key(item.get("published_date")),
                    ),
                )
                cutoff_date_str = cutoff_candidate.get("published_date")
                if isinstance(cutoff_date_str, str) and cutoff_date_str:
                    cutoff_date = _parse_date_bound(cutoff_date_str, label="published_date")
                    cutoff_reason = "similar_title_threshold_met"
                else:
                    cutoff_reason = "similar_title_but_missing_date"
            else:
                cutoff_reason = "no_similar_title_found"

    filtered: List[Dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if cutoff_candidate and cutoff_candidate.get("arxiv_id"):
            anchor_id = str(cutoff_candidate["arxiv_id"])
            record_id = extract_arxiv_id_from_record(record) or ""
            if anchor_id and record_id and trim_arxiv_id(record_id) == trim_arxiv_id(anchor_id):
                continue

        record_title = str(record.get("title") or "").strip()
        if record_title and topic_norm and _normalize_title_for_match(record_title) == topic_norm:
            continue

        if cutoff_date is None:
            filtered.append(record)
            continue

        published_raw = str(record.get("published") or "").strip()
        try:
            published_date = _parse_date_bound(published_raw, label="published") if published_raw else None
        except ValueError:
            published_date = None
        if published_date is None:
            continue
        if published_date < cutoff_date:
            filtered.append(record)

    if cutoff_date is not None and not filtered:
        cutoff_reason = "cutoff_removed_all_candidates"
        filtered = []

    selected = list(filtered)[: max(download_top_k, 0)] if download_top_k else []

    selection_report: Dict[str, object] = {
        "topic": topic,
        "topic_variants": topic_variants,
        "cutoff_by_similar_title": cutoff_by_similar_title,
        "similarity_threshold": similarity_threshold,
        "title_filter_applied": bool(required_keywords),
        "title_filter_keywords": required_keywords,
        "cutoff_reason": cutoff_reason,
        "cutoff_candidate": cutoff_candidate,
        "cutoff_date": cutoff_date.isoformat() if cutoff_date else None,
        "topic_title_normalized": topic_norm,
        "records_total": len(original_records),
        "records_after_title_filter": len(list(records)),
        "records_after_filter": len(filtered),
        "download_top_k": download_top_k,
        "download_selected": [
            {
                "arxiv_id": extract_arxiv_id_from_record(item) or "",
                "title": str(item.get("title") or "").strip(),
                "published": str(item.get("published") or "").strip(),
            }
            for item in selected
            if isinstance(item, dict)
        ],
        "candidates": candidates,
    }
    return selected, selection_report


def _load_seed_records_index(path: Path) -> Dict[str, Dict[str, object]]:
    """Index seed records by trimmed arXiv id."""
    if not path.exists():
        return {}
    records = _read_json(path)
    if not isinstance(records, list):
        return {}
    index: Dict[str, Dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        arxiv_id = extract_arxiv_id_from_record(record) or ""
        trimmed = trim_arxiv_id(arxiv_id) or arxiv_id
        if not trimmed:
            continue
        index[trimmed] = record
    return index


def _load_download_metadata_index(path: Path) -> Dict[str, Dict[str, object]]:
    """Index download manifest metadata by trimmed arXiv id."""
    if not path.exists():
        return {}
    payload = _read_json(path)
    downloads = payload.get("downloads") if isinstance(payload, dict) else None
    if not isinstance(downloads, dict):
        return {}
    arxiv_entries = downloads.get("arxiv")
    if not isinstance(arxiv_entries, list):
        return {}
    index: Dict[str, Dict[str, object]] = {}
    for entry in arxiv_entries:
        if not isinstance(entry, dict):
            continue
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            continue
        arxiv_id = str(entry.get("identifier") or metadata.get("arxiv_id") or "").strip()
        trimmed = trim_arxiv_id(arxiv_id) or arxiv_id
        if not trimmed:
            continue
        index[trimmed] = metadata
    return index


def _load_seed_filter_selected_ids(path: Path) -> Set[str]:
    """Load selected arXiv ids from filter-seed output."""
    if not path.exists():
        return set()
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return set()
    selected = payload.get("selected")
    if not isinstance(selected, list):
        return set()
    ids: Set[str] = set()
    for entry in selected:
        if not isinstance(entry, str):
            continue
        trimmed = trim_arxiv_id(entry) or entry.strip()
        if trimmed:
            ids.add(trimmed)
    return ids


def _collect_downloaded_pdfs(download_manifest: Dict[str, object]) -> List[Path]:
    """Collect PDF paths listed in a download manifest."""
    if not isinstance(download_manifest, dict):
        return []
    downloads = download_manifest.get("downloads")
    if not isinstance(downloads, dict):
        return []
    arxiv_entries = downloads.get("arxiv")
    if not isinstance(arxiv_entries, list):
        return []
    pdfs: List[Path] = []
    for entry in arxiv_entries:
        if not isinstance(entry, dict):
            continue
        pdf_path = entry.get("pdf_path")
        if isinstance(pdf_path, str) and pdf_path.strip():
            pdfs.append(Path(pdf_path))
    return pdfs


def _should_trigger_seed_rewrite(
    selection_report: Dict[str, object],
    download_manifest: Dict[str, object],
) -> Tuple[bool, str]:
    """Decide whether seed query rewrite should be triggered."""
    cutoff_reason = str(selection_report.get("cutoff_reason") or "")
    if cutoff_reason == "cutoff_removed_all_candidates":
        return True, "cutoff_removed_all_candidates"
    records_after_filter = selection_report.get("records_after_filter")
    if isinstance(records_after_filter, int) and records_after_filter == 0:
        return True, "records_after_filter_zero"
    pdfs = _collect_downloaded_pdfs(download_manifest)
    if not pdfs:
        return True, "seed_pdfs_empty"
    return False, ""


def _extract_title_abstract(record: Dict[str, object]) -> Tuple[str, str]:
    """Return title and abstract fields from a metadata record."""
    title = str(record.get("title") or "").strip()
    abstract = str(record.get("summary") or record.get("abstract") or "").strip()
    return title, abstract


def _parse_decision_payload(content: str) -> Dict[str, object]:
    """Parse and validate yes/no JSON payload from filter-seed LLM."""
    raw = (content or "").strip()
    if not raw:
        raise ValueError("LLM response is empty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM response does not contain JSON object") from None
        payload = json.loads(raw[start : end + 1])

    if not isinstance(payload, dict):
        raise ValueError("LLM response JSON must be an object")

    decision = str(payload.get("decision") or "").strip().lower()
    if decision not in {"yes", "no"}:
        raise ValueError("LLM response decision must be 'yes' or 'no'")

    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise ValueError("LLM response must include a non-empty reason")

    confidence_raw = payload.get("confidence")
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        raise ValueError("LLM response confidence must be a number") from None
    if not (0.0 <= confidence <= 1.0):
        raise ValueError("LLM response confidence must be between 0 and 1")

    return {"decision": decision, "reason": reason, "confidence": confidence}


def _parse_seed_rewrite_phrase(content: str, *, max_phrases: int = 3) -> List[str]:
    """Validate and normalize seed rewrite output into up to N phrases."""
    raw = (content or "").splitlines()
    lines = [line.strip() for line in raw if line.strip()]
    if not lines:
        raise ValueError("Seed rewrite output must contain at least one non-empty line")
    if len(lines) > max_phrases:
        raise ValueError("Seed rewrite output must contain no more than three lines")
    phrases: List[str] = []
    seen: set[str] = set()
    for line in lines:
        phrase = line.strip().lower()
        if not phrase:
            continue
        if phrase in seen:
            continue
        seen.add(phrase)
        phrases.append(phrase)
    if not phrases:
        raise ValueError("Seed rewrite output must contain at least one non-empty line")
    return phrases


def _build_seed_rewrite_prompt(
    *,
    topic: str,
    cutoff_reason: str,
    cutoff_candidate_title: str,
    original_seed_query: str,
    template_path: Optional[Path] = None,
) -> str:
    """Render the seed rewrite prompt template with runtime values."""
    prompt_path = template_path or Path("resources/LLM/prompts/seed/seed_query_rewrite.md")
    template = prompt_path.read_text(encoding="utf-8")
    replacements = {
        "<<topic>>": topic.strip(),
        "<<cutoff_reason>>": cutoff_reason.strip() if cutoff_reason else "not available",
        "<<cutoff_candidate_title>>": cutoff_candidate_title.strip() if cutoff_candidate_title else "not available",
        "<<original_seed_query>>": original_seed_query.strip() if original_seed_query else "not available",
    }
    text = template
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    return text


@dataclass
class SeedQueryRewriteAgent:
    """Generate a single-phrase rewrite for seed queries."""

    provider: str = "openai"
    model: str = "gpt-5.2"
    temperature: float = 0.2
    max_output_tokens: int = 64
    reasoning_effort: Optional[str] = "low"
    template_path: Optional[Path] = None

    def rewrite_query(
        self,
        *,
        topic: str,
        cutoff_reason: str,
        cutoff_candidate_title: str,
        original_seed_query: str,
        attempt: int,
    ) -> Tuple[List[str], str]:
        """Call the LLM to rewrite a seed query into up to three phrases."""
        load_env_file()
        prompt = _build_seed_rewrite_prompt(
            topic=topic,
            cutoff_reason=cutoff_reason,
            cutoff_candidate_title=cutoff_candidate_title,
            original_seed_query=original_seed_query,
            template_path=self.template_path,
        )
        svc = LLMService()
        metadata_payload = {
            "mode": "seed_rewrite",
            "topic": topic[:500],
            "attempt": str(attempt),
        }
        result = svc.chat(
            self.provider,
            self.model,
            [{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            reasoning_effort=self.reasoning_effort,
            metadata=metadata_payload,
        )
        if not isinstance(result, LLMResult):
            raise ProviderCallError("Provider did not return an LLMResult")
        phrases = _parse_seed_rewrite_phrase(result.content)
        return phrases, result.content


def _build_filter_seed_prompt(
    *,
    topic: str,
    title: str,
    abstract: str,
    include_keywords: Optional[Sequence[str]] = None,
    template_path: Optional[Path] = None,
) -> str:
    """Render the filter-seed prompt template."""
    prompt_path = template_path or Path("resources/LLM/prompts/filter_seed/llm_screening.md")
    template = prompt_path.read_text(encoding="utf-8")
    keywords = ", ".join(keyword.strip() for keyword in include_keywords or [] if keyword and keyword.strip())
    replacements = {
        "<<topic>>": topic.strip(),
        "<<title>>": title.strip(),
        "<<abstract>>": abstract.strip(),
        "<<keywords_hint>>": keywords or "not provided",
    }
    text = template
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    return text


def _prepare_seed_pdf_pool(workspace: TopicWorkspace) -> List[Path]:
    """Move seed PDFs into arxiv_raw/ when needed and return raw PDFs."""
    raw_dir = workspace.seed_downloads_raw_dir
    filtered_dir = workspace.seed_arxiv_pdf_dir

    raw_dir.mkdir(parents=True, exist_ok=True)
    filtered_dir.mkdir(parents=True, exist_ok=True)

    raw_pdfs = sorted(path for path in raw_dir.glob("*.pdf") if path.is_file())
    if not raw_pdfs:
        filtered_pdfs = sorted(path for path in filtered_dir.glob("*.pdf") if path.is_file())
        for pdf_path in filtered_pdfs:
            shutil.move(str(pdf_path), raw_dir / pdf_path.name)
        raw_pdfs = sorted(path for path in raw_dir.glob("*.pdf") if path.is_file())
    return raw_pdfs


def filter_seed_papers_with_llm(
    workspace: TopicWorkspace,
    *,
    provider: str = "openai",
    model: str = "gpt-5-mini",
    temperature: float = 0.2,
    max_output_tokens: int = 400,
    reasoning_effort: Optional[str] = "low",
    include_keywords: Optional[Sequence[str]] = None,
    fallback_min_selected: int = 2,
    fallback_max_additional: Optional[int] = None,
    fallback_prompt_path: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, object]:
    """Run LLM yes/no screening on seed papers using title + abstract only."""

    load_env_file()

    filters_dir = workspace.seed_filters_dir
    screening_path = filters_dir / "llm_screening.json"
    selection_path = filters_dir / "selected_ids.json"

    if screening_path.exists() and selection_path.exists() and not force:
        return {
            "screening_path": str(screening_path),
            "selection_path": str(selection_path),
            "skipped": True,
        }

    raw_pdfs = _prepare_seed_pdf_pool(workspace)

    seed_records_index = _load_seed_records_index(workspace.seed_queries_dir / "arxiv.json")
    download_index = _load_download_metadata_index(workspace.seed_downloads_dir / "download_results.json")

    session = requests.Session()
    try:
        candidates: List[Tuple[str, str, str, Path]] = []
        for pdf_path in raw_pdfs:
            arxiv_id = trim_arxiv_id(pdf_path.stem)
            if not arxiv_id:
                raise ValueError(f"Unable to infer arXiv id from PDF: {pdf_path}")

            metadata = download_index.get(arxiv_id) or seed_records_index.get(arxiv_id)
            title = ""
            abstract = ""
            if isinstance(metadata, dict):
                title, abstract = _extract_title_abstract(metadata)

            if not title or not abstract:
                fetched = fetch_arxiv_metadata(arxiv_id, session=session)
                title, abstract = _extract_title_abstract(fetched)

            if not title or not abstract:
                raise ValueError(f"Missing title/abstract for arXiv:{arxiv_id}")

            candidates.append((arxiv_id, title, abstract, pdf_path))
    finally:
        session.close()

    svc = LLMService()
    papers: List[Dict[str, object]] = []
    selected_ids: List[str] = []
    rejected_ids: List[str] = []

    for arxiv_id, title, abstract, pdf_path in candidates:
        prompt = _build_filter_seed_prompt(
            topic=workspace.topic,
            title=title,
            abstract=abstract,
            include_keywords=include_keywords,
        )
        metadata_payload = {
            "mode": "filter_seed",
            "topic": workspace.topic[:500],
            "arxiv_id": arxiv_id,
        }
        result = svc.chat(
            provider,
            model,
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            metadata=metadata_payload,
        )
        if not isinstance(result, LLMResult):
            raise ProviderCallError("Provider did not return an LLMResult")

        parsed = _parse_decision_payload(result.content)
        decision = parsed["decision"]
        papers.append(
            {
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": abstract,
                "decision": decision,
                "reason": parsed["reason"],
                "confidence": parsed["confidence"],
            }
        )
        if decision == "yes":
            selected_ids.append(arxiv_id)
        else:
            rejected_ids.append(arxiv_id)

    fallback_info: Dict[str, object] = {
        "enabled": fallback_min_selected > 0,
        "triggered": False,
        "min_selected": fallback_min_selected,
        "selected_before": len(selected_ids),
        "selected_after": len(selected_ids),
        "added": [],
        "prompt_path": None,
    }
    if fallback_min_selected > 0 and len(selected_ids) < fallback_min_selected and rejected_ids:
        fallback_prompt = fallback_prompt_path or Path(
            "resources/LLM/prompts/filter_seed/llm_screening_fallback.md"
        )
        fallback_info["prompt_path"] = str(fallback_prompt)
        fallback_info["triggered"] = True

        fallback_candidates: List[Tuple[str, float]] = []
        rejected_set = set(rejected_ids)
        for paper in papers:
            arxiv_id = str(paper.get("arxiv_id") or "")
            if not arxiv_id or arxiv_id not in rejected_set:
                continue
            title = str(paper.get("title") or "")
            abstract = str(paper.get("abstract") or "")
            prompt = _build_filter_seed_prompt(
                topic=workspace.topic,
                title=title,
                abstract=abstract,
                include_keywords=include_keywords,
                template_path=fallback_prompt,
            )
            metadata_payload = {
                "mode": "filter_seed_fallback",
                "topic": workspace.topic[:500],
                "arxiv_id": arxiv_id,
            }
            result = svc.chat(
                provider,
                model,
                [{"role": "user", "content": prompt}],
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                reasoning_effort=reasoning_effort,
                metadata=metadata_payload,
            )
            if not isinstance(result, LLMResult):
                raise ProviderCallError("Provider did not return an LLMResult")
            parsed = _parse_decision_payload(result.content)
            paper["fallback_decision"] = parsed["decision"]
            paper["fallback_reason"] = parsed["reason"]
            paper["fallback_confidence"] = parsed["confidence"]
            if parsed["decision"] == "yes":
                fallback_candidates.append((arxiv_id, float(parsed["confidence"])))

        if fallback_candidates:
            fallback_candidates.sort(key=lambda item: item[1], reverse=True)
            if fallback_max_additional is not None:
                fallback_candidates = fallback_candidates[: max(0, fallback_max_additional)]
            added_ids = []
            for arxiv_id, _ in fallback_candidates:
                if arxiv_id not in selected_ids:
                    selected_ids.append(arxiv_id)
                    added_ids.append(arxiv_id)
            rejected_ids = [arxiv_id for arxiv_id in rejected_ids if arxiv_id not in set(added_ids)]
            fallback_info["added"] = added_ids
            fallback_info["selected_after"] = len(selected_ids)

    filters_dir.mkdir(parents=True, exist_ok=True)
    screening_payload = {
        "topic": workspace.topic,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "papers": papers,
        "fallback": fallback_info,
    }
    _write_json(screening_path, screening_payload)
    _write_json(
        selection_path,
        {
            "selected": selected_ids,
            "rejected": rejected_ids,
            "fallback_added": fallback_info.get("added") if fallback_info else [],
        },
    )

    filtered_dir = workspace.seed_arxiv_pdf_dir
    filtered_dir.mkdir(parents=True, exist_ok=True)
    for pdf_path in filtered_dir.glob("*.pdf"):
        if pdf_path.is_file():
            pdf_path.unlink()

    for arxiv_id, _, _, pdf_path in candidates:
        if arxiv_id in selected_ids:
            shutil.copy2(pdf_path, filtered_dir / pdf_path.name)

    return {
        "screening_path": str(screening_path),
        "selection_path": str(selection_path),
        "selected_count": len(selected_ids),
        "rejected_count": len(rejected_ids),
        "filtered_pdf_dir": str(filtered_dir),
        "raw_pdf_dir": str(workspace.seed_downloads_raw_dir),
    }



def seed_surveys_from_arxiv(
    workspace: TopicWorkspace,
    *,
    anchor_terms: Optional[Sequence[str]] = None,
    survey_terms: Optional[Sequence[str]] = None,
    max_results: int = 25,
    download_top_k: int = 5,
    scope: str = "all",
    boolean_operator: str = "AND",
    reuse_cached_queries: bool = True,
    cutoff_by_similar_title: bool = True,
    similarity_threshold: float = 0.8,
    anchor_mode: str = "phrase",
    arxiv_raw_query: Optional[str] = None,
    seed_rewrite: bool = False,
    seed_rewrite_max_attempts: int = 2,
    seed_rewrite_model: str = "gpt-5.2",
    seed_rewrite_preview: bool = False,
) -> Dict[str, object]:
    """Search arXiv for survey-like papers and download the top results.

    Optionally rewrites the seed query when no PDFs are available or when
    cutoff removal eliminates all candidates.
    """

    load_env_file()

    # Cutoff-by-similar-title must stay enabled per project policy.
    cutoff_by_similar_title = True

    anchors = list(anchor_terms) if anchor_terms else default_topic_variants(workspace.topic)
    modifiers = list(survey_terms) if survey_terms else default_seed_survey_terms()

    queries_dir = workspace.seed_queries_dir
    records_path = queries_dir / "arxiv.json"

    session = requests.Session()
    try:
        def _run_seed_attempt(
            *,
            attempt_anchors: Sequence[str],
            query_mode: str,
            raw_query: Optional[str],
            reuse_cache: bool,
        ) -> Tuple[Dict[str, object], Dict[str, object], str]:
            search_query = None
            effective_query_mode = query_mode

            if raw_query is not None:
                search_query = str(raw_query).strip()
                if not search_query:
                    raise ValueError("--arxiv-raw-query is empty")
                effective_query_mode = "raw"

            if effective_query_mode not in {"phrase", "token_and", "raw"}:
                raise ValueError(f"Unsupported anchor_mode: {effective_query_mode}")

            field = scope.lower().strip() or "all"
            if effective_query_mode == "raw":
                if search_query is None:
                    raise ValueError("--arxiv-raw-query is empty")
            else:
                if effective_query_mode == "token_and":
                    anchor_clause = _build_arxiv_token_and_clause(attempt_anchors, field)
                else:
                    anchor_clause = _build_arxiv_phrase_clause(attempt_anchors, field)
                search_clause = _build_arxiv_phrase_clause(modifiers, field)
                if not anchor_clause:
                    raise ValueError("anchor_terms 不能為空")
                if not search_clause:
                    raise ValueError("survey_terms 不能為空")
                search_query = f"({anchor_clause}) {boolean_operator} ({search_clause})"

            if reuse_cache and records_path.exists():
                records = json.loads(records_path.read_text(encoding="utf-8"))
            else:
                records = _search_arxiv_with_query(
                    session,
                    query=search_query or "",
                    max_results=max_results,
                )
                _write_json(records_path, records)

            selected, selection_report = _select_seed_arxiv_records(
                records,
                topic=workspace.topic,
                download_top_k=download_top_k,
                cutoff_by_similar_title=cutoff_by_similar_title,
                similarity_threshold=similarity_threshold,
                title_required_keywords=["survey", "review", "overview"],
            )
            selection_report["anchor_mode"] = effective_query_mode
            selection_report["search_query"] = search_query
            selection_report["scope"] = scope
            selection_report["boolean_operator"] = boolean_operator
            selection_report["raw_query"] = raw_query
            _write_json(queries_dir / "seed_selection.json", selection_report)
            downloads = download_records_to_pdfs({"arxiv": selected}, workspace.seed_downloads_dir, session=session)

            download_manifest: Dict[str, object] = {
                "topic": workspace.topic,
                "anchors": list(attempt_anchors),
                "survey_terms": modifiers,
                "anchor_mode": effective_query_mode,
                "search_query": search_query,
                "raw_query": raw_query,
                "max_results": max_results,
                "download_top_k": download_top_k,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "downloads": {
                    source: [
                        {
                            "source": item.source,
                            "identifier": item.identifier,
                            "metadata": item.metadata,
                            "pdf_path": str(item.pdf_path) if item.pdf_path else None,
                            "bibtex_path": str(item.bibtex_path) if item.bibtex_path else None,
                            "issues": item.issues,
                        }
                        for item in results
                    ]
                    for source, results in downloads.items()
                },
            }
            _write_json(workspace.seed_downloads_dir / "download_results.json", download_manifest)
            return selection_report, download_manifest, search_query or ""

        selection_report, download_manifest, search_query = _run_seed_attempt(
            attempt_anchors=anchors,
            query_mode=anchor_mode,
            raw_query=arxiv_raw_query,
            reuse_cache=reuse_cached_queries,
        )
        if isinstance(selection_report, dict):
            _ensure_cutoff_artifact(workspace, selection_report, session=session)

        original_records = json.loads(records_path.read_text(encoding="utf-8")) if records_path.exists() else []
        original_selection_report = json.loads(json.dumps(selection_report))
        original_download_manifest = json.loads(json.dumps(download_manifest))
        original_pdfs = _collect_downloaded_pdfs(download_manifest)

        trigger_rewrite, trigger_reason = _should_trigger_seed_rewrite(selection_report, download_manifest)
        rewrite_payload: Optional[Dict[str, object]] = None
        selected_queries: Optional[List[str]] = None
        final_selection_report = selection_report
        final_download_manifest = download_manifest
        final_pdfs = list(original_pdfs)

        if seed_rewrite and trigger_rewrite:
            if seed_rewrite_max_attempts <= 0:
                raise ValueError("seed_rewrite_max_attempts must be >= 1")

            cutoff_candidate = selection_report.get("cutoff_candidate") or {}
            cutoff_candidate_title = ""
            if isinstance(cutoff_candidate, dict):
                cutoff_candidate_title = str(cutoff_candidate.get("title") or "")

            agent = SeedQueryRewriteAgent(model=seed_rewrite_model)
            rewrite_attempts: List[Dict[str, object]] = []

            for attempt in range(1, seed_rewrite_max_attempts + 1):
                attempt_record: Dict[str, object] = {
                    "attempt": attempt,
                    "model": agent.model,
                    "provider": agent.provider,
                    "raw_output": None,
                    "parsed_phrases": None,
                    "parsed_phrase": None,
                    "status": None,
                    "error": None,
                }
                try:
                    phrases, raw_output = agent.rewrite_query(
                        topic=workspace.topic,
                        cutoff_reason=str(selection_report.get("cutoff_reason") or ""),
                        cutoff_candidate_title=cutoff_candidate_title,
                        original_seed_query=search_query or "",
                        attempt=attempt,
                    )
                    attempt_record["raw_output"] = raw_output
                    attempt_record["parsed_phrases"] = phrases
                    attempt_record["parsed_phrase"] = phrases[0] if phrases else None
                    attempt_record["status"] = "ok"
                except Exception as exc:  # noqa: BLE001
                    attempt_record["status"] = "error"
                    attempt_record["error"] = str(exc)
                    rewrite_attempts.append(attempt_record)
                    continue

                rewrite_attempts.append(attempt_record)
                selected_queries = phrases

                if seed_rewrite_preview:
                    break

                attempt_selection, attempt_manifest, _ = _run_seed_attempt(
                    attempt_anchors=phrases,
                    query_mode="phrase",
                    raw_query=None,
                    reuse_cache=False,
                )
                attempt_pdfs = _collect_downloaded_pdfs(attempt_manifest)
                if attempt_pdfs:
                    final_selection_report = attempt_selection
                    final_download_manifest = attempt_manifest
                    final_pdfs = list(attempt_pdfs)
                    break

            rewrite_payload = {
                "topic": workspace.topic,
                "trigger_reason": trigger_reason,
                "attempts": rewrite_attempts,
                "selected_queries": selected_queries,
                "original_seed_query": search_query or "",
                "cutoff_reason": str(selection_report.get("cutoff_reason") or ""),
                "cutoff_candidate_title": cutoff_candidate_title,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "preview_only": seed_rewrite_preview,
            }

            if not seed_rewrite_preview and not final_pdfs and original_pdfs:
                final_selection_report = original_selection_report
                final_download_manifest = original_download_manifest
                final_pdfs = list(original_pdfs)
                _write_json(records_path, original_records)
                _write_json(queries_dir / "seed_selection.json", original_selection_report)

            if not final_pdfs and not original_pdfs:
                _write_json(queries_dir / "seed_rewrite.json", rewrite_payload)
                final_download_manifest["rewrite_attempts"] = len(rewrite_attempts)
                if selected_queries:
                    final_download_manifest["rewrite_query"] = selected_queries[0]
                    final_download_manifest["rewrite_queries"] = selected_queries
                _write_json(workspace.seed_downloads_dir / "download_results.json", final_download_manifest)
                raise ValueError("Seed rewrite exhausted without PDFs")

        if rewrite_payload is not None:
            _write_json(queries_dir / "seed_rewrite.json", rewrite_payload)
            final_download_manifest["rewrite_attempts"] = len(rewrite_payload["attempts"])
            if rewrite_payload.get("selected_queries"):
                selected = rewrite_payload["selected_queries"]
                if isinstance(selected, list) and selected:
                    final_download_manifest["rewrite_query"] = selected[0]
                    final_download_manifest["rewrite_queries"] = selected

        _write_json(workspace.seed_downloads_dir / "download_results.json", final_download_manifest)

        if final_pdfs:
            keep_names = {path.name for path in final_pdfs}
            for pdf_path in workspace.seed_arxiv_pdf_dir.glob("*.pdf"):
                if pdf_path.is_file() and pdf_path.name not in keep_names:
                    pdf_path.unlink()

        if isinstance(final_selection_report, dict):
            _ensure_cutoff_artifact(workspace, final_selection_report, session=session)
    finally:
        session.close()

    pdfs = sorted({str(path) for path in _collect_downloaded_pdfs(final_download_manifest)})
    return {
        "workspace": str(workspace.root),
        "seed_query_records": str(records_path),
        "seed_selection": str(queries_dir / "seed_selection.json"),
        "seed_download_manifest": str(workspace.seed_downloads_dir / "download_results.json"),
        "seed_pdfs": pdfs,
    }


def extract_keywords_from_seed_pdfs(
    workspace: TopicWorkspace,
    *,
    pdf_dir: Optional[Path] = None,
    max_pdfs: int = 3,
    provider: str = "openai",
    model: str = "gpt-5",
    temperature: float = 0.2,
    max_queries: int = 50,
    include_ethics: bool = False,
    seed_anchors: Optional[Sequence[str]] = None,
    reasoning_effort: Optional[str] = "medium",
    max_output_tokens: Optional[int] = 128000,
    force: bool = False,
) -> Dict[str, object]:
    """Run ``keyword_extractor`` on seed PDFs and write ``keywords.json``."""

    load_env_file()

    # Hard lock for reasoning LLM usage.
    model = "gpt-5.2"
    temperature = 1.0

    output_path = workspace.keywords_path
    if output_path.exists() and not force:
        return {"keywords_path": str(output_path), "skipped": True}

    root = Path(pdf_dir) if pdf_dir else workspace.seed_arxiv_pdf_dir
    pdf_paths = sorted(path for path in root.glob("*.pdf") if path.is_file())
    if max_pdfs and max_pdfs > 0:
        pdf_paths = pdf_paths[:max_pdfs]
    if not pdf_paths:
        raise ValueError(f"No PDFs found under: {root}")

    usage_log_path = workspace.keywords_dir / f"keyword_extractor_usage_{_now_utc_stamp()}.json"
    params = ExtractParams(
        topic=workspace.topic,
        max_queries=max_queries,
        include_ethics=include_ethics,
        seed_anchors=list(seed_anchors) if seed_anchors else None,
        use_topic_variants=False,
        reasoning_effort=reasoning_effort,
    )

    payload = extract_search_terms_from_surveys(
        pdf_paths,
        provider=provider,
        model=model,
        params=params,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
        usage_log_path=usage_log_path,
    )
    _write_json(output_path, payload)
    return {
        "keywords_path": str(output_path),
        "usage_log_path": str(usage_log_path),
        "pdf_count": len(pdf_paths),
    }


def _flatten_search_terms(search_terms: Dict[str, Sequence[str]], *, max_terms_per_category: int) -> List[str]:
    """Flatten categorized search terms with per-category caps."""
    flattened: List[str] = []
    for terms in search_terms.values():
        if not isinstance(terms, Sequence):
            continue
        for term in list(terms)[: max_terms_per_category]:
            if not isinstance(term, str):
                continue
            cleaned = " ".join(term.split())
            if cleaned and cleaned not in flattened:
                flattened.append(cleaned)
    return flattened


def harvest_arxiv_metadata(
    workspace: TopicWorkspace,
    *,
    keywords_path: Optional[Path] = None,
    max_terms_per_category: int = 3,
    top_k_per_query: int = 100,
    scope: str = "all",
    boolean_operator: str = "OR",
    require_accessible_pdf: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    force: bool = False,
) -> Dict[str, object]:
    """Harvest arXiv metadata by running anchor × search_term queries."""

    load_env_file()

    output_path = workspace.arxiv_metadata_path
    if output_path.exists() and not force:
        return {"arxiv_metadata_path": str(output_path), "skipped": True}

    payload = _read_json(Path(keywords_path) if keywords_path else workspace.keywords_path)
    anchors = payload.get("anchor_terms") or []
    search_terms_dict = payload.get("search_terms") or {}
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("keywords payload missing anchor_terms")
    if not isinstance(search_terms_dict, dict) or not search_terms_dict:
        raise ValueError("keywords payload missing search_terms")

    flattened_terms = _flatten_search_terms(search_terms_dict, max_terms_per_category=max_terms_per_category)
    if not flattened_terms:
        raise ValueError("No search terms available after flattening.")

    def _quote_arxiv_term(term: str) -> str:
        escaped = term.replace("\\", r"\\").replace('"', r"\"")
        return f'"{escaped}"'

    def _build_arxiv_query(anchor_term: str, search_term: str) -> str:
        field = scope.lower().strip() or "all"
        anchor_clause = f"{field}:{_quote_arxiv_term(anchor_term)}"
        search_clause = f"{field}:{_quote_arxiv_term(search_term)}"
        return f"({anchor_clause}) {boolean_operator} ({search_clause})"

    def _within_window(meta: Dict[str, object]) -> bool:
        if cutoff_title_norm:
            title = str(meta.get("title") or "")
            if title and _normalize_title_for_match(title) == cutoff_title_norm:
                return False
        if not start_bound and not end_bound and not cutoff_date:
            return True
        published = _extract_publication_date(meta)
        if cutoff_date and not published:
            return False
        if not published:
            return False
        if start_bound and published < start_bound:
            return False
        if cutoff_date and published >= cutoff_date:
            return False
        if end_bound and published > end_bound:
            return False
        return True

    session = requests.Session()
    try:
        start_bound = _parse_date_bound(start_date, label="--start-date")
        end_bound = _parse_date_bound(end_date, label="--end-date")
        if end_bound is None:
            inferred_end = _infer_topic_publication_date(workspace, session=session)
            end_bound = inferred_end or datetime.now(timezone.utc).date()
        if start_bound is None:
            start_bound = _subtract_years(end_bound, 3)
        if start_bound and end_bound and start_bound > end_bound:
            raise ValueError("--start-date cannot be later than --end-date")

        cutoff_info = _get_cutoff_info(workspace, session=session)
        cutoff_date: Optional[date] = None
        cutoff_title_norm: Optional[str] = None
        if cutoff_info:
            cutoff_value = cutoff_info.get("cutoff_date")
            if isinstance(cutoff_value, str) and cutoff_value.strip():
                try:
                    cutoff_date = _parse_date_bound(cutoff_value.strip(), label="cutoff_date")
                except ValueError:
                    cutoff_date = None
            target = cutoff_info.get("target_paper") or {}
            target_title = target.get("title") if isinstance(target, dict) else None
            if isinstance(target_title, str) and target_title.strip():
                cutoff_title_norm = _normalize_title_for_match(target_title)
        if cutoff_date and end_bound and end_bound >= cutoff_date:
            end_bound = cutoff_date - timedelta(days=1)

        aggregated: Dict[str, Dict[str, object]] = {}
        total_queries = 0
        query_plan_entries: List[Dict[str, object]] = []

        for anchor in anchors:
            if not isinstance(anchor, str) or not anchor.strip():
                continue
            for term in flattened_terms:
                total_queries += 1
                query_entry = {
                    "anchor": anchor,
                    "search_term": term,
                    "search_query": _build_arxiv_query(anchor, term),
                    "records_returned": 0,
                    "records_added": 0,
                    "error": None,
                }
                try:
                    records = search_arxiv_for_topic(
                        session,
                        [anchor],
                        [term],
                        max_results=top_k_per_query,
                        scope=scope,
                        boolean_operator=boolean_operator,
                    )
                except requests.RequestException:
                    query_entry["error"] = "request_error"
                    query_plan_entries.append(query_entry)
                    continue

                query_entry["records_returned"] = len(records)
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    arxiv_id = extract_arxiv_id_from_record(record)
                    if not arxiv_id:
                        continue
                    arxiv_id = trim_arxiv_id(arxiv_id) or arxiv_id

                    entry = aggregated.get(arxiv_id)
                    if entry is None:
                        try:
                            metadata = fetch_arxiv_metadata(arxiv_id, session=session)
                        except requests.RequestException:
                            continue

                        if not _within_window(metadata):
                            continue

                        pdf_url = metadata.get("pdf_url")
                        if require_accessible_pdf and isinstance(pdf_url, str) and pdf_url:
                            if not _head_ok(session, pdf_url):
                                continue
                        elif require_accessible_pdf:
                            continue

                        entry = {
                            "arxiv_id": arxiv_id,
                            "anchor": anchor,
                            "search_term": term,
                            "search_record": record,
                            "metadata": metadata,
                            "queries": [{"anchor": anchor, "search_term": term}],
                        }
                        aggregated[arxiv_id] = entry
                        query_entry["records_added"] += 1
                    else:
                        queries = entry.get("queries")
                        if isinstance(queries, list):
                            candidate = {"anchor": anchor, "search_term": term}
                            if candidate not in queries:
                                queries.append(candidate)
                query_plan_entries.append(query_entry)

    finally:
        session.close()

    results = sorted(aggregated.values(), key=lambda item: str(item.get("arxiv_id", "")))
    _write_json(output_path, results)
    query_plan_path = workspace.harvest_dir / "query_plan.json"
    query_plan = {
        "topic": workspace.topic,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "anchors": anchors,
        "search_terms": flattened_terms,
        "scope": scope,
        "boolean_operator": boolean_operator,
        "top_k_per_query": top_k_per_query,
        "start_date": start_bound.isoformat() if start_bound else None,
        "end_date": end_bound.isoformat() if end_bound else None,
        "cutoff_date": cutoff_date.isoformat() if cutoff_date else None,
        "queries_run": total_queries,
        "queries": query_plan_entries,
    }
    _write_json(query_plan_path, query_plan)
    return {
        "arxiv_metadata_path": str(output_path),
        "unique_papers": len(results),
        "queries_run": total_queries,
        "start_date": start_date,
        "end_date": end_date,
        "query_plan_path": str(query_plan_path),
    }


def harvest_other_sources(
    workspace: TopicWorkspace,
    *,
    keywords_path: Optional[Path] = None,
    max_terms_per_category: int = 3,
    semantic_limit: int = 100,
    dblp_per_term_limit: int = 50,
    request_pause: float = 0.3,
    include_semantic_scholar: bool = True,
    include_dblp: bool = True,
    force: bool = False,
) -> Dict[str, object]:
    """Harvest Semantic Scholar / DBLP search results for the topic."""

    load_env_file()

    payload = _read_json(Path(keywords_path) if keywords_path else workspace.keywords_path)
    anchors = payload.get("anchor_terms") or []
    search_terms_dict = payload.get("search_terms") or {}
    if not isinstance(anchors, list) or not anchors:
        raise ValueError("keywords payload missing anchor_terms")
    if not isinstance(search_terms_dict, dict) or not search_terms_dict:
        raise ValueError("keywords payload missing search_terms")

    flattened_terms = _flatten_search_terms(search_terms_dict, max_terms_per_category=max_terms_per_category)
    if not flattened_terms:
        raise ValueError("No search terms available after flattening.")

    semantic_path = workspace.harvest_dir / "semantic_scholar_records.json"
    dblp_path = workspace.harvest_dir / "dblp_records.json"

    if not force:
        if include_semantic_scholar and semantic_path.exists():
            include_semantic_scholar = False
        if include_dblp and dblp_path.exists():
            include_dblp = False

    semantic_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")

    session = requests.Session()
    try:
        output: Dict[str, object] = {}

        if include_semantic_scholar:
            semantic_items: Dict[str, Dict[str, object]] = {}
            for anchor in anchors:
                if not isinstance(anchor, str) or not anchor.strip():
                    continue
                for term in flattened_terms:
                    try:
                        records = search_semantic_scholar_for_topic(
                            session,
                            [anchor],
                            [term],
                            api_key=semantic_key,
                            limit=semantic_limit,
                        )
                    except requests.RequestException:
                        continue
                    for record in records:
                        if not isinstance(record, dict):
                            continue
                        paper_id = record.get("paperId") or record.get("paper_id")
                        if not isinstance(paper_id, str) or not paper_id:
                            continue
                        existing = semantic_items.get(paper_id)
                        if existing is None:
                            semantic_items[paper_id] = {
                                "paper_id": paper_id,
                                "anchor": anchor,
                                "search_term": term,
                                "record": record,
                                "queries": [{"anchor": anchor, "search_term": term}],
                            }
                        else:
                            queries = existing.get("queries")
                            if isinstance(queries, list):
                                candidate = {"anchor": anchor, "search_term": term}
                                if candidate not in queries:
                                    queries.append(candidate)
            semantic_list = sorted(semantic_items.values(), key=lambda item: str(item.get("paper_id", "")))
            _write_json(semantic_path, semantic_list)
            output["semantic_scholar_records_path"] = str(semantic_path)
            output["semantic_scholar_unique_papers"] = len(semantic_list)

        if include_dblp:
            dblp_records = search_dblp_for_topic(
                session,
                [anchor for anchor in anchors if isinstance(anchor, str) and anchor.strip()],
                flattened_terms,
                per_term_limit=dblp_per_term_limit,
                request_pause=request_pause,
            )
            _write_json(dblp_path, dblp_records)
            output["dblp_records_path"] = str(dblp_path)
            output["dblp_unique_records"] = len(dblp_records)

        return output
    finally:
        session.close()


def backfill_arxiv_metadata_from_dblp_titles(
    workspace: TopicWorkspace,
    *,
    dblp_path: Optional[Path] = None,
    arxiv_metadata_path: Optional[Path] = None,
    max_results_per_title: int = 10,
    request_pause: float = 0.3,
    force: bool = False,
) -> Dict[str, object]:
    """Backfill arXiv metadata using strict title matches from DBLP records."""

    load_env_file()

    dblp_source = Path(dblp_path) if dblp_path else workspace.harvest_dir / "dblp_records.json"
    if not dblp_source.exists():
        raise FileNotFoundError(f"找不到 DBLP records 檔案：{dblp_source}")

    if max_results_per_title <= 0:
        raise ValueError("max_results_per_title must be a positive integer")

    matches_path = workspace.harvest_dir / "dblp_title_arxiv_matches.json"
    arxiv_path = Path(arxiv_metadata_path) if arxiv_metadata_path else workspace.arxiv_metadata_path
    if matches_path.exists() and arxiv_path.exists() and not force:
        return {
            "arxiv_metadata_path": str(arxiv_path),
            "dblp_title_arxiv_matches_path": str(matches_path),
            "skipped": True,
            "skip_reason": "dblp_title_arxiv_matches_exists",
        }

    dblp_records = _read_json(dblp_source)
    if not isinstance(dblp_records, list):
        raise ValueError("DBLP records payload must be a list")

    existing_entries: List[Dict[str, object]] = []
    if arxiv_path.exists():
        payload = _read_json(arxiv_path)
        if not isinstance(payload, list):
            raise ValueError("arXiv metadata payload must be a list")
        existing_entries = payload

    def _entry_arxiv_id(entry: Dict[str, object]) -> Optional[str]:
        value = entry.get("arxiv_id")
        if not isinstance(value, str) or not value.strip():
            metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
            value = metadata.get("arxiv_id")
        if not isinstance(value, str) or not value.strip():
            return None
        trimmed = trim_arxiv_id(value.strip())
        return trimmed or value.strip()

    aggregated: Dict[str, Dict[str, object]] = {}
    for entry in existing_entries:
        if not isinstance(entry, dict):
            continue
        arxiv_id = _entry_arxiv_id(entry)
        if not arxiv_id or arxiv_id in aggregated:
            continue
        aggregated[arxiv_id] = entry

    seen_title_norms: Set[str] = set()
    matches_report: List[Dict[str, object]] = []
    queries_run = 0
    added = 0
    updated = 0
    no_match = 0

    session = requests.Session()
    try:
        for record in dblp_records:
            if not isinstance(record, dict):
                continue
            title = str(record.get("title") or "").strip()
            if not title:
                matches_report.append({"dblp_key": record.get("key"), "status": "missing_title"})
                continue
            normalized_title = _normalize_title_for_match(title)
            if not normalized_title:
                matches_report.append({"dblp_key": record.get("key"), "title": title, "status": "invalid_title"})
                continue
            if normalized_title in seen_title_norms:
                matches_report.append(
                    {"dblp_key": record.get("key"), "title": title, "status": "duplicate_title"}
                )
                continue
            seen_title_norms.add(normalized_title)

            query = _build_arxiv_phrase_clause([title], "ti")
            if not query:
                matches_report.append({"dblp_key": record.get("key"), "title": title, "status": "invalid_query"})
                continue

            matched_ids: List[str] = []
            try:
                queries_run += 1
                candidates = _search_arxiv_with_query(session, query=query, max_results=max_results_per_title)
            except requests.RequestException:
                matches_report.append({"dblp_key": record.get("key"), "title": title, "status": "request_error"})
                continue

            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                candidate_title = str(candidate.get("title") or "").strip()
                if _normalize_title_for_match(candidate_title) != normalized_title:
                    continue
                arxiv_id = extract_arxiv_id_from_record(candidate)
                if not arxiv_id:
                    continue
                arxiv_id = trim_arxiv_id(arxiv_id) or arxiv_id
                matched_ids.append(arxiv_id)
                entry = aggregated.get(arxiv_id)
                if entry is None:
                    try:
                        metadata = fetch_arxiv_metadata(arxiv_id, session=session)
                    except requests.RequestException:
                        continue
                    entry = {
                        "arxiv_id": arxiv_id,
                        "anchor": "dblp_title",
                        "search_term": title,
                        "search_record": candidate,
                        "metadata": metadata,
                        "queries": [{"anchor": "dblp_title", "search_term": title}],
                    }
                    aggregated[arxiv_id] = entry
                    existing_entries.append(entry)
                    added += 1
                else:
                    queries = entry.get("queries")
                    if not isinstance(queries, list):
                        queries = []
                        entry["queries"] = queries
                    marker = {"anchor": "dblp_title", "search_term": title}
                    if marker not in queries:
                        queries.append(marker)
                    updated += 1

            if matched_ids:
                matches_report.append(
                    {
                        "dblp_key": record.get("key"),
                        "title": title,
                        "status": "matched",
                        "arxiv_ids": matched_ids,
                        "query": query,
                    }
                )
            else:
                matches_report.append(
                    {
                        "dblp_key": record.get("key"),
                        "title": title,
                        "status": "no_match",
                        "query": query,
                    }
                )
                no_match += 1

            if request_pause > 0:
                time.sleep(request_pause)
    finally:
        session.close()

    def _sort_key(entry: Dict[str, object]) -> Tuple[str, str]:
        arxiv_id = _entry_arxiv_id(entry) or ""
        return ("" if arxiv_id else "~", arxiv_id)

    results = sorted(
        [entry for entry in existing_entries if isinstance(entry, dict)],
        key=_sort_key,
    )
    _write_json(arxiv_path, results)
    _write_json(matches_path, matches_report)

    return {
        "arxiv_metadata_path": str(arxiv_path),
        "dblp_title_arxiv_matches_path": str(matches_path),
        "dblp_title_arxiv_queries": queries_run,
        "dblp_title_arxiv_added": added,
        "dblp_title_arxiv_updated": updated,
        "dblp_title_arxiv_no_match": no_match,
    }


def generate_structured_criteria(
    workspace: TopicWorkspace,
    *,
    recency_hint: str = "過去3年",
    mode: str = "web",
    pdf_dir: Optional[Path] = None,
    max_pdfs: int = 5,
    search_model: str = "gpt-5.2-chat-latest",
    formatter_model: str = "gpt-5.2",
    pdf_model: str = "gpt-4.1",
    search_temperature: float = 0.7,
    formatter_temperature: float = 0.2,
    pdf_temperature: float = 0.4,
    search_max_output_tokens: int = 1200,
    formatter_max_output_tokens: int = 1200,
    pdf_max_output_tokens: int = 1800,
    force: bool = False,
) -> Dict[str, object]:
    """Generate structured inclusion/exclusion criteria via OpenAI web search (and optional PDF background)."""

    load_env_file()

    output_path = workspace.criteria_path
    if output_path.exists() and not force:
        return {"criteria_path": str(output_path), "skipped": True}

    effective_recency_hint = recency_hint

    tool_type = "web_search_2025_08_26" if search_model == "gpt-5-search-api" else "web_search"
    cfg = CriteriaPipelineConfig(
        recency_hint=effective_recency_hint,
        search=SearchStageConfig(
            model=search_model,
            temperature=search_temperature,
            max_output_tokens=search_max_output_tokens,
            enforce_tool_choice=True,
            options=WebSearchOptions(search_context_size="medium", tool_type=tool_type),
        ),
        formatter=FormatterStageConfig(
            model=formatter_model,
            temperature=formatter_temperature,
            max_output_tokens=formatter_max_output_tokens,
        ),
    )

    pipeline_result = None
    validation_report: Optional[Dict[str, object]] = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        pipeline_result = run_structured_criteria_pipeline(
            workspace.topic,
            config=cfg,
            recency_hint=effective_recency_hint,
            exclude_title=None,
            cutoff_before_date=None,
            web_search_service=create_web_search_service(),
            formatter_service=LLMService(),
        )
        break
    if pipeline_result is None:
        raise RuntimeError("criteria pipeline did not produce a result")

    artifacts: Dict[str, object] = {
        "topic": workspace.topic,
        "recency_hint": effective_recency_hint,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cutoff_before_date": None,
        "exclude_title": None,
        "source_validation": validation_report,
        "search_prompt": pipeline_result.search_prompt,
        "structured_prompt_template": pipeline_result.structured_prompt_template,
        "web_search_notes": pipeline_result.raw_notes,
        "structured_payload": _strip_temporal_criteria(pipeline_result.structured_payload),
    }

    _ensure_dir(workspace.criteria_dir)
    (workspace.criteria_dir / "web_search_notes.txt").write_text(
        pipeline_result.raw_notes, encoding="utf-8"
    )

    if mode.strip().lower() in {"pdf+web", "pdf_web", "pdf"}:
        root = Path(pdf_dir) if pdf_dir else workspace.seed_arxiv_pdf_dir
        pdf_paths = sorted(path for path in root.glob("*.pdf") if path.is_file())
        if max_pdfs and max_pdfs > 0:
            pdf_paths = pdf_paths[:max_pdfs]

        pdf_background_text = ""
        if pdf_paths:
            instructions = (
                "你是系統性回顧助理。這些附加的 PDF 是與主題 '{topic}' 相關的 survey 或綜述文章。\n"
                "請閱讀所有檔案，凝練出能協助後續篩選流程的背景摘要。\n"
                "輸出語言為中文，並依照以下段落結構整理：\n"
                "### PDF Topic Definition\n"
                "- 1-2 段文字描述主題的範圍、核心概念與評估面向。\n"
                "### PDF Key Trends\n"
                "- 以條列說明近年趨勢、資料來源與常見研究角度。\n"
                "### PDF Capability Highlights\n"
                "- 條列最關鍵的技術/能力要求，每條 1 句。\n"
                "### PDF Inclusion Signals\n"
                "- 列出 3-5 項建議納入條件的關鍵字或描述，可引用 PDF 章節。\n"
                "### PDF Exclusion Signals\n"
                "- 列出 3-5 項建議排除的情境或與主題無關的研究方向。\n"
                "### PDF Notes\n"
                "- 列舉每個 PDF 的重點或特色，格式為 `- <檔名>: <重點>`。\n"
                "請勿輸出 JSON，僅以純文字完成。"
            ).format(topic=workspace.topic)

            service = LLMService()
            result = service.read_pdfs(
                "openai",
                pdf_model,
                pdf_paths,
                instructions=instructions,
                temperature=pdf_temperature,
                max_output_tokens=pdf_max_output_tokens,
                metadata={"stage": "pdf_background", "topic": workspace.topic},
            )
            if isinstance(result, LLMResult):
                pdf_background_text = result.content

        combined_notes = "\n".join(
            segment
            for segment in (
                "### PDF Background (Survey Summaries)" if pdf_background_text.strip() else "",
                pdf_background_text.strip(),
                "### Web Search Notes",
                pipeline_result.raw_notes.strip(),
            )
            if segment
        )
        (workspace.criteria_dir / "pdf_background.txt").write_text(
            pdf_background_text, encoding="utf-8"
        )
        (workspace.criteria_dir / "combined_notes.txt").write_text(
            combined_notes, encoding="utf-8"
        )

        augmented_messages = [
            {
                "role": "system",
                "content": (
                    "你是系統性回顧的資料整理助理，需將研究助理的筆記轉為結構化 JSON。\n"
                    "僅能輸出單一 JSON 物件，勿加入額外敘述或 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "以下內容結合了兩種來源：\n"
                    "1) PDF Background (Survey Summaries)：模型閱讀本地 PDF 後的背景整理，僅供提供更準確的主題定義與條件靈感，來源欄請勿引用非 https 連結。\n"
                    "2) Web Search Notes：OpenAI Web Search 所產出的即時筆記與來源。\n"
                    "請輸出最終 JSON，並確保所有 source 欄位皆為 https URL。\n"
                    f"主題：{workspace.topic}。\n"
                    "inclusion_criteria.required 段落僅能包含主題定義逐字條款與英文可評估性條款；其餘條件請歸入 any_of 群組。\n"
                    "不得要求標題/摘要必須包含特定字串或關鍵字；避免任何硬字串匹配條款。\n"
                    "將以下筆記整合後再輸出：\n"
                    "---\n"
                    f"{combined_notes.strip()}\n"
                    "---"
                ),
            },
        ]
        formatter = LLMService()
        augmented = formatter.chat(
            "openai",
            formatter_model,
            augmented_messages,
            temperature=formatter_temperature,
            max_output_tokens=formatter_max_output_tokens,
        )
        if not isinstance(augmented, LLMResult):
            raise RuntimeError("Formatter did not return an LLMResult")

        text = augmented.content
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("formatter response does not contain a JSON object")
        structured_payload = json.loads(text[start : end + 1])

        artifacts["pdf_background"] = pdf_background_text
        artifacts["combined_notes"] = combined_notes
        artifacts["augmented_formatter_messages"] = augmented_messages
        artifacts["structured_payload"] = structured_payload
        artifacts["formatter_raw"] = augmented.content

        (workspace.criteria_dir / "formatter_prompt.json").write_text(
            json.dumps(augmented_messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (workspace.criteria_dir / "formatter_raw.txt").write_text(
            augmented.content, encoding="utf-8"
        )

    _write_json(output_path, artifacts)
    return {"criteria_path": str(output_path), "mode": mode}


def _ensure_latte_review_importable() -> None:
    """Inject minimal stubs for optional LatteReview dependencies.

    LatteReview's provider layer imports optional libraries (litellm, tokencost,
    ollama, google-genai). This project primarily uses LatteReview's
    ``OpenAIProvider``; stubs avoid import-time failures when the optional
    provider stacks are not installed.
    """

    def _install_stub(module_name: str, module: types.ModuleType) -> None:
        if module_name not in sys.modules:
            sys.modules[module_name] = module

    try:  # pragma: no cover
        import litellm  # type: ignore  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover
        stub = types.ModuleType("litellm")
        stub.drop_params = True
        stub.enable_json_schema_validation = False

        def _raise_stub(*_: object, **__: object) -> None:
            raise RuntimeError("litellm stub 被呼叫，請改用 OpenAIProvider 或安裝 litellm。")

        stub.acompletion = _raise_stub  # type: ignore[attr-defined]
        stub.completion_cost = _raise_stub  # type: ignore[attr-defined]
        _install_stub("litellm", stub)

    try:  # pragma: no cover
        from tokencost import calculate_completion_cost, calculate_prompt_cost  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover
        tokencost_stub = types.ModuleType("tokencost")

        def _zero_cost(*_: object, **__: object) -> float:
            return 0.0

        tokencost_stub.calculate_prompt_cost = _zero_cost  # type: ignore[attr-defined]
        tokencost_stub.calculate_completion_cost = _zero_cost  # type: ignore[attr-defined]
        _install_stub("tokencost", tokencost_stub)

    try:  # pragma: no cover
        import ollama  # type: ignore  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover
        ollama_stub = types.ModuleType("ollama")

        class _AsyncClient:  # type: ignore[misc]
            def __init__(self, *_: object, **__: object) -> None:
                raise RuntimeError("ollama stub 被呼叫，請安裝 ollama 套件或避免使用 OllamaProvider。")

        ollama_stub.AsyncClient = _AsyncClient  # type: ignore[attr-defined]
        _install_stub("ollama", ollama_stub)

    try:  # pragma: no cover
        import google.genai  # type: ignore  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover
        google_stub = types.ModuleType("google")
        google_stub.__path__ = []  # type: ignore[attr-defined]

        genai_stub = types.ModuleType("google.genai")

        class _GenAIStub:  # type: ignore[misc]
            def __getattr__(self, name: str) -> object:
                raise RuntimeError("google.genai stub 被呼叫，請安裝 google-genai 套件或避免使用相關 provider。")

        class _GenAIClient:  # type: ignore[misc]
            def __init__(self, *_: object, **__: object) -> None:
                raise RuntimeError("google.genai.Client stub 被呼叫，請安裝 google-genai 套件或避免使用相關 provider。")

        genai_stub.types = _GenAIStub()  # type: ignore[attr-defined]
        genai_stub.Client = _GenAIClient  # type: ignore[attr-defined]

        _install_stub("google", google_stub)
        _install_stub("google.genai", genai_stub)


def _criteria_payload_to_strings(payload: Dict[str, object]) -> Tuple[str, str]:
    """Convert structured criteria JSON into LatteReview-friendly strings."""

    topic_definition = str(payload.get("topic_definition") or "").strip()
    inclusion = payload.get("inclusion_criteria")
    exclusion = payload.get("exclusion_criteria")

    inclusion_lines: List[str] = []
    if topic_definition:
        inclusion_lines.append(f"主題定義：{topic_definition}")

    if isinstance(inclusion, dict):
        required = inclusion.get("required") or []
        any_of = inclusion.get("any_of") or []
        if isinstance(required, list):
            for item in required:
                if not isinstance(item, dict):
                    continue
                criterion = str(item.get("criterion") or "").strip()
                if criterion:
                    inclusion_lines.append(criterion)
        if isinstance(any_of, list) and any_of:
            inclusion_lines.append("以下群組每組至少滿足一項：")
            for group in any_of:
                if not isinstance(group, dict):
                    continue
                label = str(group.get("label") or "").strip() or "群組"
                options = group.get("options") or []
                option_lines: List[str] = []
                if isinstance(options, list):
                    for opt in options:
                        if not isinstance(opt, dict):
                            continue
                        criterion = str(opt.get("criterion") or "").strip()
                        if criterion:
                            option_lines.append(f"- {criterion}")
                if option_lines:
                    inclusion_lines.append(f"{label}:")
                    inclusion_lines.extend(option_lines)

    exclusion_lines: List[str] = []
    if isinstance(exclusion, list):
        for item in exclusion:
            if not isinstance(item, dict):
                continue
            criterion = str(item.get("criterion") or "").strip()
            if criterion:
                exclusion_lines.append(criterion)
    elif isinstance(exclusion, str):
        exclusion_lines.append(exclusion.strip())

    inclusion_text = "\n".join(line for line in inclusion_lines if line)
    exclusion_text = "\n".join(line for line in exclusion_lines if line)
    return inclusion_text, exclusion_text


def run_latte_review(
    workspace: TopicWorkspace,
    *,
    arxiv_metadata_path: Optional[Path] = None,
    criteria_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    top_k: Optional[int] = None,
    skip_titles_containing: str = "***",
    discard_title: Optional[str] = None,
    discard_after_date: Optional[str] = None,
    junior_nano_model: str = "gpt-5-nano",
    junior_mini_model: str = "gpt-4.1-mini",
    senior_model: str = "gpt-5-mini",
    senior_reasoning_effort: str = "medium",
) -> Dict[str, object]:
    """Run LatteReview's Title/Abstract workflow and write results JSON."""

    load_env_file()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 未設定，無法執行 LatteReview。")

    _ensure_latte_review_importable()

    import asyncio

    import pandas as pd

    from resources.LatteReview.lattereview.agents import TitleAbstractReviewer
    from resources.LatteReview.lattereview.providers.openai_provider import OpenAIProvider
    from resources.LatteReview.lattereview.workflows import ReviewWorkflow

    metadata_path = Path(arxiv_metadata_path) if arxiv_metadata_path else workspace.arxiv_metadata_path
    if not metadata_path.exists():
        raise FileNotFoundError(f"找不到 arXiv metadata 檔案：{metadata_path}")

    criteria_payload: Dict[str, object] = {}
    if criteria_path:
        loaded = _read_json(Path(criteria_path))
        if isinstance(loaded, dict):
            structured = loaded.get("structured_payload")
            if isinstance(structured, dict):
                criteria_payload = structured
            elif isinstance(loaded.get("topic_definition"), (str, dict, list)):
                criteria_payload = loaded  # allow direct criteria JSON
    elif workspace.criteria_path.exists():
        loaded = _read_json(workspace.criteria_path)
        if isinstance(loaded, dict):
            structured = loaded.get("structured_payload")
            if isinstance(structured, dict):
                criteria_payload = structured

    cutoff_info = _get_cutoff_info(workspace)
    if cutoff_info:
        target = cutoff_info.get("target_paper") or {}
        target_title = target.get("title") if isinstance(target, dict) else None
        cutoff_value = cutoff_info.get("cutoff_date")
        if isinstance(target_title, str) and target_title.strip():
            discard_title = target_title.strip()
        if isinstance(cutoff_value, str) and cutoff_value.strip():
            discard_after_date = cutoff_value.strip()

    inclusion_criteria, exclusion_criteria = _criteria_payload_to_strings(criteria_payload)
    if not inclusion_criteria:
        inclusion_criteria = "論文需與指定主題高度相關，且提供可用於評估的英文內容（全文或摘要/方法）。"
    if not exclusion_criteria:
        exclusion_criteria = "論文若與主題無關，或缺乏可判斷的英文題名/摘要/方法描述則排除。"

    payload = _read_json(metadata_path)
    if not isinstance(payload, list):
        raise ValueError("arXiv metadata payload must be a list")

    rows: List[Dict[str, object]] = []
    discarded: List[Dict[str, object]] = []
    forced_included: List[Dict[str, object]] = []
    forced_ids = _load_seed_filter_selected_ids(workspace.seed_filters_dir / "selected_ids.json")
    forced_seen: Set[str] = set()
    skip_token = skip_titles_containing.strip().lower()
    normalized_discard_title = _normalize_title_for_match(discard_title) if discard_title else None
    cutoff_date = _parse_date_bound(discard_after_date, label="discard_after_date") if discard_after_date else None
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        arxiv_id = str(
            metadata.get("arxiv_id")
            or entry.get("arxiv_id")
            or extract_arxiv_id_from_record(entry)
            or ""
        ).strip()
        arxiv_id = trim_arxiv_id(arxiv_id) or arxiv_id
        title = str(metadata.get("title") or "").strip()
        abstract = str(metadata.get("summary") or metadata.get("abstract") or "").strip()
        if not title:
            continue
        if arxiv_id and arxiv_id in forced_ids and arxiv_id not in forced_seen:
            forced_seen.add(arxiv_id)
            forced_included.append(
                {
                    "title": " ".join(title.split()),
                    "abstract": " ".join(abstract.split()) if abstract else "",
                    "metadata": metadata,
                    "final_verdict": "include (seed_filter)",
                    "review_skipped": True,
                    "discard_reason": None,
                    "force_include_reason": "seed_filter_selected",
                }
            )
            continue
        cleaned_title = " ".join(title.split())
        cleaned_abstract = " ".join(abstract.split()) if abstract else ""
        published_date = _extract_publication_date(metadata)
        discard_reason: Optional[str] = None
        if normalized_discard_title and _normalize_title_for_match(cleaned_title) == normalized_discard_title:
            discard_reason = "title_matches_exclude_title"
        elif cutoff_date and published_date is None:
            discard_reason = "missing_publication_date_for_cutoff"
        elif cutoff_date and published_date and published_date >= cutoff_date:
            discard_reason = f"published_on_or_after_cutoff:{published_date.isoformat()}"
        if discard_reason:
            discarded.append(
                {
                    "title": cleaned_title,
                    "abstract": cleaned_abstract,
                    "metadata": metadata,
                    "discard_reason": discard_reason,
                }
            )
            continue
        if not cleaned_abstract:
            continue
        if skip_token and skip_token in cleaned_title.lower():
            continue
        if top_k is None or len(rows) < top_k:
            rows.append({"title": cleaned_title, "abstract": cleaned_abstract, "metadata": metadata})

    if not rows and not discarded:
        raise RuntimeError("找不到任何可供 LatteReview 審查或標記的條目（請確認 metadata/skip 條件）。")

    review_records: List[Dict[str, object]] = []
    result_columns: List[str] = ["title", "abstract", "metadata", "final_verdict"]

    if rows:
        df = pd.DataFrame(rows)

        def _build_reviewer(
            name: str,
            model: str,
            *,
            model_args: Dict[str, Any],
            reasoning: str,
            backstory: str,
            additional_context: Optional[str] = None,
        ) -> TitleAbstractReviewer:
            return TitleAbstractReviewer(
                name=name,
                provider=OpenAIProvider(model=model),
                inclusion_criteria=inclusion_criteria,
                exclusion_criteria=exclusion_criteria,
                model_args=model_args,
                reasoning=reasoning,
                backstory=backstory,
                additional_context=additional_context,
                max_concurrent_requests=50,
                verbose=False,
            )

        junior_nano = _build_reviewer(
            "JuniorNano",
            junior_nano_model,
            model_args={},
            reasoning="brief",
            backstory="一位負責初步篩選文獻的研究助理",
        )
        junior_mini = _build_reviewer(
            "JuniorMini",
            junior_mini_model,
            model_args={},
            reasoning="brief",
            backstory="一位熟悉相關領域的研究助理",
        )
        senior = _build_reviewer(
            "SeniorLead",
            senior_model,
            model_args={"reasoning_effort": senior_reasoning_effort} if senior_reasoning_effort else {},
            reasoning="brief",
            backstory="負責統整並做最終判定的資深 reviewer",
            additional_context="兩位 junior reviewer 已提供初步評估，請在整合意見前檢視他們的回饋。",
        )

        def _senior_filter(row: "pd.Series") -> bool:  # type: ignore[name-defined]
            eval_1 = row.get("round-A_JuniorNano_evaluation")
            eval_2 = row.get("round-A_JuniorMini_evaluation")
            if pd.isna(eval_1) or pd.isna(eval_2):
                return False
            try:
                score1 = int(eval_1)
                score2 = int(eval_2)
            except (TypeError, ValueError):
                return False
            if score1 != score2:
                if score1 >= 4 and score2 >= 4:
                    return False
                if score1 >= 3 or score2 >= 3:
                    return True
            elif score1 == score2 == 3:
                return True
            return False

        def _derive_verdict(row: "pd.Series") -> str:  # type: ignore[name-defined]
            senior_eval = row.get("round-B_SeniorLead_evaluation")
            source = "junior"
            score: Optional[int] = None
            if senior_eval is not None and not pd.isna(senior_eval):
                try:
                    score = int(senior_eval)
                    source = "senior"
                except (TypeError, ValueError):
                    score = None
            if score is None:
                candidates: List[int] = []
                for value in (
                    row.get("round-A_JuniorNano_evaluation"),
                    row.get("round-A_JuniorMini_evaluation"),
                ):
                    if value is None or pd.isna(value):
                        continue
                    try:
                        candidates.append(int(value))
                    except (TypeError, ValueError):
                        continue
                if not candidates:
                    return "需再評估 (no_score)"
                score = int(round(sum(candidates) / len(candidates)))
            if score >= 4:
                return f"include ({source}:{score})"
            if score <= 2:
                return f"exclude ({source}:{score})"
            return f"maybe ({source}:{score})"

        workflow_schema = [
            {"round": "A", "reviewers": [junior_nano, junior_mini], "text_inputs": ["title", "abstract"]},
            {
                "round": "B",
                "reviewers": [senior],
                "text_inputs": [
                    "title",
                    "abstract",
                    "round-A_JuniorNano_output",
                    "round-A_JuniorNano_evaluation",
                    "round-A_JuniorMini_output",
                    "round-A_JuniorMini_evaluation",
                ],
                "filter": _senior_filter,
            },
        ]

        workflow = ReviewWorkflow.model_validate(
            {"workflow_schema": workflow_schema, "verbose": False}, context={"data": df}
        )
        result_df = asyncio.run(workflow.run(df))
        result_df["final_verdict"] = result_df.apply(_derive_verdict, axis=1)

        result_columns = list(result_df.columns)
        for index, row in result_df.iterrows():
            record = {column: row[column] for column in result_df.columns}
            metadata_value = row.get("metadata") if "metadata" in row else None
            if metadata_value is None:
                metadata_value = df.loc[index, "metadata"]
            record["metadata"] = metadata_value
            record["review_skipped"] = False
            verdict = str(record.get("final_verdict") or "")
            if verdict.startswith("exclude"):
                record["discard_reason"] = verdict
            elif verdict.startswith("maybe"):
                record["discard_reason"] = "review_needs_followup"
            else:
                record["discard_reason"] = None
            review_records.append(record)

    output_records: List[Dict[str, object]] = []
    output_records.extend(forced_included)
    output_records.extend(review_records)
    if discarded:
        base_record = {column: None for column in result_columns}
        for item in discarded:
            record = dict(base_record)
            record["title"] = item.get("title")
            record["abstract"] = item.get("abstract")
            record["metadata"] = item.get("metadata")
            discard_reason = str(item.get("discard_reason") or "discard_rule")
            record["final_verdict"] = f"discard ({discard_reason})"
            record["review_skipped"] = True
            record["discard_reason"] = discard_reason
            output_records.append(record)

    out = Path(output_path) if output_path else workspace.review_results_path
    _ensure_dir(out.parent)
    out.write_text(json.dumps(output_records, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "review_results_path": str(out),
        "reviewed": len(review_records),
        "forced_included": len(forced_included),
        "discarded": len(discarded),
        "total": len(output_records),
    }


def run_snowball_asreview(
    workspace: TopicWorkspace,
    *,
    review_results_path: Optional[Path] = None,
    metadata_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    round_index: Optional[int] = None,
    registry_path: Optional[Path] = None,
    email: Optional[str] = None,
    keep_label: Optional[Sequence[str]] = ("include",),
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    skip_forward: bool = False,
    skip_backward: bool = False,
) -> Dict[str, object]:
    """Convert LatteReview results to ASReview CSV and run snowballing."""

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "test" / "speech_lm_results_to_asreview.py"
    if not script_path.exists():
        raise FileNotFoundError(f"找不到 snowball 腳本：{script_path}")

    spec = importlib_util.spec_from_file_location("autosr_speech_lm_results_to_asreview", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 snowball 腳本：{script_path}")

    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    asreview_main = getattr(module, "main", None)
    if not callable(asreview_main):
        raise RuntimeError(f"{script_path} 未提供可呼叫的 main(argv) 函式")

    results_path = Path(review_results_path) if review_results_path else workspace.review_results_path
    meta_path = Path(metadata_path) if metadata_path else workspace.arxiv_metadata_path
    if output_dir is not None:
        out_dir = Path(output_dir)
    elif round_index is not None:
        out_dir = workspace.snowball_round_dir(round_index)
    else:
        out_dir = workspace.snowball_round_dir(1)
    _ensure_dir(out_dir)
    registry = Path(registry_path) if registry_path else workspace.snowball_registry_path

    criteria_hash = ""
    if workspace.criteria_path.exists():
        criteria_hash = _sha256_file(workspace.criteria_path)
        _update_registry_criteria_hash(registry, criteria_hash)

    exclude_title: Optional[str] = None
    cutoff_before_date: Optional[str] = None
    cutoff_info = _get_cutoff_info(workspace)
    if cutoff_info:
        target = cutoff_info.get("target_paper") or {}
        target_title = target.get("title") if isinstance(target, dict) else None
        cutoff_value = cutoff_info.get("cutoff_date")
        if isinstance(target_title, str) and target_title.strip():
            exclude_title = target_title.strip()
        if isinstance(cutoff_value, str) and cutoff_value.strip():
            cutoff_before_date = cutoff_value.strip()

    effective_min_date = min_date
    effective_max_date = max_date
    if cutoff_before_date:
        try:
            cutoff_date = _parse_date_bound(cutoff_before_date, label="cutoff_before_date")
        except ValueError:
            cutoff_date = None
        if cutoff_date:
            cutoff_max = (cutoff_date - timedelta(days=1))
            if effective_max_date:
                try:
                    user_max = _parse_date_bound(effective_max_date, label="max_date")
                except ValueError:
                    user_max = None
                if user_max and user_max < cutoff_max:
                    effective_max_date = user_max.isoformat()
                else:
                    effective_max_date = cutoff_max.isoformat()
            else:
                effective_max_date = cutoff_max.isoformat()

    argv: List[str] = [
        "--input",
        str(results_path),
        "--metadata",
        str(meta_path),
        "--output-dir",
        str(out_dir),
    ]
    if email:
        argv.extend(["--email", email])
    if keep_label:
        for label in keep_label:
            argv.extend(["--keep-label", str(label)])
    if effective_min_date:
        argv.extend(["--min-date", effective_min_date])
    if effective_max_date:
        argv.extend(["--max-date", effective_max_date])
    if exclude_title:
        argv.extend(["--exclude-title", exclude_title])
    if registry:
        argv.extend(["--registry", str(registry)])
    if criteria_hash:
        argv.extend(["--criteria-hash", criteria_hash])
    if skip_forward:
        argv.append("--skip-forward")
    if skip_backward:
        argv.append("--skip-backward")

    rc = asreview_main(argv)
    if rc != 0:
        raise RuntimeError(f"ASReview snowball stage failed with code {rc}")
    return {"asreview_dir": str(out_dir)}


def run_snowball_iterative(
    workspace: TopicWorkspace,
    *,
    mode: str = "loop",
    max_rounds: int = 1,
    start_round: int = 1,
    stop_raw_threshold: Optional[int] = None,
    stop_included_threshold: Optional[int] = None,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
    email: Optional[str] = None,
    keep_label: Optional[Sequence[str]] = ("include",),
    skip_forward: bool = False,
    skip_backward: bool = False,
    review_top_k: Optional[int] = None,
    skip_titles_containing: Optional[str] = "***",
    registry_path: Optional[Path] = None,
    retain_registry: bool = False,
    bootstrap_review: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, object]:
    """Run iterative snowballing (each round includes LatteReview)."""

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "snowball_iterate.py"
    if not script_path.exists():
        raise FileNotFoundError(f"找不到 snowball 迭代腳本：{script_path}")

    spec = importlib_util.spec_from_file_location("autosr_snowball_iterate", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 snowball 迭代腳本：{script_path}")

    module = importlib_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    snowball_main = getattr(module, "main", None)
    if not callable(snowball_main):
        raise RuntimeError(f"{script_path} 未提供可呼叫的 main(argv) 函式")

    workspace_root = workspace.root.parent
    argv: List[str] = [
        "--topic",
        workspace.topic,
        "--workspace-root",
        str(workspace_root),
        "--mode",
        mode,
        "--max-rounds",
        str(max_rounds),
        "--start-round",
        str(start_round),
    ]
    if stop_raw_threshold is not None:
        argv.extend(["--stop-raw-threshold", str(stop_raw_threshold)])
    if stop_included_threshold is not None:
        argv.extend(["--stop-included-threshold", str(stop_included_threshold)])
    if min_date:
        argv.extend(["--min-date", min_date])
    if max_date:
        argv.extend(["--max-date", max_date])
    if email:
        argv.extend(["--email", email])
    if keep_label:
        for label in keep_label:
            argv.extend(["--keep-label", str(label)])
    if skip_forward:
        argv.append("--skip-forward")
    if skip_backward:
        argv.append("--skip-backward")
    if review_top_k is not None:
        argv.extend(["--review-top-k", str(review_top_k)])
    if skip_titles_containing is not None:
        argv.extend(["--skip-titles-containing", skip_titles_containing])
    if registry_path:
        argv.extend(["--registry", str(registry_path)])
    if retain_registry:
        argv.append("--retain-registry")
    if bootstrap_review:
        argv.extend(["--bootstrap-review", str(bootstrap_review)])
    if force:
        argv.append("--force")

    rc = snowball_main(argv)
    if rc != 0:
        raise RuntimeError(f"Snowball iterate failed with code {rc}")

    registry = Path(registry_path) if registry_path else workspace.snowball_registry_path
    return {
        "snowball_rounds_dir": str(workspace.snowball_rounds_dir),
        "registry_path": str(registry),
    }
