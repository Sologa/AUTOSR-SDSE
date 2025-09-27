import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, List

import requests

from src.utils.env import load_env_file
from src.utils.paper_downloaders import (
    DownloadResult,
    PaperDownloadError,
    download_arxiv_paper,
    download_dblp_entry,
    download_semantic_scholar_paper,
)

from src.utils.paper_workflows import (
    collect_arxiv_ids,
    dblp_key_for_arxiv_id,
    download_records_to_pdfs,
    load_records_from_directory,
    respect_semantic_scholar_rate_limit,
    search_arxiv_for_topic,
    search_dblp_for_topic,
    search_semantic_scholar_for_topic,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_env_file(PROJECT_ROOT / ".env", override=False)


DEFAULT_DATASET_ROOT = PROJECT_ROOT / "resources" / "datasets" / "arxiv_papers"
DATASET_ROOT = Path(os.environ.get("ARXIV_DATASET_ROOT", str(DEFAULT_DATASET_ROOT))).expanduser()
DOWNLOAD_SUMMARY_DIR = Path("test_artifacts/live_downloads")
QUERY_OUTPUT_DIR = Path("test_artifacts/live_queries/spoken_language_model")
TOPIC_DOWNLOAD_DIR = Path("test_artifacts/live_downloads/spoken_language_model_assets")

ANCHOR_TERMS = [
    "spoken language model",
    "speech language model",
    "spoken language modeling",
    "speech modeling",
    "spoken dialogue model",
]

SEARCH_TERMS = ["survey", "review", "overview"]


class LivePaperDownloaderTests(unittest.TestCase):
    """Integration tests that hit the real services."""

    @classmethod
    def setUpClass(cls) -> None:
        """Initialise shared HTTP session and collect arXiv IDs for the suite."""
        if not DATASET_ROOT.exists():
            raise unittest.SkipTest(f"Dataset folder not found: {DATASET_ROOT}")

        cls.arxiv_ids = collect_arxiv_ids(DATASET_ROOT)
        if not cls.arxiv_ids:
            raise unittest.SkipTest("No arXiv PDFs discovered under dataset root")

        cls.session = requests.Session()
        cls.semantic_scholar_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        cls.summary: Dict[str, List[Dict[str, object]]] = {
            "arxiv": [],
            "semantic_scholar": [],
            "dblp": [],
        }

    @classmethod
    def tearDownClass(cls) -> None:
        """Persist download summaries and close the shared HTTP session."""
        try:
            if cls.summary and any(cls.summary.values()):
                DOWNLOAD_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
                output_path = DOWNLOAD_SUMMARY_DIR / "paper_sources.json"
                output_path.write_text(json.dumps(cls.summary, indent=2), encoding="utf-8")
        finally:
            cls.session.close()

    def _handle_network_exception(self, source: str, exc: Exception) -> None:
        """Skip the current subtest when transient network issues occur."""
        if isinstance(exc, (requests.RequestException, PaperDownloadError)):
            self.skipTest(f"{source} live call failed: {exc}")
        raise exc

    def _append_summary(self, source: str, identifier: str, result: DownloadResult) -> None:
        """Capture minimal download metadata for later inspection."""
        record = {
            "identifier": identifier,
            "title": result.metadata.get("title"),
            "pdf_downloaded": bool(result.pdf_path and result.pdf_path.exists()),
            "bibtex_downloaded": bool(result.bibtex_path and result.bibtex_path.exists()),
            "issues": result.issues,
        }
        self.summary[source].append(record)

    def test_arxiv_downloads(self) -> None:
        """Verify each curated arXiv ID exposes metadata and a downloadable PDF."""
        for arxiv_id in self.arxiv_ids:
            with self.subTest(arxiv_id=arxiv_id):
                with tempfile.TemporaryDirectory() as tmpdir:
                    try:
                        result = download_arxiv_paper(
                            arxiv_id,
                            Path(tmpdir),
                            session=self.session,
                        )
                    except Exception as exc:  # pragma: no cover - integration safeguard
                        self._handle_network_exception("arXiv", exc)
                        continue

                    self.assertTrue(result.metadata.get("title"))
                    self.assertTrue(result.metadata.get("authors"))
                    self.assertIsNotNone(result.pdf_path, "Expected arXiv PDF to be downloaded")
                    self.assertTrue(result.pdf_path and result.pdf_path.exists())
                    self._append_summary("arxiv", arxiv_id, result)

    def test_semantic_scholar_downloads(self) -> None:
        """Ensure Semantic Scholar responds for the curated set within rate limits."""
        for arxiv_id in self.arxiv_ids:
            semantic_id = f"arXiv:{arxiv_id}"
            with self.subTest(semantic_id=semantic_id):
                with tempfile.TemporaryDirectory() as tmpdir:
                    attempts = 2 if not self.semantic_scholar_api_key else 1
                    for attempt in range(attempts):
                        respect_semantic_scholar_rate_limit(
                            api_key_present=bool(self.semantic_scholar_api_key)
                        )
                        try:
                            result = download_semantic_scholar_paper(
                                semantic_id,
                                Path(tmpdir),
                                session=self.session,
                                api_key=self.semantic_scholar_api_key,
                            )
                            break
                        except requests.HTTPError as exc:
                            response = getattr(exc, "response", None)
                            status = getattr(response, "status_code", None)
                            if (
                                not self.semantic_scholar_api_key
                                and status in {429, 503}
                                and attempt == 0
                            ):
                                time.sleep(3)
                                continue
                            self._handle_network_exception("Semantic Scholar", exc)
                            break
                        except Exception as exc:  # pragma: no cover - integration safeguard
                            self._handle_network_exception("Semantic Scholar", exc)
                            break
                    else:  # pragma: no cover - defensive guard
                        continue

                    self.assertTrue(result.metadata.get("title"))
                    self.assertIn("authors", result.metadata)

                    pdf_exists = result.pdf_path and result.pdf_path.exists()
                    bib_exists = result.bibtex_path and result.bibtex_path.exists()
                    self.assertTrue(
                        pdf_exists or bib_exists,
                        "Semantic Scholar should return either an open-access PDF or a citation entry",
                    )
                    self._append_summary("semantic_scholar", semantic_id, result)

    def test_dblp_downloads(self) -> None:
        """Confirm DBLP records exist and expose at least BibTeX entries."""
        for arxiv_id in self.arxiv_ids:
            dblp_key = dblp_key_for_arxiv_id(arxiv_id)
            with self.subTest(dblp_key=dblp_key):
                with tempfile.TemporaryDirectory() as tmpdir:
                    try:
                        result = download_dblp_entry(
                            dblp_key,
                            Path(tmpdir),
                            session=self.session,
                        )
                    except Exception as exc:  # pragma: no cover - integration safeguard
                        self._handle_network_exception("DBLP", exc)
                        continue

                    self.assertTrue(result.metadata.get("title"))
                    self.assertIn("authors", result.metadata)
                    self.assertTrue(
                        result.bibtex_path and result.bibtex_path.exists(),
                        "DBLP should expose BibTeX downloads for corrs entries",
                    )
                    if result.pdf_path:
                        self.assertTrue(result.pdf_path.exists())
                    self._append_summary("dblp", dblp_key, result)



class SpokenLanguageModelSearchTests(unittest.TestCase):
    _topic_records_cache: Dict[str, List[Dict[str, object]]] | None = None

    @classmethod
    def setUpClass(cls) -> None:
        """Create a session for search queries and ensure output directories exist."""
        cls.session = requests.Session()
        cls.semantic_scholar_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        QUERY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        TOPIC_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls) -> None:
        """Release the shared HTTP session after the search tests finish."""
        cls.session.close()

    def _load_or_fetch_topic_records(self) -> Dict[str, List[Dict[str, object]]]:
        """Retrieve topic records, preferring cached JSON when present."""

        if self.__class__._topic_records_cache is not None:
            return self.__class__._topic_records_cache

        existing = load_records_from_directory(QUERY_OUTPUT_DIR)
        if existing:
            self.__class__._topic_records_cache = existing
            return existing

        records = {
            "arxiv": search_arxiv_for_topic(self.session, ANCHOR_TERMS, SEARCH_TERMS),
            "semantic_scholar": search_semantic_scholar_for_topic(
                self.session,
                ANCHOR_TERMS,
                SEARCH_TERMS,
                api_key=self.semantic_scholar_api_key,
            ),
            "dblp": search_dblp_for_topic(self.session, ANCHOR_TERMS, SEARCH_TERMS),
        }

        for source, entries in records.items():
            output_path = QUERY_OUTPUT_DIR / f"{source}.json"
            output_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

        self.__class__._topic_records_cache = records
        return records

    def test_collect_topic_surveys(self) -> None:
        """Collect candidate spoken language model surveys across three sources."""
        try:
            data = self._load_or_fetch_topic_records()
        except requests.RequestException as exc:  # pragma: no cover - integration safeguard
            self.skipTest(f"Live search failed: {exc}")
            return

        for source, records in data.items():
            self.assertIsInstance(records, list)

        total_records = sum(len(records) for records in data.values())
        self.assertGreater(total_records, 0, "No search results collected for spoken language model surveys")

        if not self.semantic_scholar_api_key:
            time.sleep(3.0)

    def test_download_topic_survey_assets(self) -> None:
        """Download PDFs/BibTeX for spoken language model survey candidates."""

        try:
            records = self._load_or_fetch_topic_records()
        except requests.RequestException as exc:  # pragma: no cover - integration safeguard
            self.skipTest(f"Live search failed: {exc}")
            return

        collected = download_records_to_pdfs(
            records,
            TOPIC_DOWNLOAD_DIR,
            session=self.session,
            api_key=self.semantic_scholar_api_key,
        )

        serialised = {}
        successful_pdf = 0
        for source, results in collected.items():
            serialised[source] = []
            for result in results:
                if result.pdf_path and result.pdf_path.exists():
                    successful_pdf += 1
                serialised[source].append(
                    {
                        "identifier": result.identifier,
                        "title": result.metadata.get("title"),
                        "pdf_path": str(result.pdf_path) if result.pdf_path else None,
                        "bibtex_path": str(result.bibtex_path) if result.bibtex_path else None,
                        "issues": result.issues,
                    }
                )

        output_path = TOPIC_DOWNLOAD_DIR / "download_results.json"
        output_path.write_text(json.dumps(serialised, indent=2), encoding="utf-8")

        total_attempts = sum(len(results) for results in collected.values())
        self.assertGreater(total_attempts, 0, "No records attempted for download")
        self.assertGreater(
            successful_pdf,
            0,
            "Expected at least one spoken language model survey PDF to download successfully",
        )

        if not self.semantic_scholar_api_key:
            time.sleep(3.0)
