"""Live test covering the basic OpenAI web search flow for the speech-language topic."""
from __future__ import annotations

import os

from src.utils.env import load_env_file
from src.utils.openai_web_search import WebSearchOptions, ask_with_web_search


def _require_api_key() -> str:
    """Load `.env` and ensure an API key is available before hitting OpenAI."""

    load_env_file()
    key = os.environ.get("OPENAI_API_KEY")
    assert key, "OPENAI_API_KEY is required for live OpenAI web search tests."
    return key


SURVEY_TOPIC = os.environ.get(
    "WEB_SEARCH_SURVEY_TOPIC",
    "我要寫一篇關於 speech language model 的 survey。請在查詢完相關資料後。給出主題的定義，並且列出論文錄入inclusion/exclusion criteria。 inclusion criteria中需要說明主題的定義。",
)
RECENCY_HINT = os.environ.get("WEB_SEARCH_RECENCY_HINT", "過去7年")
MODEL = os.environ.get("WEB_SEARCH_TEST_MODEL", "gpt-4o")


def _build_prompt(topic: str, recency: str) -> str:
    return (
        "請協助我們執行系統性文獻搜尋。\n"
        f"主題：{topic}。\n"
        f"優先關注 {recency} 內的研究。\n"
        "步驟：使用 OpenAI Responses API 提供的 web search 工具，整合可信來源，"
        "並給出摘要與主要論點，最後列出至少三個來源網址。\n"
        "輸出格式：自由文字即可，重點是標明引用來源。"
    )


def test_openai_web_search_live() -> None:
    """Smoke test: ensure web search returns non-empty content with citations."""

    _require_api_key()

    prompt = _build_prompt(SURVEY_TOPIC, RECENCY_HINT)
    options = WebSearchOptions()

    result = ask_with_web_search(
        prompt,
        model=MODEL,
        options=options,
        temperature=0.7,
        max_output_tokens=1_200,
    )

    print("\n=== Web Search Output ===\n")
    print(result.content)
    print("\n=== Usage Metadata ===\n")
    print(result.usage)

    content = result.content.strip()
    assert content, "OpenAI web search 應回傳內容"
    assert "http" in content.lower(), "結果應包含至少一個來源網址"
