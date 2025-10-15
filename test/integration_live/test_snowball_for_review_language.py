from __future__ import annotations

import csv
import re
from pathlib import Path

try:  # pragma: no cover - optional dependency
    from langdetect import detect
except ImportError:  # pragma: no cover - fallback when langdetect is unavailable
    detect = None


SNOWBALL_CSV = Path(
    "test_artifacts/metadata_harvest/speech_language_models/snowball_for_review.csv"
)

csv.field_size_limit(1024 * 1024 * 5)


def _normalize_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


EN_STOPWORDS = {
    "the",
    "be",
    "to",
    "of",
    "and",
    "a",
    "in",
    "that",
    "have",
    "it",
    "for",
    "not",
    "on",
    "with",
    "as",
    "you",
    "do",
    "at",
    "this",
    "but",
    "his",
    "by",
    "from",
    "they",
    "we",
    "say",
    "her",
    "she",
    "or",
    "an",
    "will",
    "my",
    "one",
    "all",
    "would",
    "there",
    "their",
}


def _english_stopword_ratio(text: str) -> float:
    tokens = re.findall(r"[a-z]+", text.lower())
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in EN_STOPWORDS)
    return hits / len(tokens)


def _is_english(text: str) -> bool:
    if not text:
        return False
    if detect is not None:
        try:
            lang = detect(text)
            if lang and lang.lower().startswith("en"):
                return True
        except Exception:
            pass
    ascii_letters = sum(1 for ch in text if ch.isalpha() and ord(ch) < 128)
    total_letters = sum(1 for ch in text if ch.isalpha())
    if total_letters == 0:
        total_letters = len(text)
    ascii_ratio = ascii_letters / total_letters if total_letters else 0.0
    stop_ratio = _english_stopword_ratio(text)
    return ascii_ratio >= 0.7 and stop_ratio >= 0.02


def test_snowball_for_review_contains_only_english() -> None:
    assert SNOWBALL_CSV.exists(), f"雪球輸入檔不存在：{SNOWBALL_CSV}"

    non_english_rows: list[str] = []
    missing_rows: list[str] = []

    with SNOWBALL_CSV.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            title = _normalize_text(row.get("title"))
            abstract = _normalize_text(row.get("abstract"))

            if not title or not abstract:
                missing_rows.append(f"row {index}")
                continue

            if not (_is_english(title) and _is_english(abstract)):
                non_english_rows.append(f"row {index}: {title[:80]}")

    assert not missing_rows, (
        "snowball_for_review.csv 仍包含缺少標題或摘要的紀錄：\n" + "\n".join(missing_rows)
    )
    assert not non_english_rows, (
        "snowball_for_review.csv 仍包含非英文標題/摘要的紀錄：\n"
        + "\n".join(non_english_rows[:20])
    )
