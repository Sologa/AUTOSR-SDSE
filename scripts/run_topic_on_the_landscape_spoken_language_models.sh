#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='On The Landscape of Spoken Language Models: A Comprehensive Survey'

python scripts/topic_pipeline.py seed --topic "$TOPIC"
python scripts/topic_pipeline.py filter-seed --topic "$TOPIC"
python scripts/topic_pipeline.py keywords --topic "$TOPIC"
python scripts/topic_pipeline.py harvest --topic "$TOPIC"
python scripts/topic_pipeline.py harvest-other --topic "$TOPIC"
python scripts/topic_pipeline.py criteria --topic "$TOPIC" --mode pdf+web

# criteria 之後的步驟先註解，debug 時再打開
# python scripts/topic_pipeline.py review --topic "$TOPIC"
# python scripts/snowball_iterate.py --topic "$TOPIC" --mode loop --max-rounds 2 --force
