from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.utils.env import load_env_file
from src.utils.keyword_extractor import ExtractParams, extract_search_terms_from_surveys


MODEL = os.environ.get("AUTOSR_OPENAI_MODEL", "gpt-4o-mini")
PDF_SOURCE_ROOT = Path("resources/datasets/arxiv_papers")
ARTIFACT_DIR = Path("test_artifacts/keyword_extractor_live")


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


def test_extract_search_terms_combined_mode(tmp_path: Path) -> None:
    _require_api_key()
    pdfs = _pick_small_pdfs(1)
    params = ExtractParams(
        topic="spoken language models",
        max_queries=3,
        include_ethics=False,
        mode="combined",
        custom_categories=["core_concepts"],
        seed_anchors=["spoken language model"],
    )

    result = extract_search_terms_from_surveys(
        pdfs,
        provider="openai",
        model=MODEL,
        params=params,
        temperature=0.15,
        usage_log_path=tmp_path / "combined_usage.json",
    )

    assert isinstance(result, dict)
    assert "anchor_terms" in result and result["anchor_terms"]
    assert "queries" in result and isinstance(result["queries"], list)
    _write_artifact("combined", result)


def test_extract_search_terms_two_step_mode(tmp_path: Path) -> None:
    _require_api_key()
    pdfs = _pick_small_pdfs(2)
    params = ExtractParams(
        topic="spoken language models",
        max_queries=3,
        include_ethics=False,
        mode="two_step",
        custom_categories=["core_concepts"],
        seed_anchors=["spoken language model"],
    )

    result = extract_search_terms_from_surveys(
        pdfs,
        provider="openai",
        model=MODEL,
        params=params,
        temperature=0.2,
        usage_log_path=tmp_path / "two_step_usage.json",
    )

    assert isinstance(result, dict)
    assert "anchor_terms" in result and result["anchor_terms"]
    assert "queries" in result and result["queries"]
    assert isinstance(result.get("papers"), list)
    _write_artifact("two_step", result)
