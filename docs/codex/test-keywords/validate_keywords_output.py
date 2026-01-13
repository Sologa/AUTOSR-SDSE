#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from keywords_cli_utils import collect_arxiv_metadata, read_json


def _is_snake_case(value: str) -> bool:
    """Return True when value is snake_case (letters, digits, underscores)."""
    return all(part.isalnum() for part in value.split("_")) and value == value.lower()


def _term_word_count(term: str) -> int:
    """Return the number of space-delimited words in term."""
    return len(term.split())


def _normalize_space(text: str) -> str:
    """Normalize whitespace for comparisons."""
    return " ".join(text.split())


def validate_keywords_output(payload: Dict[str, Any]) -> List[str]:
    """Validate keywords output payload and return a list of errors."""
    errors: List[str] = []
    for key in ("run_id", "mode", "provider", "models", "topic", "prompt_path", "input_pdfs", "payload"):
        if key not in payload:
            errors.append(f"missing top-level key: {key}")

    if payload.get("mode") != "single":
        errors.append("mode must be 'single'")

    input_pdfs = payload.get("input_pdfs")
    if not isinstance(input_pdfs, list) or not input_pdfs:
        errors.append("input_pdfs must be a non-empty list")

    content = payload.get("payload")
    if not isinstance(content, dict):
        errors.append("payload must be an object")
        return errors

    for key in ("topic", "anchor_terms", "search_terms", "papers"):
        if key not in content:
            errors.append(f"payload missing key: {key}")

    anchor_terms = content.get("anchor_terms")
    if not isinstance(anchor_terms, list) or not anchor_terms:
        errors.append("anchor_terms must be a non-empty list")
    else:
        if len(anchor_terms) < 2 or len(anchor_terms) > 4:
            errors.append("anchor_terms must contain 2–4 items")
        normalized_topic = _normalize_space(str(content.get("topic", ""))).casefold()
        for term in anchor_terms:
            if not isinstance(term, str):
                errors.append("anchor_terms items must be strings")
                continue
            if "_" in term:
                errors.append(f"anchor_terms contains underscore: {term}")
            if _term_word_count(term) > 3:
                errors.append(f"anchor_terms exceeds 3 words: {term}")
            if normalized_topic and _normalize_space(term).casefold() == normalized_topic:
                errors.append(f"anchor_terms contains topic hint: {term}")

    search_terms = content.get("search_terms")
    if not isinstance(search_terms, dict) or not search_terms:
        errors.append("search_terms must be a non-empty object")
    else:
        total_terms = 0
        for category, terms in search_terms.items():
            if not isinstance(category, str):
                errors.append("search_terms category must be string")
                continue
            if not _is_snake_case(category):
                errors.append(f"search_terms category not snake_case: {category}")
            if not isinstance(terms, list):
                errors.append(f"search_terms.{category} must be a list")
                continue
            if not terms:
                errors.append(f"search_terms.{category} must be non-empty")
            total_terms += len(terms)
            for term in terms:
                if not isinstance(term, str):
                    errors.append(f"search_terms.{category} contains non-string term")
                    continue
                if "_" in term:
                    errors.append(f"search_terms.{category} term has underscore: {term}")
                if _term_word_count(term) > 3:
                    errors.append(f"search_terms.{category} term exceeds 3 words: {term}")
        if total_terms > 50:
            errors.append(f"search_terms total terms exceed 50: {total_terms}")

    papers = content.get("papers")
    if not isinstance(papers, list) or not papers:
        errors.append("papers must be a non-empty list")
        return errors

    if isinstance(input_pdfs, list) and input_pdfs:
        pdf_paths = [Path(path) for path in input_pdfs if isinstance(path, str)]
        if pdf_paths:
            metadata_list = collect_arxiv_metadata(pdf_paths)
            if len(metadata_list) != len(papers):
                errors.append("papers length does not match metadata length")
            for idx, meta in enumerate(metadata_list):
                if idx >= len(papers):
                    break
                paper = papers[idx]
                if not isinstance(paper, dict):
                    errors.append(f"papers[{idx}] must be an object")
                    continue
                for key in ("id", "source_id", "title", "abstract", "year", "source_url", "detected_keywords"):
                    if key not in paper:
                        errors.append(f"papers[{idx}] missing key: {key}")
                if _normalize_space(str(paper.get("title", ""))) != _normalize_space(meta["title"]):
                    errors.append(f"papers[{idx}] title mismatch for arXiv:{meta['arxiv_id']}")
                if _normalize_space(str(paper.get("abstract", ""))) != _normalize_space(meta["abstract"]):
                    errors.append(f"papers[{idx}] abstract mismatch for arXiv:{meta['arxiv_id']}")

    for idx, paper in enumerate(papers):
        if not isinstance(paper, dict):
            errors.append(f"papers[{idx}] must be an object")
            continue
        detected = paper.get("detected_keywords")
        if not isinstance(detected, list):
            errors.append(f"papers[{idx}].detected_keywords must be a list")
            continue
        for jdx, keyword in enumerate(detected):
            if not isinstance(keyword, dict):
                errors.append(f"papers[{idx}].detected_keywords[{jdx}] must be an object")
                continue
            for key in ("term", "category", "evidence", "confidence"):
                if key not in keyword:
                    errors.append(f"papers[{idx}].detected_keywords[{jdx}] missing key: {key}")
            evidence = keyword.get("evidence")
            if not isinstance(evidence, dict):
                errors.append(f"papers[{idx}].detected_keywords[{jdx}].evidence must be object")
                continue
            if "quote" not in evidence or "page" not in evidence:
                errors.append(f"papers[{idx}].detected_keywords[{jdx}].evidence missing quote/page")
            if not isinstance(evidence.get("page"), str):
                errors.append(f"papers[{idx}].detected_keywords[{jdx}].evidence.page must be string")

    return errors


def main() -> int:
    """CLI entrypoint for validating keywords output JSON."""
    parser = argparse.ArgumentParser(description="Validate keywords output JSON")
    parser.add_argument("path", help="Path to keywords output JSON")
    args = parser.parse_args()

    payload = read_json(Path(args.path))
    if not isinstance(payload, dict):
        print("payload must be JSON object")
        return 1

    errors = validate_keywords_output(payload)
    if errors:
        for err in errors:
            print(err)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
