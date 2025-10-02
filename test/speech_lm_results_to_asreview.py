#!/usr/bin/env python
"""Convert LatteReview results JSON to ASReview CSV and run snowballing."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import requests

DEFAULT_RESULTS = Path(
    "test_artifacts/metadata_harvest/speech_language_models/latte_review_results_top797.json"
)
DEFAULT_METADATA = Path(
    "test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata.json"
)
DEFAULT_BASENAME = "speech_lm_arxiv"
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
        raw = str(self.metadata.get("published", "")).strip()
        if not raw:
            return ""
        return raw


@dataclass
class OpenAlexClient:
    email: str | None

    def request(self, params: Dict[str, str]) -> Dict[str, Any]:
        query = dict(params)
        query.setdefault("per_page", "5")
        if self.email:
            query["mailto"] = self.email
        response = requests.get(
            "https://api.openalex.org/works",
            params=query,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def fetch(self, doi: str, title: str) -> Optional[str]:
        normalized_doi = normalize_doi(doi)
        if normalized_doi:
            data = self.request({"filter": f"doi:{normalized_doi}", "per_page": "1"})
            results = data.get("results") or []
            if results:
                return results[0].get("id")
        if title:
            data = self.request({"search": title})
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


def normalize_doi(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    if not value:
        return ""
    value = value.replace("https://doi.org/", "").replace("http://doi.org/", "")
    return value


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


def parse_verdict(verdict: str) -> tuple[int | str, str]:
    verdict = verdict.strip()
    label: int | str
    if "納入" in verdict:
        label = 1
    elif "排除" in verdict:
        label = 0
    elif "需再評估" in verdict:
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
        if not arxiv_id:
            continue
        record = MetadataRecord(
            arxiv_id=arxiv_id,
            anchor=item.get("anchor"),
            search_term=item.get("search_term"),
            metadata=meta,
        )
        mapping[arxiv_id] = record
        title = record.title
        if title:
            mapping[normalize_title(title)] = record
    return mapping


def resolve_metadata(
    item: Dict[str, Any],
    metadata_map: Dict[str, MetadataRecord],
) -> MetadataRecord | None:
    meta = item.get("metadata") or {}
    arxiv_id = str(meta.get("arxiv_id", "")).strip()
    title = normalize_title(str(item.get("title") or meta.get("title") or ""))

    if arxiv_id and arxiv_id in metadata_map:
        base = metadata_map[arxiv_id]
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


def convert(
    results_path: Path,
    metadata_path: Path,
    output_csv: Path,
) -> list[MetadataRecord]:
    metadata_map = load_metadata(metadata_path)
    payload = json.loads(results_path.read_text(encoding="utf-8"))

    csv_rows: list[Dict[str, Any]] = []
    resolved_records: list[MetadataRecord] = []

    for item in payload:
        title = str(item.get("title", "")).strip()
        abstract = str(item.get("abstract", "")).strip()
        verdict = str(item.get("final_verdict", "")).strip()
        metadata_record = resolve_metadata(item, metadata_map)
        if metadata_record is None:
            raise ConversionError(f"找不到對應 metadata：{title}")
        resolved_records.append(metadata_record)

        year = parse_year(metadata_record.published)
        doi = metadata_record.doi
        label, source = parse_verdict(verdict)

        csv_rows.append(
            {
                "id": metadata_record.arxiv_id,
                "title": title,
                "abstract": abstract,
                "doi": doi,
                "url": metadata_record.landing_url,
                "pdf_url": metadata_record.pdf_url,
                "year": year,
                "source_anchor": metadata_record.anchor or "",
                "source_term": metadata_record.search_term or "",
                "label": label,
                "decision_source": source,
                "final_verdict": verdict,
                "metadata_json": json.dumps(metadata_record.metadata, ensure_ascii=False),
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)

    return resolved_records


def ensure_cli_available(commands: Iterable[str]) -> None:
    for command in commands:
        if shutil.which(command) is None:
            raise ConversionError(f"找不到指令：{command}")


def run_dedup(input_csv: Path, output_csv: Path, threshold: float) -> None:
    subprocess.run(
        [
            "asreview",
            "data",
            "dedup",
            str(input_csv),
            str(output_csv),
            "--threshold",
            str(threshold),
        ],
        check=True,
    )


def enrich_openalex(csv_path: Path, email: str | None) -> int:
    df = pd.read_csv(csv_path)
    if df.empty:
        df["openalex_id"] = ""
        df.to_csv(csv_path, index=False)
        return 0
    if "openalex_id" not in df.columns:
        df["openalex_id"] = ""
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


def run_snowball(dedup_csv: Path, forward_csv: Path, backward_csv: Path, email: str | None, run_forward: bool, run_backward: bool) -> None:
    if run_forward:
        cmd = ["asreview", "data", "snowball", str(dedup_csv), str(forward_csv), "--forward"]
        if email:
            cmd.extend(["--email", email])
        subprocess.run(cmd, check=True)
    if run_backward:
        cmd = ["asreview", "data", "snowball", str(dedup_csv), str(backward_csv), "--backward"]
        if email:
            cmd.extend(["--email", email])
        subprocess.run(cmd, check=True)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_RESULTS, help="LatteReview 結果 JSON 路徑")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="原始 metadata JSON 路徑")
    parser.add_argument("--output-dir", type=Path, default=None, help="輸出資料夾，預設與輸入相同")
    parser.add_argument("--basename", default=DEFAULT_BASENAME, help="輸出檔案前綴")
    parser.add_argument("--email", default=None, help="OpenAlex 查詢用 email")
    parser.add_argument("--threshold", type=float, default=float(os.environ.get("ASREVIEW_DEDUP_THRESHOLD", 0.98)))
    parser.add_argument("--skip-forward", action="store_true", help="略過 forward snowball")
    parser.add_argument("--skip-backward", action="store_true", help="略過 backward snowball")
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

    asreview_csv = output_dir / f"{args.basename}_asreview.csv"
    dedup_csv = output_dir / f"{args.basename}_asreview_dedup.csv"
    forward_csv = output_dir / f"{args.basename}_asreview_forward.csv"
    backward_csv = output_dir / f"{args.basename}_asreview_backward.csv"

    converted_records = convert(args.input, args.metadata, asreview_csv)
    print(f"寫入 ASReview CSV：{asreview_csv} ({len(converted_records)} 筆)")

    run_dedup(asreview_csv, dedup_csv, args.threshold)
    print(f"去重輸出：{dedup_csv}")

    mapped = enrich_openalex(dedup_csv, args.email)
    print(f"OpenAlex 識別碼補齊：{mapped} 筆")

    run_snowball(
        dedup_csv,
        forward_csv,
        backward_csv,
        args.email,
        run_forward=not args.skip_forward,
        run_backward=not args.skip_backward,
    )
    print("雪球完成")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConversionError as exc:  # pragma: no cover - CLI 錯誤處理
        print(f"錯誤：{exc}", file=sys.stderr)
        raise SystemExit(1)
