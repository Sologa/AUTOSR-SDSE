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
import os
import re
import shutil
import sys
import types
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from importlib import util as importlib_util
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def _parse_date_bound(raw: Optional[str], *, label: str) -> Optional[date]:
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
    for key in ("published", "published_date", "publication_date", "date", "year"):
        raw = metadata.get(key)
        if raw is None:
            continue
        try:
            return _parse_date_bound(str(raw), label=key)
        except ValueError:
            continue
    return None


def _head_ok(session: requests.Session, url: str, *, timeout: int = 15) -> bool:
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
        return slugify_topic(self.topic)

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def seed_dir(self) -> Path:
        return self.root / "seed"

    @property
    def seed_queries_dir(self) -> Path:
        return self.seed_dir / "queries"

    @property
    def seed_downloads_dir(self) -> Path:
        return self.seed_dir / "downloads"

    @property
    def seed_downloads_raw_dir(self) -> Path:
        return self.seed_downloads_dir / "arxiv_raw"

    @property
    def seed_arxiv_pdf_dir(self) -> Path:
        return self.seed_downloads_dir / "arxiv"

    @property
    def seed_filters_dir(self) -> Path:
        return self.seed_dir / "filters"

    @property
    def keywords_dir(self) -> Path:
        return self.root / "keywords"

    @property
    def keywords_path(self) -> Path:
        return self.keywords_dir / "keywords.json"

    @property
    def harvest_dir(self) -> Path:
        return self.root / "harvest"

    @property
    def arxiv_metadata_path(self) -> Path:
        return self.harvest_dir / "arxiv_metadata.json"

    @property
    def criteria_dir(self) -> Path:
        return self.root / "criteria"

    @property
    def criteria_path(self) -> Path:
        return self.criteria_dir / "criteria.json"

    @property
    def review_dir(self) -> Path:
        return self.root / "review"

    @property
    def review_results_path(self) -> Path:
        return self.review_dir / "latte_review_results.json"

    @property
    def asreview_dir(self) -> Path:
        return self.root / "asreview"

    def ensure_layout(self) -> None:
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
        ):
            _ensure_dir(path)

    def write_config(self, payload: Dict[str, object]) -> None:
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

    def _add_variant(text: str) -> None:
        candidate = " ".join(str(text).split())
        if candidate:
            variants.append(candidate)

    lower = normalized.lower()
    _add_variant(normalized)
    _add_variant(lower)
    _add_variant(normalized.title())

    if "spoken" in lower:
        _add_variant(lower.replace("spoken", "speech"))
    if "speech" in lower:
        _add_variant(lower.replace("speech", "spoken"))

    tokens = re.split(r"[\s/_-]+", lower)
    if tokens:
        last = tokens[-1]
        if last.endswith("s") and len(last) > 1:
            singular_tokens = tokens[:-1] + [last[:-1]]
            _add_variant(" ".join(singular_tokens))
        elif len(last) > 1:
            plural_tokens = tokens[:-1] + [last + "s"]
            _add_variant(" ".join(plural_tokens))

    if len(tokens) >= 2:
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
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\\u4e00-\\u9fff\\s]+", " ", text)
    return " ".join(text.split())


def _quote_term(term: str) -> str:
    escaped = term.replace("\\", r"\\").replace('"', r"\"")
    return f'"{escaped}"'


def _tokenize_query_phrase(text: str) -> List[str]:
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
    prefix = field.strip() or "all"
    return " OR ".join(f"{prefix}:{_quote_term(term)}" for term in terms if str(term).strip())


def _build_arxiv_token_and_clause(terms: Sequence[str], field: str) -> str:
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
    if token.endswith("s") and len(token) > 3:
        return token[:-1]
    return token


