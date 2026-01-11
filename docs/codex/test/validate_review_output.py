#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from review_cli_utils import read_json


def _is_int_in_range(value: Any, low: int, high: int) -> bool:
    """Return True when value is an integer within the inclusive range."""
    if not isinstance(value, int):
        return False
    return low <= value <= high


def validate_review_output(payload: Dict[str, Any]) -> List[str]:
    """Validate the review output payload and return a list of errors."""
    errors: List[str] = []
    for key in ("run_id", "mode", "items", "criteria_source", "criteria"):
        if key not in payload:
            errors.append(f"missing top-level key: {key}")

    mode = payload.get("mode")
    if mode not in ("single", "full"):
        errors.append("mode must be 'single' or 'full'")

    criteria = payload.get("criteria")
    if isinstance(criteria, dict):
        if "inclusion" not in criteria or "exclusion" not in criteria:
            errors.append("criteria must include inclusion and exclusion")
    else:
        errors.append("criteria must be an object")

    items = payload.get("items")
    if not isinstance(items, list):
        errors.append("items must be a list")
        return errors

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"item[{idx}] is not an object")
            continue
        for key in ("index", "arxiv_id", "title", "abstract", "missing_fields"):
            if key not in item:
                errors.append(f"item[{idx}] missing key: {key}")
        if mode == "single":
            if item.get("error"):
                continue
            if not _is_int_in_range(item.get("evaluation"), 1, 5):
                errors.append(f"item[{idx}] evaluation must be int 1-5")
            if not isinstance(item.get("reasoning"), str):
                errors.append(f"item[{idx}] reasoning must be string")
        if mode == "full":
            rounds = item.get("rounds")
            if not isinstance(rounds, dict):
                errors.append(f"item[{idx}] rounds must be object")
                continue
            round_a = rounds.get("A")
            if not isinstance(round_a, dict):
                errors.append(f"item[{idx}] rounds.A missing")
                continue
            for reviewer in ("JuniorNano", "JuniorMini"):
                reviewer_obj = round_a.get(reviewer)
                if not isinstance(reviewer_obj, dict):
                    errors.append(f"item[{idx}] rounds.A.{reviewer} missing")
                    continue
                if reviewer_obj.get("error"):
                    continue
                if not _is_int_in_range(reviewer_obj.get("evaluation"), 1, 5):
                    errors.append(f"item[{idx}] rounds.A.{reviewer}.evaluation invalid")
                if not isinstance(reviewer_obj.get("reasoning"), str):
                    errors.append(f"item[{idx}] rounds.A.{reviewer}.reasoning invalid")
    return errors


def main() -> int:
    """CLI entrypoint for validating review output JSON."""
    parser = argparse.ArgumentParser(description="Validate review output JSON")
    parser.add_argument("path", help="Path to review output JSON")
    args = parser.parse_args()

    payload = read_json(Path(args.path))
    if not isinstance(payload, dict):
        print("payload must be JSON object")
        return 1

    errors = validate_review_output(payload)
    if errors:
        for err in errors:
            print(err)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
