"""Helpers for live paper download workflows and search orchestration."""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, MutableMapping, Optional, Sequence

import requests

from .env import load_env_file
from .paper_downloaders import (
    DownloadResult,
    PaperDownloadError,
    download_arxiv_paper,
    download_dblp_entry,
    download_semantic_scholar_paper,
)


load_env_file()


# Precompile patterns / helpers used across search utilities.
_ARXIV_ID_PATTERN = re.compile(r"(\d{4}\.\d{5,})(?:v\d+)?")
# Official guideline caps anonymous traffic at roughly 100 requests / 5 minutes.
_SEMANTIC_RATE_LIMIT_SECONDS_WITH_KEY = 1.0
_SEMANTIC_RATE_LIMIT_SECONDS_ANON = 3.0

_semantic_last_call: float = 0.0



def collect_arxiv_ids(pdf_root: Path) -> List[str]:
    """Return trimmed arXiv identifiers for all PDFs under ``pdf_root``."""

    ids = {trim_arxiv_id(path.stem) for path in pdf_root.rglob("*.pdf")}
    return sorted(identifier for identifier in ids if identifier)


def trim_arxiv_id(stem: str) -> Optional[str]:
    """Normalise a filename stem into a standard five-digit arXiv identifier."""

    match = _ARXIV_ID_PATTERN.match(stem)
    if not match:
        return None
    identifier = match.group(1)
    prefix, suffix = identifier.split(".", 1)
    return f"{prefix}.{suffix[:5]}"


def dblp_key_for_arxiv_id(arxiv_id: str) -> str:
    """Translate an arXiv identifier into the corresponding DBLP ``corr`` key."""

    return f"journals/corr/abs-{arxiv_id.replace('.', '-')}"


def _quote_term(term: str) -> str:
    """Return a double-quoted term with embedded quotes escaped."""

    escaped = term.replace("\\", r"\\").replace('"', r"\"")
    return f'"{escaped}"'


def build_semantic_scholar_query(anchor_terms: Sequence[str], search_terms: Sequence[str]) -> str:
    """Construct a Semantic Scholar boolean query from anchor and search terms."""

    anchor_fragment = " OR ".join(_quote_term(term) for term in anchor_terms)
    search_fragment = " OR ".join(_quote_term(term) for term in search_terms)
    return f"({anchor_fragment}) AND ({search_fragment})"


def respect_semantic_scholar_rate_limit(api_key_present: bool) -> None:
    """Sleep as needed to satisfy Semantic Scholar's per-second rate policy."""

    global _semantic_last_call

    min_interval = (
        _SEMANTIC_RATE_LIMIT_SECONDS_WITH_KEY
        if api_key_present
        else _SEMANTIC_RATE_LIMIT_SECONDS_ANON
    )
    now = time.monotonic()
    wait_for = min_interval - (now - _semantic_last_call)
    if wait_for > 0:
        time.sleep(wait_for)
    _semantic_last_call = time.monotonic()


