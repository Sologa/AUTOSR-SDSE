#!/usr/bin/env python3
"""Compute title-only Precision/Recall/F1 between oracle and retrieved pools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Set

from title_normalization import normalize_title


def load_oracle_titles(path: Path) -> List[str]:
    titles: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            title = item.get("query_title") or item.get("title") or ""
            titles.append(title)
    return titles


def load_retrieved_titles(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    titles: List[str] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("normalized_title") or ""
            titles.append(title)
    elif isinstance(data, dict):
        # Best-effort: find a list of dicts with titles.
        for value in data.values():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        title = item.get("title") or item.get("normalized_title") or ""
                        titles.append(title)
    return titles


def normalize_set(titles: Iterable[str]) -> Set[str]:
    normalized = {normalize_title(title) for title in titles if title}
    return {title for title in normalized if title}


def compute_metrics(oracle: Set[str], retrieved: Set[str]) -> dict:
    tp = len(oracle & retrieved)
    precision = tp / len(retrieved) if retrieved else 0.0
    recall = tp / len(oracle) if oracle else 0.0
    f1 = 0.0
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "oracle_count": len(oracle),
        "retrieved_count": len(retrieved),
        "true_positive": tp,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "matched_titles": sorted(oracle & retrieved),
        "oracle_only_titles": sorted(oracle - retrieved),
        "retrieved_only_titles": sorted(retrieved - oracle),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle-jsonl", type=str, required=True)
    parser.add_argument("--retrieved-json", type=str, required=True)
    parser.add_argument("--out-report", type=str, default=None)
    args = parser.parse_args()

    oracle_titles = load_oracle_titles(Path(args.oracle_jsonl))
    retrieved_titles = load_retrieved_titles(Path(args.retrieved_json))

    oracle_set = normalize_set(oracle_titles)
    retrieved_set = normalize_set(retrieved_titles)

    report = compute_metrics(oracle_set, retrieved_set)

    if args.out_report:
        out_path = Path(args.out_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    else:
        print(json.dumps(report, ensure_ascii=True, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
