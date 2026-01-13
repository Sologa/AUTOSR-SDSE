#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from review_cli_utils import (
    build_review_prompt,
    build_run_id,
    init_manifest,
    load_arxiv_items,
    load_criteria,
    load_env,
    prepare_gemini_settings,
    repo_root,
    restore_gemini_settings,
    run_gemini_cli,
    update_manifest,
    write_json,
)


def run_single_gemini(
    *,
    metadata_path: Path,
    criteria_path: Path,
    limit: int,
    model: str,
    reviewer: str,
    run_id: str,
    output_dir: Path,
    allow_web_search: bool,
    gemini_root: Optional[Path],
) -> Path:
    """Run a single-reviewer Gemini flow with repo-local tool policy and write outputs."""
    items, warnings = load_arxiv_items(metadata_path, limit)
    inclusion, exclusion, criteria_source, used_criteria_path = load_criteria(criteria_path)

    results: List[Dict[str, Any]] = []
    errors: List[str] = list(warnings)
    model_used = model
    settings_state = prepare_gemini_settings(root=gemini_root, allow_web_search=allow_web_search)

    try:
        for item in items:
            item_text = f"Review Task ID: S-{item['index']}\n" + (
                f"=== title ===\n{item['title']}\n\n=== abstract ===\n{item['abstract']}"
            )
            prompt = build_review_prompt(item_text, inclusion, exclusion)
            parsed, raw, err, detected_model = run_gemini_cli(prompt, model)
            item_error = None
            if detected_model:
                model_used = detected_model
            if err:
                item_error = err
                errors.append(f"{item.get('arxiv_id') or item['index']}: {err}")
                evaluation = None
                reasoning = ""
            else:
                evaluation = parsed.get("evaluation") if isinstance(parsed, dict) else None
                if isinstance(evaluation, str) and evaluation.strip().isdigit():
                    evaluation = int(evaluation.strip())
                reasoning = parsed.get("reasoning") if isinstance(parsed, dict) else ""
            results.append(
                {
                    "index": item["index"],
                    "arxiv_id": item["arxiv_id"],
                    "title": item["title"],
                    "abstract": item["abstract"],
                    "missing_fields": item["missing_fields"],
                    "reviewer": reviewer,
                    "evaluation": evaluation,
                    "reasoning": reasoning,
                    "raw_output": raw,
                    "error": item_error,
                }
            )
    finally:
        restore_gemini_settings(settings_state)

    output_payload = {
        "run_id": run_id,
        "mode": "single",
        "provider": "gemini",
        "reviewer": reviewer,
        "models": {reviewer: model_used},
        "criteria_source": criteria_source,
        "criteria": {"inclusion": inclusion, "exclusion": exclusion},
        "items": results,
        "errors": errors,
    }

    output_path = output_dir / "gemini_single.json"
    write_json(output_path, output_payload)

    manifest = init_manifest(
        output_dir,
        run_id,
        metadata_path,
        criteria_source,
        used_criteria_path,
    )
    update_manifest(
        output_dir,
        manifest,
        name="gemini_single",
        path=output_path,
        mode="single",
        provider="gemini",
        reviewer=reviewer,
        model=model_used,
        command=["gemini", "--output-format", "json", "--model", model],
        command_meta=settings_state["policy"],
    )

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gemini CLI single reviewer test")
    parser.add_argument(
        "--metadata-path",
        type=Path,
        default=None,
        help="Path to arxiv_metadata.json",
    )
    parser.add_argument(
        "--criteria-path",
        type=Path,
        default=None,
        help="Path to criteria.json (optional)",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--model", default="gemini-2.5-pro")
    parser.add_argument("--reviewer", default="JuniorMini")
    parser.add_argument(
        "--gemini-allow-web-search",
        action="store_true",
        help="Allow Gemini web search tool for this run (disabled by default).",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    load_env()
    root = repo_root()
    metadata_path = args.metadata_path or root / "workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json"
    criteria_path = args.criteria_path or root / "workspaces/discrete_audio_tokens_more_than_a_survey/criteria/criteria.json"
    run_id = args.run_id or build_run_id()
    output_dir = args.output_dir or root / "docs/codex/test-review/outputs" / run_id
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    run_single_gemini(
        metadata_path=metadata_path,
        criteria_path=criteria_path,
        limit=args.limit,
        model=args.model,
        reviewer=args.reviewer,
        run_id=run_id,
        output_dir=output_dir,
        allow_web_search=args.gemini_allow_web_search,
        gemini_root=root,
    )
    print(str(output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
