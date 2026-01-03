#!/usr/bin/env python
"""Parse LatteReview snowball screening results and extract included papers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, List


def load_results(path: Path) -> List[dict[str, Any]]:
    """Load LatteReview JSON results from a file path."""
    if not path.exists():
        raise FileNotFoundError(f"找不到輸入檔案：{path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("輸入 JSON 應為列表格式")
    return data


def filter_included(records: Iterable[dict[str, Any]]) -> List[dict[str, Any]]:
    """Filter records whose final_verdict indicates inclusion."""
    included: List[dict[str, Any]] = []
    for item in records:
        verdict = str(item.get("final_verdict", "")).strip()
        if "納入" in verdict:
            included.append(item)
    return included


def write_output(records: List[dict[str, Any]], path: Path) -> None:
    """Write filtered records to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the screening result parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="LatteReview 雪球審查 JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="輸出檔案路徑（預設為同目錄 + _included.json）",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for extracting included papers."""
    args = parse_args()
    records = load_results(args.input)
    included = filter_included(records)

    output_path = args.output
    if output_path is None:
        suffix = args.input.stem + "_included.json"
        output_path = args.input.with_name(suffix)

    write_output(included, output_path)
    print(f"原始紀錄：{len(records)} 筆，納入：{len(included)} 筆 -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
