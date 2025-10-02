import json
from pathlib import Path

import requests

from src.utils import paper_downloaders


def test_download_dblp_entry_full_metadata_dump():
    dblp_key = "journals/corr/abs-2406-18871"

    session = requests.Session()

    tmp_download_dir = Path("test/.tmp/dblp_full")
    tmp_download_dir.mkdir(parents=True, exist_ok=True)

    result = paper_downloaders.download_dblp_entry(
        dblp_key,
        tmp_download_dir,
        session=session,
    )

    metadata = result.metadata
    assert "raw_fields" in metadata and metadata["raw_fields"], "raw_fields should capture the full RDF content"
    assert any(
        tag.endswith("title")
        for tag in metadata["raw_fields"].keys()
    ), "title field missing from raw_fields"

    artifact_dir = Path("test_artifacts/metadata_harvest/dblp_full")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{paper_downloaders._safe_stem(dblp_key)}.json"
    artifact_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    assert artifact_path.exists(), "Metadata artifact should be created for inspection"
