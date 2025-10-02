#!/usr/bin/env bash
set -euo pipefail

DEFAULT_FORWARD="test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_asreview_forward.csv"
DEFAULT_BACKWARD="test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_asreview_backward.csv"
DEFAULT_OUTPUT="test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_snowball_merged.json"

FORWARD_PATH="$DEFAULT_FORWARD"
BACKWARD_PATH="$DEFAULT_BACKWARD"
OUTPUT_PATH="$DEFAULT_OUTPUT"
ANCHOR_LABEL="snowballing"
SEARCH_TERM="speech-language-models"

usage() {
  cat <<USAGE
用法：speech_lm_snowball_merge.sh [選項]

選項：
  --forward PATH    指定 forward 雪球 CSV（預設：${DEFAULT_FORWARD}）
  --backward PATH   指定 backward 雪球 CSV（預設：${DEFAULT_BACKWARD}）
  --output PATH     指定輸出 JSON 路徑（預設：${DEFAULT_OUTPUT}）
  --anchor LABEL    調整輸出中的 anchor 欄位（預設：${ANCHOR_LABEL}）
  --search-term TXT 調整輸出中的 search_term 欄位（預設：${SEARCH_TERM}）
  -h, --help        顯示此說明

此腳本會：
  1. 讀取 forward/backward 雪球結果
  2. 依 openalex_id → DOI → 標題 建立別名並去重
  3. 產出結構對齊 arxiv_metadata.json 的 JSON 檔
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --forward)
      FORWARD_PATH="$2"
      shift 2
      ;;
    --backward)
      BACKWARD_PATH="$2"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="$2"
      shift 2
      ;;
    --anchor)
      ANCHOR_LABEL="$2"
      shift 2
      ;;
    --search-term)
      SEARCH_TERM="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知參數：$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

for path in "$FORWARD_PATH" "$BACKWARD_PATH"; do
  if [[ ! -f "$path" ]]; then
    echo "找不到輸入檔：$path" >&2
    exit 1
  fi
done

python - <<'PY' "$FORWARD_PATH" "$BACKWARD_PATH" "$OUTPUT_PATH" "$ANCHOR_LABEL" "$SEARCH_TERM"
from __future__ import annotations

import csv
import json
import sys
from ast import literal_eval
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

csv.field_size_limit(1024 * 1024 * 5)

forward_path = Path(sys.argv[1]).expanduser().resolve()
backward_path = Path(sys.argv[2]).expanduser().resolve()
output_path = Path(sys.argv[3]).expanduser().resolve()
anchor_label = sys.argv[4]
search_term = sys.argv[5]


