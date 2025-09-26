from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

import requests


_DEFAULT_TIMEOUT = 30


class PaperDownloadError(RuntimeError):
    """Raised when a paper or one of its artefacts cannot be retrieved."""


@dataclass
class DownloadResult:
    source: str
    identifier: str
    metadata: Dict[str, object]
    pdf_path: Optional[Path]
    bibtex_path: Optional[Path]
    issues: List[Dict[str, object]] = field(default_factory=list)


def _ensure_session(session: Optional[requests.Session]) -> requests.Session:
    return session or requests.Session()


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _safe_stem(identifier: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", identifier)
    return stem or "paper"


def _write_binary(path: Path, content: bytes) -> Path:
    _ensure_dir(path.parent)
    path.write_bytes(content)
    return path


def _write_text(path: Path, content: str) -> Path:
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

    categories = [
        cat.get("term")
        for cat in entry.findall("atom:category", ns)
        if cat.get("term")
    ]

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


_PRE_PATTERN = re.compile(r"<pre[^>]*>(.*?)</pre>", re.IGNORECASE | re.DOTALL)


def _fetch_arxiv_bibtex(
    session: requests.Session,
    arxiv_id: str,
    timeout: int,
) -> Optional[str]:
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
    if element is None or element.text is None:
        return None
    return element.text.strip()


_SEMANTIC_SCHOLAR_FIELDS = [
    "title",
    "abstract",
    "authors",
    "publicationVenue",
    "year",
    "url",
    "openAccessPdf",
    "externalIds",
    "citationCount",
    "referenceCount",
    "isOpenAccess",
    "tldr",
    "citationStyles",
]


def download_semantic_scholar_paper(
    paper_id: str,
    output_dir: Path,
    *,
    session: Optional[requests.Session] = None,
    api_key: Optional[str] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> DownloadResult:
    session = _ensure_session(session)
    output_dir = Path(output_dir)
    safe_stem = _safe_stem(paper_id)

    metadata = _fetch_semantic_scholar_metadata(
        session,
        paper_id,
        api_key=api_key,
        timeout=timeout,
    )

    pdf_url = None
    open_access = metadata.get("openAccessPdf")
    if isinstance(open_access, dict):
        pdf_url = open_access.get("url")

    issues: List[Dict[str, object]] = []

    pdf_path, pdf_issue = _download_file(
        session,
        pdf_url,
        output_dir / f"{safe_stem}.pdf",
        timeout=timeout,
    )
    if pdf_issue:
        pdf_issue.setdefault("asset", "pdf")
        issues.append(pdf_issue)

    bibtex_text = None
    citation_styles = metadata.get("citationStyles")
    if isinstance(citation_styles, dict):
        bibtex_text = citation_styles.get("bibtex") or citation_styles.get("BibTeX")

    bibtex_path = None
    if bibtex_text:
        bibtex_path = _write_text(output_dir / f"{safe_stem}.bib", bibtex_text.strip())
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
    encoded_id = quote_plus(paper_id)
    url = f"https://api.semanticscholar.org/graph/v1/paper/{encoded_id}"

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    params = {"fields": ",".join(_SEMANTIC_SCHOLAR_FIELDS)}

    response = session.get(url, headers=headers, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


_DBLP_NS = {"dblp": "https://dblp.org/rdf/schema#", "litre": "http://purl.org/spar/literal/", "datacite": "http://purl.org/spar/datacite/"}


def download_dblp_entry(
    dblp_key: str,
    output_dir: Path,
    *,
    session: Optional[requests.Session] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> DownloadResult:
    session = _ensure_session(session)
    output_dir = Path(output_dir)
    safe_stem = _safe_stem(dblp_key)

    metadata = _fetch_dblp_metadata(session, dblp_key, timeout)

    issues: List[Dict[str, object]] = []

    pdf_path = None
    pdf_issue: Optional[Dict[str, object]] = None
    for candidate in metadata.get("document_urls", []):
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
                "url": metadata.get("document_urls"),
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

    doc_urls = {
        elem.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
        for elem in record.findall("dblp:primaryDocumentPage", _DBLP_NS)
    } | {
        elem.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
        for elem in record.findall("dblp:documentPage", _DBLP_NS)
    }

    metadata: Dict[str, object] = {
        "dblp_key": dblp_key,
        "title": _get_text(record.find("dblp:title", _DBLP_NS)),
        "year": _get_text(record.find("dblp:yearOfPublication", _DBLP_NS))
        or _get_text(record.find("dblp:yearOfEvent", _DBLP_NS)),
        "venue": _get_text(record.find("dblp:publishedIn", _DBLP_NS)),
        "pagination": _get_text(record.find("dblp:pagination", _DBLP_NS)),
        "document_urls": [url for url in doc_urls if url],
    }

    identifier = record.find("datacite:hasIdentifier/datacite:ResourceIdentifier/litre:hasLiteralValue", _DBLP_NS)
    if identifier is not None and identifier.text:
        metadata["identifier"] = identifier.text.strip()

    authors = [
        _get_text(sig.find("dblp:signatureDblpName", _DBLP_NS))
        for sig in record.findall("dblp:hasSignature/dblp:AuthorSignature", _DBLP_NS)
    ]
    metadata["authors"] = [name for name in authors if name]

    return metadata


def _fetch_dblp_bibtex(
    session: requests.Session,
    dblp_key: str,
    timeout: int,
) -> Optional[str]:
    url = f"https://dblp.org/rec/{dblp_key}.bib?download=1"
    response = session.get(url, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text.strip()
