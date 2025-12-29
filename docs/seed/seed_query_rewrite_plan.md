# Seed Query 改寫判斷（修改計劃）

## 目的
在 **同名 cutoff 必開** 的前提下，當 seed 查詢結果因為過度精準或 cutoff 而「完全沒有可用 PDF」時，由 agent 判斷是否需要改寫 topic 作為 seed query，避免整個 pipeline 在 keywords 之前中止。

## 背景/現況
- 目前 seed query 以 `topic variants × survey/review/overview` 組合產生，且預設啟用同名 cutoff。
- 若 topic 是完整論文標題，常出現「只命中同名論文 → 被 cutoff 移除 → 下載 0 份 PDF」。
- 一旦 seed 沒有 PDF，`keywords` 會直接報錯而停止流程。

## 修改目標
- 保留同名 cutoff 規則不變。
- 當「seed 無可用 PDF」時，自動判斷是否需要**改寫** topic query，並重新執行 seed（最多 N 次）。
- 改寫必須保持原 topic 核心語意，不可新增無關領域或變成另一個主題。
- 改寫結果需要**可追溯**與**可關閉**。

## 修改範圍（計劃）
1) **seed 階段主流程**  
   - 在 seed 完成後，讀取 `seed/queries/seed_selection.json` 與 `seed/downloads/download_results.json`，判斷是否需要改寫。
2) **agent 改寫模組**  
   - 新增一個「改寫 topic → arXiv raw query」的代理邏輯（可使用 LLM 或規則 fallback）。
3) **輸出與記錄**  
   - 新增 `seed/queries/seed_rewrite.json` 追蹤改寫決策與最終 query。
   - 在 `download_results.json` 中補上 `rewrite_attempts` 與 `rewrite_query`（如有）。

## 判斷條件（觸發改寫）
以下任一成立即觸發改寫流程（擇一即可）：
- `seed_selection.json.records_after_filter == 0`
- `download_results.json.seed_pdfs == []`
- `seed_selection.json.cutoff_reason == "cutoff_removed_all_candidates"`

## 改寫策略（計劃）
### A) LLM 改寫（優先）
輸入：
- 原始 topic 字串
- `seed_selection.json`（含 cutoff_candidate 與 cutoff_reason）
- 原始 seed query（若有）

輸出（限制）：
- 產出 1~3 組「縮短且保留核心概念」的 query 片語
- 不得新增新領域名詞或縮寫
- 不得移除關鍵概念（如 “Spoken Language Models”）

### B) 規則 fallback（無 LLM 時）
- 自動去除 `: A Comprehensive Survey` / `Survey` / `Review` 等後綴
- 移除標點、僅保留核心名詞片語作為 query

## 代理與 Prompt（計劃）
- **Rewrite Agent 名稱**：`SeedQueryRewriteAgent`
- **使用模型**：`gpt-5.2`
- **Prompt 路徑**：`resources/LLM/prompts/seed/seed_query_rewrite.md`
- **Prompt 職責**：
  - 輸入：原始 topic、seed_selection.json（cutoff_reason/cutoff_candidate）、原始 seed query
  - 輸出：1~3 個「保留核心概念、去除冗長後綴」的改寫 query 片語
  - 僅回傳建議片語清單，不執行搜尋

## 介面 / 參數（計劃）
新增 seed 參數：
- `--seed-rewrite`：是否啟用改寫（預設 off）
- `--seed-rewrite-max-attempts N`：最多改寫次數（預設 1~2）
- `--seed-rewrite-model`：LLM 模型（預設 `gpt-5.2`）
- `--seed-rewrite-preview`：只輸出改寫結果、不實際重跑 seed

## 輸出規格（計劃）
- `seed/queries/seed_rewrite.json`（示意）
  - `topic`
  - `trigger_reason`
  - `attempts`
  - `rewrite_candidates`
  - `selected_query`
  - `generated_at`

## 使用範例（計劃）
```bash
python scripts/topic_pipeline.py seed --topic "<topic>" --seed-rewrite
```

## 測試要點
- 同名 cutoff 仍啟用時，若 `records_after_filter == 0`，會進入改寫流程。
- 產生 `seed_rewrite.json`，並記錄 trigger reason 與最終 query。
- 改寫後若仍無 PDF，流程需清楚回報並停止，不可隱性吞錯。

## 已知限制
- 改寫需要 LLM 時依賴 `OPENAI_API_KEY`；無金鑰時只能使用規則 fallback。
- 若 topic 過度寬泛，改寫可能帶來噪音，需要後續 filter-seed / criteria 補強。
