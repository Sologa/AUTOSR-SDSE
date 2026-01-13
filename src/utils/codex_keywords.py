from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple

import requests

from src.utils.codex_cli import DEFAULT_CODEX_DISABLE_FLAGS, run_codex_exec
from src.utils.env import load_env_file
from src.utils.keyword_extractor import ExtractParams, build_generate_instructions
from src.utils.paper_downloaders import fetch_arxiv_metadata
from src.utils.paper_workflows import trim_arxiv_id

_TERM_INVALID_CHARS = re.compile(r"[^0-9A-Za-z /-]+")
_TERM_MULTI_SPACES = re.compile(r"\s{2,}")


class KeywordsWorkspace(Protocol):
    topic: str
    keywords_path: Path
    keywords_dir: Path
    seed_arxiv_pdf_dir: Path


@dataclass
class CodexKeywordsResult:
    keywords_path: str
    usage_log_path: str
    pdf_count: int


def _now_utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _sanitize_search_term(value: str, *, max_words: int = 3) -> Optional[str]:
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
        words = words[:max_words]
    cleaned = " ".join(words).lower().strip()
    return cleaned or None


def sanitize_search_terms(
    search_terms: Dict[str, List[str]],
    *,
    max_words: int = 3,
    min_terms_per_category: int = 1,
    max_total: Optional[int] = None,
) -> Dict[str, List[str]]:
    cleaned: Dict[str, List[str]] = {}
    for category, values in search_terms.items():
        if not isinstance(category, str):
            continue
        bucket: List[str] = []
        seen: set[str] = set()
        for value in values or []:
            sanitized = _sanitize_search_term(value, max_words=max_words)
            if not sanitized:
                continue
            if sanitized in seen:
                continue
            seen.add(sanitized)
            bucket.append(sanitized)
        if len(bucket) >= min_terms_per_category:
            cleaned[category] = bucket
    if max_total is None:
        return cleaned

    trimmed: Dict[str, List[str]] = {}
    total = 0
    for category, values in cleaned.items():
        if total >= max_total:
            break
        remaining = max_total - total
        bucket = values[:remaining]
        if bucket:
            trimmed[category] = bucket
            total += len(bucket)
    return trimmed


def sanitize_search_terms_payload(
    payload: Dict[str, Any],
    *,
    max_words: int = 3,
    max_total: Optional[int] = None,
) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    search_terms = payload.get("search_terms")
    if not isinstance(search_terms, dict):
        return payload
    updated = dict(payload)
    updated["search_terms"] = sanitize_search_terms(
        search_terms,
        max_words=max_words,
        max_total=max_total,
    )
    return updated


def load_pdf_paths(pdf_dir: Path, limit: int) -> List[Path]:
    if not pdf_dir.exists():
        raise FileNotFoundError(f"PDF directory not found: {pdf_dir}")
    pdf_paths = sorted(path for path in pdf_dir.glob("*.pdf") if path.is_file())
    if limit and limit > 0:
        pdf_paths = pdf_paths[:limit]
    if not pdf_paths:
        raise ValueError(f"No PDFs found under: {pdf_dir}")
    return pdf_paths


def _infer_arxiv_id(pdf_path: Path) -> str:
    candidate = trim_arxiv_id(pdf_path.stem)
    if not candidate:
        raise ValueError(f"Unable to infer arXiv identifier from PDF name: {pdf_path}")
    return candidate


def collect_arxiv_metadata(pdf_paths: Sequence[Path]) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    session = requests.Session()
    try:
        for pdf_path in pdf_paths:
            arxiv_id = _infer_arxiv_id(pdf_path)
            metadata = fetch_arxiv_metadata(arxiv_id, session=session)
            title = (metadata.get("title") or "").strip()
            abstract = (metadata.get("summary") or metadata.get("abstract") or "").strip()
            if not title or not abstract:
                raise ValueError(f"Metadata for arXiv:{arxiv_id} missing title or abstract")
            published = (metadata.get("published") or "").strip()
            year = published.split("-", 1)[0] if published else "unknown"
            url = (metadata.get("landing_url") or f"https://arxiv.org/abs/{arxiv_id}").strip()
            records.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "abstract": abstract,
                    "year": year,
                    "url": url,
                    "pdf_path": str(pdf_path),
                }
            )
    finally:
        session.close()
    return records


def format_metadata_block(metadata_list: Sequence[Dict[str, str]]) -> str:
    if not metadata_list:
        return "(no metadata provided)"
    lines: List[str] = []
    for idx, meta in enumerate(metadata_list, start=1):
        lines.extend(
            [
                f"--- Paper {idx} ---",
                f"source_id: arXiv:{meta['arxiv_id']}",
                f"title: {meta['title']}",
                f"abstract: {meta['abstract']}",
                f"year: {meta['year']}",
                f"url: {meta['url']}",
                f"pdf_path: {meta['pdf_path']}",
            ]
        )
    return "\n".join(lines)


def build_keywords_prompt(
    *,
    params: ExtractParams,
    metadata_block: str,
    pdf_text_blocks: Optional[List[Tuple[str, str]]] = None,
) -> str:
    prompt = build_generate_instructions(params, metadata_block=metadata_block)

    if pdf_text_blocks:
        prompt += "\n\nExtracted PDF text (pre-processed):\n"
        for label, text in pdf_text_blocks:
            prompt += f"\n--- {label} ---\n{text}\n"

    return prompt.strip()


def load_text_inputs(paths: Sequence[Path]) -> List[Tuple[str, str]]:
    blocks: List[Tuple[str, str]] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        blocks.append((path.name, text))
    return blocks


