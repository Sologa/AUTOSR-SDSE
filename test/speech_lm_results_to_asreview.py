#!/usr/bin/env python
"""Convert LatteReview results JSON to ASReview CSV and run snowballing."""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

import pandas as pd

try:  # pragma: no cover - optional dependency
    from langdetect import detect
except ImportError:  # pragma: no cover - fallback when langdetect is unavailable
    detect = None
import requests
import urllib3
from asreviewcontrib.datatools import snowball as datatools_snowball
from pyalex import config as pyalex_config

DEFAULT_RESULTS = Path(
    "test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json"
)
DEFAULT_METADATA = Path(
    "test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata_peer_reviewed.json"
)
CONVERTED_FILENAME = "screening_included.csv"
SNOWBALL_FILENAME = "snowball_results.csv"
SNOWBALL_RAW_FILENAME = "snowball_results_raw.csv"
SNOWBALL_REVIEW_FILENAME = "snowball_for_review.csv"
CANDIDATES_JSON_FILENAME = "candidates_for_review.json"
DEDUP_REPORT_FILENAME = "dedup_report.json"
USER_AGENT = "AUTOSR-SDSE/1.0"


class ConversionError(RuntimeError):
    """Raised when conversion cannot be completed."""


@dataclass
class MetadataRecord:
    arxiv_id: str
    anchor: str | None
    search_term: str | None
    metadata: Dict[str, Any]

    @property
    def title(self) -> str:
        return str(self.metadata.get("title", "")).strip()

    @property
    def landing_url(self) -> str:
        return str(self.metadata.get("landing_url", "")).strip()

    @property
    def pdf_url(self) -> str:
        return str(self.metadata.get("pdf_url", "")).strip()

    @property
    def doi(self) -> str:
        return str(self.metadata.get("doi", "")).strip()

    @property
    def published(self) -> str:
        raw = str(
            self.metadata.get("published")
            or self.metadata.get("publication_date")
            or self.metadata.get("published_date")
            or self.metadata.get("date")
            or ""
        ).strip()
        if not raw:
            return ""
        return raw


@dataclass
class ConversionResult:
    records: List[MetadataRecord]
    total: int
    kept: int
    skipped: int
    filtered_by_date: int


