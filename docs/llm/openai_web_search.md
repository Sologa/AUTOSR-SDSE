# OpenAI Web Search Provider 擴充

## 目的
提供基於 `OpenAIWebSearchProvider` 的封裝，讓系統能透過 OpenAI Responses API 的 `web_search` 工具自動檢索最新網頁或論文資訊，再回傳整合後的結果。

## 介面 / 參數
- `WebSearchOptions`
  - `allowed_domains`: 限制搜尋網域清單，會轉換成 `filters.allowed_domains` 傳給 OpenAI，從源頭約束 web search 只能引用指定網站。
  - `search_context_size`: 控制模型為搜尋結果保留的上下文長度，允許 `low|medium|high`。
  - `user_location`: 供 OpenAI 判斷本地化結果的近似使用者位置（city/country/region/timezone）。
  - `tool_type`: 預設 `web_search`，也可選 `web_search_2025_08_26` 以保留特定版本。
- `OpenAIWebSearchProvider.chat_with_web_search(model, messages, options=None, force_tool=True, **kwargs)`
  - `messages`: 單輪或多輪訊息 payload（字串或 chat message 陣列）。
  - `options`: 上述 `WebSearchOptions`；若未提供則使用預設設定。
  - `force_tool`: 預設 `True`，會將 `tool_choice='required'` 傳給 OpenAI，確保至少執行一次 web search。
  - `**kwargs`: 傳遞給底層 `responses.create` 的其他參數（例如 `temperature`、`max_output_tokens`）。
- `create_web_search_service(**provider_kwargs)`：產生只含 OpenAI web search provider 的 `LLMService`。
- `ask_with_web_search(prompt, model='gpt-4o', service=None, options=None, force_tool=True, **kwargs)`：單輪便捷函式，預設使用成本較佳的 `gpt-4o`。

## 使用範例
```python
from src.utils.openai_web_search import ask_with_web_search, WebSearchOptions

options = WebSearchOptions(
    allowed_domains=["pubmed.ncbi.nlm.nih.gov", "arxiv.org"],
    search_context_size="high",
)
result = ask_with_web_search(
    "近一年有什麼針對 speech-language model 的文獻回顧？",
    model="gpt-4o",
    options=options,
    temperature=0.1,
)
print(result.content)
```

若需要在既有流程中注入，可改用 `create_web_search_service()` 取得 `LLMService` 實例，並傳給接受 `service` 參數的函式，例如 `extract_search_terms_from_surveys(..., service=my_service)`。

> 需要追求更完整的多輪查證時，可改用 `model="o3-deep-research"` 搭配預設的 `force_tool=True`；該流程會強制執行 Deep Research，平均多出 20–30 秒延遲，重試最多再增加約 9 秒，但能帶來較詳盡的引用。後續因預算考量，預設模型改為 `gpt-4o`。

## 結構化輸出（Structured Outputs）
- `test/integration_live/test_openai_web_search_structured.py` 示範如何同時啟用 `tools=[{"type": "web_search"}]` 與 `response_format={"type": "json_schema", ...}`，要求模型依 `SURVEY_SCHEMA` 回傳。
- Schema 核心欄位：
  - `topic_definition`：主題定義，後續標準必須引用原文。
  - `inclusion_criteria` / `exclusion_criteria`：各 3–5 條，`text` 需以 `topic_definition` 完整字串開頭，並搭配 `rationale`、`source_urls`。
- 測試會解析 JSON 並驗證條目是否遵循主題定義，確保後續程式能直接解析與比對。

## 測試要點
1. 需在已載入 `.env` 且含合法 `OPENAI_API_KEY` 的環境下執行。
2. 建議對 `ask_with_web_search` 做人工 smoke test，確認回傳內容含自動引用的網頁摘要。
3. 若要整合現有管線，請同時執行 `pytest -q`、`ruff check .` 確認沒有新的靜態檢查問題。

## 已知限制
- OpenAI 可能針對 web search 回傳延伸工具呼叫結果，回覆延遲較長。必要時可調整 `max_output_tokens` 或 `search_context_size`。
- `tool_choice='required'` 會強制模型至少呼叫一次工具；若想讓模型自行判斷可將 `force_tool=False`。
- 目前僅建構 OpenAI provider，不包含對 Anthropic 或 Gemini 等其他供應商的同類功能。
- Deep Research 流程（`model="o3-deep-research"` 且 `tool_choice='required'`）延遲最明顯；若需要降低延遲，可改用預設的 `gpt-4o`、調整搜尋上下文或縮減輸出長度。

## 測試腳本
- `test/integration_live/test_openai_web_search_structured.py`：載入 `.env` 後執行 `pytest -q test/integration_live/test_openai_web_search_structured.py` 即可觸發 web search 與 JSON schema 檢驗。
  - 可透過環境變數 `WEB_SEARCH_SURVEY_TOPIC`、`WEB_SEARCH_RECENCY_HINT`、`WEB_SEARCH_TEST_MODEL`、`WEB_SEARCH_ALLOWED_DOMAINS` 調整題目、時間範圍、模型與網域限制。
  - 測試會將原始 JSON、解析結果與 token 使用量印出，請使用 `pytest -s` 以保留標準輸出。
