# Research: Codex CLI Keywords Provider Switch

**Date**: 2026-01-13  
**Spec**: `docs/specs/001-codex-cli-keywords/spec.md`  
**Scope**: keywords 階段導入 `codex-cli` 支線（不改動 OpenAI 路徑）

## Sources

- `docs/codex/test-keywords/`（CLI 測試流程與輸出）
- `docs/codex/test-review/`（review 模型與 CLI 流程）
- https://developers.openai.com/codex/noninteractive
- https://raw.githubusercontent.com/openai/codex/main/README.md

## Decisions

### Decision 1: 使用 pdfplumber 做 PDF→text

**Rationale**: 現有 `docs/codex/test-keywords` 已使用 pdfplumber，最小化改動風險。  
**Alternatives considered**: CLI 直接讀 PDF（無官方流程）；拒絕。  
**Status**: Approved

### Decision 2: 使用 `--output-schema` 確保結構化輸出

**Rationale**: 需要穩定結構以維持 `keywords.json` 相容性。  
**Alternatives considered**: freeform JSON（不保證 schema）。  
**Status**: Approved

### Decision 3: 固定 Codex CLI 路徑（CODEX_BIN 或絕對路徑）

**Rationale**: `sdse-uv/pyproject.toml` 內含 `codex` Python 套件，可能與 CLI 同名產生混淆。  
**Alternatives considered**: 移除 Python 套件依賴（需變更環境設定）。  
**Status**: Approved (mitigation)

### Decision 4: 測試主題與模型矩陣固定

**Rationale**: 需在 spec/quickstart 中明確標注測試 topic、使用的 script 與每階段模型。  
**Decision**:
- Topic: `Discrete Audio Tokens: More Than a Survey!`
- Keywords: codex-cli `gpt-5.2`
- Criteria: search/formatter/pdf = `gpt-5.2`
- Review/Snowball: JuniorNano `gpt-5.1-codex-mini`, JuniorMini `gemini-2.5-pro`, SeniorLead `gpt-5.2`
- Reasoning effort: `medium`（Gemini CLI 不支援，僅記錄）
**Status**: Approved

## Open Questions (Resolved)

### Q1: Python 版本

**Answer**: Python >=3.13，定義於 `sdse-uv/pyproject.toml`。  
**Status**: Resolved

### Q2: keyword_cli_usage 欄位清單

**Answer**: 以 `data-model.md` 中的 `KeywordRunRecord` 為準，包含 `provider/model/command/input_pdfs/text_paths/output_path/errors/created_at`。  
**Status**: Resolved
