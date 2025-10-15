"""下載 Speech LM 相關論文 PDF 並整理 BibTeX。

此腳本會同時處理兩份 JSON：
- `latte_review_results_step5_full.json`：LatteReviewer 初審的完整結果，僅下載
  「納入」且發表年份晚於 2022 年的條目。
- `latte_review_snowball_full_screening.json`（若無則退回 `latte_review_snowball_top*.json`）：
  雪崩審查後的最終結果，同樣僅下載判定為「納入」的條目。

下載流程：
1. arXiv 結果直接使用 JSON 內的 `pdf_url` 或 `arxiv_id` 產生連結。
2. 雪球結果依序嘗試：
   a. 呼叫 OpenAlex 取得 `best_oa_location` / `primary_location` 的 PDF 連結。
   b. 根據 DOI 前綴套用特定站點的 PDF URL（如 ACL Anthology、arXiv）。
   c. 以標題查詢 arXiv API，若找到相同標題則下載其 PDF。

所有 PDF 會下載到 `test_artifacts/SpeechLM_pdfs/`，檔名使用 BibTeX key；
同時會整併所有條目的 `title`、`abstract` 與官方 BibTeX 到 `bib_metadata.json`。

指令支援下列選項：
    --max-arxiv N        只下載前 N 筆初審結果（預設不限）
    --max-snowball N     只下載前 N 筆雪崩結果（預設不限）
    --skip-arxiv         略過初審結果下載
    --skip-snowball      略過雪崩結果下載

執行範例：
    python test/tools/download_speechlm_pdfs.py --max-snowball 200
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
ARXIV_JSON = REPO_ROOT / "test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json"
DEFAULT_SNOWBALL_JSON = REPO_ROOT / "test_artifacts/metadata_harvest/speech_language_models/latte_review_snowball_full_screening.json"
LEGACY_SNOWBALL_JSON_PATTERN = "latte_review_snowball_top"
OUTPUT_DIR = REPO_ROOT / "test_artifacts/SpeechLM_pdfs"
BIB_JSON_OUTPUT = OUTPUT_DIR / "bib_metadata.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 20
DOWNLOAD_SLEEP_SECONDS = 0.3


@dataclass
class DownloadRecord:
    """描述單筆下載結果。"""

    source: str
    title: str
    url: Optional[str]
    filepath: Optional[Path]
    reason: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.url is not None and self.filepath is not None and self.filepath.exists()


def parse_year(value: Optional[str]) -> Optional[int]:
    """將 ISO 8601 或簡單年份字串轉換成整數年份。"""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.endswith("Z"):
        cleaned = cleaned.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).year
    except ValueError:
        try:
            return int(cleaned[:4])
        except ValueError:
            return None


def load_json(path: Path) -> List[Dict[str, object]]:
    """載入指定 JSON 路徑並確保為 list 結構。"""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"{path} 的 JSON 結構不是 list")
    return data


def resolve_snowball_json() -> Path:
    if DEFAULT_SNOWBALL_JSON.exists():
        return DEFAULT_SNOWBALL_JSON
    base_dir = DEFAULT_SNOWBALL_JSON.parent
    candidates = sorted(
        base_dir.glob(f"{LEGACY_SNOWBALL_JSON_PATTERN}*.json")
    )
    if candidates:
        return candidates[-1]
    raise FileNotFoundError(
        "找不到雪崩審查結果 JSON，請確認已執行 "
        "`test/integration_live/test_latte_review_snowball_screening.py`。"
    )


SNOWBALL_JSON = resolve_snowball_json()


def slugify(text: str) -> str:
    """將標題轉為檔名可用的 slug。"""
    lowered = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


def build_filename(identifier: str, title: str) -> str:
    """依識別碼與標題產生唯一檔名。"""
    slug = slugify(title)[:80]
    digest = hashlib.md5(identifier.encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}.pdf"


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def stream_download(session: requests.Session, url: str, dest: Path) -> None:
    """以串流方式下載檔案。"""
    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
        stream=True,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.1",
        },
    )
    response.raise_for_status()
    temp_path = dest.with_suffix(".tmp")
    with temp_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                handle.write(chunk)
    temp_path.replace(dest)


def resolve_arxiv_pdf(entry: Dict[str, object]) -> Optional[str]:
    """從 Latte Review arXiv 條目取得 PDF URL。"""
    metadata = entry.get("metadata")
    if not isinstance(metadata, dict):
        return None
    pdf_url = metadata.get("pdf_url")
    if isinstance(pdf_url, str) and pdf_url.startswith("http"):
        return pdf_url.replace("https://arxiv.org", "https://export.arxiv.org").replace(
            "http://arxiv.org", "https://export.arxiv.org"
        )
    arxiv_id = metadata.get("arxiv_id")
    if isinstance(arxiv_id, str):
        return f"https://export.arxiv.org/pdf/{arxiv_id}.pdf"
    doi = metadata.get("doi")
    if isinstance(doi, str):
        lower = doi.lower()
        match = re.search(r"arxiv\.([\d\.]+v?\d*)", lower)
        if match:
            return f"https://export.arxiv.org/pdf/{match.group(1)}.pdf"
    return None


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    doi = doi.strip()
    if not doi:
        return None
    if doi.lower().startswith("https://doi.org/"):
        return doi[16:]
    if doi.lower().startswith("http://doi.org/"):
        return doi[15:]
    return doi


def build_acl_url(doi_suffix: str) -> str:
    return f"https://aclanthology.org/{doi_suffix}.pdf"


def build_arxiv_url_from_doi(doi_suffix: str) -> Optional[str]:
    match = re.search(r"arxiv\.([\d\.]+v?\d*)", doi_suffix.lower())
    if match:
        return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    return None


def candidate_urls_from_doi(doi: Optional[str]) -> List[str]:
    """根據 DOI 推測可能的 PDF 位置。"""
    suffix = normalize_doi(doi)
    if not suffix:
        return []
    candidates: List[str] = []
    lower = suffix.lower()
    if lower.startswith("10.48550/"):
        arxiv_url = build_arxiv_url_from_doi(suffix)
        if arxiv_url:
            candidates.append(
                arxiv_url.replace("https://arxiv.org", "https://export.arxiv.org")
            )
    if lower.startswith("10.18653/"):
        candidates.append(build_acl_url(suffix))
    return candidates


def _print_progress(label: str, current: int, total: int) -> None:
    if total <= 0:
        return
    ratio = min(max(current / total, 0.0), 1.0)
    bar_len = 30
    filled = int(bar_len * ratio)
    bar = "#" * filled + "-" * (bar_len - filled)
    print(f"\r[{label}] [{bar}] {current}/{total}", end="", flush=True)
    if current >= total:
        print()


def extract_abstract(entry: Dict[str, object]) -> str:
    abstract = entry.get("abstract")
    if isinstance(abstract, str) and abstract.strip():
        return abstract.strip()
    metadata = entry.get("metadata")
    if isinstance(metadata, dict):
        for key in ("summary", "abstract", "description"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def fetch_openalex_pdf(session: requests.Session, openalex_id: Optional[str]) -> Optional[str]:
    """利用 OpenAlex API 嘗試取得 PDF 連結。"""
    if not openalex_id:
        return None
    identifier = openalex_id.rsplit("/", 1)[-1]
    url = f"https://api.openalex.org/works/{identifier}"
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        return None
    data = response.json()

    def extract(location: Optional[Dict[str, object]]) -> Optional[str]:
        if not isinstance(location, dict):
            return None
        for key in ("pdf_url", "url_for_pdf"):
            value = location.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
        return None

    for key in ("best_oa_location", "primary_location"):
        pdf = extract(data.get(key))
        if pdf:
            return pdf
    for location in data.get("locations", []) or []:
        pdf = extract(location)
        if pdf:
            return pdf
    return None


def search_arxiv_by_title(session: requests.Session, title: str) -> Optional[str]:
    """使用 ArXiv API 依標題搜尋並比對。"""
    if not title:
        return None
    query = f'ti:"{title.replace("\"", " ")}"'
    params = {
        "search_query": query,
        "start": 0,
        "max_results": 5,
    }
    url = "http://export.arxiv.org/api/query" + "?" + urllib.parse.urlencode(params)
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        return None
    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return None
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().lower()

    target = normalize(title)
    for entry in root.findall("atom:entry", ns):
        found_title = entry.findtext("atom:title", default="", namespaces=ns)
        if normalize(found_title) != target:
            continue
        for link in entry.findall("atom:link", ns):
            href = link.attrib.get("href")
            link_type = link.attrib.get("type")
            if href and (link.attrib.get("title") == "pdf" or link_type == "application/pdf"):
                return href
    return None


def identify_entry(entry: Dict[str, object]) -> str:
    metadata = entry.get("metadata")
    if isinstance(metadata, dict):
        for key in ("arxiv_id", "doi", "openalex_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    title = entry.get("title", "unknown")
    assert isinstance(title, str)
    return title


def build_fallback_key(entry: Dict[str, object], *, fallback_prefix: str = "entry") -> str:
    metadata = entry.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("arxiv_id", "doi", "openalex_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
                slug = re.sub(r"_+", "_", slug).strip("_")
                if slug:
                    return slug.lower()
    title = str(entry.get("title", "")).strip()
    if title:
        slug = re.sub(r"[^A-Za-z0-9]+", "_", title.lower()).strip("_")
        if slug:
            return slug[:64]
    return f"{fallback_prefix}_{hashlib.md5(title.encode('utf-8')).hexdigest()[:8]}"


_BIB_KEY_PATTERN = re.compile(r"@\w+\{([^,]+),")


def parse_bib_key(bibtex: str) -> Optional[str]:
    match = _BIB_KEY_PATTERN.search(bibtex)
    if match:
        return match.group(1).strip()
    return None


def compute_custom_key(entry: Dict[str, object], metadata: Dict[str, Any], fallback_prefix: str) -> str:
    authors = metadata.get("authors") or entry.get("authors") or []
    first_author = "entry"
    if isinstance(authors, list) and authors:
        first_author = authors[0].split()[-1].lower()
    elif isinstance(authors, str) and authors.strip():
        first_author = authors.split()[-1].lower()

    def _parse_year(value: Any) -> Optional[int]:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).year
        except ValueError:
            if text.isdigit() and len(text) == 4:
                return int(text)
        return None

    year = _parse_year(metadata.get("updated")) or _parse_year(metadata.get("published"))
    if year is None:
        try:
            year = datetime.now().year
        except Exception:
            year = 0

    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        title = metadata.get("title", "paper")
    raw_words = re.findall(r"[a-z0-9]+", str(title).lower())
    stopwords = {
        "in",
        "to",
        "the",
        "a",
        "an",
        "of",
        "for",
        "and",
        "on",
        "at",
        "with",
        "by",
        "from",
        "using",
        "via",
        "into",
    }
    filtered = []
    seen = set()
    for word in raw_words:
        if word in stopwords:
            continue
        if word in seen:
            continue
        seen.add(word)
        filtered.append(word)
    if not filtered:
        filtered = raw_words or ["paper"]
    title_slug = "".join(filtered)
    if not title_slug:
        title_slug = "paper"
    title_slug = title_slug[:40]
    return f"{first_author}{year}{title_slug}"


def resolve_bibtex_and_key(
    session: requests.Session,
    entry: Dict[str, object],
    metadata: Dict[str, Any],
    fallback_prefix: str,
) -> Tuple[str, Optional[str]]:
    fetchers = [
        lambda: fetch_arxiv_bibtex(session, metadata.get("arxiv_id")),
        lambda: fetch_openalex_bibtex(session, metadata.get("openalex_id")),
        lambda: fetch_doi_bibtex(session, metadata.get("doi")),
    ]

    bibtex: Optional[str] = None
    bib_key: Optional[str] = None
    for fetch in fetchers:
        bibtex = fetch()
        if bibtex:
            raw_key = parse_bib_key(bibtex)
            if raw_key:
                sanitized = re.sub(r"[^A-Za-z0-9_]+", "_", raw_key).strip("_")
                if not sanitized:
                    sanitized = build_fallback_key(entry, fallback_prefix=fallback_prefix)
                if sanitized != raw_key:
                    bibtex = bibtex.replace(raw_key, sanitized, 1)
                bib_key = sanitized
                break
    if not bib_key:
        bib_key = build_fallback_key(entry, fallback_prefix=fallback_prefix)
    custom_key = compute_custom_key(entry, metadata, fallback_prefix)
    if bibtex:
        raw_key = parse_bib_key(bibtex)
        if raw_key and raw_key != custom_key:
            bibtex = bibtex.replace(raw_key, custom_key, 1)
    final_key = re.sub(r"[^A-Za-z0-9_-]+", "_", custom_key).strip("_")
    if not final_key:
        final_key = build_fallback_key(entry, fallback_prefix=fallback_prefix)
    if bibtex:
        raw_key = parse_bib_key(bibtex)
        if raw_key and raw_key != final_key:
            bibtex = bibtex.replace(raw_key, final_key, 1)
    return final_key, bibtex


def fetch_openalex_bibtex(session: requests.Session, openalex_id: Optional[str]) -> Optional[str]:
    if not openalex_id:
        return None
    identifier = openalex_id.rsplit("/", 1)[-1]
    url = f"https://api.openalex.org/works/{identifier}/bibtex"
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    if response.status_code == 200 and response.text.strip():
        return response.text.strip()
    return None


def fetch_doi_bibtex(session: requests.Session, doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    normalized = normalize_doi(doi)
    if not normalized:
        return None
    url = f"https://doi.org/{normalized}"
    headers = {"Accept": "application/x-bibtex", "User-Agent": USER_AGENT}
    response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response.status_code == 200 and response.text.strip():
        return response.text.strip()
    return None


def fetch_arxiv_bibtex(session: requests.Session, arxiv_id: Optional[str]) -> Optional[str]:
    if not arxiv_id:
        return None
    cleaned = str(arxiv_id).strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("arXiv:", "").replace("ARXIV:", "")
    cleaned = cleaned.replace("http://arxiv.org/abs/", "").replace("https://arxiv.org/abs/", "")
    cleaned = cleaned.replace("https://export.arxiv.org/abs/", "")
    cleaned = cleaned.replace("http://arxiv.org/pdf/", "").replace("https://arxiv.org/pdf/", "")
    cleaned = cleaned.replace("https://export.arxiv.org/pdf/", "")
    cleaned = cleaned.replace(".pdf", "")
    url = f"https://export.arxiv.org/bibtex/{cleaned}"
    headers = {"User-Agent": USER_AGENT}
    response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response.status_code == 200 and response.text.strip():
        return response.text.strip()
    return None


def ensure_bib_record(
    session: requests.Session,
    bib_records: Dict[str, Dict[str, Any]],
    bib_key: str,
    *,
    title: str,
    abstract: str,
    metadata: Dict[str, Any],
    bibtex: Optional[str] = None,
) -> None:
    record = bib_records.get(bib_key) or {
        "title": title,
        "abstract": abstract,
        "bibtex": None,
    }
    if not record.get("title"):
        record["title"] = title
    if not record.get("abstract"):
        record["abstract"] = abstract

    if not record.get("bibtex") and bibtex:
        desired_year = None
        for key in ("updated", "published"):
            value = metadata.get(key)
            if value:
                match = re.search(r"(\d{4})", str(value))
                if match:
                    desired_year = match.group(1)
                    break
        if desired_year:
            bibtex = re.sub(r"(year\s*=\s*\{)\d{4}(\})", rf"\g<1>{desired_year}\2", bibtex, count=1)
        record["bibtex"] = bibtex

    bib_records[bib_key] = record


def download_entry(
    session: requests.Session,
    entry: Dict[str, object],
    source: str,
    pdf_url: Optional[str],
    *,
    bib_records: Dict[str, Dict[str, Any]],
) -> DownloadRecord:
    title = entry.get("title", "(無標題)")
    if not isinstance(title, str):
        title = str(title)
    identifier = identify_entry(entry)
    metadata_raw = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    metadata = dict(metadata_raw) if isinstance(metadata_raw, dict) else {}
    bib_key, bibtex = resolve_bibtex_and_key(session, entry, metadata, fallback_prefix=source)
    abstract = extract_abstract(entry)
    ensure_bib_record(
        session,
        bib_records,
        bib_key,
        title=title,
        abstract=abstract,
        metadata=metadata,
        bibtex=bibtex,
    )

    filename = f"{bib_key}.pdf"
    dest = OUTPUT_DIR / filename

    if dest.exists():
        try:
            with dest.open("rb") as f:
                header = f.read(512).strip()
            if header.startswith(b"%PDF-"):
                ensure_bib_record(
                    session,
                    bib_records,
                    bib_key,
                    title=title,
                    abstract=abstract,
                    metadata=metadata,
                    bibtex=bibtex,
                )
                return DownloadRecord(source=source, title=title, url=pdf_url, filepath=dest)
            dest.unlink(missing_ok=True)
        except Exception:
            dest.unlink(missing_ok=True)
    if not pdf_url:
        return DownloadRecord(source=source, title=title, url=None, filepath=None, reason="無可用 PDF 連結")
    try:
        stream_download(session, pdf_url, dest)
        time.sleep(DOWNLOAD_SLEEP_SECONDS)
        with dest.open("rb") as f:
            header = f.read(512).strip()
        if not header.startswith(b"%PDF-"):
            dest.unlink(missing_ok=True)
            return DownloadRecord(
                source=source,
                title=title,
                url=pdf_url,
                filepath=None,
                reason="回應非 PDF 內容",
            )
        ensure_bib_record(
            session,
            bib_records,
            bib_key,
            title=title,
            abstract=abstract,
            metadata=metadata,
            bibtex=bibtex,
        )
        return DownloadRecord(source=source, title=title, url=pdf_url, filepath=dest)
    except requests.RequestException as exc:
        return DownloadRecord(source=source, title=title, url=pdf_url, filepath=None, reason=str(exc))


def process_arxiv_entries(
    session: requests.Session,
    *,
    bib_records: Dict[str, Dict[str, Any]],
    max_entries: Optional[int] = None,
) -> List[DownloadRecord]:
    entries = load_json(ARXIV_JSON)
    targets: List[Dict[str, object]] = []
    for entry in entries:
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            continue
        year = parse_year(str(metadata.get("published", "")))
        verdict = str(entry.get("final_verdict", ""))
        if year and year > 2022 and "納入" in verdict:
            targets.append(entry)
    if max_entries is not None:
        targets = targets[:max_entries]
    results: List[DownloadRecord] = []
    total = len(targets)
    for entry in targets:
        url = resolve_arxiv_pdf(entry)
        record = download_entry(session, entry, source="arxiv", pdf_url=url, bib_records=bib_records)
        results.append(record)
        _print_progress("arXiv", len(results), total)
    return results


def process_snowball_entries(
    session: requests.Session,
    *,
    bib_records: Dict[str, Dict[str, Any]],
    max_entries: Optional[int] = None,
) -> List[DownloadRecord]:
    entries = load_json(SNOWBALL_JSON)
    results: List[DownloadRecord] = []
    filtered_entries: List[Dict[str, object]] = []
    for entry in entries:
        verdict = str(entry.get("final_verdict", ""))
        if "納入" not in verdict:
            continue
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            continue
        filtered_entries.append(entry)
    if max_entries is not None:
        filtered_entries = filtered_entries[:max_entries]

    total = len(filtered_entries)
    for entry in filtered_entries:
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        pdf_url = fetch_openalex_pdf(session, metadata.get("openalex_id"))
        if not pdf_url:
            for candidate in candidate_urls_from_doi(metadata.get("doi")):
                pdf_url = candidate
                break
        if not pdf_url:
            pdf_url = search_arxiv_by_title(session, str(entry.get("title", "")))
        record = download_entry(session, entry, source="snowball", pdf_url=pdf_url, bib_records=bib_records)
        results.append(record)
        _print_progress("Snowball", len(results), total)
    return results


def summarize(records: Sequence[DownloadRecord]) -> None:
    ok = [r for r in records if r.ok]
    failed = [r for r in records if not r.ok]
    print(f"成功下載: {len(ok)} 筆")
    print(f"失敗/跳過: {len(failed)} 筆")
    if failed:
        print("以下條目需要人工處理：")
        for rec in failed:
            reason = rec.reason or "未知原因"
            print(f"- [{rec.source}] {rec.title} -> {reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Speech LM PDFs and aggregate BibTeX")
    parser.add_argument("--max-arxiv", type=int, default=None, help="限制初審下載筆數")
    parser.add_argument("--max-snowball", type=int, default=None, help="限制雪球下載筆數")
    parser.add_argument("--skip-arxiv", action="store_true", help="略過初審結果下載")
    parser.add_argument("--skip-snowball", action="store_true", help="略過雪球結果下載")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_output_dir()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    bib_records: Dict[str, Dict[str, Any]] = {}

    if not args.skip_arxiv:
        print("處理 arXiv 結果...")
        arxiv_records = process_arxiv_entries(
            session,
            bib_records=bib_records,
            max_entries=args.max_arxiv,
        )
        summarize(arxiv_records)
        print()

    if not args.skip_snowball:
        print("處理雪球結果...")
        snowball_records = process_snowball_entries(
            session,
            bib_records=bib_records,
            max_entries=args.max_snowball,
        )
        summarize(snowball_records)

    if bib_records:
        metadata_output = [
            {
                "id": key,
                "title": data.get("title", ""),
                "abstract": data.get("abstract", ""),
                "bibtex": data.get("bibtex"),
            }
            for key, data in sorted(bib_records.items())
        ]
        BIB_JSON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        BIB_JSON_OUTPUT.write_text(
            json.dumps(metadata_output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n已寫出 BibTeX 統整檔：{BIB_JSON_OUTPUT}")


if __name__ == "__main__":
    main()
