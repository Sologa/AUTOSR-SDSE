"""統計符合特定條件的論文數量。

本腳本會進行兩項統計：
1. 讀取 `screening_included.csv`，計算所有年份為 2023（含）之後且摘要
   中包含 "speech" 或 "spoken"（大小寫不拘）的論文。
2. 讀取 `latte_review_results_step5_full.json`，計算最終判定為「納入」，且
   `published` 年份晚於 2022 年的論文。

執行方式：
    python test/integration_live/test_screening_paper_count.py
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

CSV_RELATIVE_PATH = Path(
    "test_artifacts/metadata_harvest/speech_language_models/screening_included.csv"
)
JSON_RELATIVE_PATH = Path(
    "test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json"
)


def locate_repo_root(start: Path) -> Path:
    """Find the repository root by searching for known top-level folders upwards."""
    base = start if start.is_dir() else start.parent
    for candidate in [base] + list(base.parents):
        marker = candidate / "test_artifacts"
        if marker.exists() and marker.is_dir():
            return candidate
    # Fallback to the immediate base directory when the marker is missing.
    return base


def load_rows(csv_path: Path) -> Iterable[Dict[str, str]]:
    """Yield CSV rows as dictionaries using UTF-8 decoding."""
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def year_is_after_2022(year_str: str | None) -> bool:
    """Return True if the year string represents a year strictly greater than 2022."""
    if not year_str:
        return False
    try:
        return int(year_str) > 2022
    except ValueError:
        return False


def abstract_mentions_keywords(abstract: str | None) -> bool:
    """Check whether the abstract contains "speech" or "spoken" (case-insensitive)."""
    if not abstract:
        return False
    lowered = abstract.lower()
    return "speech" in lowered or "spoken" in lowered


def collect_matches(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    """Filter rows that satisfy both the year and abstract keyword conditions."""
    matches: List[Dict[str, str]] = []
    for row in rows:
        if year_is_after_2022(row.get("year")) and abstract_mentions_keywords(
            row.get("abstract")
        ):
            matches.append(row)
    return matches


def parse_year(published: str | None) -> int | None:
    """Parse an ISO 8601 timestamp (or year prefix) into an integer year."""
    if not published:
        return None
    cleaned = published.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).year
    except ValueError:
        try:
            return int(cleaned[:4])
        except ValueError:
            return None


def collect_json_matches(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Select entries with verdict ""納入"" and published year after 2022."""
    matches: List[Dict[str, object]] = []
    for entry in entries:
        final_verdict = str(entry.get("final_verdict", ""))
        if "納入" not in final_verdict:
            continue
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            continue
        year = parse_year(str(metadata.get("published", "")))
        if year and year > 2022:
            matches.append(entry)
    return matches


def main() -> None:
    """Load the CSV and print the count of matching papers along with sample IDs."""
    repo_root = locate_repo_root(Path(__file__).resolve())
    csv_path = repo_root / CSV_RELATIVE_PATH
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到指定的 CSV 檔案：{csv_path}")

    matches = collect_matches(load_rows(csv_path))
    total = len(matches)

    print(f"符合條件的論文數量: {total}")
    if total:
        sample = matches[:5]
        print("前 5 筆紀錄資訊（若有）:")
        for row in sample:
            identifier = row.get("doi") or row.get("landing_url") or "N/A"
            year = row.get("year", "?")
            title = row.get("title", "(無標題)")
            print(f"- {year} | {identifier} | {title}")

    json_path = repo_root / JSON_RELATIVE_PATH
    if not json_path.exists():
        raise FileNotFoundError(f"找不到指定的 JSON 檔案：{json_path}")

    with json_path.open("r", encoding="utf-8") as handle:
        json_entries = json.load(handle)
    json_matches = collect_json_matches(json_entries)
    json_total = len(json_matches)

    print(f"\nJSON 入選且出版年份晚於 2022 的論文數量: {json_total}")
    if json_total:
        sample = json_matches[:5]
        print("前 5 筆紀錄資訊（若有）:")
        for entry in sample:
            metadata = entry.get("metadata", {})
            title = entry.get("title", "(無標題)")
            published = metadata.get("published", "?") if isinstance(metadata, dict) else "?"
            landing = metadata.get("landing_url") if isinstance(metadata, dict) else None
            print(f"- {published} | {landing or '(無連結)'} | {title}")


if __name__ == "__main__":
    main()
