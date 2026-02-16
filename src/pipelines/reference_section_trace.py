#!/usr/bin/env python3
"""Trace LaTeX citation keys back to section labels for a target paper."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


COMMENT_RE = re.compile(r"(?<!\\)%.*")
TOKEN_RE = re.compile(
    r"\\(?P<section>section|subsection|subsubsection)\*?\{(?P<section_title>[^}]*)\}"
    r"|\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)?(?:\[[^\]]*\]\s*)?\{(?P<cites>[^}]*)\}"
    r"|\\(?P<input_cmd>input|include)\{(?P<input_path>[^}]*)\}",
    re.DOTALL,
)


@dataclass
class SectionContext:
    """Track current section state while scanning LaTeX sources."""

    section: Optional[str] = None
    subsection: Optional[str] = None
    subsubsection: Optional[str] = None

    def update(self, level: str, title: str) -> None:
        if level == "section":
            self.section = title
            self.subsection = None
            self.subsubsection = None
            return
        if level == "subsection":
            self.subsection = title
            self.subsubsection = None
            return
        if level == "subsubsection":
            self.subsubsection = title
            return
        raise ValueError(f"Unknown section level: {level}")


def strip_comments(text: str) -> str:
    """Remove LaTeX comments while preserving escaped percent signs."""
    return "\n".join(COMMENT_RE.sub("", line) for line in text.splitlines())


def normalize_title(text: str) -> str:
    """Collapse whitespace to keep section titles stable."""
    return re.sub(r"\s+", " ", text).strip()


def split_cite_keys(text: str) -> List[str]:
    return [part.strip() for part in text.replace("\n", " ").split(",") if part.strip()]


def resolve_tex_path(raw_path: str, current_dir: Path, root_dir: Path) -> Optional[Path]:
    raw_path = raw_path.strip()
    candidate = Path(raw_path)
    candidates = [candidate] if candidate.suffix else [candidate.with_suffix(".tex"), candidate]

    for item in candidates:
        if item.is_absolute() and item.exists():
            return item
        local_path = current_dir / item
        if local_path.exists():
            return local_path
        root_path = root_dir / item
        if root_path.exists():
            return root_path
    return None


def build_section_label(
    rel_path: Path,
    context: SectionContext,
    level: str,
) -> str:
    path_label = rel_path.as_posix()
    section = context.section or ""
    subsection = context.subsection or ""
    subsubsection = context.subsubsection or ""

    if level == "file":
        return path_label
    if level == "section":
        return f"{path_label}#{section}" if section else path_label
    if level == "subsection":
        if section and subsection:
            return f"{path_label}#{section} / {subsection}"
        if section:
            return f"{path_label}#{section}"
        return path_label
    if level == "subsubsection":
        if section and subsection and subsubsection:
            return f"{path_label}#{section} / {subsection} / {subsubsection}"
        if section and subsection:
            return f"{path_label}#{section} / {subsection}"
        if section:
            return f"{path_label}#{section}"
        return path_label
    raise ValueError(f"Unknown level: {level}")


def collect_citations(
    main_tex: Path,
    root_dir: Path,
    level: str,
) -> Tuple[Dict[str, Counter], List[str]]:
    citations: Dict[str, Counter] = defaultdict(Counter)
    missing_includes: List[str] = []
    visited: Set[Path] = set()
    context = SectionContext()

    def walk(path: Path) -> None:
        if path in visited:
            return
        visited.add(path)

        text = strip_comments(path.read_text(encoding="utf-8", errors="ignore"))
        rel_path = path.relative_to(root_dir) if path.is_relative_to(root_dir) else path

        for match in TOKEN_RE.finditer(text):
            if match.group("section"):
                context.update(match.group("section"), normalize_title(match.group("section_title")))
                continue

            if match.group("cites"):
                section_label = build_section_label(rel_path, context, level)
                for key in split_cite_keys(match.group("cites")):
                    citations[key][section_label] += 1
                continue

            if match.group("input_cmd"):
                resolved = resolve_tex_path(match.group("input_path"), path.parent, root_dir)
                if resolved is None:
                    missing_includes.append(match.group("input_path"))
                else:
                    walk(resolved)

    walk(main_tex)
    return citations, sorted(set(missing_includes))


def load_oracle(path: Path) -> Tuple[Dict[str, dict], List[str]]:
    records: Dict[str, dict] = {}
    order: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        key = str(data.get("key") or "").strip()
        if not key:
            continue
        if key not in records:
            order.append(key)
        records[key] = data
    return records, order


def load_arxiv_metadata(path: Path) -> Tuple[Dict[str, dict], List[str]]:
    records: Dict[str, dict] = {}
    order: List[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data:
        metadata = entry.get("metadata") or {}
        key = str(metadata.get("key") or "").strip()
        if not key:
            continue
        if "arxiv_id" not in metadata and entry.get("arxiv_id"):
            metadata["arxiv_id"] = entry.get("arxiv_id")
        if key not in records:
            order.append(key)
        records[key] = metadata
    return records, order


def build_record(
    key: str,
    oracle: Optional[dict],
    metadata: Optional[dict],
    section_counts: Counter,
) -> dict:
    record: dict = {}
    if oracle:
        record.update(oracle)
    else:
        record["key"] = key

    if metadata:
        record.setdefault("query_title", metadata.get("title"))
        record.setdefault("normalized_title", metadata.get("normalized_title"))
        record.setdefault("source", "arxiv_metadata")
        record["arxiv_id"] = metadata.get("arxiv_id")
        record["metadata_title"] = metadata.get("title")
        record["metadata_source"] = metadata.get("source")
        record["match_status"] = metadata.get("match_status")

    record["section_hits"] = [
        {"section": section, "count": count}
        for section, count in sorted(section_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    record["sections"] = sorted(section_counts.keys())
    record["total_citations"] = sum(section_counts.values())
    record["missing_in_sections"] = record["total_citations"] == 0
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-dir", required=True)
    parser.add_argument("--main-tex", default=None)
    parser.add_argument("--oracle-jsonl", default=None)
    parser.add_argument("--arxiv-metadata", default=None)
    parser.add_argument("--out-json", default=None)
    parser.add_argument("--out-csv", default=None)
    parser.add_argument(
        "--level",
        choices=("file", "section", "subsection", "subsubsection"),
        default="section",
    )
    args = parser.parse_args()

    paper_dir = Path(args.paper_dir)
    main_tex = Path(args.main_tex) if args.main_tex else paper_dir / "tmlr_main_arxiv.tex"
    if not main_tex.exists():
        raise SystemExit(f"Main tex not found: {main_tex}")

    oracle_path = Path(args.oracle_jsonl) if args.oracle_jsonl else paper_dir / "reference_oracle.jsonl"
    oracle_records: Dict[str, dict] = {}
    oracle_order: List[str] = []
    if oracle_path.exists():
        oracle_records, oracle_order = load_oracle(oracle_path)

    arxiv_path = Path(args.arxiv_metadata) if args.arxiv_metadata else None
    metadata_records: Dict[str, dict] = {}
    metadata_order: List[str] = []
    if arxiv_path and arxiv_path.exists():
        metadata_records, metadata_order = load_arxiv_metadata(arxiv_path)

    if not oracle_records and not metadata_records:
        raise SystemExit("No oracle or arxiv metadata input found.")

    keys: List[str] = []
    keys.extend(oracle_order)
    for key in metadata_order:
        if key not in keys:
            keys.append(key)

    citations, missing_includes = collect_citations(main_tex, paper_dir, args.level)

    records = [
        build_record(
            key,
            oracle_records.get(key),
            metadata_records.get(key),
            citations.get(key, Counter()),
        )
        for key in keys
    ]

    input_keys = set(keys)
    missing_keys = sorted(key for key in keys if key not in citations)
    unmatched_citations = sorted(key for key in citations.keys() if key not in input_keys)

    output = {
        "paper_dir": str(paper_dir),
        "main_tex": str(main_tex),
        "section_level": args.level,
        "records": records,
        "missing_keys": missing_keys,
        "unmatched_citations": unmatched_citations,
        "missing_includes": missing_includes,
    }

    out_json = Path(args.out_json) if args.out_json else paper_dir / "reference_section_map.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(output, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    if args.out_csv:
        out_csv = Path(args.out_csv)
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["key", "section", "count"])
            for key in keys:
                for section, count in citations.get(key, Counter()).items():
                    writer.writerow([key, section, count])

    print(f"Wrote: {out_json}")
    if args.out_csv:
        print(f"Wrote: {args.out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
