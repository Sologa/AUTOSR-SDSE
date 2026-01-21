from __future__ import annotations

import json
from pathlib import Path

from src.pipelines.topic_pipeline import (
    _parse_date_bound,
    resolve_workspace,
    seed_surveys_from_arxiv_cutoff_first,
)


def test_seed_cutoff_first_live() -> None:
    Path("test_artifacts").mkdir(parents=True, exist_ok=True)
    Path("test/.tmp").mkdir(parents=True, exist_ok=True)

    topic = "Discrete Audio Tokens: More Than a Survey!"
    workspace_root = Path("test_artifacts") / "seed_cutoff_first"
    ws = resolve_workspace(topic=topic, workspace_root=workspace_root / "workspaces")

    seed_surveys_from_arxiv_cutoff_first(
        ws,
        seed_rewrite_n=3,
        seed_arxiv_max_results_per_query=10,
        seed_max_merged_results=50,
        cutoff_arxiv_id="2506.10274",
    )

    cutoff_payload = json.loads(ws.cutoff_path.read_text(encoding="utf-8"))
    selection_path = ws.seed_queries_dir / "seed_selection.json"
    selection_payload = json.loads(selection_path.read_text(encoding="utf-8"))
    arxiv_path = ws.seed_queries_dir / "arxiv.json"
    arxiv_payload = json.loads(arxiv_path.read_text(encoding="utf-8"))

    cutoff = cutoff_payload.get("cutoff") or {}
    cutoff_id = str(cutoff.get("arxiv_id") or "").strip()
    date_field = str(cutoff_payload.get("date_field") or "published")
    cutoff_date_raw = str(cutoff_payload.get("cutoff_date") or "").strip()
    cutoff_date = _parse_date_bound(cutoff_date_raw, label="cutoff_date")

    assert cutoff_id
    assert cutoff_date is not None

    selected = selection_payload.get("selected") if isinstance(selection_payload, dict) else []
    if isinstance(selected, list):
        for item in selected:
            if not isinstance(item, dict):
                continue
            assert item.get("arxiv_id") != cutoff_id
            raw_date = item.get(date_field)
            parsed = _parse_date_bound(str(raw_date), label="selected_date") if raw_date else None
            assert parsed is not None
            assert parsed <= cutoff_date

    queries = arxiv_payload.get("queries") if isinstance(arxiv_payload, dict) else []
    if isinstance(queries, list):
        for query in queries:
            if not isinstance(query, dict):
                continue
            filtered = query.get("filtered")
            kept = query.get("results_kept")
            if isinstance(filtered, dict) and isinstance(kept, list):
                assert filtered.get("kept") == len(kept)
