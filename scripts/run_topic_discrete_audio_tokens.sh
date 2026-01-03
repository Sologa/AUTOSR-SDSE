#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='Discrete Audio Tokens: More Than a Survey!'

python scripts/topic_pipeline.py seed --topic "$TOPIC" \
  --anchor "discrete speech tokens" \
  --anchor "discrete audio tokens" \
  --anchor-mode token_and \
  --scope ti \
  --max-results 200 \
  --download-top-k 8 \
  --seed-rewrite \
  --seed-rewrite-max-attempts 2 \
  --seed-rewrite-model gpt-5.2 \
  --no-cache
python scripts/topic_pipeline.py filter-seed --topic "$TOPIC"
python scripts/topic_pipeline.py keywords --topic "$TOPIC" --force
python scripts/topic_pipeline.py harvest --topic "$TOPIC" --max-terms-per-category 100 --top-k-per-query 25 --force
python scripts/topic_pipeline.py criteria --topic "$TOPIC" --mode web --force

python scripts/topic_pipeline.py review --topic "$TOPIC"
python scripts/snowball_iterate.py \
  --topic "$TOPIC" \
  --mode loop \
  --start-round 1 \
  --max-rounds 4 \
  --retain-registry \
  --force
