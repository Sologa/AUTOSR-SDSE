#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='Discrete Audio Tokens: More Than a Survey!'

# Repo-local Codex config (recommended)
export CODEX_HOME="${CODEX_HOME:-$PWD/.codex}"

# Optional explicit CLI path
# export CODEX_BIN=/opt/homebrew/bin/codex

python scripts/topic_pipeline.py seed --topic "$TOPIC" \
  --seed-rewrite \
  --seed-rewrite-max-attempts 10 \
  --seed-rewrite-model gpt-5.2 \
  --seed-rewrite-reasoning-effort xhigh \
  --no-cache

# python scripts/topic_pipeline.py filter-seed --topic "$TOPIC"

# python scripts/topic_pipeline.py keywords \
#   --topic "$TOPIC" \
#   --provider codex-cli \
#   --model gpt-5.2 \
#   --reasoning-effort medium \
#   --codex-home "$CODEX_HOME" \
#   --force

# python scripts/topic_pipeline.py harvest --topic "$TOPIC" --force

# python scripts/topic_pipeline.py criteria \
#   --topic "$TOPIC" \
#   --mode pdf+web \
#   --search-model gpt-5.2 \
#   --formatter-model gpt-5.2 \
#   --pdf-model gpt-5.2 \
#   --search-reasoning-effort medium \
#   --formatter-reasoning-effort medium \
#   --pdf-reasoning-effort medium \
#   --force

# python scripts/topic_pipeline.py review \
#   --topic "$TOPIC" \
#   --provider codex-cli \
#   --junior-nano-model gpt-5.1-codex-mini \
#   --junior-mini-model gemini-2.5-pro \
#   --senior-model gpt-5.2 \
#   --junior-nano-reasoning-effort medium \
#   --junior-mini-reasoning-effort medium \
#   --senior-reasoning-effort medium \
#   --codex-home "$CODEX_HOME"

# python scripts/snowball_iterate.py \
#   --topic "$TOPIC" \
#   --mode loop \
#   --start-round 1 \
#   --max-rounds 1 \
#   --review-provider codex-cli \
#   --junior-nano-model gpt-5.1-codex-mini \
#   --junior-mini-model gemini-2.5-pro \
#   --senior-model gpt-5.2 \
#   --junior-nano-reasoning-effort medium \
#   --junior-mini-reasoning-effort medium \
#   --senior-reasoning-effort medium \
#   --codex-home "$CODEX_HOME" \
#   --force
