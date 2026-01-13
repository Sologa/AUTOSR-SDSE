---
description: "Task list template for feature implementation"
---

# Tasks: Codex CLI Keywords Provider Switch

**Input**: Design documents from `docs/specs/001-codex-cli-keywords/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Not requested in the feature specification; do not add test tasks unless the spec is updated.  
**Organization**: Tasks are grouped by user story to enable independent implementation and validation of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths below assume single project layout

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and shared assets

- [x] T001 Create `resources/schemas/keywords_response_codex.schema.json` (copy from `docs/codex/test-keywords/keywords_response_codex.schema.json`)
- [x] T002 [P] Add `src/utils/codex_cli.py` wrapper for `codex exec` (stdout/stderr capture, schema support)
- [x] T003 [P] Add `src/utils/codex_keywords.py` module skeleton and public API

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities required before any user story implementation

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Implement PDF→text extraction in `src/utils/codex_keywords.py` using pdfplumber; write to `workspaces/<topic_slug>/keywords/codex_text/`
- [x] T005 Implement prompt assembly (metadata block + extracted text blocks) in `src/utils/codex_keywords.py`
- [x] T006 Implement schema normalization (`search_terms` array → dict) and term sanitation + `max_queries` cap
- [x] T007 Implement CLI run record writer `keyword_cli_usage_<timestamp>.json` (model, command, input PDFs, text paths, errors)

**Checkpoint**: Core codex-cli helpers ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Run keywords with codex-cli (Priority: P1) 🎯 MVP

**Goal**: 在 keywords 階段以 `codex-cli` 產出可用的 `keywords.json`。

**Independent Test**: 使用同一組 seed PDFs，provider=codex-cli 時輸出 schema 與既有 `keywords.json` 相容。

### Implementation for User Story 1

- [x] T008 [US1] Add `provider == "codex-cli"` branch in `src/pipelines/topic_pipeline.py: extract_keywords_from_seed_pdfs()`
- [x] T009 [US1] Write codex-cli output to `workspaces/<topic_slug>/keywords/keywords.json`
- [x] T010 [P] [US1] Update `scripts/topic_pipeline.py` keywords subcommand help:
  - add `--codex-bin` argument for explicit CLI path
  - document `--provider codex-cli` and `--model` usage for CLI
- [x] T011 [US1] Ensure missing PDFs raise a hard error (reuse existing guard in keywords flow)

**Checkpoint**: User Story 1 complete - codex-cli keywords can run end-to-end

---

## Phase 4: User Story 2 - Preserve default OpenAI path (Priority: P1)

**Goal**: OpenAI keywords 路徑保持現況，不影響既有行為。

**Independent Test**: 未指定 provider 時結果與現行一致。

### Implementation for User Story 2

- [x] T012 [US2] Guard codex-cli branch to only run when provider == "codex-cli"
- [x] T013 [US2] Keep OpenAI defaults (model locked to gpt-5.2, temperature 1.0) unchanged

**Checkpoint**: User Story 2 complete - OpenAI path verified unchanged

---

## Phase 5: User Story 3 - Traceable CLI runs (Priority: P2)

**Goal**: codex-cli 執行具備可追溯性。

**Independent Test**: `keyword_cli_usage_<timestamp>.json` 含模型、命令與輸入。

### Implementation for User Story 3

- [x] T014 [US3] Include `codex exec` command, model, schema path in run record
- [x] T015 [US3] Include input PDFs and generated text paths in run record

**Checkpoint**: User Story 3 complete - CLI runs are auditable

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and bookkeeping updates

- [x] T016 [P] Document codex-cli keywords usage in `docs/pipelines/keywords_codex_cli.md`
- [x] T017 Update `docs/codex/codex_cli_implementation_report.md` with final implementation details
- [x] T018 Update `logs/YYYY-MM-DD.md` with implementation summary

## Phase 6: Review/Snowball CLI Integration (補充需求)

- [x] T019 [P] Add `src/utils/gemini_cli.py` for Gemini CLI execution + settings override
- [x] T020 [US1] Add `run_cli_review()` in `src/pipelines/topic_pipeline.py` (codex exec + gemini)
- [x] T021 [US1] Update `scripts/topic_pipeline.py` review subcommand with provider/model/reasoning flags
- [x] T022 [US1] Update `scripts/snowball_iterate.py` review provider flags for snowball rounds
- [x] T023 [P] Add full pipeline script `scripts/run_topic_discrete_audio_tokens_full_codex_cli.sh`
- [x] T024 [P] Update spec/quickstart with test topic, script, and model matrix

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** → **Foundational (Phase 2)** → **User Story 1 (Phase 3)** → **User Story 2 (Phase 4)** → **User Story 3 (Phase 5)** → **Polish**

### User Story Dependencies

- **US1** depends on Phase 1–2 completion
- **US2** depends on US1 branch wiring
- **US3** depends on codex-cli run record support from Phase 2

---

## Parallel Example: User Story 1

```bash
Task: "T008 [US1] Add provider branch in src/pipelines/topic_pipeline.py"
Task: "T010 [US1] Update scripts/topic_pipeline.py help text"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Verify `keywords.json` schema compatibility

### Incremental Delivery

1. Add User Story 2 → validate OpenAI path unchanged
2. Add User Story 3 → validate run record completeness
3. Finish Polish updates

---

## Notes

- [P] tasks = different files, no dependencies
- Each user story should be independently completable and testable
- Avoid changing protected files
