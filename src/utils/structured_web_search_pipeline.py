"""Two-stage pipeline that mirrors the original structured web search test flow."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence

from .env import load_env_file
from .llm import LLMResult, LLMService
from .openai_web_search import WebSearchOptions, ask_with_web_search, create_web_search_service

DEFAULT_SEARCH_MODEL = "gpt-5.2-chat-latest"
DEFAULT_FORMATTER_MODEL = "gpt-5.2"
DEFAULT_RECENCY_HINT = "過去3年"
DEFAULT_SEARCH_TEMPERATURE = 0.7
DEFAULT_FORMATTER_TEMPERATURE = 0.2
DEFAULT_SEARCH_MAX_OUTPUT_TOKENS = 1_200
DEFAULT_FORMATTER_MAX_OUTPUT_TOKENS = 1_200


@dataclass
class SearchStageConfig:
    """OpenAI web search stage configuration (stage 1)."""

    model: str = DEFAULT_SEARCH_MODEL
    temperature: float = DEFAULT_SEARCH_TEMPERATURE
    max_output_tokens: int = DEFAULT_SEARCH_MAX_OUTPUT_TOKENS
    enforce_tool_choice: bool = True
    options: WebSearchOptions = field(default_factory=WebSearchOptions)


@dataclass
class FormatterStageConfig:
    """Formatter stage configuration (stage 2)."""

    model: str = DEFAULT_FORMATTER_MODEL
    temperature: float = DEFAULT_FORMATTER_TEMPERATURE
    max_output_tokens: int = DEFAULT_FORMATTER_MAX_OUTPUT_TOKENS


@dataclass
class CriteriaPipelineConfig:
    """Aggregate config container for the structured criteria pipeline."""

    recency_hint: str = DEFAULT_RECENCY_HINT
    search: SearchStageConfig = field(default_factory=SearchStageConfig)
    formatter: FormatterStageConfig = field(default_factory=FormatterStageConfig)


@dataclass
class CriteriaPipelineResult:
    """Result bundle returned by ``run_structured_criteria_pipeline``."""

    topic: str
    recency_hint: str
    search_prompt: str
    formatter_messages: Sequence[Dict[str, str]]
    structured_prompt_template: str
    search_result: LLMResult
    formatter_result: LLMResult
    structured_payload: Dict[str, Any]

    @property
    def raw_notes(self) -> str:
        """Return the raw note text from the search stage."""
        return self.search_result.content

    @property
    def structured_text(self) -> str:
        """Return the formatter stage response text."""
        return self.formatter_result.content


PROMPT_HEADER = (
    "你是系統性回顧助理。\n"
    "我們正準備撰寫與該主題相關的 survey/systematic review，需產出可直接用於收錄/排除的篩選 paper 規則。\n"
    "請使用內建 web search，且至少引用 3 個 https 來源。\n"
    "輸出語言：全部以中文撰寫。\n"
)

def _build_structured_json_prompt(
    topic: str,
    recency: str,
    *,
    exclude_title: Optional[str] = None,
    cutoff_before_date: Optional[str] = None,
) -> str:
    """Exact copy of the original structured web search prompt."""

    prompt = (
        "你是系統性回顧助理。\n"
        f"主題：{topic}。\n"
        "我們正準備撰寫與該主題相關的 survey/systematic review，需產出可直接用於收錄/排除的篩選 paper 規則。\n"
        "請使用內建 web search，且至少引用 3 個 https 來源。\n"
        "輸出語言：全部以中文撰寫。\n"
    )
    if cutoff_before_date:
        prompt += f"補充限制：來源或論文的發表日期需早於 {cutoff_before_date}（僅作為來源選擇，不得寫入納入/排除條款）。\n"
    prompt += "來源頁面需提供明確年月日（YYYY-MM-DD）；僅有年份或年月者視為不合格來源。\n"
    if exclude_title:
        prompt += f"補充限制：排除標題完全等於「{exclude_title}」的論文與來源。\n"
    prompt += (
        "僅輸出單一 JSON 物件，鍵為：topic_definition、summary、summary_topics、inclusion_criteria、exclusion_criteria；JSON 外勿輸出其他文字。\n"
        "topic_definition：以中文撰寫，1–2 段清楚定義主題，可補充背景脈絡與核心能力描述。\n"
        "topic_definition 的來源應優先引用一手論文頁（如 arXiv/期刊/會議頁），避免彙整站、排行榜或動態搜尋結果頁。\n"
        "summary：中文、簡潔扼要。\n"
        "summary_topics：列出 3–4 項主題，每項含 id（如 S1、S2）與 description；用詞與 summary 一致。\n"
        "inclusion_criteria：每條含 criterion、source、topic_ids（至少 1 個）；僅能使用正向條件（不得寫否定句）。\n"
        "inclusion_criteria 的第一條必須以『主題定義：』+ topic_definition 原文開頭，之後接上『—』或『:』與具體條件（需逐字包含 topic_definition）。\n"
        "inclusion_criteria 中至少一條需明確要求英文（例如提供英文全文或英文評估語料）。\n"
        "若條件之間為 OR 關係，請放入 inclusion_criteria.any_of 的 options。\n"
        "any_of 群組語意：只需滿足「任一群組中的任一 option」即可；群組彼此為 OR，而非全部都必須滿足。\n"
        "inclusion_criteria 的範圍僅量廣泛，不可限縮在特定的小範圍內。\n"
        "exclusion_criteria：列『具體剔除情境』，不可是 inclusion 的鏡像否定（例如僅單一語言或單一應用、與主題無關）；每條同樣含 source、topic_ids。\n"
        "source 規則：一般條件必須是 https；若條件屬於系統設定（例如 exclude_title），可用 source=internal 或留空，且這類來源不要放入 sources 清單。\n"
        "來源一致性：source 必須能直接支持該條件，不可使用會與條件相矛盾的來源；若找不到合適來源，請用 source=internal。\n"
        "來源選擇：避免動態排行榜、搜尋結果頁或彙整站，優先使用一手論文頁或正式出版頁。\n"
    )
    if exclude_title:
        prompt += "exclusion_criteria 必須包含排除：標題完全等於上述指定標題的論文。\n"
    prompt += "一致性：每條 criterion 必須對應至少一個 summary topic（以 topic_ids 連結）。"
    return prompt


def _build_web_search_prompt(
    topic: str,
    recency_hint: str,
    *,
    exclude_title: Optional[str] = None,
    cutoff_before_date: Optional[str] = None,
) -> str:
    """Stage 1 prompt that keeps the same semantics as the historical test."""

    prompt = PROMPT_HEADER + f"主題：{topic}。\n"
    if cutoff_before_date:
        prompt += f"補充限制：來源或論文的發表日期需早於 {cutoff_before_date}（僅作為來源選擇，不得寫入納入/排除條款）。\n"
    prompt += "來源頁面需提供明確年月日（YYYY-MM-DD）；僅有年份或年月者視為不合格來源。\n"
    if exclude_title:
        prompt += f"補充限制：排除標題完全等於「{exclude_title}」的論文與來源。\n"
    prompt += (
        "請先以純文字整理資訊，不要輸出 JSON、Markdown 表格或程式碼區塊。\n"
        "依序撰寫下列段落：\n"
        "### Topic Definition\n"
        "- 以 1–2 段中文精準定義主題，可包含背景脈絡與核心能力描述。\n"
        "### Summary\n"
        "- 以 2–3 句中文概述趨勢與亮點。\n"
        "### Summary Topics\n"
        "- 列 3–4 個主題節點，格式為 `S1: 描述`。\n"
        "### Inclusion Criteria (Required)\n"
        "- 僅保留必須同時滿足的條件：① 主題定義條款（以『主題定義：』+定義原文開頭）、② 提供英文可評估性的條件。\n"
        "- 每條附上來源 (source) 與對應 topic id；一般條件需為 https。\n"
        "### Inclusion Criteria (Any-of Groups)\n"
        "- 針對技術覆蓋或差異化條件建立至少一個群組，格式為 `- Group 名稱` 搭配 `* Option:`，各自附上 source 與 topic ids。\n"
        "- 群組語意為 OR：只需滿足任一群組中的任一 option 即可。\n"
        "- 若筆記中原本在 Required 段落出現多個技術細節條件，請搬移到任選群組，不要重複留在 Required。\n"
        "- 若確實沒有任選條件，再寫 `(none)`。\n"
        "### Exclusion Criteria\n"
        "- 條列需要排除的情境，同樣附來源與 topic ids；若屬於系統設定（如 exclude_title），可標示 source: internal 或留空。\n"
        "- source 必須能直接支持該排除條件；若找不到合適來源，請用 internal。\n"
        "### Sources\n"
        "- 逐行呈現所有引用來源 (https)，不包含 internal/空白來源。\n"
        "- 優先引用一手論文頁（arXiv/期刊/會議/出版社），避免動態排行榜、搜尋結果頁或彙整站作為核心依據。"
    )
    return prompt


def _build_formatter_messages(
    raw_text: str,
    *,
    topic: str,
    recency_hint: str,
    exclude_title: Optional[str] = None,
    cutoff_before_date: Optional[str] = None,
) -> Sequence[Dict[str, str]]:
    """Stage 2 messages, requesting the same JSON schema as原測試."""

    system_prompt = (
        "你是系統性回顧的資料整理助理，需將研究助理的純文字筆記轉為結構化 JSON。\n"
        "僅能輸出單一 JSON 物件，勿加入額外敘述或 Markdown。"
    )

    structured_prompt = _build_structured_json_prompt(
        topic,
        recency_hint,
        exclude_title=exclude_title,
        cutoff_before_date=cutoff_before_date,
    )

    user_prompt = (
        "以下筆記需整理成 JSON。結構與欄位說明請依照原始 structured 提示：\n"
        f"{structured_prompt}\n"
        "上述 structured 提示僅用於說明輸出欄位與內容要求，無需再次執行 web search。\n"
        "請在實際輸出時依照下列結構：\n"
        "{\n"
        "  \"topic_definition\": str,\n"
        "  \"summary\": str,\n"
        "  \"summary_topics\": [ {\"id\": str, \"description\": str} ],\n"
        "  \"inclusion_criteria\": {\n"
        "    \"required\": [ {\"criterion\": str, \"topic_ids\": [str], \"source\": str} ],\n"
        "    \"any_of\": [ {\"label\": str, \"options\": [ {\"criterion\": str, \"topic_ids\": [str], \"source\": str} ]} ]\n"
        "  },\n"
        "  \"exclusion_criteria\": [ {\"criterion\": str, \"topic_ids\": [str], \"source\": str} ],\n"
        "  \"sources\": [str]\n"
        "}\n"
        "其中 inclusion_criteria.required 僅能包含：\n"
        "- 以『主題定義：』開頭且逐字引用 topic_definition 的條款。\n"
        "- 英文可評估性/英文資料要求條款。\n"
        "所有其他符合納入但屬於技術覆蓋或能力差異的條件，一律放入單一或多個 any_of 群組；每個群組需有說明性的 label（例如『技術覆蓋需求』），其 options 為各別條件。\n"
        "any_of 群組語意：只需滿足任一群組中的任一 option 即可。\n"
        "source 規則：一般條件的 source 必須是 https；若條件屬於系統設定（例如 exclude_title），可用 source='internal' 或留空。\n"
        "來源一致性：source 需能直接支持該條件；若找不到合適來源或來源會與條件相矛盾，請用 source='internal'。\n"
        "sources 需去重且只保留 https 連結；internal/空白來源不要放入 sources。\n"
        "請整合下列筆記：\n"
        "--- 原始筆記開始 ---\n"
        f"{raw_text.strip()}\n"
        "--- 原始筆記結束 ---"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _extract_json_payload(raw_text: str) -> Dict[str, Any]:
    """Replicate the JSON extraction helper used in the live test."""

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("formatter response does not contain a JSON object")
    payload = raw_text[start : end + 1]
    return json.loads(payload)


def run_structured_criteria_pipeline(
    topic: str,
    *,
    config: Optional[CriteriaPipelineConfig] = None,
    recency_hint: Optional[str] = None,
    exclude_title: Optional[str] = None,
    cutoff_before_date: Optional[str] = None,
    web_search_service: Optional[LLMService] = None,
    formatter_service: Optional[LLMService] = None,
) -> CriteriaPipelineResult:
    """Execute the staged pipeline; mirrors ``test_openai_web_search_structured.py`` semantics."""

    load_env_file()

    cfg = config or CriteriaPipelineConfig()
    search_cfg = cfg.search
    formatter_cfg = cfg.formatter
    hint = recency_hint or cfg.recency_hint

    search_prompt = _build_web_search_prompt(
        topic,
        hint,
        exclude_title=exclude_title,
        cutoff_before_date=cutoff_before_date,
    )
    search_service = web_search_service or create_web_search_service()
    search_result = ask_with_web_search(
        search_prompt,
        model=search_cfg.model,
        service=search_service,
        options=search_cfg.options,
        force_tool=search_cfg.enforce_tool_choice,
        temperature=search_cfg.temperature,
        max_output_tokens=search_cfg.max_output_tokens,
    )

    structured_prompt_template = _build_structured_json_prompt(
        topic,
        hint,
        exclude_title=exclude_title,
        cutoff_before_date=cutoff_before_date,
    )

    formatter_messages = _build_formatter_messages(
        search_result.content,
        topic=topic,
        recency_hint=hint,
        exclude_title=exclude_title,
        cutoff_before_date=cutoff_before_date,
    )
    formatter = formatter_service or LLMService()
    formatter_result = formatter.chat(
        "openai",
        formatter_cfg.model,
        formatter_messages,
        temperature=formatter_cfg.temperature,
        max_output_tokens=formatter_cfg.max_output_tokens,
    )

    structured_payload = _extract_json_payload(formatter_result.content)

    return CriteriaPipelineResult(
        topic=topic,
        recency_hint=hint,
        search_prompt=search_prompt,
        formatter_messages=formatter_messages,
        structured_prompt_template=structured_prompt_template,
        search_result=search_result,
        formatter_result=formatter_result,
        structured_payload=structured_payload,
    )


__all__ = [
    "CriteriaPipelineConfig",
    "CriteriaPipelineResult",
    "FormatterStageConfig",
    "SearchStageConfig",
    "run_structured_criteria_pipeline",
]