def read_rows(path: Path, source: str) -> Iterable[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            row: Dict[str, str] = {}
            for key, value in raw.items():
                if key is None:
                    continue
                stripped_key = key.strip()
                if not stripped_key or stripped_key.startswith("Unnamed"):
                    continue
                row[stripped_key] = (value or "").strip()
            row["_source"] = source
            yield row


def normalize_openalex(value: str) -> str:
    return value.lower().strip() if value else ""


def normalize_doi(value: str) -> str:
    if not value:
        return ""
    value = value.lower().strip()
    if value.startswith("https://doi.org/"):
        value = value.split("https://doi.org/", 1)[1]
    return value


def normalize_title(value: str) -> str:
    return "".join(value.lower().split()) if value else ""


def key_candidates(row: Dict[str, str]) -> Sequence[Tuple[str, str]]:
    candidates: List[Tuple[str, str]] = []
    openalex_id = normalize_openalex(row.get("openalex_id", ""))
    if openalex_id:
        candidates.append(("openalex_id", openalex_id))
    doi = normalize_doi(row.get("doi", ""))
    if doi:
        candidates.append(("doi", doi))
    title = normalize_title(row.get("title", ""))
    if title:
        candidates.append(("title", title))
    return candidates


def parse_references(raw: str) -> List[str]:
    if not raw:
        return []
    try:
        parsed = literal_eval(raw)
        if isinstance(parsed, (list, tuple)):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except (ValueError, SyntaxError):
        pass
    if raw.startswith("[") and raw.endswith("]"):
        stripped = raw[1:-1].strip()
        if not stripped:
            return []
        candidates = [segment.strip().strip("'\"") for segment in stripped.split(",")]
        return [candidate for candidate in candidates if candidate]
    return [raw.strip()]


def build_entry(row: Dict[str, str]) -> Dict[str, object]:
    references = parse_references(row.get("referenced_works", ""))
    openalex_id = row.get("openalex_id") or None
    doi = row.get("doi") or None
    title = row.get("title") or None
    abstract = row.get("abstract") or None
    published = row.get("publication_date") or None
    sources = [row.get("_source") or "unknown"]

    search_record = {
        "id": openalex_id,
        "title": title,
        "summary": abstract,
        "published": published,
        "doi": doi,
        "referenced_works": references,
    }

    metadata = {
        "openalex_id": openalex_id,
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "publication_date": published,
        "referenced_works": references,
        "source": "openalex_snowball",
        "snowball_sources": sources,
    }

    return {
        "arxiv_id": None,
        "anchor": anchor_label,
        "search_term": search_term,
        "search_record": search_record,
        "metadata": metadata,
    }


def merge_entry(entry: Dict[str, object], row: Dict[str, str]) -> None:
    references = parse_references(row.get("referenced_works", ""))
    metadata = entry.get("metadata", {})
    search_record = entry.get("search_record", {})

    def prefer(target_key: str, new_value: str | None, *, transform=lambda x: x) -> None:
        if not new_value:
            return
        current = metadata.get(target_key)
        if not current:
            metadata[target_key] = transform(new_value)
        current_record = search_record.get(target_key if target_key != "publication_date" else "published")
        if not current_record:
            if target_key == "publication_date":
                search_record["published"] = new_value
            elif target_key == "abstract":
                search_record["summary"] = new_value
            elif target_key == "openalex_id":
                search_record["id"] = new_value
            elif target_key == "doi":
                search_record["doi"] = new_value
            elif target_key == "title":
                search_record["title"] = new_value

    prefer("openalex_id", row.get("openalex_id"))
    prefer("doi", row.get("doi"))
    prefer("title", row.get("title"))
    prefer("abstract", row.get("abstract"))
    prefer("publication_date", row.get("publication_date"))

    existing_refs = set(metadata.get("referenced_works", []) or [])
    existing_refs.update(references)
    metadata["referenced_works"] = sorted(existing_refs)
    search_record["referenced_works"] = metadata["referenced_works"]

    sources = set(metadata.get("snowball_sources", []) or [])
    source_label = row.get("_source") or "unknown"
    if source_label:
        sources.add(source_label)
    metadata["snowball_sources"] = sorted(sources)


records: Dict[str, Dict[str, object]] = {}
aliases: Dict[Tuple[str, str], str] = {}


def handle_row(row: Dict[str, str]) -> None:
    candidates = key_candidates(row)
    if not candidates:
        return
    existing_key = None
    for candidate in candidates:
        existing_key = aliases.get(candidate)
        if existing_key:
            break
    if existing_key is None:
        canonical = f"{candidates[0][0]}:{candidates[0][1]}"
        records[canonical] = build_entry(row)
        existing_key = canonical
    else:
        merge_entry(records[existing_key], row)
    for candidate in candidates:
        aliases[candidate] = existing_key


for row in read_rows(forward_path, "forward"):
    handle_row(row)

for row in read_rows(backward_path, "backward"):
    handle_row(row)

output_path.parent.mkdir(parents=True, exist_ok=True)
ordered = sorted(
    records.values(),
    key=lambda item: (
        (item["metadata"].get("publication_date") or ""),
        (item["metadata"].get("title") or "")
    ),
)
output_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"合併完成，共 {len(ordered)} 筆去重紀錄 -> {output_path}")
PY
PY_STATUS=$?

if [[ $PY_STATUS -ne 0 ]]; then
  exit $PY_STATUS
fi

echo "Done."
