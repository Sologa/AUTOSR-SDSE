#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from review_cli_utils import (
    build_review_prompt,
    build_run_id,
    DEFAULT_CODEX_DISABLE_FLAGS,
    init_manifest,
    load_arxiv_items,
    load_criteria,
    load_env,
    repo_root,
    resolve_codex_bin,
    run_codex_exec,
    update_manifest,
    write_json,
)

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


def run_single_codex(
    *,
    metadata_path: Path,
    criteria_path: Path,
    limit: int,
    model: str,
    reviewer: str,
    run_id: str,
    output_dir: Path,
    schema_path: Path,
    codex_bin: str,
    codex_extra_args: Optional[List[str]] = None,
    allow_web_search: bool = False,
) -> Path:
    """Run a single-reviewer Codex flow and write outputs plus manifest entries."""
    items, warnings = load_arxiv_items(metadata_path, limit)
    inclusion, exclusion, criteria_source, used_criteria_path = load_criteria(criteria_path)

    results: List[Dict[str, Any]] = []
    errors: List[str] = list(warnings)

    for item in items:
        item_text = f"Review Task ID: S-{item['index']}\n" + (
            f"=== title ===\n{item['title']}\n\n=== abstract ===\n{item['abstract']}"
        )
        prompt = build_review_prompt(item_text, inclusion, exclusion)
        parsed, raw, err = run_codex_exec(
            prompt,
            model,
            schema_path,
            codex_bin=codex_bin,
            codex_extra_args=_resolve_extra_args(codex_extra_args, allow_web_search),
        )
        item_error = None
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

    output_payload = {
        "run_id": run_id,
        "mode": "single",
        "provider": "codex",
        "reviewer": reviewer,
        "models": {reviewer: model},
        "criteria_source": criteria_source,
        "criteria": {"inclusion": inclusion, "exclusion": exclusion},
        "items": results,
        "errors": errors,
    }

    output_path = output_dir / "codex_single.json"
    write_json(output_path, output_payload)

    manifest = init_manifest(
        output_dir,
        run_id,
        metadata_path,
        criteria_source,
        used_criteria_path,
    )
    combined_extra_args = _resolve_extra_args(codex_extra_args, allow_web_search)
    update_manifest(
        output_dir,
        manifest,
        name="codex_single",
        path=output_path,
        mode="single",
        provider="codex",
        reviewer=reviewer,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Codex CLI single reviewer test")
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
    parser.add_argument("--model", default="gpt-5.1-codex-mini")
    parser.add_argument("--reviewer", default="JuniorNano")
    parser.add_argument("--codex-bin", default=None, help="Path to OpenAI Codex CLI binary")
    parser.add_argument(
        "--codex-extra-arg",
        action="append",
        help="Additional CLI flag passed to `codex exec` before the prompt (e.g., --full-auto).",
    )
    parser.add_argument(
        "--allow-web-search",
        action="store_true",
        help="Allow Codex to emit web search tool calls for this run (disabled by default).",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=Path("docs/codex/test-review/review_response.schema.json"),
    )
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
    schema_path = args.schema_path
    if not schema_path.is_absolute():
        schema_path = root / schema_path
    codex_bin = resolve_codex_bin(args.codex_bin)

    run_single_codex(
        metadata_path=metadata_path,
        criteria_path=criteria_path,
        limit=args.limit,
        model=args.model,
        reviewer=args.reviewer,
        run_id=run_id,
        output_dir=output_dir,
        schema_path=schema_path,
        codex_bin=codex_bin,
        codex_extra_args=args.codex_extra_arg,
        allow_web_search=args.allow_web_search,
    )
    print(str(output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
