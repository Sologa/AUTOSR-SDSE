"""Keyword/search-term extraction from survey PDFs using the LLM provider layer.

The pipeline reads each PDF individually, then aggregates the partial JSON responses
into a consolidated payload aligned with arXiv metadata. It uses the OpenAI
Responses API via the local provider abstraction in ``src/utils/llm.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import requests

from .paper_downloaders import fetch_arxiv_metadata
from .paper_workflows import trim_arxiv_id

from .llm import LLMResult, LLMService, ProviderCallError

DEFAULT_PROMPT_PATH = Path("resources/LLM/prompts/keyword_extractor/generate_search_terms.md")
DEFAULT_AGGREGATE_PATH = Path("resources/LLM/prompts/keyword_extractor/aggregate_terms.md")
_DEFAULT_DYNAMIC_CATEGORY_COUNT = 6



@dataclass(frozen=True)
class PaperMetadataRecord:
    arxiv_id: str
    title: str
    abstract: str
    year: Optional[str]
    url: str
    pdf_path: Path

    @property
    def source_id(self) -> str:
        return f"arXiv:{self.arxiv_id}"


_METADATA_CACHE: Dict[str, tuple[str, str, Optional[str], str]] = {}
_CATEGORY_ALIAS_PATTERN = re.compile(r"[^a-z0-9]+")
_TERM_INVALID_CHARS = re.compile(r"[^0-9A-Za-z\- /]+")
_TERM_MULTI_SPACES = re.compile(r"\s{2,}")


def _infer_arxiv_id(pdf_path: Path) -> str:
    candidate = trim_arxiv_id(pdf_path.stem)
    if not candidate:
        raise ValueError(f"Unable to infer arXiv identifier from PDF name: {pdf_path}")
    return candidate


def _collect_paper_metadata(pdf_list: Sequence[Path]) -> List[PaperMetadataRecord]:
    if not pdf_list:
        return []

    session = requests.Session()
    records: List[PaperMetadataRecord] = []
    try:
        for pdf_path in pdf_list:
            arxiv_id = _infer_arxiv_id(pdf_path)
            cached = _METADATA_CACHE.get(arxiv_id)
            if cached is None:
                metadata = fetch_arxiv_metadata(arxiv_id, session=session)
                title = (metadata.get("title") or "").strip()
                abstract = (metadata.get("summary") or metadata.get("abstract") or "").strip()
                if not title or not abstract:
                    raise ValueError(f"Metadata for arXiv:{arxiv_id} is missing title or abstract")
                published = (metadata.get("published") or "").strip()
                year = published.split("-", 1)[0] if published else None
                url = (metadata.get("landing_url") or f"https://arxiv.org/abs/{arxiv_id}").strip()
                cached = (title, abstract, year, url)
                _METADATA_CACHE[arxiv_id] = cached

            title, abstract, year, url = cached
            records.append(
                PaperMetadataRecord(
                    arxiv_id=arxiv_id,
                    title=title,
                    abstract=abstract,
                    year=year,
                    url=url,
                    pdf_path=pdf_path,
                )
            )
    finally:
        session.close()

    return records


def _format_metadata_block(metadata_list: Sequence[PaperMetadataRecord]) -> str:
    if not metadata_list:
        return "(no metadata provided)"

    lines: List[str] = []
    for idx, meta in enumerate(metadata_list, start=1):
        lines.extend(
            [
                f"--- Paper {idx} ---",
                f"source_id: {meta.source_id}",
                f"title: {meta.title}",
                f"abstract: {meta.abstract}",
                f"year: {meta.year or 'unknown'}",
                f"url: {meta.url}",
                f"pdf_path: {meta.pdf_path}",
            ]
        )
    return "\n".join(lines)


def _normalize_string(value: Optional[str]) -> str:
    return " ".join((value or "").split())


def _extend_unique_strings(target: List[str], values: Iterable[str]) -> None:
    """Extend ``target`` with ``values`` while preserving order and deduplicating."""

    seen = {item.casefold() for item in target if isinstance(item, str)}
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = _normalize_phrase(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        target.append(normalized)


def _resolved_categories(params: "ExtractParams") -> List[str]:
    if params.custom_categories:
        return [category for category in params.custom_categories if category]

    return []


def _default_category_terms_target(params: "ExtractParams", *, category_count: Optional[int] = None) -> int:
    if category_count is None:
        category_count = len(_resolved_categories(params))

    max_total = params.max_queries or 50
    if max_total <= 0:
        return 0

    if category_count is None or category_count <= 0:
        category_count = _DEFAULT_DYNAMIC_CATEGORY_COUNT

    baseline = max_total // category_count
    if max_total >= category_count * 3:
        return min(10, max(3, baseline))

    if max_total >= category_count * 2:
        return max(2, baseline)

    if baseline >= 1:
        return baseline

    return 1 if max_total else 0


def _collect_detected_keyword_candidates(
    papers: Sequence[Dict[str, Any]],
) -> Dict[str, List[str]]:
    by_category: Dict[str, List[str]] = {}
    for paper in papers:
        if not isinstance(paper, dict):
            continue
        for keyword in paper.get("detected_keywords", []) or []:
            if not isinstance(keyword, dict):
                continue
            category = keyword.get("category")
            term = keyword.get("term")
            if not isinstance(category, str) or not isinstance(term, str):
                continue
            category = category.strip()
            if not category:
                continue
            bucket = by_category.setdefault(category, [])
            bucket.append(term)
    return by_category


def _canonical_category_label(label: str) -> str:
    slug = _CATEGORY_ALIAS_PATTERN.sub("", label.casefold())
    return slug or label.casefold()


def _merge_duplicate_categories(search_terms: Dict[str, List[str]]) -> Dict[str, List[str]]:
    if not isinstance(search_terms, dict):
        return {}

    normalized_map: Dict[str, str] = {}
    merged: Dict[str, List[str]] = {}

    for original_label, values in search_terms.items():
        if not isinstance(original_label, str):
            continue
        canonical = _canonical_category_label(original_label)
        existing_label = normalized_map.get(canonical)
        if existing_label is None:
            normalized_map[canonical] = original_label
            bucket = merged.setdefault(original_label, [])
        else:
            bucket = merged.setdefault(existing_label, [])
        if isinstance(values, list):
            _extend_unique_strings(bucket, values)

    return merged


def _sanitize_search_term(value: str, *, max_words: int = 4, max_length: int = 60) -> Optional[str]:
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    text = text.replace("_", " ")
    text = _TERM_INVALID_CHARS.sub(" ", text)
    text = _TERM_MULTI_SPACES.sub(" ", text)
    text = text.strip(" ,.;:|/")
    if not text:
        return None

    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])
        words = text.split()

    if len(words) == 1:
        text = words[0].lower()
    else:
        text = " ".join(word.lower() for word in words)

    if len(text) > max_length or not text:
        return None

    if len(words) == 0:
        return None

    return text


def _sanitize_search_term_buckets(
    search_terms: Dict[str, List[str]],
    *,
    max_words_per_term: int = 4,
    min_terms_per_category: int = 1,
) -> Dict[str, List[str]]:
    cleaned: Dict[str, List[str]] = {}
    for category, values in search_terms.items():
        if not isinstance(category, str):
            continue
        bucket: List[str] = []
        seen: set[str] = set()
        for value in values or []:
            sanitized = _sanitize_search_term(value, max_words=max_words_per_term)
            if not sanitized:
                continue
            key = sanitized.casefold()
            if key in seen:
                continue
            seen.add(key)
            bucket.append(sanitized)
        if len(bucket) >= min_terms_per_category:
            cleaned[category] = bucket
    return cleaned


def _enrich_search_terms_from_papers(
    payload: Dict[str, Any],
    params: "ExtractParams",
    per_payloads: Optional[Sequence[Dict[str, Any]]] = None,
) -> None:
    if not isinstance(payload, dict):
        return

    papers = payload.get("papers")
    if not isinstance(papers, list):
        return

    search_terms = payload.get("search_terms")
    if not isinstance(search_terms, dict):
        search_terms = {}
        payload["search_terms"] = search_terms

    categories = list(_resolved_categories(params))
    if params.allow_additional_categories:
        for category in search_terms:
            if category not in categories:
                categories.append(category)

    keyword_candidates = _collect_detected_keyword_candidates(papers)

    if per_payloads:
        for per_payload in per_payloads:
            if not isinstance(per_payload, dict):
                continue
            per_terms = per_payload.get("search_terms")
            if not isinstance(per_terms, dict):
                continue
            for category, values in per_terms.items():
                if not isinstance(category, str) or not isinstance(values, list):
                    continue
                bucket = keyword_candidates.setdefault(category, [])
                for value in values:
                    if isinstance(value, str):
                        bucket.append(value)

    for category, terms in keyword_candidates.items():
        if not params.allow_additional_categories and category not in categories:
            continue
        bucket = search_terms.setdefault(category, [])
        _extend_unique_strings(bucket, terms)
        if params.allow_additional_categories and category not in categories:
            categories.append(category)

    target_count = (
        params.min_terms_per_category
        if params.min_terms_per_category is not None
        else _default_category_terms_target(params, category_count=len(categories))
    )

    if target_count > 0:
        all_candidates: Dict[str, List[str]] = {}
        for category, terms in keyword_candidates.items():
            all_candidates[category] = _dedupe_preserve_order(terms)

        for category in categories:
            bucket = search_terms.setdefault(category, [])
            if len(bucket) >= target_count:
                continue
            supplemental = all_candidates.get(category, [])
            if not supplemental:
                continue
            _extend_unique_strings(bucket, supplemental)

    merged_terms = _merge_duplicate_categories(search_terms)
    sanitized_terms = _sanitize_search_term_buckets(
        merged_terms,
        max_words_per_term=3,
        min_terms_per_category=1,
    )
    payload["search_terms"] = sanitized_terms

def _validate_output_against_metadata(
    payload: Dict[str, Any],
    metadata_list: Sequence[PaperMetadataRecord],
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Keyword extractor must return a JSON object.")

    papers = payload.get("papers")
    if not isinstance(papers, list):
        raise ValueError("Keyword extractor output missing 'papers' list.")
    if len(papers) != len(metadata_list):
        raise ValueError("Number of papers in output does not match metadata block.")

    for index, meta in enumerate(metadata_list):
        paper_entry = papers[index] if index < len(papers) else None
        if not isinstance(paper_entry, dict):
            raise ValueError("Each paper entry must be an object.")

        source_id = (paper_entry.get("source_id") or paper_entry.get("id") or "").strip()
        if not source_id:
            raise ValueError("Paper entry missing 'source_id'.")
        normalized_source = source_id.replace("arXiv:", "").strip()
        if normalized_source != meta.arxiv_id:
            raise ValueError(
                f"Paper entry source_id '{source_id}' does not match metadata arXiv:{meta.arxiv_id}."
            )

        paper_title = _normalize_string(paper_entry.get("title"))
        if paper_title != _normalize_string(meta.title):
            raise ValueError(
                f"Paper title mismatch for arXiv:{meta.arxiv_id}. Expected '{meta.title}'."
            )

        paper_abstract = _normalize_string(paper_entry.get("abstract"))
        if paper_abstract != _normalize_string(meta.abstract):
            raise ValueError(
                f"Paper abstract mismatch for arXiv:{meta.arxiv_id}. Title: {meta.title}"
            )


def _build_metadata_aligned_paper_entry(
    meta: PaperMetadataRecord,
    template: Dict[str, Any],
) -> Dict[str, Any]:
    entry = dict(template) if isinstance(template, dict) else {}
    entry.setdefault("id", meta.source_id.replace(":", "_"))
    entry["source_id"] = meta.source_id
    entry["title"] = meta.title
    entry["abstract"] = meta.abstract
    entry["year"] = str(entry.get("year") or meta.year or "unknown")
    entry["source_url"] = entry.get("source_url") or meta.url
    detected = entry.get("detected_keywords")
    if not isinstance(detected, list):
        entry["detected_keywords"] = []
    return entry


def _build_stub_payload(
    meta: PaperMetadataRecord,
    params: "ExtractParams",
    anchor_variants: Sequence[str],
) -> Dict[str, Any]:
    anchors = _dedupe_preserve_order(anchor_variants)
    if not anchors and params.seed_anchors:
        anchors = _dedupe_preserve_order(params.seed_anchors)
    if not anchors and params.topic:
        normalized_topic = _normalize_phrase(params.topic)
        if normalized_topic:
            anchors = [normalized_topic]
    if not anchors:
        fallback = _normalize_phrase(meta.title) or meta.source_id
        anchors = [fallback]

    paper_entry = _build_metadata_aligned_paper_entry(meta, {})

    payload = {
        "topic": params.topic or "",
        "anchor_terms": anchors,
        "search_terms": {},
        "papers": [paper_entry],
    }

    return payload


def _enforce_metadata_alignment(
    payload: Dict[str, Any],
    metadata_list: Sequence[PaperMetadataRecord],
) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Keyword extractor must return a JSON object.")

    original_papers = payload.get("papers")
    remaining_papers = [item for item in original_papers or [] if isinstance(item, dict)]

    aligned_papers: List[Dict[str, Any]] = []

    for meta in metadata_list:
        matched_paper: Dict[str, Any] = {}
        for idx, candidate in enumerate(remaining_papers):
            source = (candidate.get("source_id") or candidate.get("id") or "").replace(
                "arXiv:", ""
            ).strip()
            if source == meta.arxiv_id:
                matched_paper = candidate
                remaining_papers.pop(idx)
                break
        if not matched_paper and remaining_papers:
            matched_paper = remaining_papers.pop(0)

        aligned_papers.append(_build_metadata_aligned_paper_entry(meta, matched_paper))

    payload["papers"] = aligned_papers


def _fallback_aggregate_per_paper_outputs(
    per_payloads: Sequence[Dict[str, Any]],
    metadata_list: Sequence[PaperMetadataRecord],
    params: "ExtractParams",
) -> Dict[str, Any]:
    if len(per_payloads) != len(metadata_list):
        raise ValueError("Per-paper payloads do not align with metadata for fallback aggregation.")

    anchor_candidates: List[str] = []
    search_terms: Dict[str, List[str]] = {}
    papers: List[Dict[str, Any]] = []

    for payload, meta in zip(per_payloads, metadata_list):
        if not isinstance(payload, dict):
            raise ValueError("Per-paper payload must be a JSON object.")

        anchor_list = [item for item in payload.get("anchor_terms", []) if isinstance(item, str)]
        anchor_candidates.extend(anchor_list)

        source_terms = payload.get("search_terms", {})
        if isinstance(source_terms, dict):
            for category, values in source_terms.items():
                if not isinstance(category, str):
                    continue
                bucket = search_terms.setdefault(category, [])
                if isinstance(values, list):
                    _extend_unique_strings(bucket, values)

        paper_entry: Dict[str, Any] = {}
        per_papers = payload.get("papers")
        if isinstance(per_papers, list):
            for candidate in per_papers:
                if not isinstance(candidate, dict):
                    continue
                source_id = (candidate.get("source_id") or candidate.get("id") or "").replace(
                    "arXiv:", ""
                ).strip()
                if source_id == meta.arxiv_id:
                    paper_entry = candidate
                    break
            if not paper_entry and per_papers and isinstance(per_papers[0], dict):
                paper_entry = per_papers[0]

        papers.append(_build_metadata_aligned_paper_entry(meta, paper_entry))

    topic_value = None
    if per_payloads:
        topic_value = per_payloads[0].get("topic")
    if not isinstance(topic_value, str) or not topic_value.strip():
        topic_value = params.topic or ""

    return {
        "topic": topic_value,
        "anchor_terms": _dedupe_preserve_order(anchor_candidates),
        "search_terms": {key: value for key, value in search_terms.items() if value},
        "papers": papers,
    }

@dataclass
class ExtractParams:
    topic: Optional[str] = None
    max_queries: int = 50
    include_ethics: bool = True
    language: str = "en"
    custom_categories: Optional[List[str]] = None
    seed_anchors: Optional[List[str]] = None
    anchor_variants: Optional[List[str]] = None
    exclude_terms: Optional[List[str]] = None
    prompt_path: Optional[Path | str] = None
    aggregate_prompt_path: Optional[Path | str] = None
    max_output_tokens: Optional[int] = None
    reasoning_effort: Optional[str] = None
    allow_additional_categories: bool = True
    min_terms_per_category: Optional[int] = None


def _normalize_phrase(value: str) -> str:
    return " ".join(value.split())


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if not value:
            continue
        normalized = _normalize_phrase(str(value))
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _generate_topic_variants(topic: Optional[str]) -> List[str]:
    if not topic:
        return []

    base = _normalize_phrase(topic)
    if not base:
        return []

    variants: List[str] = []

    def _add_variant(text: str) -> None:
        for candidate in (_normalize_phrase(text), _normalize_phrase(text).title()):
            if candidate:
                variants.append(candidate)

    lower = base.lower()
    _add_variant(base)
    _add_variant(lower)

    if "spoken" in lower:
        _add_variant(lower.replace("spoken", "speech"))
    if "speech" in lower:
        _add_variant(lower.replace("speech", "spoken"))

    tokens = re.split(r"[\s\-_/]+", lower)
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

    return _dedupe_preserve_order(variants)


def _resolved_anchor_variants(params: ExtractParams) -> List[str]:
    if params.anchor_variants:
        return _dedupe_preserve_order(params.anchor_variants)

    variants = _generate_topic_variants(params.topic)
    if params.seed_anchors:
        variants.extend(params.seed_anchors)
    return _dedupe_preserve_order(variants)


def _anchor_guidance_text(params: ExtractParams, variants: Sequence[str]) -> str:
    if variants:
        return (
            "use exactly these topic-aligned variants: "
            + " | ".join(variants)
            + "; do not introduce unrelated anchor terms"
        )
    if params.topic:
        return (
            "limit anchors to well-formed variants of the provided topic; reject unrelated concepts"
        )
    return "infer 2–4 anchors grounded in the PDFs"


def _anchor_policy_text(topic: Optional[str], variants: Sequence[str]) -> str:
    if variants:
        return (
            "Restrict anchor_terms to the exact topic variants: "
            + " | ".join(variants)
        )
    if topic:
        return (
            f"Anchor terms must stay aligned with the topic '{_normalize_phrase(topic)}' and only include close synonyms or abbreviations."
        )
    return "Maintain anchors consistent with the strongest consensus across inputs."


def _apply_anchor_postprocessing(
    payload: Dict[str, Any],
    variants: Sequence[str],
    params: ExtractParams,
) -> None:
    if not isinstance(payload, dict):
        return

    normalized_variants = _dedupe_preserve_order(variants)
    if normalized_variants:
        payload["anchor_terms"] = normalized_variants
        return

    anchors = [
        item
        for item in payload.get("anchor_terms", [])
        if isinstance(item, str) and item.strip()
    ]
    if params.topic:
        topic_lower = params.topic.lower()
        filtered = [anchor for anchor in anchors if topic_lower in anchor.lower()]
        if not filtered and params.seed_anchors:
            filtered = _dedupe_preserve_order(params.seed_anchors)
        if not filtered and anchors:
            filtered = _dedupe_preserve_order(anchors)
        if not filtered:
            filtered = [_normalize_phrase(params.topic)]
        payload["anchor_terms"] = filtered
    else:
        payload["anchor_terms"] = _dedupe_preserve_order(anchors)

def _load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_generate_instructions(
    params: ExtractParams,
    *,
    resolved_anchor_variants: Optional[Sequence[str]] = None,
    metadata_block: Optional[str] = None,
) -> str:
    template_path = Path(params.prompt_path) if params.prompt_path else DEFAULT_PROMPT_PATH
    template = _load_template(template_path)

    def _format_list(values: Optional[Sequence[str]], *, default: str) -> str:
        if not values:
            return default
        return ", ".join(str(item) for item in values if item)

    categories = _resolved_categories(params)
    estimated_category_count = len(categories) if categories else _DEFAULT_DYNAMIC_CATEGORY_COUNT

    anchor_variants = (
        _dedupe_preserve_order(resolved_anchor_variants)
        if resolved_anchor_variants is not None
        else _resolved_anchor_variants(params)
    )
    anchor_guidance = _anchor_guidance_text(params, anchor_variants)
    additional_category_note = ""
    if params.allow_additional_categories:
        additional_category_note = (
            "  - 如果既有分類不足以描述重要議題，可以新增最多兩個新的 snake_case 分類，並提供代表性術語。\n"
        )

    if categories:
        category_display = ", ".join(categories)
    else:
        category_display = (
            "自行歸納 4–6 個具描述性的 snake_case 分類（例如 benchmarks, training_methods, datasets, evaluation_metrics）"
        )

    target_count = (
        params.min_terms_per_category
        if params.min_terms_per_category is not None
        else _default_category_terms_target(
            params, category_count=estimated_category_count
        )
    )

    if categories:
        if target_count:
            coverage_note = (
                f"每個分類至少收集 {target_count} 個術語，若低於 3 個請合併到最接近的既有分類"
            )
        else:
            coverage_note = "維持各分類皆有代表性與去重的術語"
    else:
        coverage_note = (
            f"推導多個主題分類，並讓每個分類至少包含 {target_count} 個術語（不足 3 個術語時不要獨立成分類）"
            if target_count
            else "推導多個主題分類並讓每個分類保持具體多樣"
        )

    total_goal = target_count * (len(categories) if categories else estimated_category_count)
    if not total_goal:
        total_goal = params.max_queries or 50
    if total_goal:
        coverage_note += f"，目標總數大約 {total_goal} 個或依據證據調整"

    replacements = {
        "<<max_queries>>": str(params.max_queries),
        "<<include_ethics>>": str(params.include_ethics).lower(),
        "<<language>>": params.language,
        "<<topic_hint>>": params.topic or "not provided",
        "<<topic_or_inferred>>": params.topic or "inferred from provided PDFs",
        "<<category_list>>": category_display,
        "<<seed_anchors_info>>": _format_list(params.seed_anchors, default="not provided"),
        "<<exclude_terms_info>>": _format_list(params.exclude_terms, default="not provided"),
        "<<custom_categories_info>>": _format_list(
            params.custom_categories,
            default="not provided (use defaults)",
        ),
        "<<anchor_guidance>>": anchor_guidance,
        "<<category_coverage_note>>": coverage_note,
    }

    text = template
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    text = text.replace("<<paper_metadata_block>>", metadata_block or "(metadata unavailable)")
    text = text.replace("<<additional_category_note>>", additional_category_note)
    return text


def build_aggregate_instructions(
    partials: Iterable[str],
    *,
    max_queries: int = 50,
    topic: Optional[str] = None,
    anchor_variants: Optional[Sequence[str]] = None,
    metadata_block: Optional[str] = None,
    aggregate_prompt_path: Optional[Path | str] = None,
    allow_additional_categories: bool = False,
    category_target: Optional[int] = None,
) -> str:
    template_path = Path(aggregate_prompt_path) if aggregate_prompt_path else DEFAULT_AGGREGATE_PATH
    template = _load_template(template_path)
    joined = "\n\n".join(partials)
    text = template.replace("<<partial_json_list>>", joined)
    text = text.replace("<<max_queries>>", str(max_queries))
    anchor_list = _dedupe_preserve_order(anchor_variants) if anchor_variants else []
    text = text.replace("<<topic_hint>>", _normalize_phrase(topic or "not provided"))
    text = text.replace("<<anchor_policy>>", _anchor_policy_text(topic, anchor_list))
    text = text.replace("<<paper_metadata_block>>", metadata_block or "(metadata unavailable)")
    additional_note = ""
    if allow_additional_categories:
        additional_note = (
            "  - 保留並整併模型新增的分類，確保相關術語與證據被收錄。\n"
        )
    text = text.replace("<<additional_category_note>>", additional_note)
    coverage_target = category_target if category_target is not None else 0
    if coverage_target:
        coverage_note = (
            f"每個分類至少維持 {coverage_target} 個術語，保留模型推導出的分類並避免超過 {max_queries} 個總量；若某分類不足 3 個術語請併入相關分類"
        )
    else:
        coverage_note = (
            f"保留並擴展輸入中的分類結構，同時讓總術語不超過 {max_queries} 個"
        )
    text = text.replace("<<category_coverage_note>>", coverage_note)
    return text


def extract_search_terms_from_surveys(
    pdf_paths: Sequence[Path | str],
    *,
    provider: str = "openai",
    model: str = "gpt-5-nano",
    params: Optional[ExtractParams] = None,
    service: Optional[LLMService] = None,
    temperature: Optional[float] = 0.2,
    max_output_tokens: Optional[int] = 2000,
    reasoning_effort: Optional[str] = None,
    usage_log_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Run the extraction pipeline and return the parsed JSON dictionary."""

    p = params or ExtractParams()
    svc = service or LLMService()

    pdf_list = [Path(pth) for pth in pdf_paths]
    if not pdf_list:
        raise ValueError("pdf_paths must contain at least one item")

    effective_max_output = p.max_output_tokens if p.max_output_tokens is not None else max_output_tokens
    effective_reasoning = p.reasoning_effort if p.reasoning_effort is not None else reasoning_effort

    paper_metadata = _collect_paper_metadata(pdf_list)
    combined_metadata_block = _format_metadata_block(paper_metadata)
    per_metadata_blocks = [_format_metadata_block([meta]) for meta in paper_metadata]

    resolved_anchor_variants = _resolved_anchor_variants(p)
    usage_log_file = (
        Path(usage_log_path)
        if usage_log_path
        else Path("test_artifacts/keyword_extractor_live")
        / f"keyword_extractor_usage_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    )

    usage_results: List[LLMResult | None] = []

    per_paper_jsons: List[str] = []
    per_results: List[LLMResult | None] = []
    per_parsed_payloads: List[Dict[str, Any]] = []

    for idx, pdf_path in enumerate(pdf_list):
        per_instructions = build_generate_instructions(
            p,
            resolved_anchor_variants=resolved_anchor_variants,
            metadata_block=per_metadata_blocks[idx],
        )
        try:
            metadata_payload = {
                "mode": "per_pdf",
                "topic": (p.topic or "")[:500],
                "pdf_path": str(pdf_path),
            }
            if resolved_anchor_variants:
                metadata_payload["anchor_variants"] = " | ".join(resolved_anchor_variants)[:900]

            result = svc.read_pdf(
                provider,
                model,
                pdf_path,
                instructions=per_instructions,
                temperature=temperature,
                max_output_tokens=effective_max_output,
                reasoning_effort=effective_reasoning,
                metadata=metadata_payload,
            )
            per_result = result
        except ProviderCallError:
            prov = svc.get_provider(provider)
            fallback_reader = getattr(prov, "fallback_read_pdf", None)
            if fallback_reader is None:
                raise
            per_result = fallback_reader(
                model=model,
                pdf_path=pdf_path,
                instructions=per_instructions,
                temperature=temperature,
                max_output_tokens=effective_max_output,
                reasoning_effort=effective_reasoning,
            )
            if not isinstance(per_result, LLMResult):  # pragma: no cover - defensive
                raise ProviderCallError("Fallback provider did not return an LLMResult")
        if not isinstance(per_result, LLMResult):  # pragma: no cover - defensive
            raise ProviderCallError("Provider did not return an LLMResult")

        per_paper_jsons.append(per_result.content)
        per_results.append(per_result)
        try:
            parsed_partial = _parse_json_content(per_result)
        except json.JSONDecodeError:
            parsed_partial = _build_stub_payload(
                paper_metadata[idx],
                p,
                resolved_anchor_variants,
            )
        _apply_anchor_postprocessing(parsed_partial, resolved_anchor_variants, p)
        _enforce_metadata_alignment(parsed_partial, [paper_metadata[idx]])
        _validate_output_against_metadata(parsed_partial, [paper_metadata[idx]])
        per_parsed_payloads.append(parsed_partial)

    target_terms = (
        p.min_terms_per_category
        if p.min_terms_per_category is not None
        else _default_category_terms_target(p)
    )

    aggregate_prompt = build_aggregate_instructions(
        per_paper_jsons,
        max_queries=p.max_queries,
        topic=p.topic,
        anchor_variants=resolved_anchor_variants,
        metadata_block=combined_metadata_block,
        aggregate_prompt_path=p.aggregate_prompt_path,
        allow_additional_categories=p.allow_additional_categories,
        category_target=target_terms,
    )
    metadata_payload = {
        "mode": "aggregation",
        "topic": (p.topic or "")[:500],
    }
    if resolved_anchor_variants:
        metadata_payload["anchor_variants"] = " | ".join(resolved_anchor_variants)[:900]

    chat_result = svc.chat(
        provider,
        model,
        messages=[{"role": "user", "content": aggregate_prompt}],
        max_output_tokens=effective_max_output,
        temperature=temperature,
        reasoning_effort=effective_reasoning,
        metadata=metadata_payload,
    )
    assert isinstance(chat_result, LLMResult)
    usage_results.extend(per_results)
    usage_results.append(chat_result)

    parsed: Dict[str, Any] = {}
    use_fallback = False
    try:
        try:
            parsed = _parse_json_content(chat_result)
        except json.JSONDecodeError:
            use_fallback = True
        else:
            try:
                _apply_anchor_postprocessing(parsed, resolved_anchor_variants, p)
                _enforce_metadata_alignment(parsed, paper_metadata)
                _enrich_search_terms_from_papers(parsed, p, per_parsed_payloads)
                _validate_output_against_metadata(parsed, paper_metadata)
            except ValueError:
                use_fallback = True

        if use_fallback:
            parsed = _fallback_aggregate_per_paper_outputs(
                per_parsed_payloads,
                paper_metadata,
                p,
            )
            _apply_anchor_postprocessing(parsed, resolved_anchor_variants, p)
            _enforce_metadata_alignment(parsed, paper_metadata)
            _enrich_search_terms_from_papers(parsed, p, per_parsed_payloads)
            _validate_output_against_metadata(parsed, paper_metadata)
    finally:
        _write_usage_log(usage_log_file, usage_results)

    return parsed


def _parse_json_content(result: LLMResult) -> Dict[str, Any]:
    text = result.content.strip()
    # Some models may wrap JSON in code fences; attempt to strip if present.
    if text.startswith("```"):
        text = text[3:]
        text = text.lstrip()
        language_match = re.match(r"(?i)json[\w+-]*", text)
        if language_match:
            text = text[language_match.end():]
            if text.startswith("\r\n"):
                text = text[2:]
            elif text[:1] in {"\n", "\r"}:
                text = text[1:]
            else:
                newline_index = text.find("\n")
                if newline_index != -1:
                    text = text[newline_index + 1 :]
        text = text.lstrip()
        if text and text[0] not in "{[\"-0123456789tfn'":
            json_start = re.search(r"[{\[\"\-0-9tfn]", text)
            if json_start:
                text = text[json_start.start() :]
    text = text.rstrip()
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    return json.loads(text)


def _write_usage_log(path: Optional[Path | str], results: Sequence[LLMResult | None]) -> None:
    if not path:
        return

    records: List[Dict[str, Any]] = []
    total_input = 0
    total_output = 0
    total_cost = 0.0

    for res in results:
        if not isinstance(res, LLMResult):
            continue
        usage = res.usage
        record = {
            "provider": usage.provider,
            "model": usage.model,
            "mode": usage.mode,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost": usage.cost,
            "metadata": usage.metadata,
        }
        records.append(record)
        total_input += usage.input_tokens
        total_output += usage.output_tokens
        total_cost += usage.cost

    if not records:
        return

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "total": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cost": total_cost,
        },
    }

    usage_path = Path(path)
    usage_path.parent.mkdir(parents=True, exist_ok=True)
    usage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "PaperMetadataRecord",
    "ExtractParams",
    "build_generate_instructions",
    "build_aggregate_instructions",
    "extract_search_terms_from_surveys",
]
