# Seed Stage 規格（spec）

本文件定義「Seed」階段的行為與介面：以單一 `topic` 驅動 arXiv 查詢，收集 **survey/review/overview** 類型的 seed papers，並下載 PDF 供後續 keyword extraction 使用。

---

## 1) 目的

- 從 arXiv 找到與 `topic` 相關的 survey/review/overview 論文
- 下載 PDF 作為 keyword extraction 的輸入
- 產出可追溯的查詢記錄與篩選報告

---

## 2) 介面 / 參數

### CLI
```
python scripts/topic_pipeline.py seed --topic "<topic>"
```

### 主要參數
- `--topic`：主題字串（用於 workspace 與查詢）
- `--max-results`：arXiv API 回傳上限（預設 25）
- `--download-top-k`：下載前 k 筆（預設 5）
- `--scope`：查詢範圍 `all|ti|abs`（預設 all）
- `--boolean-operator`：anchor 與 survey 條件的布林運算 `AND|OR`（預設 AND）
- `--anchor`：可重複指定 anchor（不給則使用內建 topic variants）
- `--survey-term`：可重複指定 survey 修飾詞（不給則用預設清單）
- `--no-cache`：忽略 `seed/queries/arxiv.json`，強制重新查詢
- `--anchor-mode`：anchor 組合方式 `phrase|token_and`
- `--arxiv-raw-query`：直接提供 arXiv `search_query`（會忽略 anchors/survey_terms/scope/boolean_operator）

### 相似標題 cutoff
避免把「與 topic 高度相似」的最新 survey 當成 seed：
- `--cutoff-by-similar-title/--no-cutoff-by-similar-title`（預設啟用）
- `--similarity-threshold`：相似度門檻（預設 0.8）

---

## 3) 查詢行為（摘要）

### 一般模式
組合規則如下（示意）：
```
(<anchor_clause>) <boolean_operator> (<survey_clause>)
```

- `anchor_clause`：
  - `phrase`：`ti:"discrete audio tokens"`（完整片語）
  - `token_and`：`ti:("discrete" AND "audio" AND "tokens")`
- `survey_clause`：`ti:"survey" OR ti:"review" OR ti:"overview" ...`
- 多個 anchor 之間為 **OR**

### Raw query 模式
若 `--arxiv-raw-query` 有值，直接送出該查詢字串，忽略其餘查詢參數。

---

## 4) 輸出

### 主要產物
```
workspaces/<topic_slug>/seed/queries/arxiv.json
workspaces/<topic_slug>/seed/queries/seed_selection.json
workspaces/<topic_slug>/seed/downloads/download_results.json
workspaces/<topic_slug>/seed/downloads/arxiv/*.pdf
```

### seed_selection.json
記錄：
- cutoff candidate / cutoff reason / cutoff date
- 實際保留並下載的清單
- 最終使用的查詢設定

---

## 5) 使用範例

### 基本用法
```
python scripts/topic_pipeline.py seed --topic "speech language model"
```

### title token AND（對齊 UI 的 token 搜尋）
```
python scripts/topic_pipeline.py seed \
  --topic "..." \
  --scope ti \
  --anchor-mode token_and \
  --no-cache
```

### raw query（完全自訂）
```
python scripts/topic_pipeline.py seed \
  --topic "..." \
  --arxiv-raw-query 'ti:("discrete" AND "audio" AND "token") AND (survey OR review)' \
  --no-cache
```

---

## 6) 測試要點

- `seed/queries/arxiv.json` 是否更新（使用 `--no-cache` 可強制更新）
- `seed/queries/seed_selection.json` 是否記錄 cutoff 與候選清單
- `seed/downloads/download_results.json` 是否有下載結果與錯誤原因
- `seed/downloads/arxiv/*.pdf` 是否落盤（若無，可能是 pdf 被 block）

---

## 7) 已知限制

- arXiv API 回傳結果受限於查詢字串與 `max_results`
- survey 條件可能過嚴，導致沒有 seed
- cutoff 相似標題規則可能排除唯一相關 survey
- PDF 可能因權限或 404 下載失敗（會記錄在 download_results.json）
- 本階段只查 arXiv，不涵蓋 Semantic Scholar 或 DBLP

