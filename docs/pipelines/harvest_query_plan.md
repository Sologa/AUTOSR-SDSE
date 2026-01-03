# Harvest Query Plan

## 目的
- 落盤 harvest 的實際查詢組合，方便檢視 anchor coverage 與 query 使用情況。

## 介面 / 參數
- 入口：`python scripts/topic_pipeline.py harvest --topic "<topic>"`
- 產出位置：`workspaces/<topic>/harvest/query_plan.json`

## 內容概要
- `anchors` / `search_terms` / `scope` / `boolean_operator`
- `start_date` / `end_date` / `cutoff_date`
- `queries_run`
- `queries[]`：每個 anchor × term 的查詢細節
  - `search_query`、`records_returned`、`records_added`、`error`

## 測試要點
- 確認 `queries_run == len(queries)`。
- `records_returned` 與 `records_added` 有數值變化。

## 已知限制
- `records_added` 代表「唯一新增的 arXiv id」數量，非總保留數。
- 若 API 請求失敗，該 query 會標記 `error`。
