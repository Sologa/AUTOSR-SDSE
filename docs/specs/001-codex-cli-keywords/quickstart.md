# Quickstart: Codex CLI Keywords Provider Switch

**Date**: 2026-01-13  
**Spec**: `docs/specs/001-codex-cli-keywords/spec.md`

## Prerequisites

- 已建立 seed PDFs（位於 `workspaces/<topic_slug>/seed/downloads/arxiv/`）
- `codex` CLI 可用（僅 codex-cli 路徑需要，建議設定 `CODEX_BIN`）
- `gemini` CLI 可用（review/snowball）
- `pdfplumber` 已可用於 PDF→text
- 已載入 `.env`

## Test Topic & Workspace

- **Topic**: `Discrete Audio Tokens: More Than a Survey!`
- **Workspace**: `workspaces/discrete_audio_tokens_more_than_a_survey/`
- **Reference (existing paper workspace)**: `workspaces/discrete_audio_tokens_more_than_a_survey-api/`（僅作為比對參考）

## Model Matrix (per stage)

- **Keywords**: codex-cli `gpt-5.2`（reasoning effort=medium）
- **Criteria**:
  - search: `gpt-5.2`（reasoning effort=medium）
  - formatter: `gpt-5.2`（reasoning effort=medium）
  - pdf: `gpt-5.2`（reasoning effort=medium）
- **Review**: JuniorNano `gpt-5.1-codex-mini` / JuniorMini `gemini-2.5-pro` / SeniorLead `gpt-5.2`
  - reasoning effort=medium（Gemini CLI 不支援，僅記錄）
- **Snowball review**: 同 Review

## Codex CLI 安裝

OpenAI Codex CLI 為獨立命令列工具，可透過以下方式安裝：

```bash
npm install -g @openai/codex
brew install --cask codex
```

## Codex CLI 路徑設定

由於 `sdse-uv` 內含同名 Python 套件，請明確指定 CLI 路徑：

```bash
export CODEX_BIN=/opt/homebrew/bin/codex
```

CLI 路徑解析順序（預期與 `docs/codex/test-shared/codex_cli_utils.py` 一致）：
1. 明確傳入的 `codex_bin` 參數（若實作 `--codex-bin`）
2. `CODEX_BIN` 環境變數
3. `/opt/homebrew/bin/codex`
4. 系統 PATH 中的 `codex`（可能是 Python 套件）

## Repo-local CODEX_HOME（建議）

```bash
export CODEX_HOME=$PWD/.codex
```

## OpenAI keywords（現有路徑）

```bash
python scripts/topic_pipeline.py keywords --topic "<topic>"
```

## Codex CLI keywords（新增支線）

```bash
python scripts/topic_pipeline.py keywords \
  --topic "<topic>" \
  --provider codex-cli \
  --model gpt-5.2 \
  --reasoning-effort medium \
  --codex-home "$CODEX_HOME"
```

## Outputs

- `workspaces/<topic_slug>/keywords/keywords.json`
- `workspaces/<topic_slug>/keywords/keyword_extractor_usage_<timestamp>.json`（openai 路徑）
- `workspaces/<topic_slug>/keywords/keyword_cli_usage_<timestamp>.json`（codex-cli 路徑）

## Full Pipeline Script

使用 `scripts/run_topic_discrete_audio_tokens_full_codex_cli.sh` 作為完整 pipeline 指令集（seed → keywords → harvest → criteria → review → snowball）。  
請先檢視腳本內容，再依需求逐行執行。
