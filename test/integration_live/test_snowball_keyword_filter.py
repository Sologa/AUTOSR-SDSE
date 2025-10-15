from __future__ import annotations

import csv
import json
import re
from pathlib import Path


KEYWORD_JSON = Path(
    "test_artifacts/keyword_extractor_live/multi_20250929_114024.json"
)
SNOWBALL_CSV = Path(
    "test_artifacts/metadata_harvest/speech_language_models/snowball_for_review.csv"
)

csv.field_size_limit(1024 * 1024 * 5)


def _normalize_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _expand_keyword(keyword: str) -> set[str]:
    items: set[str] = set()
    base = _normalize_text(keyword)
    if not base:
        return items
    base_lower = base.lower()
    items.add(base_lower)

    parts = re.split(r"\\s+", base_lower)
    for part in parts:
        if part:
            items.add(part)

    compact = base_lower.replace(" ", "")
    if len(compact) >= 2 and len(parts) == 1:
        items.update(char for char in compact)

    return items


def _load_keywords() -> set[str]:
    assert KEYWORD_JSON.exists(), f"找不到關鍵字輸入檔：{KEYWORD_JSON}"
    payload = json.loads(KEYWORD_JSON.read_text(encoding="utf-8"))

    keywords: set[str] = set()

    for term in payload.get("anchor_terms", []) or []:
        keywords.update(_expand_keyword(str(term)))

    search_terms = payload.get("search_terms", {}) or {}
    for term_list in search_terms.values():
        for term in term_list or []:
            keywords.update(_expand_keyword(str(term)))

    return {kw for kw in keywords if kw}


def test_snowball_filter_against_keyword_list() -> None:
    assert SNOWBALL_CSV.exists(), f"找不到雪崩輸入檔：{SNOWBALL_CSV}"
    keywords = _load_keywords()
    assert keywords, "關鍵字集合不可為空"

    matched = []
    unmatched = []

    with SNOWBALL_CSV.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            title = _normalize_text(row.get("title"))
            abstract = _normalize_text(row.get("abstract"))
            combined = f"{title} {abstract}".lower()
            if not combined.strip():
                unmatched.append((row.get("openalex_id"), "缺少 title/abstract"))
                continue

            if any(keyword in combined for keyword in keywords):
                matched.append(row.get("openalex_id"))
            else:
                unmatched.append((row.get("openalex_id"), combined[:120]))

    assert matched, "未找到符合關鍵字的雪球候選"
    # 允許存在未命中的紀錄，但若全部透過後續審查時需要，可在這裡檢視
    print(f"[INFO] snowball_for_review.csv 關鍵字命中 {len(matched)} 筆 / 未命中 {len(unmatched)} 筆")
    if unmatched[:5]:
        print("[INFO] 未命中範例：")
        for sample in unmatched[:5]:
            print(f"  - {sample[0]} | {sample[1]}")
