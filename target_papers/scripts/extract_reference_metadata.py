#!/usr/bin/env python3
"""Extract titles from BibTeX and enrich with arXiv metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from title_normalization import normalize_title


ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


@dataclass
class BibEntry:
    entry_type: str
    key: Optional[str]
    fields: Dict[str, str]
    raw_fields: Dict[str, str]


class BibTexError(RuntimeError):
    pass


def parse_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    value = value.strip().lower()
    if value in {"1", "true", "yes", "y"}:
        return True
    if value in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value}")


def find_matching(text: str, open_idx: int, open_char: str, close_char: str) -> int:
    level = 0
    for idx in range(open_idx, len(text)):
        ch = text[idx]
        if ch == open_char:
            level += 1
        elif ch == close_char:
            level -= 1
            if level == 0:
                return idx
    raise BibTexError("Unmatched entry delimiter")


def split_key_and_body(body: str) -> Tuple[str, str]:
    depth = 0
    in_quote = False
    escape = False
    for idx, ch in enumerate(body):
        if in_quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_quote = False
        else:
            if ch == '"':
                in_quote = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
            elif ch == "," and depth == 0:
                key = body[:idx].strip()
                rest = body[idx + 1 :]
                return key, rest
    raise BibTexError("Missing citation key or field body")


def parse_value_expression(body: str, start: int) -> Tuple[str, int]:
    depth = 0
    in_quote = False
    escape = False
    idx = start
    while idx < len(body):
        ch = body[idx]
        if in_quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_quote = False
        else:
            if ch == '"':
                in_quote = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
            elif ch == "," and depth == 0:
                break
        idx += 1
    return body[start:idx].strip(), idx


def split_concat_parts(expr: str) -> List[str]:
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    in_quote = False
    escape = False
    for ch in expr:
        if in_quote:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_quote = False
            continue

        if ch == '"':
            in_quote = True
            buf.append(ch)
            continue
        if ch == "{":
            depth += 1
            buf.append(ch)
            continue
        if ch == "}" and depth > 0:
            depth -= 1
            buf.append(ch)
            continue
        if ch == "#" and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            continue
        buf.append(ch)
    part = "".join(buf).strip()
    if part:
        parts.append(part)
    return parts


def eval_expr(expr: str, string_macros: Dict[str, str]) -> str:
    parts = split_concat_parts(expr)
    if not parts:
        return ""
    values: List[str] = []
    for part in parts:
        piece = part.strip()
        if not piece:
            continue
        if piece.startswith("{") and piece.endswith("}"):
            values.append(piece[1:-1])
        elif piece.startswith('"') and piece.endswith('"'):
            values.append(piece[1:-1])
        else:
            macro = string_macros.get(piece.lower())
            values.append(macro if macro is not None else piece)
    return "".join(values).strip()


def parse_fields(body: str, string_macros: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    fields: Dict[str, str] = {}
    raw_fields: Dict[str, str] = {}
    idx = 0
    while idx < len(body):
        while idx < len(body) and body[idx] in "\n\r\t ,":
            idx += 1
        if idx >= len(body):
            break
        start = idx
        while idx < len(body) and (body[idx].isalnum() or body[idx] in "_-:"):
            idx += 1
        name = body[start:idx].strip().lower()
        if not name:
            break
        while idx < len(body) and body[idx].isspace():
            idx += 1
        if idx >= len(body) or body[idx] != "=":
            # Skip malformed field.
            while idx < len(body) and body[idx] != ",":
                idx += 1
            idx += 1
            continue
        idx += 1
        while idx < len(body) and body[idx].isspace():
            idx += 1
        expr, idx = parse_value_expression(body, idx)
        raw_fields[name] = expr
        fields[name] = eval_expr(expr, string_macros) if expr else ""
        if idx < len(body) and body[idx] == ",":
            idx += 1
    return fields, raw_fields


def parse_bibtex(text: str) -> Tuple[List[BibEntry], Dict[str, str]]:
    entries: List[BibEntry] = []
    string_macros: Dict[str, str] = {}
    idx = 0
    while idx < len(text):
        at_pos = text.find("@", idx)
        if at_pos == -1:
            break
        idx = at_pos + 1
        while idx < len(text) and text[idx].isspace():
            idx += 1
        start = idx
        while idx < len(text) and text[idx].isalpha():
            idx += 1
        entry_type = text[start:idx].strip().lower()
        if not entry_type:
            continue
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text) or text[idx] not in "({":
            continue
        open_char = text[idx]
        close_char = ")" if open_char == "(" else "}"
        open_idx = idx
        close_idx = find_matching(text, open_idx, open_char, close_char)
        body = text[open_idx + 1 : close_idx]
        idx = close_idx + 1

        if entry_type in {"comment", "preamble"}:
            continue

        if entry_type == "string":
            fields, _ = parse_fields(body, string_macros)
            for key, value in fields.items():
                if key:
                    string_macros[key.lower()] = value
            continue

        try:
            key, field_body = split_key_and_body(body)
        except BibTexError:
            continue
        fields, raw_fields = parse_fields(field_body, string_macros)
        entries.append(
            BibEntry(entry_type=entry_type, key=key, fields=fields, raw_fields=raw_fields)
        )
    return entries, string_macros


def discover_bib(paper_dir: Optional[str], bib_path: Optional[str]) -> Path:
    if bib_path:
        path = Path(bib_path)
        if not path.exists():
            raise FileNotFoundError(f"BibTeX not found: {path}")
        return path
    if not paper_dir:
        raise FileNotFoundError("Either --paper-dir or --bib-path is required")
    base = Path(paper_dir)
    bibs = sorted(base.glob("*.bib"))
    if not bibs:
        raise FileNotFoundError(f"No .bib found in {base}")
    if len(bibs) > 1:
        raise FileExistsError(f"Multiple .bib files in {base}; use --bib-path")
    return bibs[0]


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_arxiv_url(title: str, max_results: int) -> str:
    query = f'ti:"{title}"'
    encoded = urllib.parse.quote(query)
    return f"{ARXIV_API_URL}?search_query={encoded}&start=0&max_results={max_results}"


def fetch_arxiv_feed(url: str, timeout: int) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8")


def parse_arxiv_feed(feed: str) -> List[dict]:
    root = ET.fromstring(feed)
    ns = {"atom": ATOM_NS, "arxiv": ARXIV_NS}
    results: List[dict] = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
        doi = ""
        doi_elem = entry.find("arxiv:doi", ns)
        if doi_elem is not None and doi_elem.text:
            doi = doi_elem.text.strip()
        primary_category = ""
        cat_elem = entry.find("arxiv:primary_category", ns)
        if cat_elem is not None:
            primary_category = cat_elem.attrib.get("term", "")
        authors = [
            author.findtext("atom:name", default="", namespaces=ns).strip()
            for author in entry.findall("atom:author", ns)
        ]
        url = entry_id
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("rel") == "alternate" and link.attrib.get("href"):
                url = link.attrib["href"]
                break
        results.append(
            {
                "id": entry_id,
                "title": title,
                "authors": [a for a in authors if a],
                "published": published,
                "doi": doi,
                "url": url,
                "primary_category": primary_category,
            }
        )
    return results


def score_title(query_norm: str, candidate_norm: str) -> float:
    if not query_norm or not candidate_norm:
        return 0.0
    # Simple character overlap ratio.
    from difflib import SequenceMatcher

    return SequenceMatcher(None, query_norm, candidate_norm).ratio()


def choose_best_match(query_norm: str, candidates: List[dict]) -> Tuple[Optional[dict], float]:
    best = None
    best_score = 0.0
    for cand in candidates:
        cand_norm = normalize_title(cand.get("title", ""))
        score = score_title(query_norm, cand_norm)
        if score > best_score:
            best_score = score
            best = cand
    return best, best_score


def load_cache(cache_dir: Path, cache_key: str) -> Optional[str]:
    cache_path = cache_dir / f"{cache_key}.json"
    if not cache_path.exists():
        return None
    with cache_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("response")


def save_cache(cache_dir: Path, cache_key: str, response: str, query_title: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{cache_key}.json"
    payload = {
        "query_title": query_title,
        "response": response,
    }
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def hash_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-dir", type=str, default=None)
    parser.add_argument("--bib-path", type=str, default=None)
    parser.add_argument("--out-jsonl", type=str, required=True)
    parser.add_argument("--cache-dir", type=str, default="target_papers/.cache/arxiv")
    parser.add_argument("--use-arxiv", type=parse_bool, default=False)
    parser.add_argument("--min-score", type=float, default=0.85)
    parser.add_argument("--max-rps", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--entry-types", type=str, default="all")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    bib_path = discover_bib(args.paper_dir, args.bib_path)
    logging.info("Using BibTeX: %s", bib_path)

    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    entries, _ = parse_bibtex(text)
    entry_types_arg = (args.entry_types or "").strip().lower()
    if entry_types_arg in {"", "all", "*"}:
        entry_types = {entry.entry_type for entry in entries}
    else:
        entry_types = {t.strip().lower() for t in args.entry_types.split(",") if t.strip()}

    selected = [
        entry
        for entry in entries
        if entry.entry_type in entry_types and "title" in entry.fields
    ]
    logging.info("Entry types included: %s", ", ".join(sorted(entry_types)))
    logging.info("Selected entries: %d", len(selected))

    out_path = Path(args.out_jsonl)
    ensure_dir(out_path)
    cache_dir = Path(args.cache_dir)

    errors: List[str] = []
    last_request_time = 0.0

    with out_path.open("w", encoding="utf-8") as handle:
        for entry in selected:
            raw_title = entry.raw_fields.get("title", "").strip()
            query_title = raw_title or entry.fields.get("title", "").strip()
            normalized = normalize_title(query_title)
            record = {
                "key": entry.key,
                "entry_type": entry.entry_type,
                "query_title": query_title,
                "normalized_title": normalized,
                "matched": False,
                "match_score": 0.0,
                "arxiv": None,
                "sources": {"query_title": "local"},
                "raw": {"local": entry.raw_fields},
            }

            if args.use_arxiv and normalized:
                cache_key = hash_key(normalized)
                cached = load_cache(cache_dir, cache_key)
                response_text = None
                source_label = "arxiv"
                if cached is not None:
                    response_text = cached
                    source_label = "cache"
                else:
                    # Rate limiting.
                    if args.max_rps > 0:
                        delay = max(0.0, (1.0 / args.max_rps) - (time.time() - last_request_time))
                        if delay > 0:
                            time.sleep(delay)
                    search_title = normalized or query_title
                    url = build_arxiv_url(search_title, max_results=5)
                    for attempt in range(3):
                        try:
                            response_text = fetch_arxiv_feed(url, args.timeout)
                            save_cache(cache_dir, cache_key, response_text, query_title)
                            last_request_time = time.time()
                            break
                        except urllib.error.HTTPError as exc:
                            if exc.code in {429} or exc.code >= 500:
                                backoff = 2**attempt
                                time.sleep(backoff)
                                continue
                            errors.append(f"HTTP error for {entry.key}: {exc}")
                            response_text = None
                            break
                        except urllib.error.URLError as exc:
                            backoff = 2**attempt
                            time.sleep(backoff)
                            if attempt == 2:
                                errors.append(f"Network error for {entry.key}: {exc}")
                            continue
                        except Exception as exc:  # noqa: BLE001
                            errors.append(f"Unexpected error for {entry.key}: {exc}")
                            response_text = None
                            break

                if response_text:
                    try:
                        candidates = parse_arxiv_feed(response_text)
                        best, score = choose_best_match(normalized, candidates)
                        record["match_score"] = round(score, 4)
                        if best and score >= args.min_score:
                            record["matched"] = True
                            record["arxiv"] = best
                            record["sources"]["arxiv"] = source_label
                            record["raw"]["arxiv"] = best
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"Parse error for {entry.key}: {exc}")

            handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    if errors:
        logging.error("Completed with %d errors", len(errors))
        for err in errors:
            logging.error(err)
        return 2

    logging.info("Completed without errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
