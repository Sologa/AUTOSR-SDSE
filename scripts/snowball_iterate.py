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
    _normalize_title_for_match,
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
    "published_date",
    "criteria_hash",
    "source",
    "updated_at",
    "round",
]


def _load_registry_module(repo_root: Path):
    """Load the registry update script as an importable module."""
    script_path = repo_root / "scripts" / "update_snowball_registry.py"
    spec = importlib.util.spec_from_file_location("update_snowball_registry", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"無法載入 registry 腳本：{script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _count_csv_rows(path: Path) -> int:
    """Return row count for a CSV file, treating missing/empty as zero."""
    if not path.exists() or path.stat().st_size == 0:
        return 0
    df = pd.read_csv(path)
    return 0 if df.empty else len(df)


def _count_review_outcome(path: Path) -> Dict[str, int]:
    """Aggregate final_verdict labels from a LatteReview JSON list."""
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
    """Count entries marked include in the snowball registry."""
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
    """Load a dedup report JSON file if present."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_round_meta(round_dir: Path, meta: Dict[str, Any]) -> None:
    """Write round_meta.json into the round directory."""
    meta_path = round_dir / "round_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_iso_date(value: str) -> Optional[datetime]:
    """Parse an ISO date string (YYYY-MM-DD or ISO datetime)."""
    if not value:
        return None
    text = value.strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_cutoff_payload(ws) -> Optional[Dict[str, Any]]:
    """Load cutoff.json if present."""
    cutoff_path = ws.cutoff_path
    if not cutoff_path.exists():
        return None
    payload = json.loads(cutoff_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _validate_final_included(
    ws,
    included: List[Dict[str, Any]],
    *,
    output_dir: Path,
) -> None:
    """Assert final_included respects cutoff title/date constraints."""
    cutoff = _load_cutoff_payload(ws)
    if not cutoff:
        return
    cutoff_value = cutoff.get("cutoff_date")
    if not isinstance(cutoff_value, str) or not cutoff_value.strip():
        raise RuntimeError("cutoff.json missing cutoff_date; cannot validate final_included")
    cutoff_dt = _parse_iso_date(cutoff_value)
    if cutoff_dt is None:
        raise RuntimeError(f"cutoff.json contains invalid cutoff_date: {cutoff_value}")

    topic_norm = _normalize_title_for_match(ws.topic)
    topic_slug = "".join(topic_norm.split())

    violations: List[Dict[str, Any]] = []
    for entry in included:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "")
        normalized_title = str(entry.get("normalized_title") or "")
        if title and _normalize_title_for_match(title) == topic_norm:
            violations.append({"type": "same_title", "title": title})
        elif normalized_title and normalized_title == topic_slug:
            violations.append({"type": "same_title", "title": normalized_title})

        published_raw = entry.get("published_date")
        if published_raw is None or (isinstance(published_raw, str) and not published_raw.strip()):
            violations.append(
                {"type": "missing_published_date", "title": title or normalized_title}
            )
            continue
        if isinstance(published_raw, str):
            published_dt = _parse_iso_date(published_raw)
        else:
            published_dt = None
        if published_dt is None:
            violations.append(
                {"type": "invalid_published_date", "title": title or normalized_title}
            )
            continue
        if published_dt.date() >= cutoff_dt.date():
            violations.append(
                {
                    "type": "published_on_or_after_cutoff",
                    "title": title or normalized_title,
                    "published_date": published_raw,
                    "cutoff_date": cutoff_value,
                }
            )

    if violations:
        report_path = output_dir / "cutoff_violations.json"
        report_path.write_text(
            json.dumps({"violations": violations}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise RuntimeError(
            f"final_included violates cutoff policy; see {report_path}"
        )


def _write_final_included_outputs(
    registry_path: Path,
    *,
    workspace,
    output_dir: Optional[Path] = None,
) -> Dict[str, object]:
    """Write final_included JSON/CSV from the registry include entries."""
    if not registry_path.exists():
        return {"written": False, "count": 0}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return {"written": False, "count": 0}
    included = [entry for entry in entries if isinstance(entry, dict) and entry.get("status") == "include"]
    output_dir = output_dir or registry_path.parent
    _validate_final_included(workspace, included, output_dir=output_dir)
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
    """Parse CLI arguments for the iterative snowball runner."""
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
    """Execute iterative snowballing and return an exit code."""
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

        _write_final_included_outputs(registry_path, workspace=ws, output_dir=round_dir)

    _write_final_included_outputs(registry_path, workspace=ws)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
