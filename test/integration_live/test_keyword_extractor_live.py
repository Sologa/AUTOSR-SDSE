from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.utils.env import load_env_file
from src.utils.keyword_extractor import ExtractParams, extract_search_terms_from_surveys


MODEL = os.environ.get("AUTOSR_OPENAI_MODEL", "gpt-5")
PDF_SOURCE_ROOT = Path("test_artifacts/live_downloads/spoken_language_model_assets/arxiv")
ARTIFACT_DIR = Path("test_artifacts/keyword_extractor_live")

REASONING_EFFORT = "high"

def _require_api_key() -> str:
    load_env_file()
    key = os.environ.get("OPENAI_API_KEY")
    assert key, "OPENAI_API_KEY is required for keyword extractor live tests."
    return key


def _pick_small_pdfs(n: int) -> list[Path]:
    pdfs: list[Path] = []
    for path in sorted(PDF_SOURCE_ROOT.rglob("*.pdf")):
        try:
            if path.stat().st_size <= 4 * 1024 * 1024:
                pdfs.append(path)
        except FileNotFoundError:
            continue
        if len(pdfs) >= n:
            break
    assert len(pdfs) >= n, f"Need at least {n} PDFs under {PDF_SOURCE_ROOT}"
    return pdfs


def _write_artifact(prefix: str, payload: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = ARTIFACT_DIR / f"{prefix}_{ts}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_extract_search_terms_single_pdf() -> None:
    _require_api_key()
    pdfs = _pick_small_pdfs(1)
    params = ExtractParams(
        topic="speech language models",
        max_queries=40,
        include_ethics=False,
        seed_anchors=["speech language model"],
        max_output_tokens=128000,
        reasoning_effort=REASONING_EFFORT,
    )

    result = extract_search_terms_from_surveys(
        pdfs,
        provider="openai",
        model=MODEL,
        params=params,
        temperature=1.0,
        reasoning_effort=REASONING_EFFORT,
        max_output_tokens=128000,
    )

    assert isinstance(result, dict)
    assert "anchor_terms" in result and result["anchor_terms"]
    assert "papers" in result and isinstance(result["papers"], list) and result["papers"]
    first_paper = result["papers"][0]
    assert first_paper.get("title")
    assert first_paper.get("abstract")
    assert str(first_paper.get("source_id", "")).startswith("arXiv:")
    assert "reviewer_profile" not in result
    assert "queries" not in result
    _write_artifact("single", result)


def test_extract_search_terms_multi_pdf() -> None:
    _require_api_key()
    pdfs = _pick_small_pdfs(2)
    params = ExtractParams(
        topic="speech language models",
        max_queries=40,
        include_ethics=False,
        seed_anchors=["speech language model"],
        max_output_tokens=128000,
        reasoning_effort=REASONING_EFFORT,
    )

    result = extract_search_terms_from_surveys(
        pdfs,
        provider="openai",
        model=MODEL,
        params=params,
        temperature=1.0,
        reasoning_effort=REASONING_EFFORT,
        max_output_tokens=128000,
    )

    assert isinstance(result, dict)
    assert "anchor_terms" in result and result["anchor_terms"]
    assert isinstance(result.get("papers"), list)
    assert "reviewer_profile" not in result
    assert "queries" not in result
    _write_artifact("multi", result)
