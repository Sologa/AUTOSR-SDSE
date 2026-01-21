# Tasks: Codex/Gemini CLI Keywords Smoke Test (docs/codex/test-keywords)

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

**Input**: Design documents from `docs/codex/test-keywords/`  
**Prerequisites**: `docs/codex/test-keywords/plan.md` (required), `docs/codex/test-keywords/spec.md`

## Execution Flow (main)
```
1. 讀取 plan.md，確認輸入來源與決策點
2. 先完成 schema 與共用 utils
3. 完成 codex/gemini runners
4. 確認 PDF→text 策略（pdfplumber、每 PDF 一檔）與執行 Gemini PDF 實測
```

## Phase 3.1: Setup
- [x] **T001** 新增 `docs/codex/test-keywords/keywords_response.schema.json`
- [x] **T002** 新增 `docs/codex/test-keywords/keywords_output.schema.json`
- [x] **T003** 新增 `docs/codex/test-keywords/run_manifest.schema.json`
- [x] **T010** 將 `pdfplumber` 加入 `sdse-uv/pyproject.toml`

## Phase 3.2: Core Implementation
- [x] **T004** 新增 `docs/codex/test-keywords/keywords_cli_utils.py`（共用 CLI/manifest/prompt 組裝）
- [x] **T021** 抽出 `docs/codex/test-shared/codex_cli_utils.py` 以共用 CLI/manifest helpers
- [x] **T005** 完成 Codex runner：`docs/codex/test-keywords/run_codex_keywords.py`
- [x] **T006** 完成 Gemini runner：`docs/codex/test-keywords/run_gemini_keywords.py`
- [x] **T012** Gemini runner 隔離 `.env` 變數影響，避免 JSON 輸出為空
- [x] **T013** Codex runner 支援 `--pdf-to-text`，以 `pdfplumber` 產生每 PDF 一個 `.txt`
- [x] **T014** Gemini runner 暫時關閉 `respectGitIgnore` 以允許讀取被忽略的 PDF
- [x] **T015** 新增 Codex 專用 schema 與 search_terms 陣列→物件轉換
- [x] **T017** 新增 keywords 輸出檢核腳本 `validate_keywords_output.py`
- [x] **T018** Runner 追加 search_terms 正規化（去除 `_`、限制 1–3 字詞、去重）
- [x] **T020** Runner 限制 `search_terms` 總術語數量不超過 `max_queries`

## Phase 3.3: Decision Gates
- [x] **T007** 確認 PDF→text 前處理依賴採用 `pdfplumber`
- [x] **T008** 指定 Gemini CLI PDF 讀取實測的 topic 與 PDF 範例集合（topic: `workspaces/discrete_audio_tokens_more_than_a_survey/`, PDFs: `workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/ta_filtered/2502.06490.pdf`）
- [x] **T011** 確認 PDF→text 保存檔名與子目錄規則（檔名沿用 PDF 檔名）

## Phase 3.4: Manual Validation
- [x] **T009** 以指定 topic/PDFs 執行 Gemini runner，記錄工具使用結果（run_id=20260112_214347，read_file 成功）
- [x] **T016** 以 `--pdf-to-text` 執行 Codex runner，記錄輸出結果（run_id=20260112_213838）
- [x] **T019** 重新執行 Codex/Gemini runner 並以 validate_keywords_output 驗證通過

## Dependencies
- T001/T002/T003/T010 → T004 → T005/T006 → T007/T008/T011 → T009

## Notes
- 不修改 `src/` 或正式 pipeline。
- Codex runner 若未提供 PDF→text 輸入必須直接報錯。
