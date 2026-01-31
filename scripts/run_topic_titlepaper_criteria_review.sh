#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='Discrete Audio Tokens: More Than a Survey!'
WORKSPACE_ROOT='workspaces/titlepaper_criteria_review'
WORKSPACE_SLUG='discrete_audio_tokens_more_than_a_survey'
METADATA_PATH="$WORKSPACE_ROOT/$WORKSPACE_SLUG/harvest/arxiv_metadata.json"

python scripts/topic_pipeline.py criteria --topic "$TOPIC" --mode pdf+web --workspace-root "$WORKSPACE_ROOT"
python scripts/topic_pipeline.py review --topic "$TOPIC" --workspace-root "$WORKSPACE_ROOT" --metadata "$METADATA_PATH"
