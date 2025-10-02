#!/usr/bin/env bash
set -euo pipefail

DEFAULT_INPUT="test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata_peer_reviewed.json"
DEFAULT_BASENAME="speech_lm_arxiv"
ASREVIEW_POLITE_EMAIL="f07942150@g.ntu.edu.tw"
INPUT_PATH="$DEFAULT_INPUT"
OUTPUT_DIR=""
BASENAME="$DEFAULT_BASENAME"
EMAIL="${ASREVIEW_POLITE_EMAIL:-}"
DEDUP_THRESHOLD="${ASREVIEW_DEDUP_THRESHOLD:-0.98}"
FORWARD=1
BACKWARD=1

usage() {
  cat <<USAGE
用法：speech_lm_per_query_asreview.sh [選項]

選項：
  -i, --input PATH         指定輸入 JSON 檔（預設：${DEFAULT_INPUT}）
  -o, --output-dir DIR     指定輸出資料夾（預設：沿用輸入檔所在資料夾）
      --basename NAME      自訂輸出檔案前綴（預設：${DEFAULT_BASENAME}）
      --email ADDRESS      提供給 OpenAlex 的聯絡信箱（加速 API 限額）
      --threshold VALUE    調整 asreview data dedup 相似度門檻（預設：${DEDUP_THRESHOLD}）
      --skip-forward       僅產生後向雪球結果
      --skip-backward      僅產生前向雪球結果
  -h, --help               顯示此說明

執行前請先啟用 sdse-uv 虛擬環境，並確保 'asreview' CLI 可用。
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i|--input)
      INPUT_PATH="$2"
      shift 2
      ;;
    -o|--output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --basename)
      BASENAME="$2"
      shift 2
      ;;
    --email)
      EMAIL="$2"
      shift 2
      ;;
    --threshold)
      DEDUP_THRESHOLD="$2"
      shift 2
      ;;
    --skip-forward)
      FORWARD=0
      shift
      ;;
    --skip-backward)
      BACKWARD=0
      shift
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

if [[ ! -f "$INPUT_PATH" ]]; then
  echo "找不到輸入檔：$INPUT_PATH" >&2
  exit 1
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$(dirname "$INPUT_PATH")"
fi

OUTPUT_DIR="$(realpath "$OUTPUT_DIR")"
INPUT_PATH="$(realpath "$INPUT_PATH")"
mkdir -p "$OUTPUT_DIR"

ASREVIEW_CSV="$OUTPUT_DIR/${BASENAME}_asreview.csv"
DEDUP_CSV="$OUTPUT_DIR/${BASENAME}_asreview_dedup.csv"
FORWARD_CSV="$OUTPUT_DIR/${BASENAME}_asreview_forward.csv"
BACKWARD_CSV="$OUTPUT_DIR/${BASENAME}_asreview_backward.csv"

for tool in python asreview; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "找不到指令 $tool，請確認已安裝於目前環境" >&2
    exit 1
  fi
done

printf 'Step 1/3 轉換 JSON 為 ASReview CSV：%s\n' "$ASREVIEW_CSV"
python - <<'PY' "$INPUT_PATH" "$ASREVIEW_CSV"
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

input_path = Path(sys.argv[1]).expanduser().resolve()
output_path = Path(sys.argv[2]).expanduser().resolve()

payload = json.loads(input_path.read_text(encoding="utf-8"))
rows: list[dict[str, str]] = []
seen_doi: set[str] = set()


def normalize_year(raw: str | None) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""
    try:
        return str(datetime.fromisoformat(raw.replace("Z", "+00:00")).year)
    except ValueError:
        digits = ''.join(ch for ch in raw if ch.isdigit())
        return digits[:4]


def sanitize(value: object) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return " ".join(text.split())


for entry in payload:
    metadata = entry.get("metadata") or {}
    search_record = entry.get("search_record") or {}

    doi_raw = sanitize(metadata.get("doi"))
    if doi_raw.startswith("https://doi.org/"):
        doi_raw = doi_raw[len("https://doi.org/"):]
    if not doi_raw:
        continue

    doi_key = doi_raw.lower()
    if doi_key in seen_doi:
        continue

    title = sanitize(metadata.get("title") or search_record.get("title"))
    if not title:
        continue

    abstract = sanitize(
        metadata.get("summary")
        or search_record.get("summary")
    )

    pdf_url = sanitize(metadata.get("pdf_url"))
    landing_url = sanitize(
        metadata.get("landing_url")
        or search_record.get("id")
        or search_record.get("url")
    )

    year = sanitize(metadata.get("published") or metadata.get("updated"))
    year = normalize_year(year) if year else ""

    identifier = sanitize(
        metadata.get("arxiv_id")
        or doi_raw
        or search_record.get("id")
    )
    if not identifier:
        identifier = doi_raw

    row = {
        "id": identifier,
        "title": title,
        "abstract": abstract,
        "doi": doi_raw,
        "url": landing_url,
        "pdf_url": pdf_url,
        "year": year,
        "source_anchor": sanitize(entry.get("anchor")),
        "source_term": sanitize(entry.get("search_term")),
    }

    rows.append(row)
    seen_doi.add(doi_key)

if not rows:
    raise SystemExit("No ASReview rows could be generated；請確認輸入 JSON 是否含 DOI。")

