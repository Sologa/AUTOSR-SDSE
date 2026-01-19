#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate


TOPIC='Discrete Audio Tokens: More Than a Survey!'
SEED_ANCHOR_MODE="${SEED_ANCHOR_MODE:-core_token_or}"

# Repo-local Codex config (recommended)
CODEX_HOME="${CODEX_HOME:-$PWD/.codex}"
export CODEX_DISABLE_PROJECT_DOC=1
CODEX_EXEC_WORKDIR="${CODEX_EXEC_WORKDIR:-/tmp/codex_exec_clean_outside}"
export CODEX_EXEC_WORKDIR
echo $CODEX_HOME

# Optional explicit CLI path
# export CODEX_BIN=/opt/homebrew/bin/codex

python scripts/topic_pipeline.py seed --topic "$TOPIC" \
  --anchor-mode "$SEED_ANCHOR_MODE" \
  --seed-rewrite \
  --seed-rewrite-max-attempts 1 \
  --seed-rewrite-provider codex-cli \
  --seed-rewrite-model gpt-5.2-codex \
  --seed-rewrite-reasoning-effort xhigh \
  --seed-rewrite-codex-home "$CODEX_HOME" \
  --seed-rewrite-codex-extra-arg=--cd \
  --seed-rewrite-codex-extra-arg="$CODEX_EXEC_WORKDIR" \
  --seed-rewrite-codex-extra-arg=--skip-git-repo-check \
  --no-cache

python scripts/topic_pipeline.py filter-seed --topic "$TOPIC" \
  --provider codex-cli \
  --model gpt-5.2-codex \
  --codex-home "$CODEX_HOME" \
  --codex-extra-arg=--cd \
  --codex-extra-arg="$CODEX_EXEC_WORKDIR" \
  --codex-extra-arg=--skip-git-repo-check

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
#   --mode web \
#   --provider codex-cli \
#   --search-model gpt-5.2 \
#   --formatter-model gpt-5.2 \
#   --pdf-model gpt-5.2 \
#   --search-reasoning-effort medium \
#   --formatter-reasoning-effort medium \
#   --pdf-reasoning-effort medium \
#   --codex-home "$CODEX_HOME" \
#   --codex-allow-web-search \
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
