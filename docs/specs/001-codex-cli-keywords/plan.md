# Implementation Plan: Codex CLI Keywords Provider Switch

**Branch**: `001-codex-cli-keywords` | **Date**: 2026-01-13 | **Spec**: `docs/specs/001-codex-cli-keywords/spec.md`  
**Input**: Feature specification from `docs/specs/001-codex-cli-keywords/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

新增 keywords 階段的 `codex-cli` provider 支線，透過 PDF→text 與 `codex exec` 產出與既有 `keywords.json` 相容的結果；OpenAI 路徑維持不變，並新增可追溯的 CLI 執行紀錄。同時補齊 codex/gemini CLI review 與 snowball 測試流程，讓完整 pipeline 可用同一主題跑到尾端並控制各階段 reasoning effort。

## Technical Context

**Language/Version**: Python >=3.13（定義於 `sdse-uv/pyproject.toml`）  
**Primary Dependencies**: openai SDK（既有）、requests（既有）、pdfplumber（供 PDF→text）、本機 `codex`/`gemini` CLI、ruff、pytest  
**Storage**: 檔案輸出至 `workspaces/<topic_slug>/`  
**Testing**: `pytest -q`, `ruff check .`, `mypy src/`（若已設定）  
**Target Platform**: 本機 CLI（`scripts/topic_pipeline.py`）  
**Project Type**: single  
**Performance Goals**: 未指定（待確認）  
**Constraints**: 不修改受保護檔案；OpenAI keywords 路徑保持現況；不得自動安裝依賴  
**Scale/Scope**: keywords 階段新增 provider 切換；review/snowball 增加 codex-cli provider 與 reasoning effort 控制；其餘 pipeline 不變

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution 檔案未提供（待確認）。

## Project Structure

### Documentation (this feature)

```text
docs/specs/001-codex-cli-keywords/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── pipelines/
│   └── topic_pipeline.py
└── utils/
    ├── codex_cli.py              # new
    ├── codex_keywords.py         # new
    ├── keyword_extractor.py      # protected
    └── llm.py                    # protected

resources/
└── schemas/
    ├── keywords_response_codex.schema.json  # new
    └── review_response.schema.json          # new

scripts/
├── topic_pipeline.py
├── snowball_iterate.py
└── run_topic_discrete_audio_tokens_full_codex_cli.sh

src/utils/
├── codex_cli.py
├── codex_keywords.py
└── gemini_cli.py
```

**Structure Decision**: Single project，新增 utils 與 schema 檔案，維持既有 pipelines 結構。

## Complexity Tracking

None.
