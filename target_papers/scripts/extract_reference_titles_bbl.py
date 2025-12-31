#!/usr/bin/env python3
"""Extract reference titles from a .bbl file (special-case)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterator, Optional, Tuple

from title_normalization import normalize_title


_BIBITEM_RE = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}")


def split_entries(text: str) -> Iterator[str]:
    positions = [match.start() for match in re.finditer(r"\\bibitem", text)]
    for idx, start in enumerate(positions):
        end = positions[idx + 1] if idx + 1 < len(positions) else len(text)
        yield text[start:end]


def parse_entry(entry_text: str) -> Tuple[Optional[str], Optional[str]]:
    match = _BIBITEM_RE.search(entry_text)
    key = match.group(1).strip() if match else None

    parts = entry_text.split("\\newblock")
    if len(parts) < 2:
        return key, None

    raw_title = parts[1].strip()
    title = re.sub(r"\s+", " ", raw_title).strip()
    if title.endswith("."):
        title = title[:-1].strip()

    return key, title


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbl-path", type=str, required=True)
    parser.add_argument("--out-jsonl", type=str, required=True)
    args = parser.parse_args()

    bbl_path = Path(args.bbl_path)
    text = bbl_path.read_text(encoding="utf-8", errors="ignore")

    out_path = Path(args.out_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for entry in split_entries(text):
            key, title = parse_entry(entry)
            if not title:
                continue
            record = {
                "key": key,
                "query_title": title,
                "normalized_title": normalize_title(title),
                "source": "bbl",
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
            count += 1

    print(f"Extracted titles: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
