# Filter-Seed LLM 審核（spec）

本文件定義「Filter-Seed」功能規格：在 **Seed → Keywords** 之間新增一個 LLM 自動審核步驟，**只用 title + abstract** 判斷每篇 seed paper 是否應納入 keyword extraction。  
目標是**最小人類介入**，但仍保留可追溯的審核報告。

---

## 1) 背景與問題

現行 pipeline：
1. Seed surveys（arXiv）
2. Keyword extraction（讀 seed PDFs）

問題：  
Seed 的搜尋條件會帶入不相干 paper（即使 title 含 survey/review 字樣），而 keyword extraction 會**照單全收**這些 PDFs，導致關鍵字污染。

---

## 2) 目標 / 非目標

### 目標
- 以 **LLM yes/no** 方式自動判斷 seed paper 是否與主題高度相關。
- 僅依 **title + abstract**（不讀 PDF 內容）。
- 產出完整審核記錄（含 reason / confidence）。
- 成為 **可選、可重跑** 的獨立 stage。

### 非目標
- 不做人工標註或手動覆寫機制（後續可擴充）。
- 不引入 fallback 行為（當全為 NO 時，不自動替代或中止）。
- 不在此階段做摘要/關鍵字抽取。

---

## 3) 位置與流程

```
Seed → Filter-Seed (新增) → Keywords → Harvest → ...
```

### 建議整合方式
- **獨立 stage**（可單獨執行與重跑）
- 同時提供 **keywords 前置觸發**（避免使用者多一步）

範例（CLI）：
```
python scripts/topic_pipeline.py filter-seed --topic "<topic>"
```

---

## 4) CLI 參數（建議）

- `--provider`（預設 openai）
- `--model`（預設 gpt-5-mini）
- `--temperature`（預設 0.2）
- `--max-output-tokens`（預設 400）
- `--reasoning-effort`（預設 low）
- `--include-keyword`（可重複，提供判斷線索）
- `--force`（覆寫既有篩選輸出）

---

## 5) 輸入資料

### 必要輸入
- `topic`（使用者指定的主題字串）
- seed metadata（title/abstract）
  - 優先來源：`seed/queries/arxiv.json`
  - 候選清單：`seed/queries/seed_selection.json`（優先採 `download_selected`，若空則用 `candidates`）
  - 補充來源：若缺 abstract，使用 `fetch_arxiv_metadata` 補齊
  - 若 `seed_selection.json` 有 `cutoff_candidate`，Filter-Seed 會排除該篇（避免回流）

### 可選輸入
- `include_keywords`（幫助 LLM 判斷的輔助詞）
- `model / temperature / max_output_tokens`

---

## 6) LLM 判斷規格

### 輸出格式（每篇）
必須是 JSON，且僅以下欄位：
```json
{
  "arxiv_id": "2502.06490",
  "title": "...",
  "decision": "yes",
  "reason": "一句話理由（中文）",
  "confidence": 0.0
}
```

### 決策規則
LLM 必須做 **二分決策**：
- `yes`：主題高度相關，適合做 keyword extraction
- `no`：主題不相關 / 過度發散 / 僅泛泛提及

### 判斷依據
- **只用** title + abstract
- topic 作為「關聯度基準」
- **必須**明確屬於 survey/review/overview 範疇（需在 title 或 abstract 中明確表述）
- 若僅為側邊提及或與 topic 關聯不明確，必須判定為 `no`

---

## 7) Prompt 規格（摘要）

Prompt 要求：
- 固定輸出 JSON（含 `decision`, `reason`, `confidence`）
- 嚴禁回答模糊語句（只允許 yes/no）
- 指示模型「不確定時選 no」

建議輸入結構（示意）：
```
Topic: <topic>
Paper:
title: ...
abstract: ...

請輸出 JSON：
{ "decision": "...", "reason": "...", "confidence": ... }
```

---

## 8) 輸出與落盤

### 主要輸出
```
workspaces/<topic_slug>/seed/filters/llm_screening.json
workspaces/<topic_slug>/seed/filters/selected_ids.json
```

### llm_screening.json 結構
```json
{
  "topic": "...",
  "model": "gpt-5",
  "generated_at": "ISO-8601",
  "papers": [
    {
      "arxiv_id": "...",
      "title": "...",
      "decision": "yes",
      "reason": "...",
      "confidence": 0.82
    }
  ]
}
```

### selected_ids.json
```json
{
  "selected": ["2502.06490", "...."],
  "rejected": ["..."]
}
```

### 與 Keywords 的檔案對接
Filter-Seed 會在篩選後下載並整理 seed PDF 目錄：

- **經 LLM 篩選後的 PDF（供下游使用）**：`seed/downloads/ta_filtered/`
- **保留給「下載後複審」的目錄**：`seed/downloads/pdf_filtered/`（目前不寫入）

行為規則：
- Filter-Seed 完成後，`seed/downloads/ta_filtered/` 只保留 `decision == yes` 的 PDFs（必要時現場下載）。
- 若重新執行，會重用已存在的 PDFs，並移除不在本次 `selected` 的檔案。
- keywords 預設讀 `seed/downloads/ta_filtered/`。

---

## 9) 行為與錯誤處理

- 若 seed metadata 為空 → 直接輸出空結果（不報錯）
- 若 LLM 呼叫失敗 → 回報錯誤（遵守 repo 規則，不做 fallback）
- 若 **全部為 NO** → 輸出 empty selection（不做額外處理）

---

## 10) 可重跑與快取

預設 **可重跑**：  
- 允許 `--force` 覆寫 `seed/filters/*`  
- 若不加 `--force`，則遇到既有結果直接回傳 `skipped: true`

---

## 11) 測試與驗證要點

由於 repo 規則禁止 mock：
- 只能用真實 API 驗證（integration test）
- 測試重點：輸出 JSON 格式、decision 僅 yes/no、confidence 為 0~1

---

## 12) 風險與緩解

### 風險
- LLM 誤判（false negative / false positive）
- 模型輸出不穩定（非 deterministic）

### 緩解
- 固定 prompt、低溫度（如 0.2）
- 落盤 reason + confidence，方便抽查

---

## 13) 與 Keywords 的整合策略

採用單一路徑：Filter-Seed 會整理 `seed/downloads/ta_filtered/`，keywords 預設讀取該目錄。  
`seed/downloads/pdf_filtered/` 保留給後續「下載後複審」流程。

---

## 14) 待確認事項（本 spec 預設）

- 只用 title + abstract
- 保留 reason + confidence
- 全部為 NO 時不做額外處理
