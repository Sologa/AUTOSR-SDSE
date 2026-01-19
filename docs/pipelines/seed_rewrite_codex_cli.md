# Seed Rewrite (codex-cli)

## Purpose
Use `codex exec` instead of the OpenAI API for seed query rewriting, while keeping the original prompt and parser intact.

## Interface / Parameters
- `--seed-rewrite-provider codex-cli`: enable the codex CLI path.
- `--seed-rewrite-model`: codex model name.
- `--seed-rewrite-reasoning-effort`: writes `model_reasoning_effort` into `CODEX_HOME/config.toml`.
- `--seed-rewrite-codex-home`: set `CODEX_HOME` (recommended: repo-local `.codex`).
- `--seed-rewrite-codex-extra-arg`: extra flags for `codex exec` (repeatable).
- `CODEX_DISABLE_PROJECT_DOC=1`: disable loading project `AGENTS.md`/`AGENTS.override.md` for codex CLI runs.
- `CODEX_EXEC_WORKDIR`: working directory for `codex exec` (default: `test/.tmp/codex_exec_clean`).
- `--seed-rewrite-codex-extra-arg "--cd"` + `--seed-rewrite-codex-extra-arg "<dir>"`: set Codex working root explicitly.
- `--seed-rewrite-codex-extra-arg "--skip-git-repo-check"`: allow `--cd` to a non-repo path.

## Usage
```bash
python scripts/topic_pipeline.py seed --topic "<topic>" \
  --seed-rewrite \
  --seed-rewrite-provider codex-cli \
  --seed-rewrite-model gpt-5.2 \
  --seed-rewrite-reasoning-effort medium \
  --seed-rewrite-codex-home "$CODEX_HOME" \
  --seed-rewrite-codex-extra-arg "--sandbox" \
  --seed-rewrite-codex-extra-arg "read-only"
```

## Behavior
- Prompt is still built from `resources/LLM/prompts/seed/seed_query_rewrite.md`.
- Output is still parsed by `_parse_seed_rewrite_candidates()`; JSON structure stays the same.
- No OpenAI API calls; failures from `codex exec` surface as errors.
- `codex exec` runs from `CODEX_EXEC_WORKDIR` (or `test/.tmp/codex_exec_clean`) to avoid project doc leakage.
- If `CODEX_EXEC_WORKDIR` is inside the repo, Codex still treats the repo as the project root.

## Skills
- Optional: place `scientific-brainstorming` under `./.codex/skills/` to make it available to Codex.
- If used, the seed rewrite prompt must still enforce strict output formatting.
- `resources/LLM/prompts/seed/seed_query_rewrite.md` includes a note to use scientific-brainstorming internally.

## Outputs
- `seed/queries/seed_rewrite.json`
- `seed/downloads/download_results.json` (includes `rewrite_attempts` / `rewrite_query`)

## Testing points
- `seed_rewrite.json` should record `preview_only` and `selected_queries` as expected.
- `seed_selection.json` should reflect the rewritten query, not the original title variants.

## Known limitations
- Only applies to the codex-cli path; the OpenAI provider path is unchanged.
- To fully avoid project `AGENTS.md`, use `--cd` with a directory outside the repo plus `--skip-git-repo-check`.
