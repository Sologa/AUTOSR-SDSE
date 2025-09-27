"""Keyword/search-term extraction from survey PDFs using the LLM provider layer.

This module supports two modes:
- combined: attach multiple PDFs in a single LLM request and ask for a consolidated JSON.
- two_step: per-PDF extraction followed by a consolidation chat over the partial JSONs.

It uses the OpenAI Responses API via the local provider abstraction in src/utils/llm.py.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .llm import LLMResult, LLMService, ProviderCallError


DEFAULT_PROMPT_PATH = Path("resources/LLM/prompts/keyword_extractor/generate_search_terms.md")
DEFAULT_AGGREGATE_PATH = Path("resources/LLM/prompts/keyword_extractor/aggregate_terms.md")


_FALLBACK_GENERATE = (
    "- Role: Academic Search Strategy Designer and Systematic Review Analyst\n"
    "- Background: The user uploads one or more survey papers (PDFs). Your goal is to extract high-quality search terms from the surveys’ main text, suitable for building academic search queries. These terms are typically derived from surveys, covering anchor terms and category-specific search terms used in literature retrieval.\n"
    "- Profile: You design evidence-grounded, reproducible search strategies for literature reviews. You prioritize deduplication, clarity, and coverage.\n"
    "- Skills: Systematic review methodology, taxonomy-driven term extraction, boolean query synthesis, deduplication and synonym consolidation, concise rationale writing.\n"
    "- Goals: Produce a JSON-only output containing anchors, categorized search terms, synonyms, excluded terms, and finalized boolean queries with brief rationales. Ground all terms in the uploaded PDFs.\n"
    "- Constraints:\n"
    "  - Use only information present in the uploaded PDFs. Avoid hallucinations and generic terms that aren’t central.\n"
    "  - Prefer multi-paper-supported terms; mark single-paper terms with lower confidence.\n"
    "  - Keep each rationale under 20 words; cite page numbers if available; otherwise use \"page\": \"n/a\".\n"
    "  - Keep total queries ≤ <<max_queries>> (default 50).\n"
    "  - Output strictly valid JSON, no extra text.\n"
    "- Workflow:\n"
    "  1) Read all PDFs and identify the central task/topic; propose 2–4 anchor_terms.\n"
    "  2) For each paper, extract candidate terms for categories: <<category_list>>.\n"
    "  3) Normalize and merge across papers: lemmatize, deduplicate, consolidate synonyms.\n"
    "  4) Generate boolean queries by combining each anchor with terms and their synonyms; include phrase quotes where appropriate.\n"
    "  5) Identify excluded_terms to reduce noise (e.g., unrelated domains; generic words).\n"
    "  6) Score terms (0–1), count supporting papers, and add short rationales with citations.\n"
    "- Runtime overrides (current request):\n"
    "  - topic_hint: <<topic_hint>>\n"
    "  - language: <<language>>\n"
    "  - include_ethics: <<include_ethics>>\n"
    "  - max_queries: <<max_queries>>\n"
    "  - seed_anchors: <<seed_anchors_info>>\n"
    "  - custom_categories: <<custom_categories_info>>\n"
    "  - exclude_terms: <<exclude_terms_info>>\n"
    "  - anchor_terms: <<anchor_guidance>>\n"
    "- OutputFormat (strict JSON):\n"
    "{\n"
    "  \"topic\": \"<<topic_or_inferred>>\",\n"
    "  \"papers\": [\n"
    "    {\n"
    "      \"id\": \"<attachment name or short id>\",\n"
    "      \"title\": \"<if detectable>\",\n"
    "      \"year\": \"<if detectable>\",\n"
    "      \"detected_keywords\": [\n"
    "        {\n"
    "          \"term\": \"…\",\n"
    "          \"category\": \"<category label>\",\n"
    "          \"evidence\": {\"quote\": \"…\", \"page\": \"n/a|<number>\"},\n"
    "          \"confidence\": 0.0\n"
    "        }\n"
    "      ]\n"
    "    }\n"
    "  ],\n"
    "  \"anchor_terms\": [\"…\", \"…\"],\n"
    "  \"search_terms\": {\n"
    "    \"<category>\": [\"…\"],\n"
    "    \"<category>\": [\"…\"]\n"
    "  },\n"
    "  \"synonyms\": {\n"
    "    \"term_a\": [\"…\", \"…\"]\n"
    "  },\n"
    "  \"excluded_terms\": [\"…\"],\n"
    "  \"queries\": [\n"
    "    {\n"
    "      \"query\": \"\\\"<anchor>\\\" AND (\\\"<term>\\\" OR \\\"<synonym>\\\" …)\",\n"
    "      \"category\": \"<category label>\",\n"
    "      \"rationale\": \"…\",\n"
    "      \"confidence\": 0.0\n"
    "    }\n"
    "  ],\n"
    "  \"top_terms\": [\n"
    "    {\"term\": \"…\", \"weight\": 0.0, \"support_count\": 2}\n"
    "  ]\n"
    "}\n"
    "- Notes:\n"
    "  - Align \"search_terms\" keys with the category list above (or provided custom categories).\n"
    "  - Keep “queries” concise and diverse; avoid redundant variants.\n"
)


_FALLBACK_AGGREGATE = (
    "- Role: Search Term Aggregator\n"
    "- Background: You are given JSON outputs produced independently for multiple survey PDFs. Each JSON contains candidate terms with evidence. Your task is to merge them into a single consolidated JSON following the same schema used by the generator, performing deduplication, synonym consolidation, and weighting.\n"
    "- Topic focus: <<topic_hint>>\n"
    "- Anchor policy: <<anchor_policy>>\n"
    "- Constraints:\n"
    "  - Preserve evidence by keeping the strongest quote per term and counting support across papers.\n"
    "  - Merge spelling variants and morphological variants; list them under synonyms.\n"
    "  - Prefer precise, domain-specific terms; downweight overly generic words.\n"
    "  - Output strictly valid JSON only.\n"
    "- Workflow:\n"
    "  1) Load all input JSONs.\n"
    "  2) Normalize: lowercase, lemmatize, strip punctuation; map variants to a canonical form.\n"
    "  3) Merge: aggregate support_count and keep highest confidence; gather distinct evidences (limit to 2 quotes per term).\n"
    "  4) Rebuild anchor_terms (top 2–4 by global weight) and ensure search_terms cover the category set provided by the inputs.\n"
    "  5) Produce queries up to <<max_queries>> combining anchors with representative terms and synonyms.\n"
    "- Output: Same schema as generate_search_terms.md.\n\n"
    "Input placeholder:\n<<partial_json_list>>\n"
)


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
    mode: str = "combined"  # or "two_step"
    prompt_path: Optional[Path | str] = None


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

def _load_template(path: Path, fallback: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def build_generate_instructions(
    params: ExtractParams,
    *,
    resolved_anchor_variants: Optional[Sequence[str]] = None,
) -> str:
    template_path = Path(params.prompt_path) if params.prompt_path else DEFAULT_PROMPT_PATH
    template = _load_template(template_path, _FALLBACK_GENERATE)

    def _format_list(values: Optional[Sequence[str]], *, default: str) -> str:
        if not values:
            return default
        return ", ".join(str(item) for item in values if item)

    categories: List[str]
    if params.custom_categories:
        categories = [category for category in params.custom_categories if category]
    else:
        categories = [
            "core_concepts",
            "technical_terms",
            "advanced_concepts",
            "implementation",
            "subdomains",
        ]
        if params.include_ethics:
            categories.append("ethics")

    anchor_variants = (
        _dedupe_preserve_order(resolved_anchor_variants)
        if resolved_anchor_variants is not None
        else _resolved_anchor_variants(params)
    )
    anchor_guidance = _anchor_guidance_text(params, anchor_variants)

    replacements = {
        "<<max_queries>>": str(params.max_queries),
        "<<include_ethics>>": str(params.include_ethics).lower(),
        "<<language>>": params.language,
        "<<topic_hint>>": params.topic or "not provided",
        "<<topic_or_inferred>>": params.topic or "inferred from provided PDFs",
        "<<category_list>>": ", ".join(categories) if categories else "none",
        "<<seed_anchors_info>>": _format_list(params.seed_anchors, default="not provided"),
        "<<exclude_terms_info>>": _format_list(params.exclude_terms, default="not provided"),
        "<<custom_categories_info>>": _format_list(
            params.custom_categories,
            default="not provided (use defaults)",
        ),
        "<<anchor_guidance>>": anchor_guidance,
    }

    text = template
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    return text


def build_aggregate_instructions(
    partials: Iterable[str],
    *,
    max_queries: int = 50,
    topic: Optional[str] = None,
    anchor_variants: Optional[Sequence[str]] = None,
) -> str:
    template = _load_template(DEFAULT_AGGREGATE_PATH, _FALLBACK_AGGREGATE)
    joined = "\n\n".join(partials)
    text = template.replace("<<partial_json_list>>", joined)
    text = text.replace("<<max_queries>>", str(max_queries))
    anchor_list = _dedupe_preserve_order(anchor_variants) if anchor_variants else []
    text = text.replace("<<topic_hint>>", _normalize_phrase(topic or "not provided"))
    text = text.replace("<<anchor_policy>>", _anchor_policy_text(topic, anchor_list))
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
    usage_log_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Run the extraction pipeline and return the parsed JSON dictionary.

    When params.mode == "combined", attempts a single request with multiple files.
    When params.mode == "two_step", runs per-PDF extraction then aggregates.
    """

    p = params or ExtractParams()
    svc = service or LLMService()

    pdf_list = [Path(pth) for pth in pdf_paths]
    if not pdf_list:
        raise ValueError("pdf_paths must contain at least one item")

    resolved_anchor_variants = _resolved_anchor_variants(p)
    usage_log_file = (
        Path(usage_log_path)
        if usage_log_path
        else Path("test_artifacts/llm")
        / f"keyword_extractor_usage_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    )

    if p.mode not in ("combined", "two_step"):
        raise ValueError("params.mode must be 'combined' or 'two_step'")

    usage_results: List[LLMResult | None] = []

    if p.mode == "combined":
        instructions = build_generate_instructions(
            p, resolved_anchor_variants=resolved_anchor_variants
        )
        metadata_payload = {
            "mode": p.mode,
            "topic": (p.topic or "")[:500],
        }
        if resolved_anchor_variants:
            metadata_payload["anchor_variants"] = " | ".join(resolved_anchor_variants)[:900]

        result = svc.read_pdfs(
            provider,
            model,
            pdf_list,
            instructions=instructions,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata_payload,
        )
        usage_results.append(result)
        try:
            parsed = _parse_json_content(result)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM output was not valid JSON") from exc
        finally:
            _write_usage_log(usage_log_file, usage_results)
        _apply_anchor_postprocessing(parsed, resolved_anchor_variants, p)
        return parsed

    # two_step mode
    per_paper_jsons: List[str] = []
    per_results: List[LLMResult | None] = []
    per_instructions = build_generate_instructions(
        p, resolved_anchor_variants=resolved_anchor_variants
    )
    for pdf_path in pdf_list:
        try:
            metadata_payload = {
                "mode": "two_step",
                "topic": (p.topic or "")[:500],
                "pdf_path": str(pdf_path),
            }
            if resolved_anchor_variants:
                metadata_payload["anchor_variants"] = " | ".join(resolved_anchor_variants)[:900]

            r = svc.read_pdf(
                provider,
                model,
                pdf_path,
                instructions=per_instructions,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                metadata=metadata_payload,
            )
            per_paper_jsons.append(r.content)
            per_results.append(r)
        except ProviderCallError:
            prov = svc.get_provider(provider)
            fallback_reader = getattr(prov, "fallback_read_pdf", None)
            if fallback_reader is None:
                raise
            fallback_result = fallback_reader(
                model=model,
                pdf_path=pdf_path,
                instructions=per_instructions,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            )
            if not isinstance(fallback_result, LLMResult):  # pragma: no cover - defensive
                raise ProviderCallError("Fallback provider did not return an LLMResult")
            per_paper_jsons.append(fallback_result.content)
            per_results.append(fallback_result)

    aggregate_prompt = build_aggregate_instructions(
        per_paper_jsons,
        max_queries=p.max_queries,
        topic=p.topic,
        anchor_variants=resolved_anchor_variants,
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
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        metadata=metadata_payload,
    )
    assert isinstance(chat_result, LLMResult)
    usage_results.extend(per_results)
    usage_results.append(chat_result)
    try:
        parsed = _parse_json_content(chat_result)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM output was not valid JSON") from exc
    finally:
        _write_usage_log(usage_log_file, usage_results)
    _apply_anchor_postprocessing(parsed, resolved_anchor_variants, p)
    return parsed


def _parse_json_content(result: LLMResult) -> Dict[str, Any]:
    text = result.content.strip()
    # Some models may wrap JSON in code fences; attempt to strip if present.
    if text.startswith("```"):
        text = text[3:]
        text = text.lstrip()
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.lstrip()
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
    "ExtractParams",
    "build_generate_instructions",
    "build_aggregate_instructions",
    "extract_search_terms_from_surveys",
]
