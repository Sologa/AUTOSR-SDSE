# Filter-Seed (codex-cli)

## Purpose
Run the title/abstract screening step using `codex exec` instead of the OpenAI API.

## Usage
```bash
python scripts/topic_pipeline.py filter-seed --topic "<topic>" \
  --provider codex-cli \
  --model gpt-5-mini \
  --reasoning-effort low \
  --codex-home "$CODEX_HOME"
```

## Flags
- `--provider codex-cli`: enable the codex CLI path.
- `--model`: codex model name.
- `--reasoning-effort`: writes `model_reasoning_effort` into `CODEX_HOME/config.toml`.
- `--codex-home`: set `CODEX_HOME` (recommended: repo-local `.codex`).
- `--codex-extra-arg`: extra flags for `codex exec` (repeatable).

## Behavior
- Prompt stays at `resources/LLM/prompts/filter_seed/llm_screening.md` (strict JSON required).
- Output is parsed by `_parse_decision_payload()`; schema is unchanged.
- No OpenAI API calls; failures from `codex exec` surface as errors.
- Screening uses title/abstract only, then downloads selected PDFs into `seed/downloads/arxiv/`.

## Outputs
- `seed/filters/llm_screening.json`
- `seed/filters/selected_ids.json`
- `seed/downloads/arxiv/*.pdf`
