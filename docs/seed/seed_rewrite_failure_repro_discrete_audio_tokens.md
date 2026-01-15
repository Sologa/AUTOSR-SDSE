# Discrete Audio Tokens seed rewrite 失敗復現（CLI 實跑版）

## 目的
- 依指定指令實跑 `seed` 階段並復現失敗。
- 彙整本地產物與 arXiv 查核結果，說明前因後果。
- 回答「iter 為何看不到前面結果」的事實依據。

## 限制與遵循
- 僅使用 arXiv 作為外部查核來源（符合限制）。
- 本報告不提供修正建議，僅描述事實與可驗證原因。

## 實跑指令與結果
執行命令：
```
python scripts/topic_pipeline.py seed --topic "Discrete Audio Tokens: More Than a Survey!" \
  --seed-rewrite \
  --seed-rewrite-max-attempts 10 \
  --seed-rewrite-model gpt-5.2 \
  --seed-rewrite-reasoning-effort xhigh \
  --no-cache
```
執行結果：失敗（`ValueError: Seed rewrite exhausted without PDFs`）。

## 產物證據（本地）
1) `workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_rewrite.json`
   - `generated_at = 2026-01-14T23:25:36.426558+00:00`
   - `attempt = 10`
   - `selected_queries = ["discrete audio tokenization", "discrete audio token sequences", "discrete audio token representations"]`
   - 檔內未出現字串 `speech`（以檔案內容檢視確認）。
2) `workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_selection.json`
   - `records_total = 1`
   - `records_after_filter = 0`
   - `cutoff_reason = "cutoff_removed_all_candidates"`
   - `search_query = (all:"discrete audio tokenization" OR all:"discrete audio token sequences" OR all:"discrete audio token representations") AND (...)`
3) `workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/download_results.json`
   - `downloaded_at = 2026-01-14T23:21:12.543412+00:00`
   - `downloads.arxiv = []`
   - `rewrite_attempts = 10`

## 外部查核（arXiv）
查核動機：確認原始 query 與 rewrite query 在 arXiv 的實際召回。  
查核渠道：arXiv API（mcp__arxiv__search_papers）。

### A) 原始 seed query
```
(all:"Discrete Audio Tokens: More Than a Survey!" OR all:"discrete audio tokens: more than a survey" OR all:"Discrete Audio Tokens" OR all:"discrete audio tokens: more than a surveys") AND (all:"survey" OR all:"review" OR all:"overview" OR all:"systematic review" OR all:"systematic literature review" OR all:"scoping review" OR all:"mapping study" OR all:"tutorial")
```
結果：`total_results = 1`，僅命中 `2506.10274`（同名論文）。

### B) rewrite 後 query（與 seed_selection.json 一致）
```
(all:"discrete audio tokenization" OR all:"discrete audio token sequences" OR all:"discrete audio token representations") AND (all:"survey" OR all:"review" OR all:"overview" OR all:"systematic review" OR all:"systematic literature review" OR all:"scoping review" OR all:"mapping study" OR all:"tutorial")
```
結果：`total_results = 1`，僅命中 `2506.10274`（同名論文）。

## 前因後果（基於證據）
1) 原始 seed query 在 arXiv 只命中同名論文 `2506.10274`。  
2) 同名論文觸發 cutoff，被排除後候選為 0。  
3) 進入 seed rewrite，輸出片語仍落在 `audio token` 詞簇。  
4) rewrite query 在 arXiv 仍只命中同名論文。  
5) cutoff 再次排除後無 PDF，程式拋出 `Seed rewrite exhausted without PDFs`。

## 為何 iter 看不到前面結果（基於程式與 prompt）
- `SeedQueryRewriteAgent` 透過 `_build_seed_rewrite_prompt` 組 prompt（`src/pipelines/topic_pipeline.py`）。  
- `resources/LLM/prompts/seed/seed_query_rewrite.md` 只有 `<<topic>>` 佔位符，未包含前次輸出或檢索結果。  
- rewrite loop 沒有把上一輪的 query、arXiv 命中數、或失敗原因寫回 prompt。  
結論：每一輪 LLM 的**輸入內容相同**，因此看不到前面完整結果。

## 測試要點
- `seed_rewrite.json` 中 `attempt` 為 10，`selected_queries` 與 B) query 對應。
- `seed_selection.json.records_total` 與外部查核 A/B 的 `total_results` 一致。
- `download_results.json.downloads.arxiv` 為空陣列。
- CLI 實跑回報 `ValueError: Seed rewrite exhausted without PDFs`。

## 已知限制
- 本報告僅描述事實，不提供修正建議。
- 外部查核僅使用 arXiv。