def _token_set(text: str) -> set[str]:
    normalized = _normalize_similarity_text(text)
    if not normalized:
        return set()
    tokens = {_stem_token(tok) for tok in normalized.split() if tok}
    tokens |= set(re.findall(r"[\\u4e00-\\u9fff]", normalized))
    return {tok for tok in tokens if tok}


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
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    topic_variants = default_topic_variants(topic)
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

    if cutoff_by_similar_title and candidates:
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
        cutoff_date = None
        cutoff_reason = "cutoff_removed_all_candidates"
        filtered = []
        anchor_id = ""
        if cutoff_candidate and cutoff_candidate.get("arxiv_id"):
            anchor_id = str(cutoff_candidate.get("arxiv_id") or "")
        for record in records:
            record_id = extract_arxiv_id_from_record(record) or ""
            if anchor_id and record_id and trim_arxiv_id(record_id) == trim_arxiv_id(anchor_id):
                continue
            filtered.append(record)

    selected = list(filtered)[: max(download_top_k, 0)] if download_top_k else []

    selection_report: Dict[str, object] = {
        "topic": topic,
        "topic_variants": topic_variants,
        "cutoff_by_similar_title": cutoff_by_similar_title,
        "similarity_threshold": similarity_threshold,
        "cutoff_reason": cutoff_reason,
        "cutoff_candidate": cutoff_candidate,
        "cutoff_date": cutoff_date.isoformat() if cutoff_date else None,
        "records_total": len(list(records)),
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


def _extract_title_abstract(record: Dict[str, object]) -> Tuple[str, str]:
    title = str(record.get("title") or "").strip()
    abstract = str(record.get("summary") or record.get("abstract") or "").strip()
    return title, abstract


def _parse_decision_payload(content: str) -> Dict[str, object]:
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


def _build_filter_seed_prompt(
    *,
    topic: str,
    title: str,
    abstract: str,
    include_keywords: Optional[Sequence[str]] = None,
    template_path: Optional[Path] = None,
) -> str:
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
                "decision": decision,
                "reason": parsed["reason"],
                "confidence": parsed["confidence"],
            }
        )
        if decision == "yes":
            selected_ids.append(arxiv_id)
        else:
            rejected_ids.append(arxiv_id)

    filters_dir.mkdir(parents=True, exist_ok=True)
    screening_payload = {
        "topic": workspace.topic,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "papers": papers,
    }
    _write_json(screening_path, screening_payload)
    _write_json(selection_path, {"selected": selected_ids, "rejected": rejected_ids})

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
) -> Dict[str, object]:
    """Search arXiv for survey-like papers and download the top results."""

    load_env_file()

    anchors = list(anchor_terms) if anchor_terms else default_topic_variants(workspace.topic)
    modifiers = list(survey_terms) if survey_terms else default_seed_survey_terms()

    queries_dir = workspace.seed_queries_dir
    records_path = queries_dir / "arxiv.json"

    session = requests.Session()
    try:
        search_query = None
        query_mode = anchor_mode

        if arxiv_raw_query:
            search_query = str(arxiv_raw_query).strip()
            if not search_query:
                raise ValueError("--arxiv-raw-query is empty")
            query_mode = "raw"

        if query_mode not in {"phrase", "token_and", "raw"}:
            raise ValueError(f"Unsupported anchor_mode: {query_mode}")

        if reuse_cached_queries and records_path.exists():
            records = json.loads(records_path.read_text(encoding="utf-8"))
        else:
            if query_mode == "raw" and search_query:
                records = _search_arxiv_with_query(
                    session,
                    query=search_query,
                    max_results=max_results,
                )
            else:
                field = scope.lower().strip() or "all"
                if query_mode == "token_and":
                    anchor_clause = _build_arxiv_token_and_clause(anchors, field)
                else:
                    anchor_clause = _build_arxiv_phrase_clause(anchors, field)
                search_clause = _build_arxiv_phrase_clause(modifiers, field)
                if not anchor_clause:
                    raise ValueError("anchor_terms 不能為空")
                if not search_clause:
                    raise ValueError("survey_terms 不能為空")
                search_query = f"({anchor_clause}) {boolean_operator} ({search_clause})"
                records = _search_arxiv_with_query(
                    session,
                    query=search_query,
                    max_results=max_results,
                )
            _write_json(records_path, records)

        selected, selection_report = _select_seed_arxiv_records(
            records,
            topic=workspace.topic,
            download_top_k=download_top_k,
            cutoff_by_similar_title=cutoff_by_similar_title,
            similarity_threshold=similarity_threshold,
        )
        selection_report["anchor_mode"] = query_mode
        selection_report["search_query"] = search_query
        selection_report["scope"] = scope
        selection_report["boolean_operator"] = boolean_operator
        selection_report["raw_query"] = arxiv_raw_query
        _write_json(queries_dir / "seed_selection.json", selection_report)
        downloads = download_records_to_pdfs({"arxiv": selected}, workspace.seed_downloads_dir, session=session)

        download_manifest: Dict[str, object] = {
            "topic": workspace.topic,
            "anchors": anchors,
            "survey_terms": modifiers,
            "anchor_mode": query_mode,
            "search_query": search_query,
            "raw_query": arxiv_raw_query,
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
    finally:
        session.close()

    pdfs = sorted(path for path in workspace.seed_arxiv_pdf_dir.glob("*.pdf") if path.is_file())
    return {
        "workspace": str(workspace.root),
        "seed_query_records": str(records_path),
        "seed_selection": str(queries_dir / "seed_selection.json"),
        "seed_download_manifest": str(workspace.seed_downloads_dir / "download_results.json"),
        "seed_pdfs": [str(path) for path in pdfs],
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

    start_bound = _parse_date_bound(start_date, label="--start-date")
    end_bound = _parse_date_bound(end_date, label="--end-date")
    if start_bound and end_bound and start_bound > end_bound:
        raise ValueError("--start-date cannot be later than --end-date")

    def _within_window(meta: Dict[str, object]) -> bool:
        if not start_bound and not end_bound:
            return True
        published = _extract_publication_date(meta)
        if not published:
            return False
        if start_bound and published < start_bound:
            return False
        if end_bound and published > end_bound:
            return False
        return True

    session = requests.Session()
    try:
        aggregated: Dict[str, Dict[str, object]] = {}
        total_queries = 0

        for anchor in anchors:
            if not isinstance(anchor, str) or not anchor.strip():
                continue
            for term in flattened_terms:
                total_queries += 1
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
                    continue

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
                    else:
                        queries = entry.get("queries")
                        if isinstance(queries, list):
                            candidate = {"anchor": anchor, "search_term": term}
                            if candidate not in queries:
                                queries.append(candidate)

    finally:
        session.close()

    results = sorted(aggregated.values(), key=lambda item: str(item.get("arxiv_id", "")))
    _write_json(output_path, results)
    return {
        "arxiv_metadata_path": str(output_path),
        "unique_papers": len(results),
        "queries_run": total_queries,
        "start_date": start_date,
        "end_date": end_date,
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


def generate_structured_criteria(
    workspace: TopicWorkspace,
    *,
    recency_hint: str = "過去3年",
    mode: str = "web",
    pdf_dir: Optional[Path] = None,
    max_pdfs: int = 5,
    search_model: str = "gpt-4.1",
    formatter_model: str = "gpt-5",
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

    cfg = CriteriaPipelineConfig(
        recency_hint=recency_hint,
        search=SearchStageConfig(
            model=search_model,
            temperature=search_temperature,
            max_output_tokens=search_max_output_tokens,
            enforce_tool_choice=True,
            options=WebSearchOptions(search_context_size="medium"),
        ),
        formatter=FormatterStageConfig(
            model=formatter_model,
            temperature=formatter_temperature,
            max_output_tokens=formatter_max_output_tokens,
        ),
    )

    pipeline_result = run_structured_criteria_pipeline(
        workspace.topic,
        config=cfg,
        recency_hint=recency_hint,
        web_search_service=create_web_search_service(),
        formatter_service=LLMService(),
    )

    artifacts: Dict[str, object] = {
        "topic": workspace.topic,
        "recency_hint": recency_hint,
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "search_prompt": pipeline_result.search_prompt,
        "structured_prompt_template": pipeline_result.structured_prompt_template,
        "web_search_notes": pipeline_result.raw_notes,
        "structured_payload": pipeline_result.structured_payload,
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
                    f"主題：{workspace.topic}；時間範圍：{recency_hint}。\n"
                    "inclusion_criteria.required 段落僅能包含主題定義逐字條款、recency 對齊條款，以及英文可評估性條款；其餘條件請歸入 any_of 群組。\n"
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
    skip_titles_containing: str = "survey",
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
        criteria_obj = _read_json(Path(criteria_path))
        if isinstance(criteria_obj, dict):
            structured = criteria_obj.get("structured_payload")
            if isinstance(structured, dict):
                criteria_payload = structured
            elif isinstance(criteria_obj.get("topic_definition"), (str, dict, list)):
                criteria_payload = criteria_obj  # allow direct criteria JSON
    elif workspace.criteria_path.exists():
        criteria_obj = _read_json(workspace.criteria_path)
        if isinstance(criteria_obj, dict):
            structured = criteria_obj.get("structured_payload")
            if isinstance(structured, dict):
                criteria_payload = structured

    inclusion_criteria, exclusion_criteria = _criteria_payload_to_strings(criteria_payload)
    if not inclusion_criteria:
        inclusion_criteria = "論文需與指定主題高度相關，且提供可用於評估的英文內容（全文或摘要/方法）。"
    if not exclusion_criteria:
        exclusion_criteria = "論文若與主題無關，或缺乏可判斷的英文題名/摘要/方法描述則排除。"

    payload = _read_json(metadata_path)
    if not isinstance(payload, list):
        raise ValueError("arXiv metadata payload must be a list")

    rows: List[Dict[str, object]] = []
    skip_token = skip_titles_containing.strip().lower()
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        title = str(metadata.get("title") or "").strip()
        abstract = str(metadata.get("summary") or metadata.get("abstract") or "").strip()
        if not title or not abstract:
            continue
        if skip_token and skip_token in title.lower():
            continue
        rows.append({"title": " ".join(title.split()), "abstract": " ".join(abstract.split()), "metadata": metadata})
        if top_k is not None and len(rows) >= top_k:
            break
    if not rows:
        raise RuntimeError("找不到任何可供 LatteReview 審查的條目（請確認 metadata/skip 條件）。")

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

    workflow = ReviewWorkflow.model_validate({"workflow_schema": workflow_schema, "verbose": False}, context={"data": df})
    result_df = asyncio.run(workflow.run(df))
    result_df["final_verdict"] = result_df.apply(_derive_verdict, axis=1)

    output_records: List[Dict[str, object]] = []
    for index, row in result_df.iterrows():
        record = {column: row[column] for column in result_df.columns}
        metadata_value = row.get("metadata") if "metadata" in row else None
        if metadata_value is None:
            metadata_value = df.loc[index, "metadata"]
        record["metadata"] = metadata_value
        output_records.append(record)

    out = Path(output_path) if output_path else workspace.review_results_path
    _ensure_dir(out.parent)
    out.write_text(json.dumps(output_records, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"review_results_path": str(out), "reviewed": len(output_records)}


def run_snowball_asreview(
    workspace: TopicWorkspace,
    *,
    review_results_path: Optional[Path] = None,
    metadata_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
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
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    asreview_main = getattr(module, "main", None)
    if not callable(asreview_main):
        raise RuntimeError(f"{script_path} 未提供可呼叫的 main(argv) 函式")

    results_path = Path(review_results_path) if review_results_path else workspace.review_results_path
    meta_path = Path(metadata_path) if metadata_path else workspace.arxiv_metadata_path
    out_dir = Path(output_dir) if output_dir else workspace.asreview_dir
    _ensure_dir(out_dir)

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
    if min_date:
        argv.extend(["--min-date", min_date])
    if max_date:
        argv.extend(["--max-date", max_date])
    if skip_forward:
        argv.append("--skip-forward")
    if skip_backward:
        argv.append("--skip-backward")

    rc = asreview_main(argv)
    if rc != 0:
        raise RuntimeError(f"ASReview snowball stage failed with code {rc}")
    return {"asreview_dir": str(out_dir)}
