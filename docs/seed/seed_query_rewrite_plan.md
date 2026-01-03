# Seed Query 改寫機制（實作版）

## 目的
在 **同名 cutoff 必開** 的前提下，當 seed 查詢結果因為過度精準或 cutoff 而「完全沒有可用 PDF」時，啟動 seed query 改寫機制並重試，避免 pipeline 在 keywords 前中止。

## 觸發條件（任一成立即觸發）
- `seed_selection.json.records_after_filter == 0`
- `download_results.json` 中無任何 `pdf_path`
- `seed_selection.json.cutoff_reason == "cutoff_removed_all_candidates"`

> 同名 cutoff 規則強制啟用，`--no-cutoff-by-similar-title` 會被忽略。

## 改寫策略（實作）
- **僅使用 LLM 改寫**，不提供規則 fallback（依專案政策禁止離線替代流程）。
- Rewrite agent：`SeedQueryRewriteAgent`
- 模型：`gpt-5.2`（可由 CLI 參數覆寫）
- Prompt：`resources/LLM/prompts/seed/seed_query_rewrite.md`
- 目標：把「標題式 query」縮成 **更廣的核心領域片語**，移除標題修飾語（如 On/overview/comprehensive/survey 等）。

### 輸出限制（嚴格）
- 只允許 **單一片語**（單行）。
- 不可修飾、不可加標號/引號/解釋。
- 輸出必須是 **核心領域片語**，不得是原題名或其改寫。
- 輸出 **一律小寫**。
- **解析規則**：
  1) 讀取 LLM 原文，按行拆分。
  2) 移除空行後必須只剩 1 行，否則視為失敗。
  3) 取得該行作為 `selected_query`，**只允許 `strip()` 後轉為小寫**。
  4) 禁止其他正規化（如去標點、替換同義詞）。

### arXiv Query 組合規則
- 改寫用 **phrase** 方式嵌入查詢（避免 token_and 造成字詞正規化）。
- `selected_query` 原樣帶入查詢，不改寫片語內容。

## 介面 / 參數
- `--seed-rewrite`：啟用改寫（預設關閉）
- `--seed-rewrite-max-attempts N`：最大嘗試次數（預設 2）
- `--seed-rewrite-model`：改寫 LLM 模型（預設 `gpt-5.2`）
- `--seed-rewrite-preview`：只產生改寫結果、不重跑 seed

## 輸出
- `seed/queries/seed_rewrite.json`
  - `topic`
  - `trigger_reason`
  - `attempts[]`（含 raw_output / parsed_phrase / status / error）
  - `selected_query`
  - `original_seed_query`
  - `cutoff_reason` / `cutoff_candidate_title`
  - `generated_at`
  - `preview_only`
- `seed/downloads/download_results.json`
  - `rewrite_attempts`
  - `rewrite_query`（如有）

## 行為重點
- 只要觸發條件成立且 `--seed-rewrite` 開啟，就會進入改寫流程。
- 若改寫後仍無 PDF，會 **明確報錯並停止**（不隱性吞錯）。
- `--seed-rewrite-preview` 只輸出改寫結果，不重跑 seed；其餘 seed 輸出維持原狀。

## 已知限制
- 需有效的 `OPENAI_API_KEY`。
- 改寫結果不保證降低噪音，若 topic 過度寬泛仍需靠 filter-seed / criteria 後續控制。
