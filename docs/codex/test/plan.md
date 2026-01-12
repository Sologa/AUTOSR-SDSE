# Implementation Plan: Codex/Gemini CLI Review Smoke Test (docs/codex/test)

**Branch**: `[docs-codex-test-review-cli]` | **Date**: 2026-01-09 | **Spec**: `docs/codex/test/spec.md`
**Input**: Feature specification from `docs/codex/test/spec.md`

## Summary
在 `docs/codex/test/` 建立可手動執行的測試腳本：先做單 reviewer smoke test，再做完整 workflow（JuniorNano/JuniorMini/SeniorLead）。輸入來源固定為 `workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json` 前 5 筆，並輸出結構化 review 結果與 run manifest。

## Technical Context
**Language/Version**: Python (sdse-uv 內部版本)  
**Primary Dependencies**: 盡量使用標準函式庫；必要時讀取 LatteReview prompt 與 criteria 既有檔案  
**Storage**: 本地檔案（`docs/codex/test/`）  
**Testing**: 手動執行 scripts 驗證輸出  
**Target Platform**: 本機執行環境（與現有 pipeline 相同）  
**Project Type**: single  
**Performance Goals**: 單次僅處理 5 篇 paper  
**Constraints**: 不修改正式 pipeline；不新增依賴；輸出不寫入 workspaces  
**Scale/Scope**: 小量資料、一次性驗證用途

## Constitution Check
- 本 repo 未見 `memory/constitution.md`；以 `AGENTS.md` 與既有 `docs/spec-kit-guide.md` 為規範基準。

## Project Structure

### Documentation (this feature)
```
docs/codex/test/
├── spec.md
├── plan.md
├── tasks.md
└── outputs/<run_id>/
```

**Structure Decision**: 文件與測試腳本全部放在 `docs/codex/test/`，避免影響 `src/` 與正式 pipeline。

## Phase 0: Outline & Research
1. **Clarified Inputs**
   - 來源固定：`workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json` 前 5 筆（檔案順序）。
   - 單 reviewer → 完整 workflow 兩階段。

2. **CLI Best Practices**
   - Codex CLI：依 `docs/codex/` 內部文件採用 `codex exec` 非互動模式與結構化輸出控制。
   - Gemini CLI：採用官方 Gemini CLI 的 headless 模式與 model selection（見外部文件）。
   - 設定控制：預設 `CODEX_HOME` 指向 repo 內 `./.codex`，並在 config 中鎖定 sandbox/network（例如 `network_access=false`）與 `--codex-extra-arg` 支援，確保測試者無需改動使用者層級設定就能關閉網路或調整 approval。
   - Web search policy：預設 `./.codex/config.toml` 關閉 `features.web_search_request`/`tools.web_search`，腳本在 manifest 及 CLI 參數中註記 `--disable web_search_request` 與 `-c 'tools.web_search=false'`，並提供 `--allow-web-search` 無縫反向覆寫，這一做法需加入手動測試檢核清單。
   - Gemini web search policy：使用 repo 內 `./.gemini/settings.json` 的 `tools.exclude`/`tools.core` 控制工具可用性，headless CLI 無單次旗標；後續 runner 需記錄設定策略並提供 per-run 覆寫。

**Output**: 更新 spec.md/plan.md 並固定輸出命名與模型策略

## Phase 1: Design & Contracts
*本需求以「測試腳本」為主，不需要 API contracts；僅定義輸出格式與輸入來源。*

1. **Input source design**
   - 讀取 `harvest/arxiv_metadata.json` 的 list 順序，取前 5 筆
   - 欄位：`arxiv_id`、`metadata.title`、`metadata.summary`
   - 若少於 5 筆，輸出不足原因與實際數量

2. **Prompt parity design**
  - 與 pipeline 一致的 review prompt 結構（Title/Abstract + criteria + 1–5 評分 + reasoning）
  - criteria 讀取順序：`workspace/criteria/criteria.json` → 內建預設文案
  - 完整 workflow：Round A（JuniorNano+JuniorMini）→ Round B（SeniorLead）
  - **Codex config design**：規範 repo-local `.codex/config.toml` 為 `CODEX_HOME`，說明如何透過該檔調整 approve/network，並記錄 flag 使用方式（`--codex-extra-arg`）。
  - **Gemini config design**：規範 repo-local `./.gemini/settings.json` 控制工具可用性（預設禁用 `google_web_search`），並在 manifest/README 說明覆寫方式。

3. **Output schema design**
   - 結構化輸出欄位（paper id/title/abstract + evaluation/reasoning + provider/meta）
   - 產出 `run_manifest.json`：run_id、來源、criteria 來源、模型與 CLI 指令、輸出檔案清單
   - 檔案命名：`docs/codex/test/outputs/<run_id>/`，`run_id=YYYYMMDD_HHMMSS`（本機時間）

## Phase 2: Task Planning Approach
**Task Generation Strategy**:
- 依 spec 的 User Stories 拆分任務（US1: codex、US2: gemini、US3: input selection）
- 先完成輸出 schema，再實作 runner
- 以「不新增依賴」為硬性限制

**Ordering Strategy**:
- 先確定資料來源 → 再做 schema → 再做 codex runner → 再做 gemini runner → 最後補文件與輸出範例

## Progress Tracking
- [ ] Phase 0: Research complete
- [ ] Phase 1: Design complete
- [ ] Phase 2: Task planning complete
- [ ] All NEEDS CLARIFICATION resolved
