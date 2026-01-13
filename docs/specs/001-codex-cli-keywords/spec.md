# Feature Specification: Codex CLI Keywords Provider Switch

**Feature Branch**: `001-codex-cli-keywords`  
**Created**: 2026-01-13  
**Status**: Draft

## User Scenarios & Testing

### User Story 1 - Run keywords with codex-cli (Priority: P1)
維護者需要在不改變既有 OpenAI 路徑的前提下，改用 Codex CLI 產出 keywords 結果，供後續 harvest 使用。

**Why this priority**: 驗證 CLI 可行性且不影響既有 pipeline。  
**Independent Test**: 使用同一組 seed PDFs，在 provider=codex-cli 下完成 keywords 輸出。

**Acceptance Scenarios**:
1. **Given** keywords provider 為 codex-cli 且有可用 PDFs，**When** 執行 keywords，**Then** 輸出符合既有 keywords schema（含 `topic`、`anchor_terms`、`search_terms`、`papers[*]`）。
2. **Given** keywords provider 為 codex-cli 且無可用 PDFs，**When** 執行 keywords，**Then** 需明確報錯並停止（不得輸出不完整的 keywords）。
3. **Given** 測試主題固定為 `Discrete Audio Tokens: More Than a Survey!`，**When** 依 `scripts/run_topic_discrete_audio_tokens_full_codex_cli.sh` 逐步執行，**Then** keywords、criteria、review、snowball 皆可產出對應輸出。

### User Story 2 - Preserve default OpenAI path (Priority: P1)
維護者需要保持既有 OpenAI keywords 路徑不變，避免破壞現行流程。

**Why this priority**: 保持既有 pipeline 穩定性。  
**Independent Test**: 未指定 provider 時，行為與現行版本一致。

**Acceptance Scenarios**:
1. **Given** 未指定 provider，**When** 執行 keywords，**Then** 產出與目前版本一致的結果與格式。

### User Story 3 - Traceable CLI runs (Priority: P2)
維護者需要能追溯 codex-cli 的輸入與輸出，以便比對與重現。

**Why this priority**: CLI 行為需要可重現與可稽核。  
**Independent Test**: 同一組輸入可重跑並得到可比對的輸出紀錄。

**Acceptance Scenarios**:
1. **Given** provider 為 codex-cli，**When** 完成 keywords，**Then** 需留下可追溯的執行紀錄（含模型、輸入 PDFs、與執行時間）。

## Test Parameters (fixed)

- **Topic**: `Discrete Audio Tokens: More Than a Survey!`
- **Workspace**: `workspaces/discrete_audio_tokens_more_than_a_survey/`
- **Script**: `scripts/run_topic_discrete_audio_tokens_full_codex_cli.sh`
- **Model Matrix**:
  - Keywords: codex-cli `gpt-5.2`
  - Criteria: search/formatter/pdf = `gpt-5.2`
  - Review: JuniorNano `gpt-5.1-codex-mini`, JuniorMini `gemini-2.5-pro`, SeniorLead `gpt-5.2`
  - Snowball review: 同 Review
- **Reasoning effort**: keywords/criteria/review/snowball 均使用 `medium`（Gemini CLI 不支援，僅記錄）

## Requirements

### Functional Requirements
- **FR-001**: 系統 MUST 支援 keywords provider 選擇（預設 openai，可選 codex-cli）。
- **FR-002**: 使用 codex-cli 時，輸出 MUST 與既有 keywords schema 相容（供後續 harvest 使用）。
- **FR-003**: 使用 codex-cli 時，系統 MUST 支援 PDF→text 的前處理輸入。
- **FR-004**: 使用 codex-cli 時，系統 MUST 對 search terms 做去重與數量上限控制。
- **FR-005**: 若無可用 PDFs，系統 MUST 直接報錯並停止。
- **FR-006**: 未選擇 codex-cli 時，OpenAI 路徑 MUST 完全維持現況。
- **FR-007**: codex-cli 執行 MUST 產生可追溯的執行紀錄。
- **FR-008**: 變更 MUST 不修改受保護檔案。
- **FR-009**: pipeline CLI MUST 提供可設定各階段 reasoning effort 的參數（keywords/criteria/review/snowball）。
- **FR-010**: review/snowball MUST 支援 `codex-cli` provider，並沿用 `docs/codex/test-review` 的模型配置。

### Key Entities
- **ProviderSelection**：keywords provider 的選擇結果（openai 或 codex-cli）。
- **KeywordInput**：PDF 與對應 metadata 的輸入集合。
- **KeywordOutput**：與既有 pipeline 相容的 keywords 結構化輸出。
- **PdfTextArtifact**：PDF 文字化後的可追溯輸入。
- **KeywordRunRecord**：包含模型、輸入與時間的執行紀錄。

## Success Criteria
- **SC-001**: codex-cli 產出的 keywords 能被既有 harvest 消費且無 schema 變更。
- **SC-002**: codex-cli 執行可追溯且可重現。
- **SC-003**: openai 路徑不受影響。