fieldnames = ["id", "title", "abstract", "doi", "url", "pdf_url", "year", "source_anchor", "source_term"]
output_path.parent.mkdir(parents=True, exist_ok=True)
with output_path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
PY

printf 'Step 2/3 asreview data dedup -> %s (threshold=%s)\n' "$DEDUP_CSV" "$DEDUP_THRESHOLD"
asreview data dedup "$ASREVIEW_CSV" \
  -o "$DEDUP_CSV" \
  --similar \
  --threshold "$DEDUP_THRESHOLD"

if [[ ! -f "$DEDUP_CSV" ]]; then
  echo "未產生去重後 CSV：$DEDUP_CSV" >&2
  exit 1
fi

SNOWBALL_TARGETS=$(python - <<'PY' "$DEDUP_CSV" "$EMAIL"
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

API_URL = "https://api.openalex.org/works"
USER_AGENT = "speech-lm-per-query-snowball/0.1"


def normalize_doi(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    prefix_http = "http://dx.doi.org/"
    prefix_https = "https://doi.org/"
    lower = value.lower()
    if lower.startswith(prefix_http):
        return prefix_https + value[len(prefix_http):]
    if lower.startswith(prefix_https):
        return value
    return prefix_https + value


def token_overlap(left: str, right: str) -> float:
    left_tokens = set(left.replace("-", " ").split())
    right_tokens = set(right.replace("-", " ").split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    return overlap / max(len(left_tokens), len(right_tokens), 1)


@dataclass
class OpenAlexClient:
    email: str | None

    def request(self, params: dict[str, str]) -> dict:
        query = dict(params)
        query.setdefault("per_page", "5")
        if self.email:
            query["mailto"] = self.email
        response = requests.get(
            API_URL,
            params=query,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def fetch(self, doi: str, title: str) -> str | None:
        if doi:
            data = self.request({"filter": f"doi:{doi}", "per_page": "1"})
            results = data.get("results") or []
            if results:
                return results[0].get("id")
        if title:
            data = self.request({"search": title})
            results = data.get("results") or []
            target = title.lower()
            best_id: str | None = None
            best_score = 0.0
            for result in results:
                candidate = (result.get("title") or "").lower()
                if not candidate:
                    continue
                score = token_overlap(target, candidate)
                if score > best_score:
                    best_score = score
                    best_id = result.get("id")
            if best_id is None and results:
                best_id = results[0].get("id")
            return best_id
        return None


def enrich(csv_path: Path, email: str | None) -> int:
    df = pd.read_csv(csv_path)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed:")]
    if df.empty:
        return 0
    if "openalex_id" not in df.columns:
        df["openalex_id"] = ""
    client = OpenAlexClient(email)
    mapped = 0
    for index, row in df.iterrows():
        existing = str(row.get("openalex_id", "")).strip()
        if existing:
            mapped += 1
            continue
        doi = normalize_doi(row.get("doi"))
        trimmed = doi.split("https://doi.org/", 1)[-1] if doi else ""
        title = str(row.get("title", ""))
        openalex_id = client.fetch(trimmed, title)
        if openalex_id:
            df.at[index, "openalex_id"] = openalex_id
            mapped += 1
        time.sleep(0.2)
    df.to_csv(csv_path, index=False)
    return mapped


def main() -> None:
    csv_path = Path(sys.argv[1]).expanduser().resolve()
    email = sys.argv[2] or None
    if not csv_path.exists():
        print("0")
        return
    mapped = enrich(csv_path, email)
    print(str(mapped))


if __name__ == "__main__":
    main()
PY
)
SNOWBALL_TARGETS=${SNOWBALL_TARGETS:-0}

if [[ $SNOWBALL_TARGETS -eq 0 ]]; then
  echo "未取得任何可用的 OpenAlex 識別碼，略過雪球步驟。"
  if [[ $FORWARD -eq 1 ]]; then
    printf 'openalex_id,doi,title,abstract,referenced_works,publication_date\n' > "$FORWARD_CSV"
  fi
  if [[ $BACKWARD -eq 1 ]]; then
    printf 'openalex_id,doi,title,abstract,referenced_works,publication_date\n' > "$BACKWARD_CSV"
  fi
else
  if [[ $FORWARD -eq 1 ]]; then
    printf 'Step 3/3a asreview data snowball --forward -> %s\n' "$FORWARD_CSV"
    if [[ -n "$EMAIL" ]]; then
      asreview data snowball "$DEDUP_CSV" "$FORWARD_CSV" --forward --email "$EMAIL"
    else
      asreview data snowball "$DEDUP_CSV" "$FORWARD_CSV" --forward
    fi
  fi

  if [[ $BACKWARD -eq 1 ]]; then
    printf 'Step 3/3b asreview data snowball --backward -> %s\n' "$BACKWARD_CSV"
    if [[ -n "$EMAIL" ]]; then
      asreview data snowball "$DEDUP_CSV" "$BACKWARD_CSV" --backward --email "$EMAIL"
    else
      asreview data snowball "$DEDUP_CSV" "$BACKWARD_CSV" --backward
    fi
  fi
fi

printf '完成。輸出位於：\n- %s\n- %s\n' "$ASREVIEW_CSV" "$DEDUP_CSV"
if [[ $FORWARD -eq 1 ]]; then
  printf '  - %s\n' "$FORWARD_CSV"
fi
if [[ $BACKWARD -eq 1 ]]; then
  printf '  - %s\n' "$BACKWARD_CSV"
fi
