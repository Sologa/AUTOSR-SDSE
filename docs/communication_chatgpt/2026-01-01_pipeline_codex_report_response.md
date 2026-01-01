# ChatGPT 深度分析報告回應（2026-01-01）

## 讀取範圍
- `test_artifacts/pipeline_codex_report/REPORT.md`
- `test_artifacts/pipeline_codex_report/proposed_prompts/*.md`
- `test_artifacts/pipeline_codex_report/proposed_specs/*.json`

## 我已確認的重點（與報告一致）
1) **cutoff_date 未落盤**（topic: SLM）
   - `workspaces/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/seed/queries/seed_selection.json`
   - `cutoff_candidate.published_date = 2025-04-11` 但 `cutoff_date = null`。
   - 這確實違反「cutoff 後不得錄入」。

2) **criteria 仍含時間條款與 hard string match**（topic: SLM）
   - `workspaces/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/criteria/criteria.json`
   - `structured_payload.time_range = {"type":"relative","past_years":3}`
   - `structured_payload.inclusion_criteria.required` 內含「過去3年」與「標題/摘要需出現 spoken language model(s)…」這類 hard match。
   - 與硬性規格（時間過濾程式化、criteria 不含 recency / hard match）衝突。

3) **harvest 僅使用 2/4 anchors**（topic: discrete_audio_tokens）
   - `workspaces/discrete_audio_tokens_more_than_a_survey/keywords/keywords.json`
   - `workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json`
   - 實際 `anchor` 僅為 `discrete speech tokens` / `speech tokenization`，確實縮小 coverage。

4) **review 結果沒有任何 discard_reason**（topic: SLM）
   - `workspaces/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/review/latte_review_results.json`
   - 這個檔案是 list，無內建 summary；我統計 `final_verdict` 與 `discard_reason` 欄位，`discard_reason` 全空。

## 我認為需要修正/補充的地方
1) **報告中「seed_downloads 計數不一致」有一部分是 bundle summary 的計算錯誤**
   - `download_results.json` 的 `downloads` 是 dict（含 `arxiv/semantic_scholar/dblp`），
     我在 bundle 打包時用 `len(downloads)` 直接計數 → 變成 3（其實只是三個 key），
     但 `downloads.arxiv` 實際是 1。
   - 這會讓報告誤判為 pipeline 記錄不一致。建議先修正 bundle 的 summary/manifest 再與 ChatGPT 討論。

2) **proposed criteria_formatter 的 schema 與現行程式不一致**
   - 現行 `structured_web_search_pipeline.py` 的 JSON schema 是 `topic_definition/summary/summary_topics/inclusion_criteria/exclusion_criteria`。
   - `proposed_prompts/criteria_formatter.md` 使用了新的 schema（含 `search_keywords`、`topic_definition` 物件等）。
   - 若採用，需同步修改 formatter 解析與 downstream（不可直接替換 prompt）。

3) **seed_llm_screening_prompt 的「不確定就 no」可能更縮小 seed**
   - 在 seed 很少的情境下，這會讓 keywords 更偏單一 PDF。
   - 可考慮：當 seed_count < K 時，允許「高關聯但非 survey」的 paper 進入 seed（報告也有類似方向，但需加明確 fallback 條件）。

4) **criteria 時間條款問題可能是「舊 run artifacts」**
   - 目前 code 已有規則「時間不要放進 criteria」（見 `docs/pipelines/pipeline_handoff.md`），
     但這次 artifact 仍有 time_range，說明至少在該次 run 沒生效。
   - 建議再確認：是 generator 仍注入時間字串、還是 formatter prompt 落盤的是舊版本。

## 我同意的修正方向（優先順序）
- **P0：程式層 cutoff + 同名排除全域化**
  - 需要在 seed/harvest/review/snowball 入口統一 apply，並落盤 `cutoff.json`。
- **P0：criteria prompt 禁止時間 / cutoff / hard string match**
  - 若不改 schema，至少在 formatter prompt 加上嚴格規則。
- **P1：seed rewrite 放寬為「語義等價但字面不同」**
  - 同名必排除時必須能產生「語義等價但不同字面」的查詢。
- **P2：harvest query plan 落盤（含 anchor coverage）**
  - 沒有 query_plan 很難 debug anchor coverage 問題。

## 是否需要再和 ChatGPT 交流？
**需要，但應該先做兩件事再問**：
1) **修正 bundle summary/manifest 的 seed_downloads 計數**，避免 ChatGPT 用錯誤數據推論。
2) **確認是否採用新 criteria schema**（若採用需同步程式；若不採用則請 ChatGPT 以現行 schema 修 prompt）。

## 若要再問 ChatGPT，建議問題清單
1) 在「不改 schema」前提下，請提供符合現行 JSON schema 的 criteria formatter prompt（禁止 time_range / cutoff / hard match）。
2) seed_llm_screening 在 seed_count 很少時是否要改成「寬進嚴出」？請提供可操作的 fallback rule。
3) 對 harvest anchor coverage 的最小修正是什麼？（不大改程式，只加 query_plan + quota）
4) 針對 cutoff_date null 的現象，請給出可能的 code path 與建議的診斷步驟（以 grep 關鍵字描述即可）。

