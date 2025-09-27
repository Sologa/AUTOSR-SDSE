import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Tuple

import requests

from src.utils import paper_downloaders
from src.utils.paper_downloaders import (
    DownloadResult,
    download_arxiv_paper,
    download_dblp_entry,
    download_semantic_scholar_paper,
)


class MockResponse:
    def __init__(self, *, status_code: int = 200, content: bytes = b"", text: str = "", json_data=None):
        self.status_code = status_code
        self.content = content if content else text.encode("utf-8")
        self._text = text
        self._json = json_data

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            error = requests.HTTPError(f"status={self.status_code}")
            error.response = self  # type: ignore[attr-defined]
            raise error

    @property
    def text(self) -> str:
        if self._text:
            return self._text
        return self.content.decode("utf-8")

    def json(self):  # pragma: no cover - trivial wrapper
        if self._json is not None:
            return self._json
        return json.loads(self.text)


class MockSession:
    def __init__(self, responses: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], MockResponse]):
        self._responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        params = kwargs.get("params") or {}
        key = (url, tuple(sorted((str(k), str(v)) for k, v in params.items())))
        self.calls.append((url, kwargs))
        response = self._responses.get(key)
        if response is None:
            response = self._responses.get((url, tuple()))
        if response is None:
            raise AssertionError(f"Unexpected request: {url} with params {params}")
        return response


class PaperDownloadersTest(unittest.TestCase):
    def test_arxiv_downloads_all_assets(self):
        arxiv_id = "1234.5678"
        metadata_xml = """<?xml version='1.0' encoding='UTF-8'?>
        <feed xmlns='http://www.w3.org/2005/Atom'>
          <entry>
            <id>http://arxiv.org/abs/1234.5678v1</id>
            <title> Sample Title </title>
            <summary> Sample abstract. </summary>
            <published>2024-01-01T00:00:00Z</published>
            <updated>2024-01-02T00:00:00Z</updated>
            <author><name>Author One</name></author>
            <author><name>Author Two</name></author>
            <category term='cs.CL'/>
            <link rel='alternate' href='https://arxiv.org/abs/1234.5678'/>
            <link title='pdf' href='https://arxiv.org/pdf/1234.5678.pdf'/>
          </entry>
        </feed>
        """
        bibtex_html = "<html><body><pre>@article{sample, title={Sample Title}}</pre></body></html>"
        pdf_bytes = b"%PDF-1.4\n"

        session = MockSession(
            {
                (
                    "https://export.arxiv.org/api/query",
                    (("id_list", arxiv_id),),
                ): MockResponse(text=metadata_xml),
                (
                    "https://arxiv.org/pdf/1234.5678.pdf",
                    tuple(),
                ): MockResponse(content=pdf_bytes),
                (
                    "https://arxiv.org/bibtex/1234.5678",
                    tuple(),
                ): MockResponse(text=bibtex_html),
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = download_arxiv_paper(arxiv_id, Path(tmp), session=session)

            self.assertIsInstance(result, DownloadResult)
            self.assertEqual(result.metadata["title"], "Sample Title")
            self.assertEqual(result.metadata["authors"], ["Author One", "Author Two"])
            self.assertTrue(result.pdf_path and result.pdf_path.exists())
            self.assertEqual(result.pdf_path.read_bytes(), pdf_bytes)
            self.assertTrue(result.bibtex_path and result.bibtex_path.exists())
            self.assertIn("@article", result.bibtex_path.read_text())

    def test_semantic_scholar_downloads_assets(self):
        paper_id = "arXiv:2401.00001"
        metadata_json = {
            "paperId": paper_id,
            "title": "Sample Paper",
            "openAccessPdf": {"url": "https://example.org/sample.pdf"},
            "citationStyles": {"bibtex": "@article{sample, title={Sample}}"},
            "authors": [{"name": "Author"}],
        }
        fields_param = ",".join(paper_downloaders._SEMANTIC_SCHOLAR_FIELDS)

        session = MockSession(
            {
                (
                    "https://api.semanticscholar.org/graph/v1/paper/arXiv%3A2401.00001",
                    (("fields", fields_param),),
                ): MockResponse(json_data=metadata_json),
                (
                    "https://example.org/sample.pdf",
                    tuple(),
                ): MockResponse(content=b"%PDF-1.4\n"),
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = download_semantic_scholar_paper(paper_id, Path(tmp), session=session)

            self.assertEqual(result.metadata["title"], "Sample Paper")
            self.assertTrue(result.pdf_path and result.pdf_path.exists())
            self.assertTrue(result.bibtex_path and result.bibtex_path.exists())
            self.assertIn("@article", result.bibtex_path.read_text())

    def test_dblp_downloads_metadata_and_bibtex(self):
        dblp_key = "conf/sample/Key2024"
        rdf_content = """<?xml version='1.0' encoding='US-ASCII'?>
        <rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
                 xmlns:dblp='https://dblp.org/rdf/schema#'
                 xmlns:datacite='http://purl.org/spar/datacite/'
                 xmlns:litre='http://purl.org/spar/literal/'>
          <dblp:Inproceedings rdf:about='https://dblp.org/rec/conf/sample/Key2024'>
            <dblp:title>Sample Title</dblp:title>
            <dblp:yearOfPublication>2024</dblp:yearOfPublication>
            <dblp:publishedIn>SampleConf</dblp:publishedIn>
            <dblp:pagination>1-10</dblp:pagination>
            <dblp:primaryDocumentPage rdf:resource='https://example.org/sample.pdf'/>
            <dblp:hasSignature>
              <dblp:AuthorSignature>
                <dblp:signatureDblpName>Author One</dblp:signatureDblpName>
              </dblp:AuthorSignature>
            </dblp:hasSignature>
            <dblp:hasSignature>
              <dblp:AuthorSignature>
                <dblp:signatureDblpName>Author Two</dblp:signatureDblpName>
              </dblp:AuthorSignature>
            </dblp:hasSignature>
          </dblp:Inproceedings>
        </rdf:RDF>
        """

        session = MockSession(
            {
                (
                    "https://dblp.org/rec/conf/sample/Key2024.rdf",
                    tuple(),
                ): MockResponse(text=rdf_content),
                (
                    "https://example.org/sample.pdf",
                    tuple(),
                ): MockResponse(content=b"%PDF-1.4\n"),
                (
                    "https://dblp.org/rec/conf/sample/Key2024.bib?download=1",
                    tuple(),
                ): MockResponse(text="@inproceedings{sample, title={Sample Title}}"),
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = download_dblp_entry(dblp_key, Path(tmp), session=session)

            self.assertEqual(result.metadata["title"], "Sample Title")
            self.assertEqual(result.metadata["authors"], ["Author One", "Author Two"])
            self.assertTrue(result.pdf_path and result.pdf_path.exists())
            self.assertTrue(result.bibtex_path and result.bibtex_path.exists())


if __name__ == "__main__":
    unittest.main()
