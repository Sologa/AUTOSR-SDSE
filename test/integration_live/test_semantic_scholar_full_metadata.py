import json
import os
from pathlib import Path

import requests

from src.utils import paper_downloaders
from src.utils.env import load_env_file


def test_download_semantic_scholar_entry_full_metadata_dump():
    load_env_file()
    api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    assert api_key, "SEMANTIC_SCHOLAR_API_KEY must be set for live Semantic Scholar tests"

    paper_id = "arXiv:2406.18871"

    session = requests.Session()
    try:
        tmp_dir = Path("test/.tmp/semantic_scholar_full")
        tmp_dir.mkdir(parents=True, exist_ok=True)

        result = paper_downloaders.download_semantic_scholar_paper(
            paper_id,
            tmp_dir,
            session=session,
            api_key=api_key,
        )

        metadata = result.metadata
        assert metadata.get("paperId"), "paperId should be present in metadata"
        assert metadata.get("author_names"), "author_names should include at least one author"
        assert metadata.get("pdf_candidates") is not None, "pdf_candidates should be recorded"

        artifact_dir = Path("test_artifacts/metadata_harvest/semantic_scholar_full")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{paper_downloaders._safe_stem(paper_id)}.json"
        artifact_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        assert artifact_path.exists(), "Metadata artifact should be created for inspection"
    finally:
        session.close()
