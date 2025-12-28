#!/usr/bin/env python
"""Update snowball review registry from LatteReview results."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

FINAL_STATUSES = {"include", "exclude", "hard_exclude"}
STATUS_PRIORITY = {
    "include": 3,
    "exclude": 2,
    "hard_exclude": 1,
    "needs_enrichment": 0,
    "temp_discard": -1,
    "error": -2,
}
DEDUP_KEY_ORDER = ("openalex_id", "doi", "arxiv_id", "title")


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


def normalize_openalex_slug(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def normalize_doi_slug(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/"):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


def compute_criteria_hash(criteria_path: Optional[Path]) -> str:
    if not criteria_path or not criteria_path.exists():
        return ""
    return hashlib.sha256(criteria_path.read_bytes()).hexdigest()


def load_registry(registry_path: Path) -> Dict[str, Any]:
    if not registry_path.exists():
        return {"version": 1, "criteria_hash": "", "entries": []}
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"version": 1, "criteria_hash": "", "entries": []}
    if not isinstance(payload.get("entries"), list):
        payload["entries"] = []
    payload.setdefault("version", 1)
    payload.setdefault("criteria_hash", "")
    return payload


def entry_key_candidates(entry: Dict[str, Any]) -> List[tuple[str, str]]:
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


def build_index(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    index: Dict[str, Dict[str, int]] = {key: {} for key in DEDUP_KEY_ORDER}
    for idx, entry in enumerate(entries):
        for key_type, key_value in entry_key_candidates(entry):
            index.setdefault(key_type, {})[key_value] = idx
    return index


def classify_status(record: Dict[str, Any]) -> str:
    verdict = str(record.get("final_verdict") or "").strip().lower()
    if verdict.startswith("include"):
        return "include"
    if verdict.startswith("exclude"):
        return "exclude"
    if verdict.startswith("needs-review"):
        return "needs_enrichment"
    if verdict.startswith("discard"):
        return "hard_exclude"
    if record.get("review_skipped"):
        return "temp_discard"
    return "error"


def build_entry(
    record: Dict[str, Any],
    *,
    status: str,
    criteria_hash: str,
    round_index: Optional[int],
    source: str,
    now: str,
) -> Dict[str, Any]:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    title = str(record.get("title") or metadata.get("title") or "").strip()
    doi = record.get("doi") or metadata.get("doi") or ""
    openalex_id = record.get("openalex_id") or metadata.get("openalex_id") or ""
    arxiv_id = record.get("arxiv_id") or metadata.get("arxiv_id") or ""
    entry: Dict[str, Any] = {
        "status": status,
        "title": title,
        "normalized_title": normalize_title_slug(title),
        "doi": normalize_doi_slug(doi),
        "openalex_id": normalize_openalex_slug(openalex_id),
        "arxiv_id": normalize_arxiv_slug(arxiv_id),
        "criteria_hash": criteria_hash,
        "source": source,
        "updated_at": now,
    }
    if round_index is not None:
        entry["round"] = round_index
    return entry


def update_registry(
    review_results: Path,
    registry_path: Path,
    *,
    criteria_hash: str,
    round_index: Optional[int],
    source: str,
) -> Dict[str, Any]:
    payload = load_registry(registry_path)
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    index = build_index(entries)

    review_payload = json.loads(review_results.read_text(encoding="utf-8"))
    if not isinstance(review_payload, list):
        raise ValueError("review results must be a list")

    now = datetime.now(timezone.utc).isoformat()
    added = 0
    updated = 0
    skipped = 0

    for record in review_payload:
        if not isinstance(record, dict):
            skipped += 1
            continue
        status = classify_status(record)
        entry = build_entry(
            record,
            status=status,
            criteria_hash=criteria_hash,
            round_index=round_index,
            source=source,
            now=now,
        )
        candidates = entry_key_candidates(entry)
        if not candidates:
            skipped += 1
            continue
        match_idx = None
        for key_type, key_value in candidates:
            match_idx = index.get(key_type, {}).get(key_value)
            if match_idx is not None:
                break
        if match_idx is None:
            entries.append(entry)
            new_idx = len(entries) - 1
            for key_type, key_value in candidates:
                index.setdefault(key_type, {})[key_value] = new_idx
            added += 1
            continue

        existing = entries[match_idx]
        existing_status = str(existing.get("status") or "")
        if STATUS_PRIORITY.get(status, -99) > STATUS_PRIORITY.get(existing_status, -99):
            existing["status"] = status
            updated += 1
        for field in ("title", "normalized_title", "doi", "openalex_id", "arxiv_id"):
            if not existing.get(field) and entry.get(field):
                existing[field] = entry.get(field)
        if criteria_hash:
            existing["criteria_hash"] = criteria_hash
        existing["updated_at"] = now
        if round_index is not None:
            existing["round"] = round_index
        existing["source"] = source

    payload["entries"] = entries
    payload["criteria_hash"] = criteria_hash or payload.get("criteria_hash") or ""
    payload["updated_at"] = now
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "total_entries": len(entries),
    }


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-results", type=Path, required=True, help="LatteReview 輸出 JSON")
    parser.add_argument("--registry", type=Path, required=True, help="review_registry.json")
    parser.add_argument("--criteria", type=Path, default=None, help="criteria.json（用於計算 criteria_hash）")
    parser.add_argument("--round", type=int, default=None, help="round index")
    parser.add_argument("--source", default="latte_review", help="來源標記")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if not args.review_results.exists():
        raise FileNotFoundError(f"找不到 review results：{args.review_results}")
    criteria_hash = compute_criteria_hash(args.criteria)
    summary = update_registry(
        args.review_results,
        args.registry,
        criteria_hash=criteria_hash,
        round_index=args.round,
        source=args.source,
    )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
