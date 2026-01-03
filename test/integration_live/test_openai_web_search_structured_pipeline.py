"""Live pipeline test combining staged web search with structured criteria JSON."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from src.utils.env import load_env_file
from src.utils.structured_web_search_pipeline import (
    CriteriaPipelineConfig,
    CriteriaPipelineResult,
    FormatterStageConfig,
    SearchStageConfig,
    run_structured_criteria_pipeline,
)

SURVEY_TOPIC = os.environ.get(
    "WEB_SEARCH_SURVEY_TOPIC",
    "speech language model",
)

RECENCY_HINT = os.environ.get("WEB_SEARCH_RECENCY_HINT", "過去3年")
SEARCH_MODEL = os.environ.get("WEB_SEARCH_STAGE1_MODEL", "gpt-4o")
FORMATTER_MODEL = os.environ.get("WEB_SEARCH_STAGE2_MODEL", "gpt-5")
SEARCH_TEMPERATURE = float(os.environ.get("WEB_SEARCH_STAGE1_TEMPERATURE", "0.7"))
FORMATTER_TEMPERATURE = float(os.environ.get("WEB_SEARCH_STAGE2_TEMPERATURE", "0.2"))
SEARCH_MAX_OUTPUT_TOKENS = int(os.environ.get("WEB_SEARCH_STAGE1_MAX_TOKENS", "1200"))
FORMATTER_MAX_OUTPUT_TOKENS = int(os.environ.get("WEB_SEARCH_STAGE2_MAX_TOKENS", "1200"))


def _require_api_key() -> str:
    """載入 `.env` 並確認 `OPENAI_API_KEY` 存在，避免誤跑在無金鑰環境。"""

    load_env_file()
    key = os.environ.get("OPENAI_API_KEY")
    assert key, "OPENAI_API_KEY is required for live OpenAI web search tests."
    return key


def _slugify(text: str) -> str:
    base = re.sub(r"[^A-Za-z0-9一-龥]+", "_", text.strip())
    base = re.sub(r"_+", "_", base).strip("_")
    return base.lower() or "topic"


def _normalize_topics(items: Iterable[str]) -> List[str]:
    normalized: List[str] = []
    for value in items:
        value_clean = str(value).strip()
        if value_clean:
            normalized.append(value_clean)
    return normalized


def _print_required(label: str, items: Sequence[Dict[str, Any]]) -> None:
    if not items:
        print(f"\n[WARN] {label} 無任何條目")
        return
    print(f"\n--- {label} ---")
    for idx, item in enumerate(items, start=1):
        criterion = str(item.get("criterion", "")).strip()
        topic_ids = _normalize_topics(item.get("topic_ids", []) or [])
        source = str(item.get("source", "")).strip()
        print(f"[{idx}] {criterion}")
        print(f"     topic_ids={topic_ids} | source={source}")


def _print_any_of(groups: Sequence[Dict[str, Any]]) -> None:
    if not groups:
        print("\n[INFO] Any-of groups 目前為空陣列。")
        return
    print("\n--- Inclusion Any-of Groups ---")
    for idx, group in enumerate(groups, start=1):
        label = str(group.get("label", "")).strip() or f"Group {idx}"
        options = group.get("options", []) or []
        print(f"[{idx}] {label}")
        if not options:
            print("     [WARN] 該群組未提供任何 option")
            continue
        for sub_idx, option in enumerate(options, start=1):
            criterion = str(option.get("criterion", "")).strip()
            topic_ids = _normalize_topics(option.get("topic_ids", []) or [])
            source = str(option.get("source", "")).strip()
            print(f"     ({sub_idx}) {criterion}")
            print(f"         topic_ids={topic_ids} | source={source}")


def _collect_topic_ids_from_groups(groups: Sequence[Dict[str, Any]]) -> List[str]:
    collected: List[str] = []
    for group in groups:
        for option in group.get("options", []) or []:
            collected.extend(_normalize_topics(option.get("topic_ids", []) or []))
    return collected


def _write_artifacts(result: CriteriaPipelineResult) -> Path:
    topic_slug = _slugify(result.topic)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")

    Path("test_artifacts").mkdir(parents=True, exist_ok=True)
    Path("test/.tmp").mkdir(parents=True, exist_ok=True)

    base_dir = Path("test_artifacts/openai_web_search_structured_pipeline") / topic_slug
    base_dir.mkdir(parents=True, exist_ok=True)

    notes_path = base_dir / f"notes_{timestamp}.txt"
    notes_path.write_text(result.raw_notes, encoding="utf-8")

    structured_path = base_dir / f"criteria_{timestamp}.json"
    structured_path.write_text(
        json.dumps(result.structured_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    prompt_path = base_dir / f"prompts_{timestamp}.json"
    prompt_payload = {
        "search_prompt": result.search_prompt,
        "formatter_messages": result.formatter_messages,
    }
    prompt_path.write_text(json.dumps(prompt_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return structured_path


def test_openai_web_search_structured_pipeline() -> None:
    """兩階段流程：stage1 web search、stage2 JSON formatter，符合原本測試語意。"""

    _require_api_key()

    search_config = SearchStageConfig(
        model=SEARCH_MODEL,
        temperature=SEARCH_TEMPERATURE,
        max_output_tokens=SEARCH_MAX_OUTPUT_TOKENS,
    )
    formatter_config = FormatterStageConfig(
        model=FORMATTER_MODEL,
        temperature=FORMATTER_TEMPERATURE,
        max_output_tokens=FORMATTER_MAX_OUTPUT_TOKENS,
    )
    config = CriteriaPipelineConfig(
        recency_hint=RECENCY_HINT,
        search=search_config,
        formatter=formatter_config,
    )

    result = run_structured_criteria_pipeline(
        SURVEY_TOPIC,
        config=config,
    )

    print("\n=== Stage 1 Web Search Prompt ===\n")
    print(result.search_prompt)
    print("\n=== Original Structured JSON Prompt (Stage 2 Guideline) ===\n")
    print(result.structured_prompt_template)
    print("\n=== Stage 1 Raw Notes ===\n")
    print(result.raw_notes)
    print("\n=== Stage 2 Formatter Messages ===\n")
    print(json.dumps(result.formatter_messages, ensure_ascii=False, indent=2))
    print("\n=== Stage 2 Raw Output ===\n")
    print(result.structured_text)

    structured = result.structured_payload
    print("\n=== Parsed JSON ===")
    print(json.dumps(structured, ensure_ascii=False, indent=2))

    topic_definition = str(structured.get("topic_definition", "")).strip()
    if not topic_definition:
        print("\n[WARN] 缺少 topic_definition。")

    summary_topics = {
        str(entry.get("id")).strip(): str(entry.get("description", "")).strip()
        for entry in structured.get("summary_topics", []) or []
        if str(entry.get("id")).strip()
    }
    if not summary_topics:
        print("\n[WARN] summary_topics 為空，後續覆蓋檢查將略過。")

    inclusion_block = structured.get("inclusion_criteria", {}) or {}
    if not isinstance(inclusion_block, dict):
        print("\n[WARN] inclusion_criteria 非 dict 結構。")
        inclusion_block = {}

    required_items = inclusion_block.get("required", []) or []
    any_of_groups = inclusion_block.get("any_of", []) or []

    _print_required("Inclusion Criteria (Required)", required_items)
    _print_any_of(any_of_groups)

    exclusion_items = structured.get("exclusion_criteria", []) or []
    _print_required("Exclusion Criteria", exclusion_items)

    sources = structured.get("sources", []) or []
    if not sources:
        print("\n[WARN] sources 為空。")
    else:
        print(f"\n[INFO] 共計 {len(sources)} 筆來源。")

    if topic_definition and required_items:
        first = required_items[0]
        first_text = str(first.get("criterion", "")).strip()
        expected_prefix = f"主題定義：{topic_definition}"
        if not first_text.startswith(expected_prefix):
            print(
                "\n[WARN] 第一條 required criterion 未逐字引用 topic_definition："
                f"應為 '{expected_prefix}…'"
            )

    covered_from_required: List[str] = []
    for item in required_items:
        covered_from_required.extend(_normalize_topics(item.get("topic_ids", []) or []))

    covered_from_any_of = _collect_topic_ids_from_groups(any_of_groups)
    covered_from_exclusion: List[str] = []
    for item in exclusion_items:
        covered_from_exclusion.extend(_normalize_topics(item.get("topic_ids", []) or []))

    if summary_topics:
        coverage_set = set(covered_from_required + covered_from_any_of + covered_from_exclusion)
        missing = [tid for tid in summary_topics.keys() if tid not in coverage_set]
        if missing:
            print(f"\n[WARN] 尚有未被引用的 summary topic: {missing}")
        else:
            print("\n[INFO] 所有 summary topics 至少被一個條件引用。")

    artifact_path = _write_artifacts(result)
    print(f"\n[INFO] 已輸出結構化結果至 {artifact_path}")

    print("\n=== Usage Metadata ===\n")
    print("Web search:", result.search_result.usage)
    print("Formatter:", result.formatter_result.usage)
