#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import requests


_MARKDOWN_LINK = re.compile(r"\((https?://[^)\s]+)\)")
_ANGLE_LINK = re.compile(r"<(https?://[^>\s]+)>")


def _iter_markdown_files(root: Path) -> Iterable[Path]:
    """Yield markdown files under root."""
    yield from root.rglob("*.md")


def _extract_links(text: str) -> List[str]:
    """Extract http(s) links from markdown content."""
    links = _MARKDOWN_LINK.findall(text)
    links.extend(_ANGLE_LINK.findall(text))
    cleaned: List[str] = []
    for link in links:
        link = link.strip().rstrip(".,;")
        if link:
            cleaned.append(link)
    return cleaned


def _check_url(url: str, timeout: int) -> Tuple[int | None, str | None]:
    """Return (status_code, error) for a URL."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout)
        if response.status_code >= 400:
            response = requests.get(url, allow_redirects=True, timeout=timeout)
        return response.status_code, None
    except requests.RequestException as exc:
        return None, f"{exc.__class__.__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check markdown links under a root directory")
    parser.add_argument("--root", type=Path, default=Path("docs/codex"))
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args()

    root = args.root
    if not root.exists():
        print(f"root not found: {root}")
        return 1

    url_to_files: Dict[str, List[str]] = defaultdict(list)
    for path in _iter_markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for link in _extract_links(text):
            url_to_files[link].append(str(path))

    results = []
    for url in sorted(url_to_files):
        status, error = _check_url(url, timeout=args.timeout)
        results.append(
            {
                "url": url,
                "status": status,
                "error": error,
                "files": url_to_files[url],
            }
        )

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "total_urls": len(results),
        "failed": [entry for entry in results if entry["status"] is None or entry["status"] >= 400],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {"summary": summary, "results": results}
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote report: {args.output}")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
