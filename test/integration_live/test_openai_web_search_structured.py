"""Live web search test that requests structured criteria aligned with summary topics."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

from src.utils.env import load_env_file
from src.utils.openai_web_search import WebSearchOptions, ask_with_web_search


def _require_api_key() -> str:
    """載入 `.env` 並確認 `OPENAI_API_KEY` 存在，避免誤跑在無金鑰環境。"""

    load_env_file()
    key = os.environ.get("OPENAI_API_KEY")
    assert key, "OPENAI_API_KEY is required for live OpenAI web search tests."
    return key


# 與 `test_openai_web_search.py` 完全相同的主題、時間提示與模型設定。
# SURVEY_TOPIC = os.environ.get(
#     "WEB_SEARCH_SURVEY_TOPIC",
#     "我要寫一篇關於 speech language model 的 survey。請在查詢完相關資料後。給出主題的定義，並且列出論文錄入inclusion/exclusion criteria。 inclusion criteria中需要說明主題的定義。",
# )
SURVEY_TOPIC = os.environ.get(
    "WEB_SEARCH_SURVEY_TOPIC",
    "speech language model",
)

RECENCY_HINT = os.environ.get("WEB_SEARCH_RECENCY_HINT", "過去3年")
MODEL = os.environ.get("WEB_SEARCH_TEST_MODEL", "gpt-4.1")



def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    """從模型輸出中擷取 JSON 段落並解析為 dict。"""

    start = raw_text.find('{')
    end = raw_text.rfind('}')

    assert start != -1 and end != -1 and end > start, "回傳內容缺少 JSON 區段"
    payload = raw_text[start : end + 1]
    # 修正常見錯誤：模型有時會把字串用 "..." + "..." 方式拼接，這不符合 JSON 規範。
    # 這裡以 regex 將相鄰的兩個字串常值合併為一個字串，重複直到不再出現。
    concat_pat = re.compile(r'"(?P<a>(?:\\.|[^"\\])*)"\s*\+\s*"(?P<b>(?:\\.|[^"\\])*)"')
    while True:
        new_payload = concat_pat.sub(lambda m: '"' + m.group('a') + m.group('b') + '"', payload)
        if new_payload == payload:
            break
        payload = new_payload
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"無法解析 JSON：{exc}") from exc



def _build_prompt(topic: str, recency: str) -> str:
    """要求模型輸出含主題定義且與主題對齊的結構化結果。"""

    return (
        "你是系統性回顧助理。\n"
        f"主題：{topic}；時間範圍：{recency}。\n"
        "我們正準備撰寫與該主題相關的 survey/systematic review，需產出可直接用於收錄/排除的篩選 paper 規則。\n"
        "請使用內建 web search，且至少引用 3 個 https 來源。\n"
        "輸出語言：全部以中文撰寫。\n"
        "僅輸出單一 JSON 物件，鍵為：topic_definition、summary、summary_topics、inclusion_criteria、exclusion_criteria；JSON 外勿輸出其他文字。\n"
        "topic_definition：以中文撰寫，1–2 句清楚定義主題。\n"
        "summary：中文、簡潔扼要。\n"
        "summary_topics：列出 3–4 項主題，每項含 id（如 S1、S2）與 description；用詞與 summary 一致。\n"
        "inclusion_criteria：每條含 criterion、source（https）、topic_ids（至少 1 個）；僅能使用正向條件（不得寫否定句）。\n"
        "inclusion_criteria 的第一條必須以『主題定義：』+ topic_definition 原文開頭，之後接上『—』或『:』與具體條件（需逐字包含 topic_definition）。\n"
        "inclusion_criteria 中至少一條需明確要求英文（例如提供英文全文或英文評估語料）。\n"
        "入選的 paper 需要達成 inclusion_criteria 中的所有條件，因此如果某些條件之間的關係是或，則需要講他們都整合在同一條 inclusion_criterion中。\n"
        "inclusion_criteria 的範圍僅量廣泛，不可限縮在特定的小範圍內。\n"
        "exclusion_criteria：列『具體剔除情境』，不可是 inclusion 的鏡像否定（例如僅單一語言或單一應用、與主題無關、超出時間範圍等）；每條同樣含 source、topic_ids。\n"
        "一致性：每條 criterion 必須對應至少一個 summary topic（以 topic_ids 連結）；source 一律使用 https。"
    )



def test_openai_web_search_structured_criteria() -> None:
    """以與基準檔相同的設定呼叫 web search，但要求結構化輸出。"""

    _require_api_key()

    prompt = _build_prompt(SURVEY_TOPIC, RECENCY_HINT)
    options = WebSearchOptions()

    result = ask_with_web_search(
        prompt,
        model=MODEL,
        options=options,
        temperature=0.7,
        max_output_tokens=1_200
    )

    print("\n=== Raw Structured Content ===\n")
    print(result.content)
    print("\n=== Usage Metadata ===\n")
    print(result.usage)

    try:
        data = _extract_json_payload(result.content)
    except AssertionError as err:
        print("\n=== JSON Parse Warning ===")
        print(err)
        return

    print("\n=== Parsed JSON ===")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # 非強制檢查（僅列印警告，不中斷測試）：
    topic_definition = str(data.get("topic_definition", "")).strip()
    if not topic_definition:
        print("\n[WARN] 缺少 topic_definition，無法檢查 inclusion 第一條是否逐字引用主題定義。")

    summary_topics = {topic.get("id"): topic.get("description", "") for topic in data.get("summary_topics", [])}
    inclusion = data.get("inclusion_criteria", []) or []
    exclusion = data.get("exclusion_criteria", []) or []

    def _print_criteria(label: str, items: List[Dict[str, Any]]) -> None:
        if not items:
            print(f"\n[WARN] {label} 無任何條目")
            return
        print(f"\n--- {label} ---")
        for idx, item in enumerate(items, start=1):
            criterion = item.get("criterion", "").strip()
            topic_ids = item.get("topic_ids", []) or []
            source = item.get("source", "")
            print(f"[{idx}] {criterion}")
            print(f"     topic_ids={topic_ids} | source={source}")

    _print_criteria("Inclusion Criteria", inclusion)
    _print_criteria("Exclusion Criteria", exclusion)

    if topic_definition and inclusion:
        first = inclusion[0] or {}
        first_text = str(first.get("criterion", "")).strip()
        expected_prefix = f"主題定義：{topic_definition}"
        if not first_text.startswith(expected_prefix):
            print(
                "\n[WARN] inclusion 第一條未以 topic_definition 原文開頭："
                f"應為 '{expected_prefix}…'"
            )

    if summary_topics:
        covered: Set[str] = set()
        for item in inclusion + exclusion:
            for topic_id in item.get("topic_ids", []) or []:
                covered.add(str(topic_id))
        missing = [tid for tid in summary_topics.keys() if tid not in covered]
        if missing:
            print(f"\n[WARN] 尚有未被引用的 summary topic: {missing}")
        else:
            print("\n[INFO] 所有 summary topics 皆已被 criteria 引用。")
    else:
        print("\n[WARN] 未提供 summary_topics，無法檢查覆蓋情況。")

    # 將 criteria 解析結果輸出至 test_artifacts，僅保留文本以供後續流程使用。
    def _slugify(text: str) -> str:
        base = re.sub(r"[^A-Za-z0-9一-龥]+", "_", text.strip())
        base = re.sub(r"_+", "_", base).strip("_")
        return base.lower() or "topic"

    topic_slug = _slugify(SURVEY_TOPIC)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")

    # 依專案規範先建立 artifacts 目錄
    Path("test_artifacts").mkdir(parents=True, exist_ok=True)
    Path("test/.tmp").mkdir(parents=True, exist_ok=True)

    artifact_dir = Path("test_artifacts/openai_web_search_structured") / topic_slug
    artifact_dir.mkdir(parents=True, exist_ok=True)

    criteria_only = {
        "topic": SURVEY_TOPIC,
        "recency_hint": RECENCY_HINT,
        "inclusion": [str(it.get("criterion", "")).strip() for it in inclusion],
        "exclusion": [str(it.get("criterion", "")).strip() for it in exclusion],
    }

    out_path = artifact_dir / f"criteria_{timestamp}.json"
    out_path.write_text(json.dumps(criteria_only, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[INFO] 已輸出 criteria 至 {out_path}")
