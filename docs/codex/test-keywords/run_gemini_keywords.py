#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from keywords_cli_utils import (
    build_keywords_prompt,
    build_run_id,
    collect_arxiv_metadata,
    init_manifest,
    load_env,
    load_pdf_paths,
    prepare_gemini_settings,
    repo_root,
    restore_gemini_settings,
    run_gemini_cli,
    sanitize_search_terms_payload,
    slugify_topic,
    update_manifest,
    write_json,
    format_metadata_block,
)
from src.utils.keyword_extractor import ExtractParams


def run_gemini_keywords(
    *,
    topic: str,
    pdf_dir: Path,
    pdf_limit: int,
    model: str,
    run_id: str,
    output_dir: Path,
    prompt_path: Path,
    allow_web_search: bool,
    gemini_root: Optional[Path],
    respect_git_ignore: Optional[bool] = None,
    max_queries: int = 50,
    include_ethics: bool = False,
    language: str = "en",
    seed_anchors: Optional[List[str]] = None,
    custom_categories: Optional[List[str]] = None,
    exclude_terms: Optional[List[str]] = None,
) -> Path:
    """Run a single Gemini keywords flow with repo-local tool policy."""
    pdf_paths, warnings = load_pdf_paths(pdf_dir, pdf_limit)
    if warnings:
        raise ValueError("; ".join(warnings))

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

    prompt = build_keywords_prompt(
        params=params,
        metadata_block=metadata_block,
        pdf_paths=pdf_paths,
    )

    errors: List[str] = []
    model_used = model
    tool_usage: Optional[Dict[str, Any]] = None
    settings_state = prepare_gemini_settings(
        root=gemini_root,
        allow_web_search=allow_web_search,
        respect_git_ignore=respect_git_ignore,
    )

    try:
        parsed, raw, err, detected_model, tools = run_gemini_cli(prompt, model)
        if detected_model:
            model_used = detected_model
        if tools:
            tool_usage = tools
        if err:
            errors.append(err)
            payload = {
                "topic": topic,
                "anchor_terms": [],
                "search_terms": {},
                "papers": [],
            }
        else:
            payload = parsed if isinstance(parsed, dict) else None
            if payload is None:
                errors.append("gemini response missing JSON payload")
                payload = {
                    "topic": topic,
                    "anchor_terms": [],
                    "search_terms": {},
                    "papers": [],
                }
            else:
                payload = sanitize_search_terms_payload(
                    payload,
                    max_words=3,
                    max_total=max_queries,
                )
    finally:
        restore_gemini_settings(settings_state)

    output_payload: Dict[str, Any] = {
        "run_id": run_id,
        "mode": "single",
        "provider": "gemini",
        "models": {"Keywords": model_used},
        "topic": topic,
        "prompt_path": str(prompt_path),
        "input_pdf_dir": str(pdf_dir),
        "input_pdfs": [str(path) for path in pdf_paths],
        "tool_usage": tool_usage or {},
        "payload": payload,
        "raw_output": raw,
        "errors": errors,
    }

    output_path = output_dir / "gemini_keywords.json"
    write_json(output_path, output_payload)

    manifest = init_manifest(
        output_dir,
        run_id,
        topic,
        pdf_paths,
        prompt_path,
        pdf_dir,
    )
    update_manifest(
        output_dir,
        manifest,
        name="gemini_keywords",
        path=output_path,
        mode="single",
        provider="gemini",
        reviewer="Keywords",
        model=model_used,
        command=["gemini", "--output-format", "json", "--model", model],
        command_meta=settings_state["policy"],
    )

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gemini CLI keywords test")
    parser.add_argument(
        "--topic",
        default="discrete audio tokens more than a survey",
        help="Topic string used for workspace lookup",
    )
    parser.add_argument("--pdf-dir", type=Path, default=None, help="Path to seed PDF directory")
    parser.add_argument("--pdf-limit", type=int, default=3)
    parser.add_argument("--model", default="gemini-2.5-pro")
    parser.add_argument(
        "--gemini-allow-web-search",
        action="store_true",
        help="Allow Gemini web search tool for this run (disabled by default).",
    )
    parser.add_argument(
        "--gemini-respect-gitignore",
        action="store_true",
        help="Respect .gitignore when Gemini reads files (disabled by default for PDF access).",
    )
    parser.add_argument("--max-queries", type=int, default=50)
    parser.add_argument("--include-ethics", action="store_true")
    parser.add_argument("--language", default="en")
    parser.add_argument("--seed-anchor", action="append", help="Seed anchor hints")
    parser.add_argument("--custom-category", action="append", help="Custom category labels")
    parser.add_argument("--exclude-term", action="append", help="Exclude term hints")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--prompt-path",
        type=Path,
        default=Path("resources/LLM/prompts/keyword_extractor/generate_search_terms.md"),
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

    run_gemini_keywords(
        topic=args.topic,
        pdf_dir=pdf_dir,
        pdf_limit=args.pdf_limit,
        model=args.model,
        run_id=run_id,
        output_dir=output_dir,
        prompt_path=prompt_path,
        allow_web_search=args.gemini_allow_web_search,
        gemini_root=root,
        respect_git_ignore=args.gemini_respect_gitignore,
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
