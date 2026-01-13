# Tasks: Codex/Gemini CLI Review Smoke Test (docs/codex/test-review)

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

**Input**: Design documents from `docs/codex/test-review/`  
**Prerequisites**: `docs/codex/test-review/plan.md` (required), `docs/codex/test-review/spec.md`

## Execution Flow (main)
```
1. 讀取 plan.md，確認資料來源與 model 對應
2. 先完成輸出 schema 與 manifest，再做 runner
3. 先單 reviewer，再完整 workflow
4. 補齊文件與範例輸出
```

## Phase 3.1: Setup
- [x] **T001** 新增 `docs/codex/test-review/review_output.schema.json`（含 evaluation 1–5、reasoning、paper metadata）
- [x] **T002** 新增 `docs/codex/test-review/run_manifest.schema.json`（run_id、來源檔、criteria 來源、模型與輸出清單）

## Phase 3.2: Tests First (Schema/Validation)
- [x] **T003 [P]** 新增 `docs/codex/test-review/validate_review_output.py`（驗證 review_output.schema.json）
- [x] **T004 [P]** 新增 `docs/codex/test-review/validate_run_manifest.py`（驗證 run_manifest.schema.json）

## Phase 3.3: Core Implementation
- [x] **T005 [Story: US1]** 完成單 reviewer（JuniorNano）runner：讀取 `harvest/arxiv_metadata.json` 前 5 筆、組 prompt、執行 `codex exec`、輸出至 `docs/codex/test-review/outputs/<run_id>/codex_single.json`
- [x] **T006 [Story: US2]** 完成單 reviewer（JuniorMini）runner：同一輸入、執行 `gemini` headless、輸出至 `docs/codex/test-review/outputs/<run_id>/gemini_single.json`

## Phase 3.4: Integration
- [x] **T007 [Story: US3]** 完成完整 workflow runner：Round A（JuniorNano+JuniorMini）→ Round B（SeniorLead），輸出 `docs/codex/test-review/outputs/<run_id>/full_workflow.json`
- [x] **T008 [Story: US3]** 補上 criteria 讀取規則（workspace criteria → 預設 criteria），並在輸出中標記來源

## Phase 3.5: Polish
- [x] **T009 [P]** 在 `docs/codex/test-review/` 補充簡短使用說明（如何手動執行、輸出位置、失敗訊息）
- [x] **T010 [P]** 提供一份最小範例輸出（可用空白範例檔）以便對照
- [x] **T011 [P]** 補充 `docs/codex/test-review/config.md`（與 README 一致）說明 `CODEX_HOME`、sandbox/network 控制與 `--codex-extra-arg` 的測試流程。
- [x] **T012 [P]** 驗證並紀錄 `docs/codex/test-review/outputs/<run_id>/run_manifest.json` 中 codex 命令包含 `--disable web_search_request`，並確認輸出 JSON 未出現 `web_search` tool entry。

## Phase 3.6: Web Search Controls (Gemini)
- [x] **T013 [P]** 補充 `docs/codex/test-review/README.md`、`docs/codex/test-review/config.md`、`docs/codex/test-review/gemini_web_search_control.md` 說明 Gemini CLI 以 `./.gemini/settings.json` 控制 `google_web_search`。
- [x] **T014 [P]** 在 Gemini runner 增加 `./.gemini/settings.json` 切換機制（預設禁用 `google_web_search`），並將設定策略寫入 `run_manifest.json`。

## Dependencies
- T001/T002 → T003/T004 → T005/T006 → T007/T008 → T009/T010

## Parallel Example
```
T003 [P] 定義 review 輸出 schema
T004 [P] 增加輸出檢核腳本
```

## Notes
- 所有檔案僅放在 `docs/codex/test-review/`，不觸碰 `src/` 或正式 pipeline。
- 若資料來源不足 5 篇，仍需完成輸出並標記原因。
