# Seed Rewrite Prompt 改寫背景與架構說明

## 目的
提供一份可直接交給 ChatGPT 的「完整上下文」，讓其在**不暴露特定論文標題或具體字串**的前提下，重新設計 `seed_query_rewrite.md` 的 prompt。

## 背景與前因後果
- Seed rewrite 的目標是**在 seed 候選為空或 cutoff 移除全部候選時**，把「標題式 query」改寫成更寬的**核心領域片語**，以避免 pipeline 在 keywords 前中止。若啟用 PDF 下載，仍可能因下載為空而觸發。
- 近期調整重點：
  - Prompt 必須**全程 generic**，不可出現任何可被視為特定論文標題的字串或例子。
  - 不可在 prompt 中暴露 `cutoff_reason`、`cutoff_candidate_title`、`original_seed_query` 等上下文。
  - 改寫輸出從「單一片語」改為「最多 3 個片語」，並由 parser 嚴格解析。
  - 允許在不引入新領域概念的前提下，使用常見同義/近義詞替換核心名詞。

## 具體問題脈絡（本次實際案例）
- 原始 seed query 以 `discrete audio tokens` 為核心片語，但結果過窄，導致 seed 召回不足。
- 使用者期望改寫能自然產生「同領域常見替代表達」，例如 `discrete speech tokens` 類型片語。
- 之前嘗試以**程式內部規則**做同義替換，導致 `seed_selection.json` 中出現 `discrete speech tokens`，但這被視為**違規（不得由程式硬編替換規則）**，已全面移除。
- 目前策略改為**完全由 LLM 產生最多 3 個片語**，再由 parser 嚴格解析，避免任何非 LLM 的同義詞注入。

## 現行架構（實作邏輯）

### 觸發條件
Seed rewrite 會在以下任一情況成立時觸發（僅列行為，不列任何具體樣本）：
- seed selection 為空或被 cutoff 移除
- 若啟用下載且下載結果為空

### LLM 改寫流程
1) `SeedQueryRewriteAgent` 讀取 `resources/LLM/prompts/seed/seed_query_rewrite.md`。
2) LLM 輸出最多 3 行，每行一個片語。
3) Parser 解析輸出，保留 1~3 個片語（去重、保序、轉小寫）。

### Parser 規則（強制）
- 允許 1~3 行，超過即報錯。
- 每行視為一個片語，`strip()` 後轉小寫。
- 移除重複片語，但保留原順序。
- **禁止**其他正規化（例如同義詞替換、移除標點等）。

### 查詢組合規則
- 改寫結果以 **phrase** 方式插入查詢（每個片語加引號）。
- 多片語以 `OR` 組合：`(all:"phrase1" OR all:"phrase2" OR all:"phrase3")`。

### 產物（落盤）
- `workspaces/<topic>/seed/queries/seed_rewrite.json`
  - `attempts[].raw_output`：LLM 原文
  - `attempts[].parsed_phrases`：解析後片語清單
  - `selected_queries`：實際採用的片語清單
- `workspaces/<topic>/seed/queries/seed_selection.json`
  - `search_query`：實際送出的 arXiv query（包含 OR 片語）
- `workspaces/<topic>/seed/downloads/download_results.json`
  - `rewrite_query`：第一個片語
  - `rewrite_queries`：完整片語清單

## Prompt 改寫需求（給 ChatGPT 的約束）
1) **全文必須是 generic**，不可出現任何可能對應特定論文標題的字串或例子。
2) 不可包含任何 seed 內部上下文（例如 cutoff reason / 原始 query / 候選標題）。
3) 輸出為**最多 3 行**，每行 1 個片語，且全小寫。
4) 允許常見同義/近義詞替換核心名詞，但不得引入新領域概念。
5) 片語必須是**核心領域片語**，不可是原標題或其改寫。
6) 不得輸出解釋、標號、引號或其他額外文字。

## 本次需求的重點（要讓 ChatGPT 理解）
- `discrete audio tokens` 屬於過窄片語，應引導模型產生**同領域等價片語**以提高召回。
- 不能在 prompt 中明示任何特定標題或固定短語（例如避免直接寫出某篇論文標題）。
- 同義替換必須由 LLM 自行決定，程式端不可硬編規則。

## 已知限制
- 改寫不保證一定提高召回；若主題本身過於狹窄，仍可能無有效候選。
- Seed rewrite 不讀 PDF，僅依賴 LLM prompt。

## 相關檔案
- Prompt：`resources/LLM/prompts/seed/seed_query_rewrite.md`
- 解析與流程：`src/pipelines/topic_pipeline.py`
- 規格文件：`docs/seed/seed_query_rewrite_plan.md`
