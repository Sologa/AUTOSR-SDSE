#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='Discrete Audio Tokens: More Than a Survey!'
WORKSPACE_ROOT='workspaces/titlepaper_criteria_review'

python scripts/topic_pipeline.py criteria --topic "$TOPIC" --mode pdf+web --workspace-root "$WORKSPACE_ROOT"
python scripts/topic_pipeline.py review --topic "$TOPIC" --workspace-root "$WORKSPACE_ROOT"
