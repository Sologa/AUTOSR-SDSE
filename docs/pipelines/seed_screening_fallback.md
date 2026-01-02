# Seed LLM Screening Fallback

## 目的
- 當 seed LLM 審核後的 `selected` 過少時，啟用放寬模式避免 seed 枯竭。
- 放寬規則：允許「高度相關但非明確 survey/review」的論文進入 seed。

## 介面 / 參數
- 入口：`python scripts/topic_pipeline.py filter-seed --topic "<topic>"`
- 內部參數（目前為程式預設值）：
  - `fallback_min_selected = 2`
  - `fallback_max_additional = None`（不設上限）
  - fallback prompt：`resources/LLM/prompts/filter_seed/llm_screening_fallback.md`

## 行為
- 先以嚴格 prompt (`llm_screening.md`) 審核。
- 若 `selected` 數量 `< fallback_min_selected`：
  - 對 `rejected` 重新以 fallback prompt 審核。
  - 重新加入 `fallback_decision == yes` 的候選。

## 產出
- `workspaces/<topic>/seed/filters/llm_screening.json`
  - 每筆記錄新增 `fallback_decision/fallback_reason/fallback_confidence`（若觸發）。
  - `fallback` 區塊記錄觸發條件與新增 IDs。
- `workspaces/<topic>/seed/filters/selected_ids.json`
  - 新增 `fallback_added` 欄位。

## 測試要點
- 人工將 seed 限制到極少數，確認 fallback 觸發與 `fallback_added` 出現。
- `selected` 數量應 >= `fallback_min_selected`（若有候選）。

## 已知限制
- fallback 仍依賴 LLM 判斷，會增加額外成本。
- 不保證一定補足到指定數量（若候選皆不合格）。