def extract_pdf_text(pdf_paths: Sequence[Path], output_dir: Path) -> List[Path]:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("pdfplumber is required; run `uv sync` before PDF-to-text extraction") from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: List[Path] = []
    for pdf_path in pdf_paths:
        text_chunks: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_chunks.append(page.extract_text() or "")
        output_path = output_dir / f"{pdf_path.stem}.txt"
        output_path.write_text("\n\n".join(text_chunks).strip() + "\n", encoding="utf-8")
        outputs.append(output_path)
    return outputs


def _normalize_search_terms(payload: Dict[str, Any]) -> Dict[str, Any]:
    search_terms = payload.get("search_terms")
    if not isinstance(search_terms, list):
        return payload

    normalized: Dict[str, List[str]] = {}
    for item in search_terms:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        terms = item.get("terms")
        if not isinstance(category, str) or not category.strip():
            continue
        if isinstance(terms, list):
            cleaned = [term for term in terms if isinstance(term, str) and term.strip()]
        else:
            cleaned = []
        normalized[category] = cleaned

    updated = dict(payload)
    updated["search_terms"] = normalized
    return updated


def _append_codex_schema_note(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "Codex schema note: output `search_terms` as a list of objects with keys "
        "`category` (string) and `terms` (array of strings). Example:\n"
        "[{\"category\": \"token_types\", \"terms\": [\"acoustic tokens\", \"semantic tokens\"]}]"
    )


def run_codex_cli_keywords(
    workspace: KeywordsWorkspace,
    *,
    pdf_dir: Optional[Path] = None,
    max_pdfs: int = 3,
    model: str,
    max_queries: int = 50,
    include_ethics: bool = False,
    seed_anchors: Optional[Sequence[str]] = None,
    prompt_path: Optional[Path] = None,
    schema_path: Optional[Path] = None,
    codex_bin: Optional[str] = None,
    codex_extra_args: Optional[Sequence[str]] = None,
    codex_home: Optional[Path] = None,
    allow_web_search: bool = False,
    reasoning_effort: Optional[str] = None,
    force: bool = False,
) -> CodexKeywordsResult:
    load_env_file()

    output_path = workspace.keywords_path
    if output_path.exists() and not force:
        return CodexKeywordsResult(
            keywords_path=str(output_path),
            usage_log_path="",
            pdf_count=0,
        )

    root = Path(pdf_dir) if pdf_dir else workspace.seed_arxiv_pdf_dir
    pdf_paths = load_pdf_paths(root, max_pdfs)

    prompt_path = prompt_path or Path("resources/LLM/prompts/keyword_extractor/generate_search_terms.md")
    schema_path = schema_path or Path("resources/schemas/keywords_response_codex.schema.json")

    metadata_records = collect_arxiv_metadata(pdf_paths)
    metadata_block = format_metadata_block(metadata_records)

    params = ExtractParams(
        topic=workspace.topic,
        use_topic_variants=False,
        max_queries=max_queries,
        include_ethics=include_ethics,
        seed_anchors=list(seed_anchors) if seed_anchors else None,
        reasoning_effort=reasoning_effort,
    )

    text_dir = workspace.keywords_dir / "codex_text"
    text_paths = extract_pdf_text(pdf_paths, text_dir)
    text_blocks = load_text_inputs(text_paths)

    prompt = build_keywords_prompt(
        params=params,
        metadata_block=metadata_block,
        pdf_text_blocks=text_blocks,
    )
    prompt = _append_codex_schema_note(prompt)

    extra_args: List[str] = []
    if not allow_web_search:
        extra_args.extend(DEFAULT_CODEX_DISABLE_FLAGS)
    if codex_extra_args:
        extra_args.extend(list(codex_extra_args))

    parsed, raw, err, cmd = run_codex_exec(
        prompt,
        model,
        schema_path,
        codex_bin=codex_bin,
        codex_extra_args=extra_args,
        codex_home=codex_home,
    )

    errors: List[str] = []
    if err:
        errors.append(err)

    payload = parsed if isinstance(parsed, dict) else None
    if payload is None:
        payload = {
            "topic": workspace.topic,
            "anchor_terms": [],
            "search_terms": {},
            "papers": [],
        }
    else:
        payload = _normalize_search_terms(payload)
        payload = sanitize_search_terms_payload(
            payload,
            max_words=3,
            max_total=max_queries,
        )

    _write_json(output_path, payload)

    run_stamp = _now_utc_stamp()
    usage_log_path = workspace.keywords_dir / f"keyword_cli_usage_{run_stamp}.json"
    run_record = {
        "provider": "codex-cli",
        "model": model,
        "command": cmd,
        "codex_home": str(codex_home) if codex_home else None,
        "input_pdfs": [str(path) for path in pdf_paths],
        "text_paths": [str(path) for path in text_paths],
        "output_path": str(output_path),
        "errors": errors,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reasoning_effort": reasoning_effort,
    }
    if raw:
        raw_output_path = workspace.keywords_dir / f"codex_raw_{run_stamp}.txt"
        run_record["raw_output_path"] = str(raw_output_path)
        raw_output_path.write_text(raw, encoding="utf-8")

    _write_json(usage_log_path, run_record)

    return CodexKeywordsResult(
        keywords_path=str(output_path),
        usage_log_path=str(usage_log_path),
        pdf_count=len(pdf_paths),
    )


__all__ = ["CodexKeywordsResult", "run_codex_cli_keywords"]
