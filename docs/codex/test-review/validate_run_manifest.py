#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from review_cli_utils import read_json


def validate_manifest(payload: Dict[str, Any]) -> List[str]:
    """Validate the run manifest payload and return a list of errors."""
    errors: List[str] = []
    for key in ("run_id", "created_at", "input_source", "criteria_source", "outputs", "commands"):
        if key not in payload:
            errors.append(f"missing top-level key: {key}")

    outputs = payload.get("outputs")
    if not isinstance(outputs, list):
        errors.append("outputs must be list")
    else:
        for idx, item in enumerate(outputs):
            if not isinstance(item, dict):
                errors.append(f"outputs[{idx}] is not object")
                continue
            for key in ("name", "path", "mode", "provider"):
                if key not in item:
                    errors.append(f"outputs[{idx}] missing {key}")

    commands = payload.get("commands")
    if not isinstance(commands, list):
        errors.append("commands must be list")
    else:
        for idx, item in enumerate(commands):
            if not isinstance(item, dict):
                errors.append(f"commands[{idx}] is not object")
                continue
            for key in ("provider", "command"):
                if key not in item:
                    errors.append(f"commands[{idx}] missing {key}")

    return errors


def main() -> int:
    """CLI entrypoint for validating run manifest JSON."""
    parser = argparse.ArgumentParser(description="Validate run manifest JSON")
    parser.add_argument("path", help="Path to run_manifest.json")
    args = parser.parse_args()

    payload = read_json(Path(args.path))
    if not isinstance(payload, dict):
        print("payload must be JSON object")
        return 1

    errors = validate_manifest(payload)
    if errors:
        for err in errors:
            print(err)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
