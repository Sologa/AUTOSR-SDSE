# Pipeline Codex Report Follow-ups (Spec / Plan / Tasks)

> 本文件為單檔整合版，包含 **Spec / Plan / Tasks**。
> 依據 speckit 工作流格式（spec.md + plan.md + tasks.md）的結構濃縮而成。

---

## Spec

### 目標
- 修正 pipeline bundle summary/manifest 的 seed_downloads 計數，避免分析誤判。
- 明確規範 criteria formatter：不得產生時間條款與 hard string match。
- 增加 seed_llm_screening 的低樣本 fallback 規則，避免 seed 過少。
- 將 harvest query plan 與 anchor coverage 落盤，便於 debug。
- 補足 review 結果的 discard_reason（或提供可追溯的 discard 依據）。
- 重新跑一次 pipeline，驗證 criteria/time_range 與 cutoff 行為。

### 非目標
- 不改動 pipeline 的核心流程順序。
- 不新增外部依賴（除非你明示）。
- 不更換 criteria JSON schema（除非你明示改採新 schema）。

### 使用者故事
- **US1（P0）**：作為維護者，我需要修正 bundle summary 的 seed_downloads 統計，避免用錯數據做推論。
  - 獨立驗證：同一個 download_results.json，summary/manifest 的 seed_downloads 與實際檔案數一致。
- **US2（P0）**：作為維護者，我需要 criteria formatter 明確禁止時間條款與 hard string match。
  - 獨立驗證：criteria.json 中無 time_range，且 required 不含「標題/摘要必含某字串」類條款。
- **US3（P1）**：作為維護者，我需要 seed_llm_screening 在 seed 過少時採用「寬進嚴出」規則。
  - 獨立驗證：當 seed_count < K 時，允許高關聯但非 survey 的 seed 進入；並在報告中標記 fallback。
- **US4（P2）**：作為維護者，我需要 harvest query plan 落盤，以檢視 anchor 覆蓋。
  - 獨立驗證：harvest 產物包含 query_plan.json，紀錄 anchor × term 覆蓋與實際查詢。
- **US5（P1）**：作為維護者，我需要 review 結果具備 discard_reason 或可回溯依據。
  - 獨立驗證：review 結果中 discard 類別不為空，或有獨立的 discard_reason 映射檔。
- **US6（P1）**：作為維護者，我需要重新跑 pipeline 驗證修正有效。
  - 獨立驗證：兩個 topic 的 criteria.json 與 cutoff.json 符合規格，且輸出可重現。

### 執行限制（使用者指定）
- 已完成現況備份：使用者已 push 現在程式碼，可回溯。
- **重跑前需先備份兩個 topic 的完整工作區/產物**。
- **預算限制：僅重跑一個 topic**（discrete audio tokens），另一個 topic 不重跑。
- 執行時務必使用「exact topic」字串，避免 topic 輸入錯誤。

### Exact Topics（必須逐字使用）
- Discrete Audio Tokens: More Than a Survey!
- On The Landscape of Spoken Language Models: A Comprehensive Survey

### 約束與規格
- criteria JSON schema 仍採現行 `structured_web_search_pipeline.py` 既有 schema。
- cutoff/date 過濾依程式規則處理，不允許由 criteria 或使用者輸入時間條款。
- 所有新產物必須落盤在 workspaces/<topic>/ 下且有清楚檔名。

---

## Plan

### 架構與實作策略
1) **Bundle summary/manifest 修正**
   - 先定位 bundle 打包腳本與 summary/manifest 產生位置。
   - 修正 seed_downloads 的計數邏輯：以實際下載數或檔案清單為準。

2) **Criteria formatter 規則補強**
   - 在 formatter prompt 明確禁止 time_range 與 hard string match。
   - 不改 schema；僅加規則與後處理檢查。

3) **Seed 低樣本 fallback**
   - 在 seed_llm_screening 或其前後流程加入條件：當 seed_count < K 時，放寬規則（高關聯非 survey 可入）。
   - 將 fallback 的觸發與採用原因記錄在 selection_report。

4) **Harvest query plan 落盤**
   - 在 harvest 階段輸出 query_plan.json：包含 anchors、search_terms、實際查詢組合與配額使用情況。

5) **Review discard_reason 補足**
   - 若上游能提供理由，落盤至 review 結果；
   - 若無法，新增後處理映射（依 cutoff / 同名 / 時間等規則給出 discard_reason）。

6) **驗證與回歸**
   - 先備份兩個 topic 產物。
   - 僅重跑 `Discrete Audio Tokens: More Than a Survey!`，確認 criteria/time_range、cutoff、query_plan、discard_reason 等輸出完整。

### 產物與檔案
- bundle summary/manifest（路徑需先定位）
- `workspaces/<topic>/harvest/query_plan.json`
- `workspaces/<topic>/review/latte_review_results.json`（含 discard_reason 或對應映射）
- `workspaces/<topic>/criteria/criteria.json`
- `workspaces/<topic>/cutoff/cutoff.json`

### 風險
- 若 bundle 打包腳本不在 repo，需要你提供路徑。
- seed_llm_screening 若在外部資源或 prompt 無法定位，需要確認實作位置。
- 重新跑 pipeline 可能依賴外部服務穩定性。

---

## Tasks

### Phase 1 — Discovery
- **T001**：定位 bundle 打包腳本與 summary/manifest 產生路徑（repo 內 grep + 你提供線索）。
- **T002**：定位 seed_llm_screening 的 prompt/規則與輸出位置。

### Phase 2 — Implementation (P0/P1)
- **T003 [US1]**：修正 seed_downloads 計數邏輯，並更新 bundle summary/manifest。（對應檔案以 T001 為準）
- **T004 [US2]**：在 formatter prompt 明確加入「禁止時間條款/硬字串匹配」規則。（`src/pipelines/topic_pipeline.py`）
- **T005 [US3]**：新增 seed_count < K 的 fallback 規則與落盤紀錄。（對應 seed screening 流程檔案）
- **T006 [US5]**：補足 discard_reason（review 結果或後處理映射）。

### Phase 3 — Implementation (P2)
- **T007 [US4]**：新增 harvest query_plan.json 產物（含 anchor coverage 與實際查詢）。

### Phase 4 — Verification
- **T008 [US6]**：備份兩個 topic 後，僅重跑 `Discrete Audio Tokens: More Than a Survey!`，驗證 criteria/time_range、cutoff、query_plan、discard_reason 輸出。
- **T009**：更新 docs/logs，整理執行證據與對照結果。

### 任務完成條件
- US1–US6 皆有獨立驗證紀錄。
- docs/logs 完整更新。
- 產物可重現且可追溯。
