from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable

FIXTURE_JSON = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "semantic_scholar_single_query_metadata.json"
)


def _iter_rows(payload: Iterable[Dict[str, Any]]) -> list[Dict[str, str]]:
    rows: list[Dict[str, str]] = []
    seen_doi: set[str] = set()

    for entry in payload:
        metadata = entry.get("metadata") or {}
        search_record = entry.get("search_record") or {}
        external_ids = metadata.get("externalIds") or {}

        doi = (external_ids.get("DOI") or "").strip()
        if not doi or doi in seen_doi:
            continue

        title = (metadata.get("title") or search_record.get("title") or "").strip()
        if not title:
            continue

        abstract: str = (
            metadata.get("abstract")
            or ((metadata.get("tldr") or {}).get("text") if isinstance(metadata.get("tldr"), dict) else "")
            or ""
        ).strip()

        openaccess = metadata.get("openAccessPdf")
        if isinstance(openaccess, dict):
            pdf_url = openaccess.get("url") or ""
        else:
            pdf_url = ""

        row = {
            "id": str(metadata.get("paperId") or search_record.get("paperId") or ""),
            "title": title,
            "abstract": abstract,
            "doi": doi,
            "url": (metadata.get("url") or search_record.get("url") or "").strip(),
            "pdf_url": pdf_url.strip(),
            "year": str(metadata.get("year") or search_record.get("year") or ""),
            "source_anchor": str(entry.get("anchor") or ""),
            "source_term": str(entry.get("search_term") or ""),
        }

        rows.append(row)
        seen_doi.add(doi)

    rows.sort(key=lambda item: item["doi"])
    return rows


def test_convert_semantic_scholar_metadata_to_asreview_csv(tmp_path: Path) -> None:
    assert FIXTURE_JSON.exists(), f"Missing fixture file: {FIXTURE_JSON}"

    payload = json.loads(FIXTURE_JSON.read_text(encoding="utf-8"))
    rows = _iter_rows(payload)

    assert rows, "No Semantic Scholar records with DOI were found"

    output_csv = tmp_path / "semantic_scholar_single_query_asreview.csv"

    fieldnames = list(rows[0].keys())

    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with output_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        result_rows = list(reader)

    assert result_rows, "Converted ASReview dataset unexpectedly empty"
    assert len(result_rows) == len(rows)

    required_columns = {"title", "doi"}
    for record in result_rows:
        missing = [column for column in required_columns if not record.get(column)]
        assert not missing, f"Record missing required values {missing}: {record}"

    doi_set = {record["doi"].strip() for record in result_rows}
    assert len(doi_set) == len(result_rows), "Duplicate DOI detected in ASReview dataset"
