"""Live pipeline test combining OpenAI web search with survey PDF background."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from src.utils.env import load_env_file
from src.utils.llm import LLMResult, LLMService
from src.utils.structured_web_search_pipeline import (
    CriteriaPipelineConfig,
    FormatterStageConfig,
    SearchStageConfig,
    run_structured_criteria_pipeline,
)

SURVEY_TOPIC = os.environ.get("WEB_SEARCH_SURVEY_TOPIC", "speech language model")
RECENCY_HINT = os.environ.get("WEB_SEARCH_RECENCY_HINT", "過去3年")
SEARCH_MODEL = os.environ.get("WEB_SEARCH_STAGE1_MODEL", "gpt-4.1")
FORMATTER_MODEL = os.environ.get("WEB_SEARCH_STAGE2_MODEL", "gpt-5")
SEARCH_TEMPERATURE = float(os.environ.get("WEB_SEARCH_STAGE1_TEMPERATURE", "0.7"))
FORMATTER_TEMPERATURE = float(os.environ.get("WEB_SEARCH_STAGE2_TEMPERATURE", "0.2"))
SEARCH_MAX_OUTPUT_TOKENS = int(os.environ.get("WEB_SEARCH_STAGE1_MAX_TOKENS", "1200"))
FORMATTER_MAX_OUTPUT_TOKENS = int(os.environ.get("WEB_SEARCH_STAGE2_MAX_TOKENS", "1200"))
PDF_MODEL = os.environ.get("WEB_SEARCH_PDF_MODEL", "gpt-4.1")
PDF_TEMPERATURE = float(os.environ.get("WEB_SEARCH_PDF_TEMPERATURE", "0.4"))
PDF_MAX_OUTPUT_TOKENS = int(os.environ.get("WEB_SEARCH_PDF_MAX_TOKENS", "1800"))
PDF_DIRECTORY = Path(
    os.environ.get(
        "WEB_SEARCH_PDF_DIRECTORY",
        "test_artifacts/live_downloads/spoken_language_model_assets/arxiv",
    )
)

PDF_INSTRUCTIONS_TEMPLATE = (
    "你是系統性回顧助理。這些附加的 PDF 是與主題 '{topic}' 相關的 survey 或綜述文章。\n"
    "請閱讀所有檔案，凝練出能協助後續篩選流程的背景摘要。\n"
    "輸出語言為中文，並依照以下段落結構整理：\n"
    "### PDF Topic Definition\n"
    "- 1-2 段文字描述主題的範圍、核心概念與評估面向。\n"
    "### PDF Key Trends\n"
    "- 以條列說明近年趨勢、資料來源與常見研究角度。\n"
    "### PDF Capability Highlights\n"
    "- 條列最關鍵的技術/能力要求，每條 1 句。\n"
    "### PDF Inclusion Signals\n"
    "- 列出 3-5 項建議納入條件的關鍵字或描述，可引用 PDF 章節。\n"
    "### PDF Exclusion Signals\n"
    "- 列出 3-5 項建議排除的情境或與主題無關的研究方向。\n"
    "### PDF Notes\n"
    "- 列舉每個 PDF 的重點或特色，格式為 `- <檔名>: <重點>`。\n"
    "請勿輸出 JSON，僅以純文字完成。"
)


def _require_api_key() -> str:
    """載入 `.env` 並確認 `OPENAI_API_KEY` 存在。"""

    load_env_file()
    key = os.environ.get("OPENAI_API_KEY")
    assert key, "OPENAI_API_KEY is required for live OpenAI tests."
    return key


def _slugify(text: str) -> str:
    base = "".join("_" if not (ch.isalnum() or "\u4e00" <= ch <= "\u9fff") else ch for ch in text.strip())
    base = "_".join(filter(None, base.split("_")))
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
        print("\n[INFO] Inclusion Any-of Groups 目前為空陣列。")
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


def _collect_pdf_paths(root: Path) -> List[Path]:
    if not root.exists():
        print(f"[WARN] PDF 路徑不存在：{root}")
        return []
    pdfs = sorted(path for path in root.glob("*.pdf") if path.is_file())
    print(f"[INFO] 偵測到 {len(pdfs)} 份 PDF：{[p.name for p in pdfs]}")
    return pdfs


def _read_pdf_background(topic: str, pdf_paths: Sequence[Path]) -> LLMResult | None:
    if not pdf_paths:
        print("[WARN] 找不到可供分析的 PDF，將以 web search 筆記為主。")
        return None
    instructions = PDF_INSTRUCTIONS_TEMPLATE.format(topic=topic)
    service = LLMService()
    print("[INFO] 讀取 PDF 並整理背景摘要...")
    return service.read_pdfs(
        "openai",
        PDF_MODEL,
        pdf_paths,
        instructions=instructions,
        temperature=PDF_TEMPERATURE,
        max_output_tokens=PDF_MAX_OUTPUT_TOKENS,
        metadata={"stage": "pdf_background", "topic": topic},
    )


def _build_structured_json_prompt(topic: str, recency: str) -> str:
    return (
        "你是系統性回顧助理。\n"
        f"主題：{topic}；時間範圍：{recency}。\n"
        "我們正準備撰寫與該主題相關的 survey/systematic review，需產出可直接用於收錄/排除的篩選 paper 規則。\n"
        "請使用內建 web search，且至少引用 3 個 https 來源。\n"
        "輸出語言：全部以中文撰寫。\n"
        "僅輸出單一 JSON 物件，鍵為：topic_definition、summary、summary_topics、inclusion_criteria、exclusion_criteria；JSON 外勿輸出其他文字。\n"
        "topic_definition：以中文撰寫，1–2 段清楚定義主題，可補充背景脈絡與核心能力描述。\n"
        "summary：中文、簡潔扼要。\n"
        "summary_topics：列出 3–4 項主題，每項含 id（如 S1、S2）與 description；用詞與 summary 一致。\n"
        "inclusion_criteria：每條含 criterion、source（https）、topic_ids（至少 1 個）；僅能使用正向條件（不得寫否定句）。\n"
        "inclusion_criteria 的第一條必須以『主題定義：』+ topic_definition 原文開頭，之後接上『—』或『:』與具體條件（需逐字包含 topic_definition）。\n"
        "inclusion_criteria 中至少一條需明確要求英文（例如提供英文全文或英文評估語料）。\n"
        "入選的 paper 需要達成 inclusion_criteria 中的所有條件，因此如果某些條件之間的關係是或，則需要講他們都整合在同一條 inclusion_criterion 中。\n"
        "inclusion_criteria 的範圍僅量廣泛，不可限縮在特定的小範圍內。\n"
        "exclusion_criteria：列『具體剔除情境』，不可是 inclusion 的鏡像否定（例如僅單一語言或單一應用、與主題無關、超出時間範圍等）；每條同樣含 source、topic_ids。\n"
        "一致性：每條 criterion 必須對應至少一個 summary topic（以 topic_ids 連結）；source 一律使用 https。"
    )


def _build_augmented_formatter_messages(
    topic: str,
    recency_hint: str,
    combined_notes: str,
) -> Sequence[Dict[str, str]]:
    system_prompt = (
        "你是系統性回顧的資料整理助理，需將研究助理的筆記轉為結構化 JSON。\n"
        "僅能輸出單一 JSON 物件，勿加入額外敘述或 Markdown。"
    )
    structured_prompt = _build_structured_json_prompt(topic, recency_hint)
    user_prompt = (
        "以下內容結合了兩種來源：\n"
        "1) PDF Background (Survey Summaries)：模型閱讀本地 PDF 後的背景整理，僅供提供更準確的主題定義與條件靈感，來源欄請勿引用非 https 連結。\n"
        "2) Web Search Notes：OpenAI Web Search 所產出的即時筆記與來源。\n"
        "請依照 structured 提示輸出最終 JSON，並確保所有 source 欄位皆為 https URL。\n"
        f"{structured_prompt}\n"
        "請在撰寫 topic_definition 時優先吸收 PDF Background 段落的知識，並用 web search 的來源驗證關鍵描述。\n"
        "inclusion_criteria.required 段落僅能包含主題定義逐字條款、recency 對齊條款，以及英文可評估性條款；其餘條件請歸入 any_of 群組。\n"
        "將以下筆記整合後再輸出：\n"
        "---\n"
        f"{combined_notes.strip()}\n"
        "---"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("formatter response does not contain a JSON object")
    payload = raw_text[start : end + 1]
    return json.loads(payload)


def _write_artifacts(
    topic: str,
    pdf_background: str,
    combined_notes: str,
    augmented_result: LLMResult,
    structured_payload: Dict[str, Any],
    formatter_messages: Sequence[Dict[str, str]],
) -> Path:
    topic_slug = _slugify(topic)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")

    Path("test_artifacts").mkdir(parents=True, exist_ok=True)
    Path("test/.tmp").mkdir(parents=True, exist_ok=True)

    base_dir = (
        Path("test_artifacts/openai_pdf_augmented_structured_pipeline") / topic_slug
    )
    base_dir.mkdir(parents=True, exist_ok=True)

    background_path = base_dir / f"pdf_background_{timestamp}.txt"
    if pdf_background.strip():
        background_path.write_text(pdf_background, encoding="utf-8")

    combined_path = base_dir / f"combined_notes_{timestamp}.txt"
    combined_path.write_text(combined_notes, encoding="utf-8")

    structured_path = base_dir / f"criteria_{timestamp}.json"
    structured_path.write_text(
        json.dumps(structured_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    prompt_path = base_dir / f"formatter_prompt_{timestamp}.json"
    prompt_path.write_text(
        json.dumps(formatter_messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    augmented_raw_path = base_dir / f"formatter_raw_{timestamp}.txt"
    augmented_raw_path.write_text(augmented_result.content, encoding="utf-8")

    return structured_path


def _build_combined_notes(pdf_background: str | None, web_search_notes: str) -> str:
    segments: List[str] = []
    if pdf_background and pdf_background.strip():
        segments.append("### PDF Background (Survey Summaries)")
        segments.append(pdf_background.strip())
    segments.append("### Web Search Notes")
    segments.append(web_search_notes.strip())
    return "\n".join(segment for segment in segments if segment)


def test_openai_pdf_augmented_structured_pipeline() -> None:
    """兩階段 web search 筆記 + PDF 背景融合後，再次整理成結構化 JSON。"""

    _require_api_key()

    pdf_paths = _collect_pdf_paths(PDF_DIRECTORY)
    pdf_background_result = _read_pdf_background(SURVEY_TOPIC, pdf_paths)
    pdf_background_text = pdf_background_result.content if pdf_background_result else ""

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

    print("[INFO] 執行原始 web search 結構化流程...")
    base_result = run_structured_criteria_pipeline(
        SURVEY_TOPIC,
        config=config,
    )

    combined_notes = _build_combined_notes(pdf_background_text, base_result.raw_notes)

    print("\n=== PDF Background Summary ===\n")
    print(pdf_background_text or "(無)")

    print("\n=== Web Search Raw Notes ===\n")
    print(base_result.raw_notes)

    print("\n=== Combined Notes (PDF + Web Search) ===\n")
    print(combined_notes)

    formatter_messages = _build_augmented_formatter_messages(
        SURVEY_TOPIC,
        base_result.recency_hint,
        combined_notes,
    )

    formatter_service = LLMService()
    augmented_formatter = formatter_service.chat(
        "openai",
        FORMATTER_MODEL,
        formatter_messages,
        temperature=FORMATTER_TEMPERATURE,
        max_output_tokens=FORMATTER_MAX_OUTPUT_TOKENS,
        metadata={"stage": "formatter_augmented", "topic": SURVEY_TOPIC},
    )

    print("\n=== Augmented Formatter Raw Output ===\n")
    print(augmented_formatter.content)

    structured = _extract_json_payload(augmented_formatter.content)
    print("\n=== Augmented Parsed JSON ===")
    print(json.dumps(structured, ensure_ascii=False, indent=2))

    inclusion_block = structured.get("inclusion_criteria")
    if isinstance(inclusion_block, dict):
        required_items = inclusion_block.get("required", []) or []
        any_of_groups = inclusion_block.get("any_of", []) or []
    else:
        required_items = []
        any_of_groups = []
    exclusion_items = structured.get("exclusion_criteria", []) or []

    _print_required("Inclusion Criteria (Required)", required_items)
    _print_any_of(any_of_groups)
    _print_required("Exclusion Criteria", exclusion_items)

    structured_path = _write_artifacts(
        SURVEY_TOPIC,
        pdf_background_text,
        combined_notes,
        augmented_formatter,
        structured,
        formatter_messages,
    )

    print(f"\n[INFO] 已寫出增強版結果：{structured_path}")