def search_arxiv_for_topic(
    session: requests.Session,
    anchor_terms: Sequence[str],
    search_terms: Sequence[str],
    *,
    max_results: int = 50,
) -> List[Dict[str, object]]:
    """Search arXiv for a topic and return Atom entries as dictionaries."""

    anchor_clause = " OR ".join(f"ti:{_quote_term(term)}" for term in anchor_terms)
    search_clause = " OR ".join(f"ti:{_quote_term(term)}" for term in search_terms)
    params = {"search_query": f"({anchor_clause}) AND ({search_clause})", "start": 0, "max_results": max_results}
    response = session.get("https://export.arxiv.org/api/query", params=params, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    records: List[Dict[str, object]] = []
    for entry in root.findall("atom:entry", ns):
        records.append(
            {
                "id": entry.findtext("atom:id", default="", namespaces=ns),
                "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip(),
                "summary": (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip(),
                "published": entry.findtext("atom:published", default="", namespaces=ns),
            }
        )
    return records


def search_semantic_scholar_for_topic(
    session: requests.Session,
    anchor_terms: Sequence[str],
    search_terms: Sequence[str],
    *,
    api_key: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, object]]:
    """Search Semantic Scholar and return the JSON payload's ``data`` list."""

    respect_semantic_scholar_rate_limit(api_key_present=bool(api_key))
    response = session.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={
            "query": build_semantic_scholar_query(anchor_terms, search_terms),
            "limit": limit,
            "fields": "paperId,title,year,url,authors,openAccessPdf,publicationVenue",
        },
        headers={"x-api-key": api_key} if api_key else {},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("data", [])


def search_dblp_for_topic(
    session: requests.Session,
    anchor_terms: Sequence[str],
    search_terms: Sequence[str],
    *,
    per_term_limit: int = 50,
    request_pause: float = 0.3,
) -> List[Dict[str, object]]:
    """Search DBLP for combinations of anchor and search terms."""

    aggregated: Dict[str, Dict[str, object]] = {}
    for anchor in anchor_terms:
        for modifier in search_terms:
            query = f"{anchor} {modifier}"
            response = session.get(
                "https://dblp.org/search/publ/api",
                params={"q": query, "h": per_term_limit, "format": "json"},
                timeout=30,
            )
            response.raise_for_status()
            hits = response.json().get("result", {}).get("hits", {}).get("hit", [])
            if isinstance(hits, dict):
                hits = [hits]
            for hit in hits:
                info = hit.get("info", {})
                key = info.get("key")
                if not key or key in aggregated:
                    continue
                aggregated[key] = {
                    "key": key,
                    "title": info.get("title"),
                    "year": info.get("year"),
                    "url": info.get("url"),
                }
            time.sleep(request_pause)
    return list(aggregated.values())


def load_records_from_directory(records_dir: Path) -> Dict[str, List[Dict[str, object]]]:
    """Read JSON result files and return a mapping keyed by source name."""

    records: Dict[str, List[Dict[str, object]]] = {}
    for source in ("arxiv", "semantic_scholar", "dblp"):
        path = records_dir / f"{source}.json"
        if not path.exists():
            continue
        records[source] = json.loads(path.read_text(encoding="utf-8"))
    return records


def download_records_to_pdfs(
    records_by_source: MutableMapping[str, Sequence[Dict[str, object]]],
    output_dir: Path,
    *,
    session: Optional[requests.Session] = None,
    api_key: Optional[str] = None,
) -> Dict[str, List[DownloadResult]]:
    """Download PDFs/BibTeX assets for search results grouped by source."""

    close_session = False
    if session is None:
        session = requests.Session()
        close_session = True

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    collected: Dict[str, List[DownloadResult]] = {"arxiv": [], "semantic_scholar": [], "dblp": []}
    try:
        for arxiv_record in records_by_source.get("arxiv", []):
            arxiv_id = extract_arxiv_id_from_record(arxiv_record)
            if not arxiv_id:
                continue
            result = download_arxiv_paper(arxiv_id, output_dir / "arxiv", session=session)
            collected["arxiv"].append(result)

        for semantic_record in records_by_source.get("semantic_scholar", []):
            paper_id = semantic_record.get("paperId") or semantic_record.get("paper_id")
            if not paper_id:
                continue
            respect_semantic_scholar_rate_limit(api_key_present=bool(api_key))
            result = download_semantic_scholar_paper(
                str(paper_id),
                output_dir / "semantic_scholar",
                session=session,
                api_key=api_key,
            )
            collected["semantic_scholar"].append(result)

        for dblp_record in records_by_source.get("dblp", []):
            key = dblp_record.get("key")
            if not key:
                continue
            try:
                result = download_dblp_entry(key, output_dir / "dblp", session=session)
            except PaperDownloadError:
                continue
            collected["dblp"].append(result)
    finally:
        if close_session:
            session.close()

    return collected


def extract_arxiv_id_from_record(record: Dict[str, object]) -> Optional[str]:
    """Extract a trimmed arXiv identifier from an Atom entry dictionary."""

    identifier = record.get("id")
    if not isinstance(identifier, str):
        return None
    match = _ARXIV_ID_PATTERN.search(identifier)
    if not match:
        return None
    return trim_arxiv_id(match.group(0))
