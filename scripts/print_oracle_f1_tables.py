#!/usr/bin/env python3
"""Print per-round title-only F1 tables for fixed oracle datasets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Set

sys.path.insert(0, "target_papers/scripts")
from title_normalization import normalize_title  # noqa: E402


DEFAULT_TOPICS = [
    {
        "name": "Discrete Audio Tokens",
        "oracle": "target_papers/discrete_audio_tokens_more_than_a_survey/reference_oracle.jsonl",
        "rounds_dir": "workspaces/discrete_audio_tokens_more_than_a_survey/snowball_rounds",
    },
    {
        "name": "Spoken Language Models",
        "oracle": "target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/reference_oracle.jsonl",
        "rounds_dir": "workspaces/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/snowball_rounds",
    },
]


def load_oracle_titles(path: Path) -> Set[str]:
    titles: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            title = item.get("query_title") or item.get("title") or ""
            if title:
                titles.append(title)
    normalized = {normalize_title(t) for t in titles if t}
    return {t for t in normalized if t}


def load_retrieved_titles(path: Path) -> Set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    titles: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                title = item.get("title") or item.get("normalized_title") or ""
                if title:
                    titles.append(title)
    normalized = {normalize_title(t) for t in titles if t}
    return {t for t in normalized if t}


def compute_metrics(oracle: Set[str], retrieved: Set[str]) -> dict:
    tp = len(oracle & retrieved)
    precision = tp / len(retrieved) if retrieved else 0.0
    recall = tp / len(oracle) if oracle else 0.0
    f1 = 0.0
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    iou = compute_iou(oracle, retrieved)
    return {
        "oracle": len(oracle),
        "retrieved": len(retrieved),
        "tp": tp,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou": iou,
    }


def _format_metric(value: object) -> str:
    if value is None or value == "NA":
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def format_table(rows: List[dict]) -> List[str]:
    lines = [
        "| Round | Retrieved | TP | Precision | Recall | F1 | IoU | Note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {round} | {retrieved} | {tp} | {precision} | {recall} | {f1} | {iou} | {note} |".format(
                round=row["round"],
                retrieved=_format_metric(row["retrieved"]),
                tp=_format_metric(row["tp"]),
                precision=_format_metric(row.get("precision")),
                recall=_format_metric(row.get("recall")),
                f1=_format_metric(row.get("f1")),
                iou=_format_metric(row.get("iou")),
                note=row.get("note", ""),
            )
        )
    return lines


def collect_round_rows(oracle: Set[str], rounds_dir: Path) -> List[dict]:
    rows: List[dict] = []
    round_dirs = sorted(rounds_dir.glob("round_*"))
    if not round_dirs:
        rows.append(
            {
                "round": "NA",
                "retrieved": "NA",
                "tp": "NA",
                "precision": None,
                "recall": None,
                "f1": None,
                "iou": None,
                "note": "no round directories",
            }
        )
        return rows

    for round_dir in round_dirs:
        retrieved_path = round_dir / "final_included.json"
        if not retrieved_path.exists():
            rows.append(
                {
                    "round": round_dir.name,
                    "retrieved": "NA",
                    "tp": "NA",
                    "precision": None,
                    "recall": None,
                    "f1": None,
                    "iou": None,
                    "note": "missing final_included.json",
                }
            )
            continue

        retrieved = load_retrieved_titles(retrieved_path)
        metrics = compute_metrics(oracle, retrieved)
        rows.append(
            {
                "round": round_dir.name,
                "retrieved": metrics["retrieved"],
                "tp": metrics["tp"],
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "iou": metrics["iou"],
                "note": "",
            }
        )
    return rows


def compute_iou(oracle: Set[str], retrieved: Set[str]) -> float:
    union = oracle | retrieved
    if not union:
        return 0.0
    return len(oracle & retrieved) / len(union)


def render_topic(topic: dict) -> List[str]:
    oracle_path = Path(topic["oracle"])
    rounds_dir = Path(topic["rounds_dir"])
    if not oracle_path.exists():
        return [f"## {topic['name']}", f"Oracle not found: {oracle_path}"]
    if not rounds_dir.exists():
        return [f"## {topic['name']}", f"Rounds dir not found: {rounds_dir}"]

    oracle = load_oracle_titles(oracle_path)
    rows = collect_round_rows(oracle, rounds_dir)

    lines = [f"## {topic['name']}", ""]
    lines.extend(format_table(rows))
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=str, default=None, help="Optional output markdown path")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Optional output directory (writes snowball_title_f1_tables.md)",
    )
    args = parser.parse_args()

    if args.out and args.out_dir:
        raise SystemExit("Use only one of --out or --out-dir")

    sections: List[str] = [
        "# Snowball Title-only F1 Tables",
        "",
        "Note: exact match after title normalization (strip `{}`, TeX commands, punctuation, lowercase).",
        "",
    ]

    for topic in DEFAULT_TOPICS:
        sections.extend(render_topic(topic))
        sections.append("")

    output = "\n".join(sections).rstrip() + "\n"

    if args.out or args.out_dir:
        if args.out_dir:
            out_path = Path(args.out_dir) / "snowball_title_f1_tables.md"
        else:
            out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