@dataclass
class OpenAlexClient:
    email: str | None

    def request(self, params: Dict[str, str]) -> Dict[str, Any]:
        query = dict(params)
        query.setdefault("per_page", "5")
        # OpenAlex API 的 `mailto` 參數會在部份測試帳號回傳 400，改由 pyalex polite pool 處理
        # Retry transient OpenAlex errors with backoff.
        attempts = 0
        while True:
            try:
                response = requests.get(
                    "https://api.openalex.org/works",
                    params=query,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept-Encoding": "identity",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                return response.json()
            except (
                requests.exceptions.ContentDecodingError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as exc:
                attempts += 1
                if attempts > 5:
                    raise ConversionError("OpenAlex 查詢失敗，請稍後重試") from exc
                wait_seconds = min(60, 5 * attempts)
                print(
                    f"OpenAlex 連線異常，第 {attempts} 次重試，等待 {wait_seconds} 秒…"
                )
                time.sleep(wait_seconds)

    def fetch(self, doi: str, title: str) -> Optional[str]:
        normalized_doi = normalize_doi(doi)
        if normalized_doi:
            try:
                data = self.request({"filter": f"doi:{normalized_doi}", "per_page": "1"})
            except requests.HTTPError:
                data = {}
            results = data.get("results") or []
            if results:
                return results[0].get("id")
        if title:
            try:
                data = self.request({"search": title})
            except requests.HTTPError:
                data = {}
            results = data.get("results") or []
            best_id: Optional[str] = None
            best_score = 0.0
            target_tokens = tokens(title)
            for result in results:
                candidate = (result.get("title") or "").strip()
                if not candidate:
                    continue
                score = jaccard_score(target_tokens, tokens(candidate))
                if score > best_score:
                    best_score = score
                    best_id = result.get("id")
            if best_id is None and results:
                best_id = results[0].get("id")
            return best_id
        return None


def tokens(text: str) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", text.lower()) if tok}


def jaccard_score(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def is_same_title(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return normalize_title(left) == normalize_title(right)


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if not value:
        return ""
    value = value.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return value.lower()


def normalize_doi_slug(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def normalize_openalex_slug(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def normalize_title_slug(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(value.lower().split())


def normalize_arxiv_slug(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().lower()
    if text.startswith("arxiv:"):
        text = text[len("arxiv:"):]
    return "".join(text.split())


def parse_year(raw: str | None) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return str(dt.year)
    except ValueError:
        digits = "".join(ch for ch in raw if ch.isdigit())
        return digits[:4]


def _parse_date_string(raw: str | None) -> Optional[date]:
    if not raw:
        return None
    text = str(raw).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    candidates = [normalized]
    if "T" in normalized:
        candidates.append(normalized.split("T", 1)[0])
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    if text.isdigit() and len(text) >= 4:
        try:
            return date(int(text[:4]), 1, 1)
        except ValueError:
            return None
    return None


def _parse_date_bound(value: Optional[str], *, label: str) -> Optional[date]:
    if not value:
        return None
    parsed = _parse_date_string(value)
    if parsed is None:
        raise ConversionError(f"無法解析 {label}：{value}")
    return parsed


def _within_date_range(target: Optional[date], *, start: Optional[date], end: Optional[date]) -> bool:
    if target is None:
        return False
    if start and target < start:
        return False
    if end and target > end:
        return False
    return True


def parse_verdict(verdict: str) -> tuple[int | str, str]:
    verdict = verdict.strip()
    verdict_lower = verdict.lower()
    label: int | str
    if "納入" in verdict or "include" in verdict_lower:
        label = 1
    elif "排除" in verdict or "exclude" in verdict_lower:
        label = 0
    elif "需再評估" in verdict or "maybe" in verdict_lower or "needs-review" in verdict_lower:
        label = ""
    else:
        label = ""
    source_match = re.search(r"來源: ([^,\)]+)", verdict)
    source = source_match.group(1).strip() if source_match else ""
    return label, source


def sanitize_record(value: Any) -> Any:
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return None
    except TypeError:
        pass
    return value


def load_metadata(metadata_path: Path) -> Dict[str, MetadataRecord]:
    mapping: Dict[str, MetadataRecord] = {}
    raw_list = json.loads(metadata_path.read_text(encoding="utf-8"))
    for item in raw_list:
        meta = item.get("metadata") or {}
        arxiv_id = str(meta.get("arxiv_id") or item.get("arxiv_id") or "").strip()
        title = str(meta.get("title") or "").strip()
        openalex_id = str(meta.get("openalex_id") or "").strip()
        doi = str(meta.get("doi") or "").strip()
        if not (arxiv_id or title or openalex_id or doi):
            continue
        record = MetadataRecord(
            arxiv_id=arxiv_id,
            anchor=item.get("anchor"),
            search_term=item.get("search_term"),
            metadata=meta,
        )
        if arxiv_id:
            mapping[arxiv_id] = record
        if title:
            mapping[normalize_title(title)] = record
        if openalex_id:
            mapping[f"openalex:{normalize_openalex_slug(openalex_id)}"] = record
        if doi:
            mapping[f"doi:{normalize_doi_slug(doi)}"] = record
    return mapping


def resolve_metadata(
    item: Dict[str, Any],
    metadata_map: Dict[str, MetadataRecord],
) -> MetadataRecord | None:
    meta = item.get("metadata") or {}
    arxiv_id = str(meta.get("arxiv_id", "")).strip()
    title = normalize_title(str(item.get("title") or meta.get("title") or ""))
    openalex_id = normalize_openalex_slug(meta.get("openalex_id"))
    doi = normalize_doi_slug(meta.get("doi"))

    if arxiv_id and arxiv_id in metadata_map:
        base = metadata_map[arxiv_id]
    elif openalex_id and f"openalex:{openalex_id}" in metadata_map:
        base = metadata_map[f"openalex:{openalex_id}"]
    elif doi and f"doi:{doi}" in metadata_map:
        base = metadata_map[f"doi:{doi}"]
    elif title and title in metadata_map:
        base = metadata_map[title]
    else:
        return None

    merged = dict(base.metadata)
    merged.update(meta)
    return MetadataRecord(
        arxiv_id=base.arxiv_id,
        anchor=base.anchor,
        search_term=base.search_term,
        metadata=merged,
    )


LABEL_ALIASES: Dict[str, int | str] = {
    "include": 1,
    "included": 1,
    "accept": 1,
    "accepted": 1,
    "納入": 1,
    "1": 1,
    "exclude": 0,
    "excluded": 0,
    "reject": 0,
    "rejected": 0,
    "排除": 0,
    "0": 0,
    "review": "",
    "needs-review": "",
    "needs_review": "",
    "pending": "",
    "reconsider": "",
    "需再評估": "",
    "再評估": "",
}


def parse_allowed_labels(options: Optional[List[str]]) -> Optional[Set[int | str]]:
    if not options:
        return None
    allowed: Set[int | str] = set()
    unknown: list[str] = []
    for option in options:
        key = option.strip().lower()
        if not key:
            key = "needs-review"
        if key in LABEL_ALIASES:
            allowed.add(LABEL_ALIASES[key])
        else:
            unknown.append(option)
    if unknown:
        valid = ", ".join(sorted({"include", "exclude", "needs-review"}))
        raise ConversionError(
            f"未知標籤：{', '.join(unknown)}；可用選項：{valid}"
        )
    return allowed


def convert(
    results_path: Path,
    metadata_path: Path,
    output_csv: Path,
    allowed_labels: Optional[Set[int | str]] = None,
    *,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    exclude_title: Optional[str] = None,
) -> ConversionResult:
    metadata_map = load_metadata(metadata_path)
    payload = json.loads(results_path.read_text(encoding="utf-8"))

    csv_rows: list[Dict[str, Any]] = []
    resolved_records: list[MetadataRecord] = []
    total_records = 0
    skipped_records = 0
    filtered_by_date = 0

    for item in payload:
        total_records += 1
        title = str(item.get("title", "")).strip()
        abstract = str(item.get("abstract", "")).strip()
        if exclude_title and is_same_title(title, exclude_title):
            skipped_records += 1
            continue
        verdict = str(item.get("final_verdict", "")).strip()
        label, source = parse_verdict(verdict)

        if allowed_labels is not None and label not in allowed_labels:
            skipped_records += 1
            continue

        metadata_record = resolve_metadata(item, metadata_map)
        if metadata_record is None:
            raise ConversionError(f"找不到對應 metadata：{title}")
        resolved_records.append(metadata_record)

        published_date = _parse_date_string(metadata_record.published)
        if (min_date or max_date) and not _within_date_range(
            published_date, start=min_date, end=max_date
        ):
            filtered_by_date += 1
            continue

        year = parse_year(metadata_record.published)
        doi = normalize_doi(metadata_record.doi)
        included_value = label if isinstance(label, int) else None
        openalex_value = metadata_record.metadata.get("openalex_id") or ""

        csv_rows.append(
            {
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "included": included_value,
                "decision_source": source,
                "final_verdict": verdict,
                "landing_url": metadata_record.landing_url,
                "pdf_url": metadata_record.pdf_url,
                "year": year,
                "source_anchor": metadata_record.anchor or "",
                "source_term": metadata_record.search_term or "",
                "metadata_json": json.dumps(
                    metadata_record.metadata,
                    ensure_ascii=False,
                ),
                "arxiv_id": metadata_record.arxiv_id,
                "openalex_id": openalex_value,
            }
        )

    if not csv_rows:
        raise ConversionError("在指定標籤條件下沒有任何紀錄可輸出")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fp:
        fieldnames = [
            "doi",
            "title",
            "abstract",
            "included",
            "decision_source",
            "final_verdict",
            "landing_url",
            "pdf_url",
            "year",
            "source_anchor",
            "source_term",
            "metadata_json",
            "arxiv_id",
            "openalex_id",
        ]
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)

    return ConversionResult(
        records=resolved_records,
        total=total_records,
        kept=len(csv_rows),
        skipped=skipped_records,
        filtered_by_date=filtered_by_date,
    )

def enrich_openalex(csv_path: Path, email: str | None) -> int:
    df = pd.read_csv(csv_path)
    if df.empty:
        df["openalex_id"] = ""
        df.to_csv(csv_path, index=False)
        return 0
    if "openalex_id" not in df.columns:
        df["openalex_id"] = ""
    else:
        df["openalex_id"] = df["openalex_id"].fillna("").astype(str)
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    client = OpenAlexClient(email)
    mapped = 0
    for idx, row in df.iterrows():
        existing = str(row.get("openalex_id", "")).strip()
        if existing:
            mapped += 1
            continue
        doi = str(row.get("doi", ""))
        title = str(row.get("title", ""))
        openalex_id = client.fetch(doi, title)
        if openalex_id:
            df.at[idx, "openalex_id"] = openalex_id
            mapped += 1
        time.sleep(0.2)
    df.to_csv(csv_path, index=False)
    return mapped


def _normalize_snowball_output(snowball_csv: Path) -> None:
    if not snowball_csv.exists() or snowball_csv.stat().st_size == 0:
        return
    df = pd.read_csv(snowball_csv)
    clean_columns = [
        column
        for column in df.columns
        if column and not str(column).startswith("Unnamed")
    ]
    if len(clean_columns) != len(df.columns):
        df = df[clean_columns]
        df.to_csv(snowball_csv, index=False)


def run_snowball(
    dedup_csv: Path,
    output_csv: Path,
    email: str | None,
    run_forward: bool,
    run_backward: bool,
    *,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    exclude_title: Optional[str] = None,
) -> None:
    if not run_forward and not run_backward:
        print("已略過雪球檢索")
        return
    pyalex_config.email = email or pyalex_config.email
    pyalex_config.user_agent = USER_AGENT
    pyalex_config.max_retries = max(pyalex_config.max_retries, 6)
    pyalex_config.retry_backoff_factor = max(pyalex_config.retry_backoff_factor, 2.5)
    pyalex_config.retry_http_codes = sorted(
        set(pyalex_config.retry_http_codes) | {429, 500, 502, 503, 504}
    )

    print("開始雪球檢索，這個步驟可能需要幾分鐘，請耐心等待…")
    attempts = 0
    while True:
        try:
            datatools_snowball.snowball(
                input_path=dedup_csv,
                output_path=output_csv,
                forward=run_forward,
                backward=run_backward,
                use_all=False,
                email=email,
            )
            _normalize_snowball_output(output_csv)
            print(f"雪球輸出：{output_csv}")
            break
        except ValueError as exc:
            message = str(exc)
            if "max() iterable argument is empty" not in message:
                raise
            print("雪球檢索完成，但未取得任何延伸文獻，輸出將寫入空檔案。")
            output_csv.parent.mkdir(parents=True, exist_ok=True)
            empty_df = pd.DataFrame(
                columns=[
                    "openalex_id",
                    "doi",
                    "title",
                    "abstract",
                    "referenced_works",
                    "publication_date",
                ]
            )
            empty_df.to_csv(output_csv, index=False)
            break
        except (requests.exceptions.RetryError, urllib3.exceptions.MaxRetryError) as exc:
            attempts += 1
            if attempts > 6:
                raise ConversionError(
                    "雪球檢索多次遭 OpenAlex 限流，請稍後重試或縮減資料集"
                ) from exc
            wait_seconds = min(180, 30 * attempts)
            print(
                f"OpenAlex 429/連線受限，第 {attempts} 次重試，等待 {wait_seconds} 秒…"
            )
            time.sleep(wait_seconds)

    raw_count = 0
    if output_csv.exists() and output_csv.stat().st_size > 0:
        df_raw = pd.read_csv(output_csv)
        raw_count = len(df_raw)
        raw_path = output_csv.with_name(SNOWBALL_RAW_FILENAME)
        shutil.copyfile(output_csv, raw_path)
        print(f"雪球原始輸出：{raw_path} ({raw_count} 筆)")

    if min_date or max_date:
        removed = _filter_csv_by_date(
            output_csv,
            column="publication_date",
            min_date=min_date,
            max_date=max_date,
        )
        if removed:
            print(f"已依日期範圍移除 {removed} 筆雪球結果")

    # 去除雪球輸出內部重複（以 DOI / OpenAlex / 標題為鍵）
    if output_csv.exists() and output_csv.stat().st_size > 0:
        df = pd.read_csv(output_csv)
        deduped_df = _deduplicate_dataframe_by_keys(df)
        if len(deduped_df) < len(df):
            deduped_df.to_csv(output_csv, index=False)
            print(f"已去除雪球結果內部重複 {len(df) - len(deduped_df)} 筆")
    removed_empty, removed_non_en = _filter_invalid_snowball_rows(output_csv)
    if removed_empty:
        print(f"已移除缺少標題/摘要的雪球候選 {removed_empty} 筆")
    if removed_non_en:
        print(f"已移除非英文標題/摘要的雪球候選 {removed_non_en} 筆")
    if exclude_title:
        removed_same_title = _filter_snowball_by_title(output_csv, exclude_title)
        if removed_same_title:
            print(f"已排除與主題同標題的雪球候選 {removed_same_title} 筆")


FINAL_REGISTRY_STATUSES = {"include", "exclude", "hard_exclude"}


def _load_registry_payload(registry_path: Path) -> tuple[List[Dict[str, Any]], str]:
    if not registry_path.exists():
        return [], ""
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [], ""
    entries = payload.get("entries")
    if not isinstance(entries, list):
        entries = []
    criteria_hash = str(payload.get("criteria_hash") or "").strip()
    return entries, criteria_hash


def _build_registry_seen(
    entries: List[Dict[str, Any]],
    active_criteria_hash: str,
) -> Dict[str, Set[str]]:
    seen = _empty_seen_index()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "").strip()
        if status not in FINAL_REGISTRY_STATUSES:
            continue
        if status == "hard_exclude" and active_criteria_hash:
            entry_hash = str(entry.get("criteria_hash") or "").strip()
            if not entry_hash or entry_hash != active_criteria_hash:
                continue
        candidates = _entry_key_candidates(entry)
        _register_seen(candidates, seen)
    return seen


def generate_snowball_review_candidates(
    *,
    screened_csv: Path,
    snowball_csv: Path,
    output_csv: Path,
    registry_path: Optional[Path] = None,
    criteria_hash: Optional[str] = None,
    dedup_report_path: Optional[Path] = None,
) -> None:
    if not snowball_csv.exists():
        print("[WARN] 雪球輸出不存在，略過合併去重階段")
        return
    if not screened_csv.exists():
        print("[WARN] 找不到 screening_included.csv，略過合併去重階段")
        return

    base_df = pd.read_csv(screened_csv)
    snow_df = pd.read_csv(snowball_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if snow_df.empty:
        print("[INFO] 雪球結果為空，無須產生額外審查清單")
        snow_df.to_csv(output_csv, index=False)
        if dedup_report_path:
            dedup_report_path.parent.mkdir(parents=True, exist_ok=True)
            report = {
                "removed_total": 0,
                "removed_by": {},
                "registry_used": False,
                "active_criteria_hash": (criteria_hash or "").strip() or None,
            }
            dedup_report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return

    seen = _empty_seen_index()
    for _, row in base_df.iterrows():
        _register_seen(_row_key_candidates(row), seen)

    registry_used = False
    active_hash = (criteria_hash or "").strip()
    if registry_path is not None:
        entries, registry_hash = _load_registry_payload(registry_path)
        if not active_hash:
            active_hash = registry_hash
        if entries:
            registry_used = True
            registry_seen = _build_registry_seen(entries, active_hash)
            for key_type, key_values in registry_seen.items():
                seen.setdefault(key_type, set()).update(key_values)

    kept_rows: list[pd.Series] = []
    skipped = 0
    removed_by = {key: 0 for key in DEDUP_KEY_ORDER}
    for _, row in snow_df.iterrows():
        candidates = _row_key_candidates(row)
        matched_by = _match_seen(candidates, seen)
        if matched_by:
            skipped += 1
            removed_by[matched_by] += 1
            continue
        kept_rows.append(row)
        _register_seen(candidates, seen)

    if kept_rows:
        merged_df = pd.DataFrame(kept_rows)
    else:
        merged_df = pd.DataFrame(columns=snow_df.columns)
    merged_df.to_csv(output_csv, index=False)
    print(
        f"雪崩新審查清單：{output_csv} (保留 {len(merged_df)} 筆，排除與初審重覆 {skipped} 筆)"
    )
    if dedup_report_path:
        dedup_report_path.parent.mkdir(parents=True, exist_ok=True)
        removed_by_clean = {key: value for key, value in removed_by.items() if value}
        report = {
            "removed_total": skipped,
            "removed_by": removed_by_clean,
            "registry_used": registry_used,
            "active_criteria_hash": active_hash or None,
        }
        dedup_report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def write_candidates_for_review_json(
    *,
    input_csv: Path,
    output_json: Path,
) -> int:
    if not input_csv.exists():
        print("[WARN] 找不到 snowball_for_review.csv，無法產生 candidates_for_review.json")
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text("[]", encoding="utf-8")
        return 0
    df = pd.read_csv(input_csv)
    records: List[Dict[str, Any]] = []
    def _cell_text(value: Any) -> str:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        return str(value).strip()

    for _, row in df.iterrows():
        title = _cell_text(row.get("title"))
        abstract = _cell_text(row.get("abstract"))
        doi = _cell_text(row.get("doi"))
        openalex_id = _cell_text(row.get("openalex_id"))
        arxiv_id = _cell_text(row.get("arxiv_id"))
        publication_date = _cell_text(row.get("publication_date"))
        metadata = {
            "title": title,
            "summary": abstract,
            "abstract": abstract,
            "doi": doi,
            "openalex_id": openalex_id,
            "arxiv_id": arxiv_id,
            "publication_date": publication_date,
            "published": publication_date,
            "source": "openalex_snowball",
        }
        records.append({"metadata": metadata})
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"雪球候選 JSON：{output_json} ({len(records)} 筆)")
    return len(records)


def _filter_csv_by_date(
    csv_path: Path,
    *,
    column: str,
    min_date: Optional[date],
    max_date: Optional[date],
) -> int:
    if not csv_path.exists() or (min_date is None and max_date is None):
        return 0
    df = pd.read_csv(csv_path)
    if column not in df.columns or df.empty:
        return 0

    def _keep(value: Any) -> bool:
        parsed = _parse_date_string(value if pd.notna(value) else None)
        return _within_date_range(parsed, start=min_date, end=max_date)

    mask = df[column].apply(_keep)
    filtered_df = df[mask]
    removed = len(df) - len(filtered_df)
    if removed:
        filtered_df.to_csv(csv_path, index=False)
    return removed


def _deduplicate_dataframe_by_keys(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    seen = _empty_seen_index()
    keep_indices: list[int] = []

    for idx, row in df.iterrows():
        candidates = _row_key_candidates(row)
        matched_by = _match_seen(candidates, seen)
        if matched_by:
            continue
        keep_indices.append(idx)
        _register_seen(candidates, seen)

    return df.iloc[keep_indices].reset_index(drop=True)


DEDUP_KEY_ORDER = ("openalex_id", "doi", "arxiv_id", "title")


def _empty_seen_index() -> Dict[str, Set[str]]:
    return {key: set() for key in DEDUP_KEY_ORDER}


def _row_key_candidates(row: pd.Series) -> List[tuple[str, str]]:
    candidates: List[tuple[str, str]] = []
    openalex = normalize_openalex_slug(row.get("openalex_id"))
    if openalex:
        candidates.append(("openalex_id", f"openalex:{openalex}"))
    doi = normalize_doi_slug(row.get("doi"))
    if doi:
        candidates.append(("doi", f"doi:{doi}"))
    arxiv_id = normalize_arxiv_slug(row.get("arxiv_id"))
    if arxiv_id:
        candidates.append(("arxiv_id", f"arxiv:{arxiv_id}"))
    title = normalize_title_slug(row.get("title"))
    if title:
        candidates.append(("title", f"title:{title}"))
    return candidates


def _entry_key_candidates(entry: Dict[str, Any]) -> List[tuple[str, str]]:
    candidates: List[tuple[str, str]] = []
    openalex = normalize_openalex_slug(entry.get("openalex_id"))
    if openalex:
        candidates.append(("openalex_id", f"openalex:{openalex}"))
    doi = normalize_doi_slug(entry.get("doi"))
    if doi:
        candidates.append(("doi", f"doi:{doi}"))
    arxiv_id = normalize_arxiv_slug(entry.get("arxiv_id"))
    if arxiv_id:
        candidates.append(("arxiv_id", f"arxiv:{arxiv_id}"))
    title_value = entry.get("normalized_title") or entry.get("title")
    title = normalize_title_slug(title_value)
    if title:
        candidates.append(("title", f"title:{title}"))
    return candidates


def _match_seen(
    candidates: List[tuple[str, str]],
    seen: Dict[str, Set[str]],
) -> Optional[str]:
    for key_type, key_value in candidates:
        if key_value in seen.get(key_type, set()):
            return key_type
    return None


def _register_seen(
    candidates: List[tuple[str, str]],
    seen: Dict[str, Set[str]],
) -> None:
    for key_type, key_value in candidates:
        seen.setdefault(key_type, set()).add(key_value)


def _normalize_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _filter_invalid_snowball_rows(csv_path: Path) -> tuple[int, int]:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return 0, 0
    df = pd.read_csv(csv_path)
    if df.empty:
        return 0, 0

    original_len = len(df)

    def has_text(value: Any) -> bool:
        return bool(_normalize_text(value))

    df = df[df["title"].apply(has_text) & df["abstract"].apply(has_text)]
    removed_empty = original_len - len(df)

    if df.empty:
        df.to_csv(csv_path, index=False)
        return removed_empty, 0

    en_stopwords = {
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

    def english_stopword_ratio(text: str) -> float:
        tokens = re.findall(r"[a-z]+", text.lower())
        if not tokens:
            return 0.0
        hits = sum(1 for token in tokens if token in en_stopwords)
        return hits / len(tokens)

    def is_english(value: Any) -> bool:
        text = _normalize_text(value)
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
        total = sum(1 for ch in text if ch.isalpha())
        if total == 0:
            total = len(text)
        ascii_ratio = ascii_letters / total if total else 0.0
        stop_ratio = english_stopword_ratio(text)
        return ascii_ratio >= 0.7 and stop_ratio >= 0.02

    mask = df["title"].apply(is_english) & df["abstract"].apply(is_english)
    filtered_df = df[mask]
    removed_non_en = len(df) - len(filtered_df)
    filtered_df.to_csv(csv_path, index=False)
    return removed_empty, removed_non_en


def _filter_snowball_by_title(csv_path: Path, exclude_title: str) -> int:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return 0
    df = pd.read_csv(csv_path)
    if df.empty or "title" not in df.columns:
        return 0
    mask = df["title"].apply(
        lambda value: not is_same_title(str(value), exclude_title)
    )
    filtered_df = df[mask]
    removed = len(df) - len(filtered_df)
    if removed:
        filtered_df.to_csv(csv_path, index=False)
    return removed


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_RESULTS, help="LatteReview 結果 JSON 路徑")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="原始 metadata JSON 路徑")
    parser.add_argument("--output-dir", type=Path, default=None, help="輸出資料夾，預設與輸入相同")
    parser.add_argument("--email", default=None, help="OpenAlex 查詢用 email")
    parser.add_argument("--skip-forward", action="store_true", help="略過 forward snowball")
    parser.add_argument("--skip-backward", action="store_true", help="略過 backward snowball")
    parser.add_argument(
        "--keep-label",
        action="append",
        default=None,
        help="僅保留指定決策（例：--keep-label include，可重複指定）",
    )
    parser.add_argument(
        "--min-date",
        default=None,
        help="僅保留發表日期不早於此日期的紀錄（格式 YYYY 或 YYYY-MM-DD）",
    )
    parser.add_argument(
        "--max-date",
        default=None,
        help="僅保留發表日期不晚於此日期的紀錄（格式 YYYY 或 YYYY-MM-DD）",
    )
    parser.add_argument(
        "--exclude-title",
        default=None,
        help="排除標題完全等於指定字串的論文（大小寫不敏感）",
    )
    parser.add_argument("--registry", type=Path, default=None, help="全歷史 review registry JSON")
    parser.add_argument("--criteria-hash", default=None, help="當前 criteria hash（供 hard_exclude 去重判斷）")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not args.input.exists():
        raise ConversionError(f"找不到輸入檔案：{args.input}")
    if not args.metadata.exists():
        raise ConversionError(f"找不到 metadata 檔案：{args.metadata}")

    output_dir = args.output_dir or args.input.parent
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    asreview_csv = output_dir / CONVERTED_FILENAME
    snowball_csv = output_dir / SNOWBALL_FILENAME

    allowed_labels = parse_allowed_labels(args.keep_label)

    min_date = _parse_date_bound(args.min_date, label="--min-date")
    max_date = _parse_date_bound(args.max_date, label="--max-date")

    if min_date and max_date and min_date > max_date:
        raise ConversionError("--min-date 不可晚於 --max-date")

    conversion = convert(
        args.input,
        args.metadata,
        asreview_csv,
        allowed_labels=allowed_labels,
        min_date=min_date,
        max_date=max_date,
        exclude_title=args.exclude_title,
    )
    if conversion.skipped:
        print(
            f"寫入 ASReview CSV：{asreview_csv} "
            f"({conversion.kept}/{conversion.total} 筆，已略過 {conversion.skipped} 筆)"
        )
    else:
        print(f"寫入 ASReview CSV：{asreview_csv} ({conversion.kept} 筆)")
    if conversion.filtered_by_date:
        print(f"因日期範圍排除 {conversion.filtered_by_date} 筆紀錄")

    mapped = enrich_openalex(asreview_csv, args.email)
    print(f"OpenAlex 識別碼補齊：{mapped} 筆")

    run_snowball(
        asreview_csv,
        snowball_csv,
        args.email,
        run_forward=not args.skip_forward,
        run_backward=not args.skip_backward,
        min_date=min_date,
        max_date=max_date,
        exclude_title=args.exclude_title,
    )

    combined_candidates_csv = output_dir / SNOWBALL_REVIEW_FILENAME
    generate_snowball_review_candidates(
        screened_csv=asreview_csv,
        snowball_csv=snowball_csv,
        output_csv=combined_candidates_csv,
        registry_path=args.registry,
        criteria_hash=args.criteria_hash,
        dedup_report_path=output_dir / DEDUP_REPORT_FILENAME,
    )
    write_candidates_for_review_json(
        input_csv=combined_candidates_csv,
        output_json=output_dir / CANDIDATES_JSON_FILENAME,
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConversionError as exc:  # pragma: no cover - CLI 錯誤處理
        print(f"錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)
