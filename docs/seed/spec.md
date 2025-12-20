# Seed Stage 規格（spec）

本文件定義「Seed」階段的行為與介面：以單一 `topic` 驅動 arXiv 查詢，收集 **survey/review/overview** 類型的 seed papers，並下載 PDF 供後續 keyword extraction 使用。

---

## 1) 目的

- 從 arXiv 找到與 `topic` 相關的 survey/review/overview 論文
- 下載 PDF 作為 keyword extraction 的輸入
- 產出可追溯的查詢記錄與篩選報告

---

## 2) 目前已知問題（需改善）

> 以下為目前流程中可明確觀察到的問題，將作為後續修正依據。

1) **Seed 無模型 prompt**  
   現行 Seed 不使用 LLM；因此沒有 prompt 可檢視或調參。

2) **Anchor 需要使用者介入或會產生雜訊**  
   - 若使用者不提供 `--anchor`，會使用 `default_topic_variants` 的字串變形，  
     對於「複雜 topic / 真實存在的論文標題」容易產生不乾淨的 anchor。  
   - 這與「最小人類介入」的目標不一致。

3) **複雜 topic 的語意壓縮不足**  
   topic 若是長標題或含副標題，直接用作 anchor 會導致查詢過窄或不穩定。

---

## 3) 介面 / 參數

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

## 4) 查詢行為（摘要）

### 一般模式
組合規則如下（示意）：
```
(<anchor_clause>) <boolean_operator> (<survey_clause>)
```

- `anchor_clause`：
  - `phrase`：`ti:"<anchor phrase>"`（完整片語）
  - `token_and`：`ti:("token1" AND "token2" AND "token3")`
- `survey_clause`：`ti:"survey" OR ti:"review" OR ti:"overview" ...`
- 多個 anchor 之間為 **OR**

### Raw query 模式
若 `--arxiv-raw-query` 有值，直接送出該查詢字串，忽略其餘查詢參數。

---

## 5) 輸出

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

## 6) 使用範例

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
  --arxiv-raw-query 'ti:("term1" AND "term2" AND "term3") AND (survey OR review)' \
  --no-cache
```

---

## 7) 測試要點

- `seed/queries/arxiv.json` 是否更新（使用 `--no-cache` 可強制更新）
- `seed/queries/seed_selection.json` 是否記錄 cutoff 與候選清單
- `seed/downloads/download_results.json` 是否有下載結果與錯誤原因
- `seed/downloads/arxiv/*.pdf` 是否落盤（若無，可能是 pdf 被 block）

---

## 8) 已知限制

- arXiv API 回傳結果受限於查詢字串與 `max_results`
- survey 條件可能過嚴，導致沒有 seed
- cutoff 相似標題規則可能排除唯一相關 survey
- PDF 可能因權限或 404 下載失敗（會記錄在 download_results.json）
- 本階段只查 arXiv，不涵蓋 Semantic Scholar 或 DBLP

---

## 9) LLM 產生 Anchor（擬議變更）

為了降低人為介入，建議在 Seed 階段加入 **LLM 自動產生 anchor terms** 的能力：

### 行為目標
- 使用者 **不必** 提供 `--anchor`
- 由模型根據 `topic` 產生 **2–6 個**穩定、可查詢的短片語
- 產生結果須落盤，便於追溯與重用

### 產出建議
```
workspaces/<topic_slug>/seed/queries/anchor_terms.json
```

### 需要新增的 CLI（擬議）
- `--anchor-source auto|manual`（預設 auto）
- `--anchor-model <model>`（預設 gpt-5-mini）
- `--anchor-temperature <float>`（預設 0.2）
- `--anchor-max-output-tokens <int>`（預設 300）

---

## 10) LLM Anchor Prompt（完整草案，無特定領域）

> 注意：此 prompt **不得**包含任何特定領域的關鍵字或規則，必須對任意 topic 通用。

```
Role: Academic Search Strategy Assistant
Task: Generate high-quality anchor terms for literature search based on the given topic.
Constraints:
  - Use ONLY the given topic text.
  - Output STRICT JSON only, no extra text.
  - Provide 2–6 anchor terms, each 1–4 words, noun-phrase style.
  - Avoid adding "survey", "review", or "overview" to anchor terms.
  - Avoid overly broad or generic terms.
  - If the topic is a long title, compress it into stable, searchable phrases.

Topic: <<topic>>

Output JSON (no extra keys):
{
  "anchor_terms": ["...", "..."],
  "notes": "一句話中文說明生成策略"
}
```

---

## 11) 變更影響評估（摘要）

- 增加 LLM anchor 生成會涉及：
  - 新 prompt 檔案
  - Seed 流程多一次 LLM 呼叫
  - 新的落盤檔案與參數
- 不影響下游介面（仍產出 `seed/queries/arxiv.json` 與 PDF）
