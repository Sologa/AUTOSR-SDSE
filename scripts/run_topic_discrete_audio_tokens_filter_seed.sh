#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='Discrete Audio Tokens: More Than a Survey!'

python scripts/topic_pipeline.py filter-seed --topic "$TOPIC" --force
