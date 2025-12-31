#!/usr/bin/env python
"""Iterative snowballing with round isolation and registry dedup."""
from __future__ import annotations

# ruff: noqa: E402

import argparse
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.pipelines.topic_pipeline import (
    resolve_workspace,
    run_latte_review,
    run_snowball_asreview,
)

FINAL_INCLUDED_COLUMNS = [
    "status",
    "title",
    "normalized_title",
    "doi",
    "openalex_id",
    "arxiv_id",
    "criteria_hash",
    "source",
    "updated_at",
    "round",
]


def _load_registry_module(repo_root: Path):
    script_path = repo_root / "scripts" / "update_snowball_registry.py"
    spec = importlib.util.spec_from_file_location("update_snowball_registry", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 registry 腳本：{script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _count_csv_rows(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    df = pd.read_csv(path)
    return 0 if df.empty else len(df)


def _count_review_outcome(path: Path) -> Dict[str, int]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return {}
    counts: Dict[str, int] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        verdict = str(item.get("final_verdict") or "").strip().lower()
        if verdict.startswith("include"):
            key = "include"
        elif verdict.startswith("exclude"):
            key = "exclude"
        elif verdict.startswith("needs-review"):
            key = "needs_enrichment"
        elif verdict.startswith("discard"):
            key = "hard_exclude"
        else:
            key = "other"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _count_registry_includes(registry_path: Path) -> int:
    if not registry_path.exists():
        return 0
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return 0
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return 0
    return sum(1 for entry in entries if isinstance(entry, dict) and entry.get("status") == "include")


def _load_dedup_report(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_round_meta(round_dir: Path, meta: Dict[str, Any]) -> None:
    meta_path = round_dir / "round_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_final_included_outputs(registry_path: Path, output_dir: Optional[Path] = None) -> Dict[str, object]:
    if not registry_path.exists():
        return {"written": False, "count": 0}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {"written": False, "count": 0}
    included = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") == "include"]
    output_dir = output_dir or registry_path.parent
    json_path = output_dir / "final_included.json"
    csv_path = output_dir / "final_included.csv"
    json_path.write_text(json.dumps(included, ensure_ascii=False, indent=2), encoding="utf-8")
    df = pd.DataFrame(included)
    df = df.reindex(columns=FINAL_INCLUDED_COLUMNS)
    df.to_csv(csv_path, index=False)
    return {
        "written": True,
        "count": len(included),
        "json_path": str(json_path),
        "csv_path": str(csv_path),
    }


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path("workspaces"))
    parser.add_argument("--mode", choices=["loop", "while"], required=True)
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--start-round", type=int, default=1)
    parser.add_argument("--stop-raw-threshold", type=int, default=None)
    parser.add_argument("--stop-included-threshold", type=int, default=None)
    parser.add_argument("--min-date", default=None)
    parser.add_argument("--max-date", default=None)
    parser.add_argument("--email", default=None)
    parser.add_argument("--keep-label", action="append", default=["include"])
    parser.add_argument("--skip-forward", action="store_true")
    parser.add_argument("--skip-backward", action="store_true")
    parser.add_argument("--review-top-k", type=int, default=None)
    parser.add_argument("--skip-titles-containing", default="survey")
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument(
        "--retain-registry",
        action="store_true",
        help="保留既有 registry（預設會清空並以 base review 重建）",
    )
    parser.add_argument("--bootstrap-review", type=Path, default=None)
    parser.add_argument("--force", action="store_true", help="覆寫既有 round 目錄")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    if args.mode == "while":
        if args.stop_raw_threshold is None or args.stop_included_threshold is None:
            raise ValueError("while 模式需提供 --stop-raw-threshold 與 --stop-included-threshold")

    registry_module = _load_registry_module(REPO_ROOT)
    compute_criteria_hash = getattr(registry_module, "compute_criteria_hash")
    update_registry = getattr(registry_module, "update_registry")
    load_registry = getattr(registry_module, "load_registry")

    ws = resolve_workspace(topic=args.topic, workspace_root=args.workspace_root)
    registry_path = args.registry or ws.snowball_registry_path
    criteria_path = ws.criteria_path if ws.criteria_path.exists() else None
    criteria_hash = compute_criteria_hash(criteria_path)

    if registry_path.exists() and not args.retain_registry:
        registry_path.unlink()

    if registry_path.exists():
        payload = load_registry(registry_path)
        if criteria_hash and payload.get("criteria_hash") != criteria_hash:
            payload["criteria_hash"] = criteria_hash
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            registry_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    else:
        base_review = args.bootstrap_review or ws.review_results_path
        if not base_review.exists():
            raise FileNotFoundError(f"找不到基準 review 結果：{base_review}")
        update_registry(
            base_review,
            registry_path,
            criteria_hash=criteria_hash,
            round_index=0,
            source="base_review",
        )

    max_rounds = max(1, args.max_rounds)
    start_round = max(1, args.start_round)

    for offset in range(max_rounds):
        round_index = start_round + offset
        round_dir = ws.snowball_round_dir(round_index)
        if round_dir.exists():
            if not args.force:
                raise RuntimeError(f"round 目錄已存在，為避免混寫請指定 --force：{round_dir}")
            shutil.rmtree(round_dir)
        round_dir.mkdir(parents=True, exist_ok=True)

        seed_review = (
            ws.review_results_path
            if round_index == 1
            else ws.snowball_round_dir(round_index - 1) / "latte_review_results.json"
        )
        if not seed_review.exists():
            raise FileNotFoundError(f"找不到上一輪 review 結果：{seed_review}")
        seed_metadata = (
            ws.arxiv_metadata_path
            if round_index == 1
            else ws.snowball_round_dir(round_index - 1) / "candidates_for_review.json"
        )
        seed_outcome = _count_review_outcome(seed_review)
        if seed_outcome.get("include", 0) == 0:
            print(f"[INFO] 上一輪 include 為 0，停止於 round_{round_index - 1:02d}")
            break

        run_snowball_asreview(
            ws,
            review_results_path=seed_review,
            metadata_path=seed_metadata,
            output_dir=round_dir,
            round_index=round_index,
            registry_path=registry_path,
            email=args.email,
            keep_label=args.keep_label,
            min_date=args.min_date,
            max_date=args.max_date,
            skip_forward=args.skip_forward,
            skip_backward=args.skip_backward,
        )

        candidates_json = round_dir / "candidates_for_review.json"
        review_output = round_dir / "latte_review_results.json"
        review_ran = False
        if candidates_json.exists():
            candidates_payload = json.loads(candidates_json.read_text(encoding="utf-8"))
            if isinstance(candidates_payload, list) and candidates_payload:
                try:
                    run_latte_review(
                        ws,
                        arxiv_metadata_path=candidates_json,
                        criteria_path=criteria_path,
                        output_path=review_output,
                        top_k=args.review_top_k,
                        skip_titles_containing=args.skip_titles_containing,
                    )
                    review_ran = True
                except RuntimeError as exc:
                    if "找不到任何可供 LatteReview 審查或標記的條目" in str(exc):
                        print("[WARN] 無可審查條目，跳過本輪 review")
                        review_output.write_text("[]", encoding="utf-8")
                        review_ran = False
                    else:
                        raise
            else:
                review_output.write_text("[]", encoding="utf-8")
        else:
            review_output.write_text("[]", encoding="utf-8")

        update_registry(
            review_output,
            registry_path,
            criteria_hash=criteria_hash,
            round_index=round_index,
            source="snowball_review",
        )

        seed_count = _count_csv_rows(round_dir / "screening_included.csv")
        raw_count = _count_csv_rows(round_dir / "snowball_results_raw.csv")
        filtered_count = _count_csv_rows(round_dir / "snowball_results.csv")
        for_review_count = _count_csv_rows(round_dir / "snowball_for_review.csv")
        dedup_report = _load_dedup_report(round_dir / "dedup_report.json")
        dedup_removed = dedup_report.get("removed_total")
        if dedup_removed is None:
            dedup_removed = max(0, filtered_count - for_review_count)
        review_outcome = _count_review_outcome(review_output)
        included_total = _count_registry_includes(registry_path)

        round_meta = {
            "round": round_index,
            "seed_review": str(seed_review),
            "seed_count": seed_count,
            "raw_count": raw_count,
            "filtered_count": filtered_count,
            "dedup_removed": dedup_removed,
            "dedup_removed_by": dedup_report.get("removed_by") if dedup_report else None,
            "for_review_count": for_review_count,
            "review_ran": review_ran,
            "review_outcome": review_outcome,
            "included_total": included_total,
            "criteria_hash": criteria_hash or None,
        }
        _write_round_meta(round_dir, round_meta)

        if args.mode == "while":
            if raw_count >= args.stop_raw_threshold or included_total >= args.stop_included_threshold:
                break

        _write_final_included_outputs(registry_path, output_dir=round_dir)

    _write_final_included_outputs(registry_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
