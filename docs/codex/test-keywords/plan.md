# Implementation Plan: Codex/Gemini CLI Keywords Smoke Test (docs/codex/test-keywords)

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

**Branch**: `[docs-codex-test-keywords-cli]` | **Date**: 2026-01-12 | **Spec**: `docs/codex/test-keywords/spec.md`  
**Input**: Feature specification from `docs/codex/test-keywords/spec.md`

## Summary
在 `docs/codex/test-keywords/` 建立 keywords smoke test：以 Codex CLI / Gemini CLI 讀取 seed PDFs，輸出 `keywords.json` 等價結構與 `run_manifest.json`，並保留 tool policy 與輸入來源。主題固定為 `discrete audio tokens more than a survey`，workspace 為 `workspaces/discrete_audio_tokens_more_than_a_survey/`。

## Technical Context
**Language/Version**: Python (sdse-uv 內部版本)  
**Primary Dependencies**: 標準函式庫 + repo 既有模組（`src/utils/keyword_extractor.py` 的 prompt 組裝邏輯） + `pdfplumber`（PDF→text）  
**Storage**: 本地檔案（`docs/codex/test-keywords/`）  
**Testing**: 手動執行 runner 進行 smoke test  
**Target Platform**: 本機 CLI（與現有 pipeline 相同）  
**Constraints**: 不修改 `src/` 或受保護檔案；不在本次變更中安裝/同步依賴（`pdfplumber` 只新增至 `sdse-uv/pyproject.toml`）；輸出不寫入 workspaces；PDF→text 純文字保存於 `docs/codex/test-keywords/outputs/<run_id>/`  

## Constitution Check
- 本 repo 未見 `memory/constitution.md`；以 `AGENTS.md` 與 `docs/spec-kit-guide.md` 為規範基準。

## Project Structure

### Documentation (this feature)
```
docs/codex/test-keywords/
├── spec.md
├── plan.md
├── tasks.md
├── keywords_cli_utils.py
├── run_codex_keywords.py
├── run_gemini_keywords.py
├── keywords_response.schema.json
├── keywords_response_codex.schema.json
├── keywords_output.schema.json
└── run_manifest.schema.json
```

**Structure Decision**: 全部文件與測試腳本放在 `docs/codex/test-keywords/`，避免影響正式 pipeline。

## Phase 0: Outline & Research
1. **Codex PDF Input Strategy**
   - PDF→text 前處理依賴：`pdfplumber`。
   - Codex runner 僅接受文字輸入並在缺失時直接報錯。

2. **Select Test Topic & PDFs (Gemini)**
   - 固定 topic：`discrete audio tokens more than a survey`。
   - PDF 範例集合：`workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/ta_filtered/2502.06490.pdf`。
   - 先執行 Gemini CLI 的 PDF 讀取實測，記錄工具使用結果。

## Phase 1: Design & Contracts
1. **Input Source Design**
   - 預設 PDF 來源：`workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/ta_filtered/*.pdf`。
   - 允許限制筆數與指定 pdf dir。
   - PDF→text 產出保存於 `docs/codex/test-keywords/outputs/<run_id>/`，每個 PDF 一個文字檔，檔名沿用 PDF 檔名，範圍為全文。

2. **Prompt Design**
   - 使用 `resources/LLM/prompts/keyword_extractor/generate_search_terms.md`。
   - 使用 `ExtractParams` 與 `build_generate_instructions` 組裝 prompt。

3. **Output Schema Design**
   - `keywords_response.schema.json`：供 `codex exec --output-schema`。
   - `keywords_output.schema.json`：包含 run metadata 與 CLI 原始輸出。
   - `run_manifest.schema.json`：記錄輸入來源、prompt 路徑、CLI 命令與 tool policy。

4. **Runner Design**
   - `run_codex_keywords.py`：讀取 prompt +（可選）PDF→text 輸入，執行 `codex exec`。
   - Codex schema 限制：`search_terms` 以 `{category, terms}` 陣列輸出，runner 轉回物件格式再寫入 `codex_keywords.json`。
   - Runner 必須正規化 `search_terms`（去除 `_`、限制 1–3 字詞、去重）。
   - `run_gemini_keywords.py`：提供 PDF 路徑並要求 `read_file`，執行 `gemini --output-format json`。

## Phase 2: Task Planning Approach
**Task Generation Strategy**:
- 先定義 schema 與共用 utils，再完成兩個 runner。
- decision gate 與實測列為明確任務。

**Ordering Strategy**:
- schema → utils → codex runner → gemini runner → decision gate → 實測。

## Progress Tracking
- [ ] Phase 0: Research complete
- [ ] Phase 1: Design complete
- [ ] Phase 2: Task planning complete
- [ ] All NEEDS CLARIFICATION resolved
