"""Download metadata, PDFs, and BibTeX from arXiv, Semantic Scholar, and DBLP."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests


_DEFAULT_TIMEOUT = 30


class PaperDownloadError(RuntimeError):
    """Raised when a paper or one of its artefacts cannot be retrieved."""


@dataclass
class DownloadResult:
    """Container for a downloaded paper and any associated issues."""

    source: str
    identifier: str
    metadata: Dict[str, object]
    pdf_path: Optional[Path]
    bibtex_path: Optional[Path]
    issues: List[Dict[str, object]] = field(default_factory=list)


def _ensure_session(session: Optional[requests.Session]) -> requests.Session:
    """Return the provided session or create a new one."""

    return session or requests.Session()


def _ensure_dir(path: Path) -> None:
    """Create the directory and its parents if missing."""

    path.mkdir(parents=True, exist_ok=True)


def _safe_stem(identifier: str) -> str:
    """Sanitize an identifier into a filesystem-safe stem."""

    stem = re.sub(r"[^A-Za-z0-9._-]", "_", identifier)
    return stem or "paper"


def _write_binary(path: Path, content: bytes) -> Path:
    """Write binary content to disk and return the path."""

    _ensure_dir(path.parent)
    path.write_bytes(content)
    return path


def _write_text(path: Path, content: str) -> Path:
    """Write text content to disk and return the path."""

    _ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")
    return path


def _download_file(
    session: requests.Session,
    url: Optional[str],
    destination: Path,
    *,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Tuple[Optional[Path], Optional[Dict[str, object]]]:
    """Download a file and return (path, issue) for error reporting."""

    if not url:
        return None, None

    response = session.get(url, timeout=timeout)
    if response.status_code in {401, 403, 404, 410, 418, 451}:
        # Access-restricted artefacts are treated as unavailable rather than fatal.
        return None, {
            "status_code": response.status_code,
            "url": url,
            "reason": "access_blocked",
        }
    response.raise_for_status()
    return _write_binary(destination, response.content), None


def fetch_arxiv_metadata(
    arxiv_id: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, object]:
    """Fetch arXiv metadata for ``arxiv_id`` without downloading files."""

    # breakpoint()
    close_session = False
    if session is None:
        session = requests.Session()
        close_session = True
    try:
        return _fetch_arxiv_metadata(session, arxiv_id, timeout)
    finally:
        if close_session:
            session.close()


def download_arxiv_paper(
    arxiv_id: str,
    output_dir: Path,
    *,
    session: Optional[requests.Session] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> DownloadResult:
    """Download metadata, PDF, and BibTeX for an arXiv paper."""

    session = _ensure_session(session)
    output_dir = Path(output_dir)
    safe_stem = _safe_stem(arxiv_id)

    metadata = _fetch_arxiv_metadata(session, arxiv_id, timeout)

    issues: List[Dict[str, object]] = []

    pdf_path, pdf_issue = _download_file(
        session,
        metadata.get("pdf_url"),
        output_dir / f"{safe_stem}.pdf",
        timeout=timeout,
    )
    if pdf_issue:
        pdf_issue.setdefault("asset", "pdf")
        issues.append(pdf_issue)

    bibtex_text = _fetch_arxiv_bibtex(session, arxiv_id, timeout)
    bibtex_path = None
    if bibtex_text:
        bibtex_path = _write_text(output_dir / f"{safe_stem}.bib", bibtex_text)
    else:
        issues.append(
            {
                "asset": "bibtex",
                "reason": "missing",
                "url": f"https://arxiv.org/bibtex/{arxiv_id}",
            }
        )

    return DownloadResult(
        source="arxiv",
        identifier=arxiv_id,
        metadata=metadata,
        pdf_path=pdf_path,
        bibtex_path=bibtex_path,
        issues=issues,
    )


def _fetch_arxiv_metadata(
    session: requests.Session,
    arxiv_id: str,
    timeout: int,
) -> Dict[str, object]:
    """Fetch arXiv metadata via the Atom API."""

    api_url = "https://export.arxiv.org/api/query"
    response = session.get(api_url, params={"id_list": arxiv_id}, timeout=timeout)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise PaperDownloadError(f"arXiv id '{arxiv_id}' not found")

    title = _get_text(entry.find("atom:title", ns))
    summary = _get_text(entry.find("atom:summary", ns))
    published = _get_text(entry.find("atom:published", ns))
    updated = _get_text(entry.find("atom:updated", ns))

    authors = [
        _get_text(author.find("atom:name", ns))
        for author in entry.findall("atom:author", ns)
        if _get_text(author.find("atom:name", ns))
    ]

    pdf_url = None
    landing_url = None
    doi = None
    for link in entry.findall("atom:link", ns):
        rel = link.get("rel") or ""
        title_attr = link.get("title") or ""
        href = link.get("href")
        if title_attr.lower() == "pdf" and href:
            pdf_url = href
        elif rel == "alternate" and href:
            landing_url = href
        elif title_attr.lower() == "doi" and href:
            doi = href

    if not doi:
        doi = _resolve_arxiv_doi_from_export(session, arxiv_id, timeout)

    categories = [
        cat.get("term")
        for cat in entry.findall("atom:category", ns)
        if cat.get("term")
    ]

    # breakpoint()

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "summary": summary,
        "authors": authors,
        "published": published,
        "updated": updated,
        "categories": categories,
        "pdf_url": pdf_url,
        "landing_url": landing_url,
        "doi": doi,
    }


def _resolve_arxiv_doi_from_export(
    session: requests.Session,
    arxiv_id: str,
    timeout: int,
) -> Optional[str]:
    """Try to extract the DataCite DOI from the export web mirror."""

    export_url = f"https://export.arxiv.org/abs/{arxiv_id}"
    try:
        response = session.get(export_url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return None

    return _extract_doi_from_export_html(response.text)


def _extract_doi_from_export_html(html_text: str) -> Optional[str]:
    """Extract a DOI link from the arXiv export HTML page."""

    marker = 'id="arxiv-doi-link"'
    lower_html = html_text.lower()
    marker_pos = lower_html.find(marker)
    if marker_pos == -1:
        return None

    anchor_start = html_text.rfind("<a", 0, marker_pos)
    anchor_end = html_text.find(">", marker_pos)
    if anchor_start == -1 or anchor_end == -1:
        return None

    anchor_tag = html_text[anchor_start:anchor_end]
    href_match = re.search(r'href="([^"]+)"', anchor_tag)
    if not href_match:
        href_match = re.search(r"href='([^']+)'", anchor_tag)
    if not href_match:
        return None

    href = html.unescape(href_match.group(1))
    if "doi" not in href.lower():
        return None

    return href.strip()


_PRE_PATTERN = re.compile(r"<pre[^>]*>(.*?)</pre>", re.IGNORECASE | re.DOTALL)


def _fetch_arxiv_bibtex(
    session: requests.Session,
    arxiv_id: str,
    timeout: int,
) -> Optional[str]:
    """Fetch BibTeX from the arXiv bibtex endpoint."""

    url = f"https://arxiv.org/bibtex/{arxiv_id}"
    response = session.get(url, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()

    html_text = response.text
    match = _PRE_PATTERN.search(html_text)
    if not match:
        return None

    return html.unescape(match.group(1)).strip()


def _get_text(element: Optional[ET.Element]) -> Optional[str]:
    """Return stripped text content for an XML element."""

    if element is None or element.text is None:
        return None
    return element.text.strip()


_ARXIV_EXTERNAL_ID_RE = re.compile(
    r"(?:arxiv:)?(?P<id>(?:\d{4}\.\d{4,5}|[a-z\-]+/\d{7}))",
    re.IGNORECASE,
)


_SEMANTIC_SCHOLAR_FIELDS = [
    "paperId",
    "corpusId",
    "title",
    "abstract",
    "venue",
    "publicationVenue",
    "publicationTypes",
    "publicationDate",
    "year",
    "journal",
    "fieldsOfStudy",
    "s2FieldsOfStudy",
    "isOpenAccess",
    "openAccessPdf",
    "url",
    "tldr",
    "citationStyles",
    "externalIds",
    "referenceCount",
    "citationCount",
    "influentialCitationCount",
    "embedding",
    "authors.authorId",
    "authors.name",
    "authors.url",
    "authors.affiliations",
    "authors.homepage",
    "authors.paperCount",
    "authors.citationCount",
    "authors.hIndex",
]


def download_semantic_scholar_paper(
    paper_id: str,
    output_dir: Path,
    *,
    session: Optional[requests.Session] = None,
    api_key: Optional[str] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> DownloadResult:
    """Download Semantic Scholar metadata plus PDF/BibTeX assets."""

    session = _ensure_session(session)
    output_dir = Path(output_dir)
    safe_stem = _safe_stem(paper_id)

    try:
        metadata_raw = _fetch_semantic_scholar_metadata(
            session,
            paper_id,
            api_key=api_key,
            timeout=timeout,
        )
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status == 429:
            return DownloadResult(
                source="semantic_scholar",
                identifier=paper_id,
                metadata={},
                pdf_path=None,
                bibtex_path=None,
                issues=[
                    {
                        "asset": "metadata",
                        "reason": "rate_limited",
                        "status_code": status,
                        "url": getattr(exc.response, "url", None),
                    }
                ],
            )
        raise

    metadata, pdf_candidates, bibtex_text = _prepare_semantic_scholar_metadata(metadata_raw)

    issues: List[Dict[str, object]] = []
    pdf_path: Optional[Path] = None
    pdf_issue_found = False

    for candidate in pdf_candidates:
        pdf_path, candidate_issue = _download_file(
            session,
            candidate,
            output_dir / f"{safe_stem}.pdf",
            timeout=timeout,
        )
        if pdf_path:
            break
        if candidate_issue:
            candidate_issue.setdefault("asset", "pdf")
            candidate_issue.setdefault("candidate_url", candidate)
            issues.append(candidate_issue)
            pdf_issue_found = True

    if not pdf_path:
        if not pdf_candidates:
            issues.append(
                {
                    "asset": "pdf",
                    "reason": "not_provided",
                    "url": None,
                }
            )
        elif not pdf_issue_found:
            issues.append(
                {
                    "asset": "pdf",
                    "reason": "missing",
                    "url": pdf_candidates,
                }
            )

    bibtex_path = None
    if bibtex_text:
        bibtex_path = _write_text(output_dir / f"{safe_stem}.bib", bibtex_text)
    else:
        issues.append(
            {
                "asset": "bibtex",
                "reason": "missing",
                "url": f"https://api.semanticscholar.org/graph/v1/paper/{quote_plus(paper_id)}",
            }
        )

    return DownloadResult(
        source="semantic_scholar",
        identifier=paper_id,
        metadata=metadata,
        pdf_path=pdf_path,
        bibtex_path=bibtex_path,
        issues=issues,
    )


def _fetch_semantic_scholar_metadata(
    session: requests.Session,
    paper_id: str,
    *,
    api_key: Optional[str],
    timeout: int,
) -> Dict[str, object]:
    """Fetch Semantic Scholar paper metadata via the Graph API."""

    encoded_id = quote_plus(paper_id)
    url = f"https://api.semanticscholar.org/graph/v1/paper/{encoded_id}"

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {"fields": ",".join(_SEMANTIC_SCHOLAR_FIELDS)}

    response = session.get(url, headers=headers, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _candidate_semantic_pdf_urls(metadata: Dict[str, object]) -> List[str]:
    """Collect candidate PDF URLs from Semantic Scholar metadata."""

    candidates: List[str] = []

    open_access = metadata.get("openAccessPdf")
    if isinstance(open_access, dict):
        url = open_access.get("url")
        if isinstance(url, str) and url.strip():
            candidates.append(url.strip())

    pdf_urls = metadata.get("pdfUrls")
    if isinstance(pdf_urls, list):
        for item in pdf_urls:
            if isinstance(item, str) and item.strip():
                candidates.append(item.strip())

    external_ids = metadata.get("externalIds")
    arxiv_pdf = _arxiv_pdf_from_external_ids(external_ids)
    if arxiv_pdf:
        candidates.append(arxiv_pdf)

    deduped: List[str] = []
    seen = set()
    for url in candidates:
        key = url.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(url)
    return deduped


def _normalise_semantic_external_ids(external_ids: Any) -> List[Dict[str, str]]:
    """Normalize external IDs into a list of {source,value} records."""

    entries: List[Dict[str, str]] = []
    if isinstance(external_ids, dict):
        for source, value in external_ids.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    if item is None:
                        continue
                    text = str(item).strip()
                    if text:
                        entries.append({"source": str(source), "value": text})
            else:
                text = str(value).strip()
                if text:
                    entries.append({"source": str(source), "value": text})
    return entries


def _prepare_semantic_scholar_metadata(
    metadata: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str], Optional[str]]:
    """Prepare Semantic Scholar metadata with derived fields and BibTeX."""

    prepared: Dict[str, Any] = dict(metadata)

    pdf_candidates = _candidate_semantic_pdf_urls(metadata)
    prepared["pdf_candidates"] = pdf_candidates
    prepared["best_pdf_url"] = pdf_candidates[0] if pdf_candidates else None

    authors = metadata.get("authors")
    author_names: List[str] = []
    if isinstance(authors, list):
        for author in authors:
            if not isinstance(author, dict):
                continue
            name = author.get("name")
            if isinstance(name, str) and name.strip():
                author_names.append(name.strip())
    prepared["author_names"] = author_names

    external_entries = _normalise_semantic_external_ids(metadata.get("externalIds"))
    prepared["external_id_entries"] = external_entries
    external_map: Dict[str, str] = {}
    for entry in external_entries:
        source = entry.get("source")
        value = entry.get("value")
        if source and value and source not in external_map:
            external_map[source] = value
    prepared["external_id_map"] = external_map

    doi_candidates = _deduplicate_sequence(
        [prepared.get("doi"), external_map.get("DOI"), external_map.get("doi")]
    )
    prepared["doi_candidates"] = doi_candidates
    if doi_candidates and not prepared.get("doi"):
        prepared["doi"] = doi_candidates[0]

    tldr_obj = metadata.get("tldr")
    tldr_text = None
    if isinstance(tldr_obj, dict):
        for key in ("text", "summary"):
            value = tldr_obj.get(key)
            if isinstance(value, str) and value.strip():
                tldr_text = value.strip()
                break
    if tldr_text:
        prepared["tldr_text"] = tldr_text

    citation_styles = metadata.get("citationStyles")
    bibtex_text: Optional[str] = None
    if isinstance(citation_styles, dict):
        for key in ("bibtex", "BibTeX", "Bibtex"):
            value = citation_styles.get(key)
            if isinstance(value, str) and value.strip():
                bibtex_text = value.strip()
                citation_styles[key] = bibtex_text
                break
        prepared["citationStyles"] = citation_styles
    if bibtex_text:
        prepared["bibtex_entry"] = bibtex_text

    return prepared, pdf_candidates, bibtex_text


def _arxiv_pdf_from_external_ids(external_ids: object) -> Optional[str]:
    """Derive an arXiv PDF URL from external IDs."""

    if isinstance(external_ids, dict):
        for key in ("ArXiv", "arXiv", "arxiv"):
            value = external_ids.get(key)
            pdf = _arxiv_pdf_from_external_ids(value)
            if pdf:
                return pdf
        return None

    if isinstance(external_ids, (list, tuple)):
        for value in external_ids:
            pdf = _arxiv_pdf_from_external_ids(value)
            if pdf:
                return pdf
        return None

    if not isinstance(external_ids, str):
        return None

    text = external_ids.strip()
    if not text:
        return None

    # Remove common URL prefixes.
    for prefix in (
        "https://arxiv.org/abs/",
        "http://arxiv.org/abs/",
        "https://arxiv.org/pdf/",
        "http://arxiv.org/pdf/",
    ):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break

    match = _ARXIV_EXTERNAL_ID_RE.search(text)
    if not match:
        return None

    arxiv_id = match.group("id")
    return f"https://export.arxiv.org/pdf/{arxiv_id}.pdf"


_DBLP_NS = {
    "dblp": "https://dblp.org/rdf/schema#",
    "litre": "http://purl.org/spar/literal/",
    "datacite": "http://purl.org/spar/datacite/",
}
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def _deduplicate_sequence(items: List[Optional[str]]) -> List[str]:
    """Deduplicate a list while preserving order."""

    seen = set()
    deduped: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _element_to_metadata_tree(element: ET.Element) -> Dict[str, Any]:
    """Recursively convert an XML element into a dict tree."""

    node: Dict[str, Any] = {}
    text = _get_text(element)
    if text:
        node["text"] = text
    if element.attrib:
        node["attributes"] = dict(element.attrib)

    children = []
    for child in list(element):
        child_repr: Dict[str, Any] = {"tag": child.tag}
        child_value = _element_to_metadata_tree(child)
        if child_value:
            child_repr["value"] = child_value
        children.append(child_repr)
    if children:
        node["children"] = children

    tail = element.tail.strip() if element.tail and element.tail.strip() else None
    if tail:
        node["tail"] = tail

    return node


def _shorten_identifier_scheme(uri: str) -> str:
    """Shorten a URI to its trailing fragment for readability."""

    for separator in ("#", "/"):
        if separator in uri:
            uri = uri.rsplit(separator, 1)[-1]
    return uri


def _collect_dblp_identifiers(record: ET.Element) -> List[Dict[str, Optional[str]]]:
    """Extract identifier records from a DBLP RDF element."""

    identifiers: List[Dict[str, Optional[str]]] = []
    for identifier in record.findall(
        "datacite:hasIdentifier/datacite:ResourceIdentifier",
        _DBLP_NS,
    ):
        raw_scheme = None
        scheme_elem = identifier.find("datacite:usesIdentifierScheme", _DBLP_NS)
        if scheme_elem is not None:
            raw_scheme = scheme_elem.get(f"{{{_RDF_NS}}}resource")
        value = _get_text(identifier.find("litre:hasLiteralValue", _DBLP_NS))
        entry: Dict[str, Optional[str]] = {"scheme": raw_scheme, "value": value}
        if raw_scheme:
            entry["scheme_short"] = _shorten_identifier_scheme(raw_scheme)
        identifiers.append(entry)
    return identifiers


def _collect_dblp_electronic_editions(record: ET.Element) -> List[Dict[str, Any]]:
    """Extract electronic edition records from a DBLP RDF element."""

    editions: List[Dict[str, Any]] = []
    for edition in record.findall("dblp:ee", _DBLP_NS):
        entry: Dict[str, Any] = {}
        resource = edition.get(f"{{{_RDF_NS}}}resource")
        if resource:
            entry["url"] = resource
        text = _get_text(edition)
        if text:
            entry["label"] = text
        attributes = dict(edition.attrib)
        if attributes:
            entry["attributes"] = attributes
        if not entry:
            entry["metadata"] = {}
        editions.append(entry)
    return editions


def _collect_dblp_signatures(record: ET.Element) -> List[Dict[str, Any]]:
    """Extract author signature details from a DBLP RDF element."""

    signatures: List[Dict[str, Any]] = []
    for signature in record.findall("dblp:hasSignature/dblp:AuthorSignature", _DBLP_NS):
        entry: Dict[str, Any] = {
            "name": _get_text(signature.find("dblp:signatureDblpName", _DBLP_NS)),
            "ordinal": _get_text(signature.find("dblp:signatureOrdinal", _DBLP_NS)),
        }
        creator = signature.find("dblp:signatureCreator", _DBLP_NS)
        if creator is not None:
            resource = creator.get(f"{{{_RDF_NS}}}resource")
            if resource:
                entry["creator"] = resource
        publication = signature.find("dblp:signaturePublication", _DBLP_NS)
        if publication is not None:
            resource = publication.get(f"{{{_RDF_NS}}}resource")
            if resource:
                entry["publication"] = resource
        signatures.append(entry)
    return signatures


def _collect_raw_dblp_fields(record: ET.Element) -> Dict[str, List[Dict[str, Any]]]:
    """Collect raw XML fields for debugging/inspection."""

    raw_fields: Dict[str, List[Dict[str, Any]]] = {}
    for child in list(record):
        raw_fields.setdefault(child.tag, []).append(_element_to_metadata_tree(child))
    return raw_fields


def download_dblp_entry(
    dblp_key: str,
    output_dir: Path,
    *,
    session: Optional[requests.Session] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> DownloadResult:
    """Download DBLP metadata plus PDF/BibTeX when available."""

    session = _ensure_session(session)
    output_dir = Path(output_dir)
    safe_stem = _safe_stem(dblp_key)

    metadata = _fetch_dblp_metadata(session, dblp_key, timeout)

    issues: List[Dict[str, object]] = []

    pdf_path = None
    pdf_issue: Optional[Dict[str, object]] = None
    pdf_candidates = metadata.get("pdf_candidates") or metadata.get("document_urls", [])
    for candidate in pdf_candidates:
        if candidate and candidate.lower().endswith(".pdf"):
            pdf_path, pdf_issue = _download_file(
                session,
                candidate,
                output_dir / f"{safe_stem}.pdf",
                timeout=timeout,
            )
            if pdf_path:
                break
    if pdf_issue:
        pdf_issue.setdefault("asset", "pdf")
        issues.append(pdf_issue)
    elif not pdf_path:
        issues.append(
            {
                "asset": "pdf",
                "reason": "missing",
                "url": pdf_candidates,
            }
        )

    bibtex_text = _fetch_dblp_bibtex(session, dblp_key, timeout)
    bibtex_path = None
    if bibtex_text:
        bibtex_path = _write_text(output_dir / f"{safe_stem}.bib", bibtex_text)
    else:
        issues.append(
            {
                "asset": "bibtex",
                "reason": "missing",
                "url": f"https://dblp.org/rec/{dblp_key}.bib?download=1",
            }
        )

    return DownloadResult(
        source="dblp",
        identifier=dblp_key,
        metadata=metadata,
        pdf_path=pdf_path,
        bibtex_path=bibtex_path,
        issues=issues,
    )


def _fetch_dblp_metadata(
    session: requests.Session,
    dblp_key: str,
    timeout: int,
) -> Dict[str, object]:
    """Fetch DBLP RDF metadata and normalize fields."""

    rdf_url = f"https://dblp.org/rec/{dblp_key}.rdf"
    response = session.get(rdf_url, timeout=timeout)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    record = next(
        (child for child in root if child.tag.startswith("{https://dblp.org/rdf/schema#}")),
        None,
    )
    if record is None:
        raise PaperDownloadError(f"DBLP record '{dblp_key}' not found")

    doc_urls = _deduplicate_sequence(
        [
            elem.get(f"{{{_RDF_NS}}}resource")
            for elem in record.findall("dblp:primaryDocumentPage", _DBLP_NS)
        ]
        + [
            elem.get(f"{{{_RDF_NS}}}resource")
            for elem in record.findall("dblp:documentPage", _DBLP_NS)
        ]
    )

    identifiers = _collect_dblp_identifiers(record)
    identifier_map: Dict[str, str] = {}
    for entry in identifiers:
        key = entry.get("scheme_short") or entry.get("scheme")
        value = entry.get("value")
        if key and value and key not in identifier_map:
            identifier_map[key] = value

    editions = _collect_dblp_electronic_editions(record)

    authors = [
        _get_text(sig.find("dblp:signatureDblpName", _DBLP_NS))
        for sig in record.findall("dblp:hasSignature/dblp:AuthorSignature", _DBLP_NS)
    ]
    author_resources = [
        elem.get(f"{{{_RDF_NS}}}resource")
        for elem in record.findall("dblp:authoredBy", _DBLP_NS)
    ]

    toc_pages = [
        elem.get(f"{{{_RDF_NS}}}resource")
        for elem in record.findall("dblp:listedOnTocPage", _DBLP_NS)
    ]
    published_streams = [
        elem.get(f"{{{_RDF_NS}}}resource")
        for elem in record.findall("dblp:publishedInStream", _DBLP_NS)
    ]

    doi_values = [
        _get_text(elem)
        for elem in record.findall("dblp:doi", _DBLP_NS)
    ]

    bibtex_type_elem = record.find("dblp:bibtexType", _DBLP_NS)
    bibtex_type = None
    if bibtex_type_elem is not None:
        bibtex_type = bibtex_type_elem.get(f"{{{_RDF_NS}}}resource")

    metadata: Dict[str, object] = {
        "dblp_key": dblp_key,
        "title": _get_text(record.find("dblp:title", _DBLP_NS)),
        "year": _get_text(record.find("dblp:yearOfPublication", _DBLP_NS))
        or _get_text(record.find("dblp:yearOfEvent", _DBLP_NS)),
        "venue": _get_text(record.find("dblp:publishedIn", _DBLP_NS)),
        "journal": _get_text(record.find("dblp:publishedInJournal", _DBLP_NS)),
        "volume": _get_text(record.find("dblp:publishedInJournalVolume", _DBLP_NS)),
        "pagination": _get_text(record.find("dblp:pagination", _DBLP_NS)),
        "number_of_creators": _get_text(record.find("dblp:numberOfCreators", _DBLP_NS)),
        "bibtex_type": bibtex_type,
        "document_urls": doc_urls,
        "electronic_editions": editions,
        "electronic_edition_urls": _deduplicate_sequence(
            [edition.get("url") for edition in editions if edition.get("url")]
        ),
        "identifiers": identifiers,
        "identifier_map": identifier_map,
        "authors": [name for name in authors if name],
        "author_resources": [resource for resource in author_resources if resource],
        "signatures": _collect_dblp_signatures(record),
        "toc_pages": [url for url in toc_pages if url],
        "published_in_stream": [url for url in published_streams if url],
        "doi_list": [doi for doi in doi_values if doi],
        "record_attributes": dict(record.attrib),
        "record_tag": record.tag,
        "raw_fields": _collect_raw_dblp_fields(record),
        "source_rdf": rdf_url,
    }

    if metadata["doi_list"] and "doi" not in metadata:
        metadata["doi"] = metadata["doi_list"][0]

    if "doi" not in metadata and "doi" in metadata["identifier_map"]:
        metadata["doi"] = metadata["identifier_map"]["doi"]

    pdf_candidates = _deduplicate_sequence(
        doc_urls
        + [edition.get("url") for edition in editions if isinstance(edition, dict)]
    )
    metadata["pdf_candidates"] = pdf_candidates

    return metadata


def _fetch_dblp_bibtex(
    session: requests.Session,
    dblp_key: str,
    timeout: int,
) -> Optional[str]:
    """Fetch BibTeX entry from DBLP."""

    url = f"https://dblp.org/rec/{dblp_key}.bib?download=1"
    response = session.get(url, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text.strip()
