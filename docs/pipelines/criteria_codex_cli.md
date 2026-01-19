# Criteria (codex-cli, web-only)

## Purpose
Use `codex exec` for the structured criteria web search and formatter stages, without calling the OpenAI API.

## Requirements
- `--mode web` only (PDF background is not supported in codex-cli mode).
- `--codex-allow-web-search` must be set.

## Usage
```bash
python scripts/topic_pipeline.py criteria --topic "<topic>" \
  --mode web \
  --provider codex-cli \
  --search-model gpt-5.2-chat-latest \
  --formatter-model gpt-5.2 \
  --search-reasoning-effort medium \
  --formatter-reasoning-effort medium \
  --codex-home "$CODEX_HOME" \
  --codex-allow-web-search
```

## Flags
- `--provider codex-cli`: enable the codex CLI path.
- `--mode web`: required in codex-cli mode.
- `--search-model`, `--formatter-model`: codex models for stage 1/2.
- `--search-reasoning-effort`, `--formatter-reasoning-effort`: writes `model_reasoning_effort` into `CODEX_HOME/config.toml` per stage.
- `--codex-allow-web-search`: required to enable the web search tool.
- `--codex-home`, `--codex-extra-arg`: codex exec configuration.

## Behavior
- Stage 1 uses `_build_web_search_prompt()`.
- Stage 2 uses `_build_formatter_messages()` and parses JSON with the same schema as the OpenAI path.
- No OpenAI API calls; failures from `codex exec` surface as errors.

## Outputs
- `criteria/criteria.json`
- `criteria/web_search_notes.txt`
- `criteria/formatter_prompt.json`
- `criteria/formatter_raw.txt`
