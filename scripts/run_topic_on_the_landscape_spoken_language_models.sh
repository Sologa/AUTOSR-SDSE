#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='On The Landscape of Spoken Language Models: A Comprehensive Survey'

python scripts/topic_pipeline.py seed --topic "$TOPIC" \
  --seed-rewrite \
  --seed-rewrite-max-attempts 2 \
  --seed-rewrite-model gpt-5.2
  
python scripts/topic_pipeline.py filter-seed --topic "$TOPIC"
python scripts/topic_pipeline.py keywords --topic "$TOPIC"
python scripts/topic_pipeline.py harvest --topic "$TOPIC"
python scripts/topic_pipeline.py harvest-other --topic "$TOPIC"
python scripts/topic_pipeline.py criteria --topic "$TOPIC" --mode pdf+web

python scripts/topic_pipeline.py review --topic "$TOPIC"
python scripts/snowball_iterate.py \
  --topic "$TOPIC" \
  --mode loop \
  --start-round 1 \
  --max-rounds 1 \
  --retain-registry \
  --force
