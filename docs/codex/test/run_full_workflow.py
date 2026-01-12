#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shlex
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
    prepare_gemini_settings,
    repo_root,
    resolve_codex_bin,
    restore_gemini_settings,
    run_codex_exec,
    run_gemini_cli,
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


def _should_run_senior(score1: Optional[int], score2: Optional[int]) -> bool:
    """Return True when the senior reviewer should be invoked."""
    if score1 is None or score2 is None:
        return False
    if score1 != score2:
        if score1 >= 4 and score2 >= 4:
            return False
        if score1 >= 3 or score2 >= 3:
            return True
    elif score1 == score2 == 3:
        return True
    return False


def _coerce_score(value: Any) -> Optional[int]:
    """Normalize evaluation values to integers when possible."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _derive_verdict(senior_eval: Optional[int], junior_scores: List[int]) -> str:
    """Derive the final verdict from senior or averaged junior scores."""
    score = None
    source = "junior"
    if senior_eval is not None:
        score = senior_eval
        source = "senior"
    if score is None:
        if not junior_scores:
            return "需再評估 (no_score)"
        score = int(round(sum(junior_scores) / len(junior_scores)))
    if score >= 4:
        return f"include ({source}:{score})"
    if score <= 2:
        return f"exclude ({source}:{score})"
    return f"maybe ({source}:{score})"


def _build_round_text(round_id: str, index: int, fields: List[tuple[str, str]]) -> str:
    """Format a review round input block for the prompt."""
    parts = []
    for key, value in fields:
        parts.append(f"=== {key} ===\n{value}")
    return f"Review Task ID: {round_id}-{index}\n" + "\n\n".join(parts)


def run_full_workflow(
    *,
    metadata_path: Path,
    criteria_path: Path,
    limit: int,
    junior_nano_model: str,
    junior_mini_model: str,
    senior_model: str,
    run_id: str,
    output_dir: Path,
    schema_path: Path,
    codex_bin: str,
    codex_extra_args: Optional[List[str]] = None,
    allow_web_search: bool = False,
    gemini_allow_web_search: bool = False,
    gemini_root: Optional[Path] = None,
) -> Path:
    """Run the full workflow with repo-local Gemini tool policy applied."""
    resolved_codex_extra_args = _resolve_extra_args(codex_extra_args, allow_web_search)
    items, warnings = load_arxiv_items(metadata_path, limit)
    inclusion, exclusion, criteria_source, used_criteria_path = load_criteria(criteria_path)

    results: List[Dict[str, Any]] = []
    errors: List[str] = list(warnings)
    settings_state = prepare_gemini_settings(root=gemini_root, allow_web_search=gemini_allow_web_search)

    try:
        for item in items:
            round_a_text = _build_round_text(
                "A",
                item["index"],
                [
                    ("title", item["title"]),
                    ("abstract", item["abstract"]),
                ],
            )
            prompt_a = build_review_prompt(round_a_text, inclusion, exclusion)

            nano_parsed, nano_raw, nano_err = run_codex_exec(
                prompt_a,
                junior_nano_model,
                schema_path,
                codex_bin=codex_bin,
                codex_extra_args=resolved_codex_extra_args,
            )
            nano_eval = None
            nano_reason = ""
            nano_error = None
            if nano_err:
                nano_error = nano_err
                errors.append(f"JuniorNano {item.get('arxiv_id') or item['index']}: {nano_err}")
            elif isinstance(nano_parsed, dict):
                nano_eval = _coerce_score(nano_parsed.get("evaluation"))
                nano_reason = nano_parsed.get("reasoning") or ""

            mini_parsed, mini_raw, mini_err, mini_model_used = run_gemini_cli(prompt_a, junior_mini_model)
            mini_eval = None
            mini_reason = ""
            mini_error = None
            if mini_err:
                mini_error = mini_err
                errors.append(f"JuniorMini {item.get('arxiv_id') or item['index']}: {mini_err}")
            elif isinstance(mini_parsed, dict):
                mini_eval = _coerce_score(mini_parsed.get("evaluation"))
                mini_reason = mini_parsed.get("reasoning") or ""

            senior_eval = None
            senior_reason = ""
            senior_error = None
            senior_raw = ""

            nano_score = _coerce_score(nano_eval)
            mini_score = _coerce_score(mini_eval)
            if _should_run_senior(nano_score, mini_score):
                round_b_text = _build_round_text(
                    "B",
                    item["index"],
                    [
                        ("title", item["title"]),
                        ("abstract", item["abstract"]),
                        ("round-A_JuniorNano_output", json.dumps(nano_parsed, ensure_ascii=False)),
                        ("round-A_JuniorNano_evaluation", str(nano_eval)),
                        ("round-A_JuniorMini_output", json.dumps(mini_parsed, ensure_ascii=False)),
                        ("round-A_JuniorMini_evaluation", str(mini_eval)),
                    ],
                )
                prompt_b = build_review_prompt(round_b_text, inclusion, exclusion)
                senior_parsed, senior_raw, senior_err = run_codex_exec(
                    prompt_b,
                    senior_model,
                    schema_path,
                    codex_bin=codex_bin,
                    codex_extra_args=resolved_codex_extra_args,
                )
                if senior_err:
                    senior_error = senior_err
                    errors.append(f"SeniorLead {item.get('arxiv_id') or item['index']}: {senior_err}")
                elif isinstance(senior_parsed, dict):
                    senior_eval = _coerce_score(senior_parsed.get("evaluation"))
                    senior_reason = senior_parsed.get("reasoning") or ""
            else:
                senior_parsed = None

            junior_scores: List[int] = []
            for score in (nano_score, mini_score):
                if isinstance(score, int):
                    junior_scores.append(score)
            verdict = _derive_verdict(
                _coerce_score(senior_eval),
                junior_scores,
            )
            discard_reason = None
            if verdict.startswith("exclude"):
                discard_reason = verdict
            elif verdict.startswith("maybe"):
                discard_reason = "review_needs_followup"

            results.append(
                {
                    "index": item["index"],
                    "arxiv_id": item["arxiv_id"],
                    "title": item["title"],
                    "abstract": item["abstract"],
                    "missing_fields": item["missing_fields"],
                    "rounds": {
                        "A": {
                            "JuniorNano": {
                                "evaluation": nano_eval,
                                "reasoning": nano_reason,
                                "raw_output": nano_raw,
                                "error": nano_error,
                            },
                            "JuniorMini": {
                                "evaluation": mini_eval,
                                "reasoning": mini_reason,
                                "raw_output": mini_raw,
                                "error": mini_error,
                                "model_used": mini_model_used,
                            },
                        },
                        "B": {
                            "SeniorLead": {
                                "evaluation": senior_eval,
                                "reasoning": senior_reason,
                                "raw_output": senior_raw,
                                "error": senior_error,
                            }
                        }
                        if senior_raw or senior_error or senior_eval is not None
                        else {},
                    },
                    "final_verdict": verdict,
                    "discard_reason": discard_reason,
                    "review_skipped": False,
                }
            )
    finally:
        restore_gemini_settings(settings_state)

    output_payload = {
        "run_id": run_id,
        "mode": "full",
        "provider": "mixed",
        "models": {
            "JuniorNano": junior_nano_model,
            "JuniorMini": junior_mini_model,
            "SeniorLead": senior_model,
        },
        "criteria_source": criteria_source,
        "criteria": {"inclusion": inclusion, "exclusion": exclusion},
        "items": results,
        "errors": errors,
    }

    output_path = output_dir / "full_workflow.json"
    write_json(output_path, output_payload)

    manifest = init_manifest(
        output_dir,
        run_id,
        metadata_path,
        criteria_source,
        used_criteria_path,
    )
    outputs = manifest.setdefault("outputs", [])
    outputs.append(
        {
            "name": "full_workflow",
            "path": str(output_path),
            "mode": "full",
            "provider": "mixed",
            "reviewer": None,
            "model": None,
        }
    )
    def _format_codex_command(model_name: str) -> str:
        parts = [codex_bin, "exec"]
        if resolved_codex_extra_args:
            parts.extend(resolved_codex_extra_args)
        parts.extend(["-", "--model", model_name, "--output-schema", str(schema_path)])
        return shlex.join(parts)

    commands = manifest.setdefault("commands", [])
    commands.append(
        {
            "provider": "codex",
            "command": _format_codex_command(junior_nano_model),
            "model": junior_nano_model,
        }
    )
    commands.append(
        {
            "provider": "gemini",
            "command": f"gemini --output-format json --model {junior_mini_model}",
            "model": junior_mini_model,
            "tool_policy": settings_state["policy"],
        }
    )
    commands.append(
        {
            "provider": "codex",
            "command": _format_codex_command(senior_model),
            "model": senior_model,
        }
    )
    write_json(output_dir / "run_manifest.json", manifest)

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full workflow with Codex + Gemini reviewers")
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
    parser.add_argument("--junior-nano-model", default="gpt-5.1-codex-mini")
    parser.add_argument("--junior-mini-model", default="gemini-2.5-pro")
    parser.add_argument("--senior-model", default="gpt-5.2")
    parser.add_argument("--codex-bin", default=None, help="Path to OpenAI Codex CLI binary")
    parser.add_argument(
        "--codex-extra-arg",
        action="append",
        help="Additional CLI flag passed to `codex exec` before the prompt (e.g., --full-auto).",
    )
    parser.add_argument(
        "--allow-web-search",
        action="store_true",
        help="Allow Codex web search tool for this workflow (disabled by default).",
    )
    parser.add_argument(
        "--gemini-allow-web-search",
        action="store_true",
        help="Allow Gemini web search tool for this workflow (disabled by default).",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--schema-path",
        type=Path,
        default=Path("docs/codex/test/review_response.schema.json"),
    )
    args = parser.parse_args()

    load_env()
    root = repo_root()
    metadata_path = args.metadata_path or root / "workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json"
    criteria_path = args.criteria_path or root / "workspaces/discrete_audio_tokens_more_than_a_survey/criteria/criteria.json"
    run_id = args.run_id or build_run_id()
    output_dir = args.output_dir or root / "docs/codex/test/outputs" / run_id
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    schema_path = args.schema_path
    if not schema_path.is_absolute():
        schema_path = root / schema_path
    codex_bin = resolve_codex_bin(args.codex_bin)

    run_full_workflow(
        metadata_path=metadata_path,
        criteria_path=criteria_path,
        limit=args.limit,
        junior_nano_model=args.junior_nano_model,
        junior_mini_model=args.junior_mini_model,
        senior_model=args.senior_model,
        run_id=run_id,
        output_dir=output_dir,
        schema_path=schema_path,
        codex_bin=codex_bin,
        codex_extra_args=args.codex_extra_arg,
        allow_web_search=args.allow_web_search,
        gemini_allow_web_search=args.gemini_allow_web_search,
        gemini_root=root,
    )
    print(str(output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
