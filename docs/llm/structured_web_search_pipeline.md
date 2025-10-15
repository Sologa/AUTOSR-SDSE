# Web Search Structured Criteria Pipeline

## 目的
- 以兩階段流程（`gpt-4o` + web search、`gpt-5` 整理）產出支援 AND / OR 分組的收錄與排除條件。
- 與現有 `test_openai_web_search_structured.py` 共用主題設定，但輸出改為明確標示 `required` 與 `any_of` 群組，方便後續與 LatteReview reviewer 整合。

## 介面 / 參數
- 模組：`src/utils/structured_web_search_pipeline.py`
- `CriteriaPipelineConfig`
  - `search_model`：預設 `gpt-4o`，負責 web search。
  - `formatter_model`：預設 `gpt-5`，負責將筆記轉成 JSON。
  - `recency_hint`、`search_temperature`、`formatter_temperature`、`search_max_output_tokens`、`formatter_max_output_tokens`：控制兩階段的生成行為。
  - `web_search_options`：傳入 `WebSearchOptions`，可指定 `tool_type`、允許網域、搜尋上下文等。
- `run_structured_criteria_pipeline(topic, *, config, recency_hint, ...)`：回傳 `CriteriaPipelineResult`，含 raw notes、formatter 輸出與解析後的 `structured_payload`。

## 使用範例
```python
from src.utils.structured_web_search_pipeline import (
    CriteriaPipelineConfig,
    run_structured_criteria_pipeline,
)

config = CriteriaPipelineConfig(recency_hint="過去3年")
result = run_structured_criteria_pipeline(
    "speech language model",
    config=config,
)
print(result.structured_payload["inclusion_criteria"]["required"])
```

## 測試要點
- `test/integration_live/test_openai_web_search_structured_pipeline.py` 直接呼叫 pipeline：
  - 驗證 formatter JSON 可解析、`required` 第一條包含主題定義。
  - 列印/記錄 `any_of` 群組並檢查 summary topic 覆蓋率。
  - 匯出 raw notes 與 JSON 至 `test_artifacts/openai_web_search_structured_pipeline/`。

## 已知限制
- 仍仰賴 `gpt-4o` / `gpt-5` 的穩定輸出；若 formatter 回傳非 JSON，流程會丟出 `ValueError`。
- `any_of` 目前以群組方式呈現，後續若需要進一步拆解為 reviewer 可直接使用的文字，需額外處理。
- 測試屬於 live integration，執行時會呼叫真實 OpenAI API 並產生費用，CI 須小心控管。 
