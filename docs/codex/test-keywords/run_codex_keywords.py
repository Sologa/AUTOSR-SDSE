#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from keywords_cli_utils import (
    DEFAULT_CODEX_DISABLE_FLAGS,
    build_keywords_prompt,
    build_run_id,
    collect_arxiv_metadata,
    extract_pdf_text,
    init_manifest,
    load_env,
    load_pdf_paths,
    load_text_inputs,
    repo_root,
    resolve_codex_bin,
    run_codex_exec,
    sanitize_search_terms_payload,
    slugify_topic,
    update_manifest,
    write_json,
    format_metadata_block,
)
from src.utils.keyword_extractor import ExtractParams


def _resolve_extra_args(
    base_arg_list: Optional[List[str]], allow_web_search: bool
) -> List[str]:
    """Build codex exec extra args, including web_search disable flags by default."""
    result: List[str] = []
    if not allow_web_search:
        result.extend(DEFAULT_CODEX_DISABLE_FLAGS)
    if base_arg_list:
        result.extend(base_arg_list)
    return result


def _normalize_search_terms(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize codex schema search_terms arrays into category -> terms dict."""
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
    """Append a Codex-only schema note to match the strict output schema."""
    return (
        f"{prompt}\n\n"
        "Codex schema note: output `search_terms` as a list of objects with keys "
        "`category` (string) and `terms` (array of strings). Example:\n"
        "[{\"category\": \"token_types\", \"terms\": [\"acoustic tokens\", \"semantic tokens\"]}]"
    )


def run_codex_keywords(
    *,
    topic: str,
    pdf_dir: Path,
    pdf_limit: int,
    model: str,
    run_id: str,
    output_dir: Path,
    schema_path: Path,
    prompt_path: Path,
    codex_bin: str,
    text_paths: List[Path],
    pdf_to_text: bool = False,
    codex_extra_args: Optional[List[str]] = None,
    allow_web_search: bool = False,
    max_queries: int = 50,
    include_ethics: bool = False,
    language: str = "en",
    seed_anchors: Optional[List[str]] = None,
    custom_categories: Optional[List[str]] = None,
    exclude_terms: Optional[List[str]] = None,
) -> Path:
    """Run a single Codex keywords flow and write outputs plus manifest entries."""
    pdf_paths, warnings = load_pdf_paths(pdf_dir, pdf_limit)
    if warnings:
        raise ValueError("; ".join(warnings))
    if text_paths and pdf_to_text:
        raise ValueError("Provide either --text-path/--text-dir or --pdf-to-text, not both")
    if not text_paths:
        if not pdf_to_text:
            raise ValueError("No PDF text inputs provided; supply --text-path/--text-dir or --pdf-to-text")
        text_paths = extract_pdf_text(pdf_paths, output_dir)

    metadata_records = collect_arxiv_metadata(pdf_paths)
    metadata_block = format_metadata_block(metadata_records)

    params = ExtractParams(
        topic=topic,
        use_topic_variants=False,
        max_queries=max_queries,
        include_ethics=include_ethics,
        language=language,
        seed_anchors=seed_anchors,
        custom_categories=custom_categories,
        exclude_terms=exclude_terms,
        prompt_path=prompt_path,
    )

    text_blocks = load_text_inputs(text_paths)
    prompt = build_keywords_prompt(
        params=params,
        metadata_block=metadata_block,
        pdf_text_blocks=text_blocks,
        pdf_paths=None,
    )
    prompt = _append_codex_schema_note(prompt)

    parsed, raw, err = run_codex_exec(
        prompt,
        model,
        schema_path,
        codex_bin=codex_bin,
        codex_extra_args=_resolve_extra_args(codex_extra_args, allow_web_search),
    )

    errors: List[str] = []
    if err:
        errors.append(err)

    payload = parsed if isinstance(parsed, dict) else None
    if payload is None:
        payload = {
            "topic": topic,
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

    output_payload: Dict[str, Any] = {
        "run_id": run_id,
        "mode": "single",
        "provider": "codex",
        "models": {"Keywords": model},
        "topic": topic,
        "prompt_path": str(prompt_path),
        "input_pdf_dir": str(pdf_dir),
        "input_pdfs": [str(path) for path in pdf_paths],
        "pdf_text_inputs": [str(path) for path in text_paths],
        "pdf_text_generated": pdf_to_text,
        "payload": payload,
        "raw_output": raw,
        "errors": errors,
    }

    output_path = output_dir / "codex_keywords.json"
    write_json(output_path, output_payload)

    manifest = init_manifest(
        output_dir,
        run_id,
        topic,
        pdf_paths,
        prompt_path,
        pdf_dir,
    )
    combined_extra_args = _resolve_extra_args(codex_extra_args, allow_web_search)
    update_manifest(
        output_dir,
        manifest,
        name="codex_keywords",
        path=output_path,
        mode="single",
        provider="codex",
        reviewer="Keywords",
        model=model,
        command=[
            codex_bin,
            "exec",
            *combined_extra_args,
            "-",
            "--model",
            model,
            "--output-schema",
            str(schema_path),
        ],
    )

    return output_path


def _collect_text_paths(text_dir: Optional[Path], text_paths: Optional[List[Path]]) -> List[Path]:
    """Collect text inputs from a directory or explicit paths."""
    collected: List[Path] = []
    if text_dir:
        if not text_dir.exists():
            raise FileNotFoundError(f"Text directory not found: {text_dir}")
        collected.extend(sorted(path for path in text_dir.glob("*.txt") if path.is_file()))
    if text_paths:
        for path in text_paths:
            if not path.exists():
                raise FileNotFoundError(f"Text file not found: {path}")
            collected.append(path)
    return collected


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Codex CLI keywords test")
    parser.add_argument(
        "--topic",
        default="discrete audio tokens more than a survey",
        help="Topic string used for workspace lookup",
    )
    parser.add_argument("--pdf-dir", type=Path, default=None, help="Path to seed PDF directory")
    parser.add_argument("--pdf-limit", type=int, default=3)
    parser.add_argument("--model", default="gpt-5.1-codex-mini")
    parser.add_argument("--codex-bin", default=None, help="Path to OpenAI Codex CLI binary")
    parser.add_argument(
        "--codex-extra-arg",
        action="append",
        help="Additional CLI flag passed to `codex exec` before the prompt.",
    )
    parser.add_argument(
        "--allow-web-search",
        action="store_true",
        help="Allow Codex web search tool for this run (disabled by default).",
    )
    parser.add_argument("--max-queries", type=int, default=50)
    parser.add_argument("--include-ethics", action="store_true")
    parser.add_argument("--language", default="en")
    parser.add_argument("--seed-anchor", action="append", help="Seed anchor hints")
    parser.add_argument("--custom-category", action="append", help="Custom category labels")
    parser.add_argument("--exclude-term", action="append", help="Exclude term hints")
    parser.add_argument("--text-dir", type=Path, default=None, help="Directory with PDF-to-text outputs")
    parser.add_argument("--text-path", type=Path, action="append", help="Explicit PDF-to-text file path")
    parser.add_argument(
        "--pdf-to-text",
        action="store_true",
        help="Generate PDF-to-text outputs with pdfplumber before running codex exec.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--prompt-path",
        type=Path,
        default=Path("resources/LLM/prompts/keyword_extractor/generate_search_terms.md"),
    )
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=Path("docs/codex/test-keywords/keywords_response_codex.schema.json"),
    )
    args = parser.parse_args()

    load_env()
    root = repo_root()
    topic_slug = slugify_topic(args.topic)
    pdf_dir = args.pdf_dir or root / "workspaces" / topic_slug / "seed" / "downloads" / "arxiv"
    run_id = args.run_id or build_run_id()
    output_dir = args.output_dir or root / "docs/codex/test-keywords/outputs" / run_id
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = args.prompt_path
    if not prompt_path.is_absolute():
        prompt_path = root / prompt_path
    schema_path = args.schema_path
    if not schema_path.is_absolute():
        schema_path = root / schema_path

    text_paths = _collect_text_paths(args.text_dir, args.text_path)
    codex_bin = resolve_codex_bin(args.codex_bin)

    run_codex_keywords(
        topic=args.topic,
        pdf_dir=pdf_dir,
        pdf_limit=args.pdf_limit,
        model=args.model,
        run_id=run_id,
        output_dir=output_dir,
        schema_path=schema_path,
        prompt_path=prompt_path,
        codex_bin=codex_bin,
        text_paths=text_paths,
        pdf_to_text=args.pdf_to_text,
        codex_extra_args=args.codex_extra_arg,
        allow_web_search=args.allow_web_search,
        max_queries=args.max_queries,
        include_ethics=args.include_ethics,
        language=args.language,
        seed_anchors=args.seed_anchor,
        custom_categories=args.custom_category,
        exclude_terms=args.exclude_term,
    )
    print(str(output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
