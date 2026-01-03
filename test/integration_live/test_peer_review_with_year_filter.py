import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Set

import requests

from src.utils import paper_downloaders, paper_workflows
from src.utils.env import load_env_file
from src.utils.paper_downloaders import PaperDownloadError


ARXIV_METADATA_PATH = Path(
    "test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata.json"
)
FILTERED_OUTPUT_PATH = ARXIV_METADATA_PATH.with_name("arxiv_metadata_peer_reviewed.json")

# 可於此調整欲保留的發表日期範圍；留空字串代表不套用該端的限制。
INCLUDE_START_DATE = "2022-01-01"
INCLUDE_END_DATE = "2025-12-31"


def _normalise_doi(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    normalised = value.strip()
    lowered = normalised.lower()
    prefixes = (
        "https://doi.org/",
        "http://doi.org/",
        "http://dx.doi.org/",
        "https://dx.doi.org/",
        "doi:",
    )
    for prefix in prefixes:
        if lowered.startswith(prefix):
            normalised = normalised[len(prefix) :]
            lowered = normalised.lower()
    return normalised


def _is_arxiv_doi(value: Optional[str]) -> bool:
    normalised = _normalise_doi(value)
    if not normalised:
        return False
    return normalised.lower().startswith("10.48550/arxiv")


_PUBLISHER_HOST_HINTS = (
    "acm.org",
    "ieee",
    "isca-speech.org",
    "springer",
    "sciencedirect",
    "aaai.org",
    "nature.com",
    "wiley.com",
    "mdpi.com",
    "usenix.org",
    "jmlr.org",
)


def _is_publisher_link(url: Optional[str]) -> bool:
    if not url or not isinstance(url, str):
        return False
    lowered = url.lower()
    return any(hint in lowered for hint in _PUBLISHER_HOST_HINTS)


def _print_progress(current: int, total: int) -> None:
    if total <= 0:
        return
    ratio = min(max(current / total, 0.0), 1.0)
    bar_length = 30
    filled = int(bar_length * ratio)
    bar = "#" * filled + "-" * (bar_length - filled)
    sys.stdout.write(f"\r[Peer Review Filter] [{bar}] {current}/{total}")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")
        sys.stdout.flush()


def _parse_date(value: object) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        try:
            year = int(value)
        except (TypeError, ValueError):
            return None
        if 1000 <= year <= 9999:
            return date(year, 1, 1)
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit() and len(text) == 4:
        return date(int(text), 1, 1)
    # 移除常見的時區與時間片段
    normalized = text.replace("Z", "+00:00")
    for candidate in (normalized, normalized.split("T")[0]):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_range_bound(value: str | None) -> Optional[date]:
    if not value:
        return None
    parsed = _parse_date(value)
    if parsed is None:
        raise ValueError(f"無法解析日期：{value}")
    return parsed


_START_DATE_BOUND = _resolve_range_bound(INCLUDE_START_DATE)
_END_DATE_BOUND = _resolve_range_bound(INCLUDE_END_DATE)


def _extract_publication_date(entry: Dict[str, object]) -> Optional[date]:
    metadata = entry.get("metadata")
    candidates = []
    if isinstance(metadata, dict):
        candidates.extend(
            metadata.get(key)
            for key in (
                "published",
                "published_date",
                "publication_date",
                "date",
                "year",
            )
        )
    candidates.extend(
        entry.get(key)
        for key in (
            "published",
            "publication_date",
            "date",
            "year",
        )
    )
    for candidate in candidates:
        parsed = _parse_date(candidate)
        if parsed:
            return parsed
    return None


def _within_date_window(value: Optional[date]) -> bool:
    if value is None:
        return False
    if _START_DATE_BOUND and value < _START_DATE_BOUND:
        return False
    if _END_DATE_BOUND and value > _END_DATE_BOUND:
        return False
    return True


def _collect_semantic_signals(
    session: requests.Session,
    arxiv_id: str,
    *,
    api_key: Optional[str],
) -> Dict[str, Set[str]]:
    signals: Dict[str, Set[str]] = {"positive": set(), "negative": set()}

    if not api_key:
        return signals

    paper_workflows.respect_semantic_scholar_rate_limit(api_key_present=True)
    try:
        raw = paper_downloaders._fetch_semantic_scholar_metadata(
            session,
            f"arXiv:{arxiv_id}",
            api_key=api_key,
            timeout=30,
        )
    except requests.HTTPError:
        return signals

    prepared, pdf_candidates, _ = paper_downloaders._prepare_semantic_scholar_metadata(raw)

    doi_candidates = prepared.get("doi_candidates") or []
    for doi_candidate in doi_candidates:
        normalised = _normalise_doi(doi_candidate)
        if _is_arxiv_doi(normalised):
            signals["negative"].add("semantic_arxiv_doi")
        elif isinstance(normalised, str) and normalised.startswith("10."):
            signals["positive"].add("semantic_publisher_doi")

    doi_value = prepared.get("doi")
    normalised_doi = _normalise_doi(doi_value)
    if _is_arxiv_doi(normalised_doi):
        signals["negative"].add("semantic_arxiv_doi")
    elif isinstance(normalised_doi, str) and normalised_doi.startswith("10."):
        signals["positive"].add("semantic_publisher_doi")

    journal_info = prepared.get("journal")
    journal_name = None
    if isinstance(journal_info, dict):
        journal_name = journal_info.get("name")
    elif isinstance(journal_info, str):
        journal_name = journal_info
    if isinstance(journal_name, str) and journal_name.strip():
        lowered = journal_name.lower()
        if "arxiv" in lowered or "corr" in lowered:
            signals["negative"].add("semantic_arxiv_journal")
        else:
            signals["positive"].add("semantic_named_journal")

    venue = prepared.get("venue")
    if isinstance(venue, str) and venue.strip():
        lowered = venue.lower()
        if "arxiv" in lowered or "corr" in lowered:
            signals["negative"].add("semantic_arxiv_venue")
        else:
            signals["positive"].add("semantic_named_venue")

    publication_venue = prepared.get("publicationVenue")
    if isinstance(publication_venue, dict):
        pv_type = (publication_venue.get("type") or "").lower()
        pv_name = (publication_venue.get("name") or "").lower()
        if pv_name:
            if "arxiv" in pv_name or "corr" in pv_name:
                signals["negative"].add("semantic_arxiv_publication")
            elif pv_type in {"conference", "journal"}:
                signals["positive"].add("semantic_peer_container")

    for candidate in pdf_candidates:
        if isinstance(candidate, str):
            if "arxiv.org" in candidate.lower():
                signals["negative"].add("semantic_arxiv_pdf")
            if _is_publisher_link(candidate):
                signals["positive"].add("semantic_publisher_pdf")

    return signals


def _collect_dblp_signals(
    session: requests.Session,
    arxiv_id: str,
) -> Dict[str, Set[str]]:
    signals: Dict[str, Set[str]] = {"positive": set(), "negative": set()}

    dblp_key = paper_workflows.dblp_key_for_arxiv_id(arxiv_id)
    try:
        metadata = paper_downloaders._fetch_dblp_metadata(
            session, dblp_key, timeout=30
        )
    except (PaperDownloadError, requests.RequestException):
        return signals

    record_tag = metadata.get("record_tag")
    if isinstance(record_tag, str) and record_tag.lower().endswith("informal"):
        signals["negative"].add("dblp_informal_tag")

    key_value = metadata.get("dblp_key") or ""
    if "journals/corr" in key_value or "/corr/" in key_value:
        signals["negative"].add("dblp_corr_key")

    venue = metadata.get("venue")
    if isinstance(venue, str) and venue.strip():
        lowered = venue.lower()
        if "corr" in lowered or "arxiv" in lowered:
            signals["negative"].add("dblp_corr_venue")
        else:
            signals["positive"].add("dblp_named_venue")

    journal = metadata.get("journal")
    if isinstance(journal, str) and journal.strip():
        lowered = journal.lower()
        if "corr" in lowered or "arxiv" in lowered:
            signals["negative"].add("dblp_corr_journal")
        else:
            signals["positive"].add("dblp_named_journal")

    pagination = metadata.get("pagination")
    if isinstance(pagination, str) and pagination.strip():
        signals["positive"].add("dblp_pagination")

    volume = metadata.get("volume")
    if isinstance(volume, str) and volume.strip():
        signals["positive"].add("dblp_volume")

    streams = metadata.get("published_in_stream") or []
    for stream in streams:
        if not isinstance(stream, str):
            continue
        lowered = stream.lower()
        if "corr" in lowered:
            signals["negative"].add("dblp_corr_stream")
        else:
            signals["positive"].add("dblp_stream")

    doi_list = metadata.get("doi_list") or []
    for doi_value in doi_list:
        normalised = _normalise_doi(doi_value)
        if _is_arxiv_doi(normalised):
            signals["negative"].add("dblp_arxiv_doi")
        elif isinstance(normalised, str) and normalised.startswith("10."):
            signals["positive"].add("dblp_publisher_doi")

    identifier_map = metadata.get("identifier_map") or {}
    if isinstance(identifier_map, dict):
        for value in identifier_map.values():
            normalised = _normalise_doi(value)
            if _is_arxiv_doi(normalised):
                signals["negative"].add("dblp_arxiv_doi")
            elif isinstance(normalised, str) and normalised.startswith("10."):
                signals["positive"].add("dblp_publisher_doi")

    return signals


def _is_peer_reviewed(
    arxiv_id: str,
    *,
    semantic_session: requests.Session,
    dblp_session: requests.Session,
    api_key: Optional[str],
    local_metadata: Optional[Dict[str, object]] = None,
) -> bool:
    positive_signals: Set[str] = set()
    negative_signals: Set[str] = set()

    local_doi_normalised = None
    if isinstance(local_metadata, dict):
        local_doi_normalised = _normalise_doi(local_metadata.get("doi"))

    if _is_arxiv_doi(local_doi_normalised):
        negative_signals.add("local_arxiv_doi")
    elif isinstance(local_doi_normalised, str) and local_doi_normalised.startswith("10."):
        positive_signals.add("local_publisher_doi")

    semantic_signals = {"positive": set(), "negative": set()}
    if not positive_signals:
        semantic_signals = _collect_semantic_signals(
            semantic_session, arxiv_id, api_key=api_key
        )
        negative_signals.update(semantic_signals["negative"])
        positive_signals.update(semantic_signals["positive"])

    dblp_signals = _collect_dblp_signals(dblp_session, arxiv_id)
    negative_signals.update(dblp_signals["negative"])
    positive_signals.update(dblp_signals["positive"])

    return bool(positive_signals)


def test_filter_peer_reviewed_arxiv_metadata():
    load_env_file()
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    assert api_key, "SEMANTIC_SCHOLAR_API_KEY must be set for this test"

    assert ARXIV_METADATA_PATH.exists(), "Source arXiv metadata file is missing"

    with ARXIV_METADATA_PATH.open("r", encoding="utf-8") as fh:
        entries = json.load(fh)

    semantic_session = requests.Session()
    dblp_session = requests.Session()

    try:
        peer_reviewed_entries = []
        classification_cache: Dict[str, bool] = {}
        total_entries = len(entries)
        processed_entries = 0

        for entry in entries:
            processed_entries += 1
            arxiv_id = entry.get("arxiv_id")
            if not isinstance(arxiv_id, str):
                _print_progress(processed_entries, total_entries)
                continue

            arxiv_id = arxiv_id.strip()
            if not arxiv_id:
                _print_progress(processed_entries, total_entries)
                continue

            published_date = _extract_publication_date(entry)
            if not _within_date_window(published_date):
                _print_progress(processed_entries, total_entries)
                continue

            try:
                result = _is_peer_reviewed(
                    arxiv_id,
                    semantic_session=semantic_session,
                    dblp_session=dblp_session,
                    api_key=api_key,
                    local_metadata=entry.get("metadata"),
                )
                classification_cache[arxiv_id] = result
                if result:
                    peer_reviewed_entries.append(entry)
            finally:
                _print_progress(processed_entries, total_entries)

    finally:
        semantic_session.close()
        dblp_session.close()

    FILTERED_OUTPUT_PATH.write_text(
        json.dumps(peer_reviewed_entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    assert FILTERED_OUTPUT_PATH.exists()

    with FILTERED_OUTPUT_PATH.open("r", encoding="utf-8") as fh:
        filtered_entries = json.load(fh)

    for item in filtered_entries:
        arxiv_id = item.get("arxiv_id")
        assert classification_cache.get(arxiv_id) is True
        assert _within_date_window(_extract_publication_date(item)), "發表日期不在指定範圍內"

    assert len(filtered_entries) <= len(entries)
