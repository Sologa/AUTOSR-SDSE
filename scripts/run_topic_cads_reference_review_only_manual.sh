#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='CADS: A Systematic Literature Review on the Challenges of Abstractive Dialogue Summarization'
WORKSPACE_ROOT='workspaces/titlepaper_criteria_review'
WORKSPACE_SLUG='cads_a_systematic_literature_review_on_the_challenges_of_abstractive_dialogue_summarization'
WORKSPACE="$WORKSPACE_ROOT/$WORKSPACE_SLUG"

CUTOFF_JSON="$WORKSPACE/cutoff/cutoff.json"
CRITERIA_JSON="$WORKSPACE/criteria/criteria.json"
HARVEST_DIR="$WORKSPACE/harvest"
SOURCE_JSONL="$HARVEST_DIR/title_abstracts_full_metadata.jsonl"
TARGET_METADATA="$HARVEST_DIR/arxiv_metadata.json"

if [[ ! -f "$CUTOFF_JSON" ]]; then
  echo "[ERR] 找不到 cutoff 檔：$CUTOFF_JSON" >&2
  exit 1
fi

if [[ ! -f "$CRITERIA_JSON" ]]; then
  echo "[ERR] 找不到 criteria 檔：$CRITERIA_JSON" >&2
  exit 1
fi

if [[ ! -f "$SOURCE_JSONL" ]]; then
  echo "[ERR] 找不到來源 metadata JSONL：$SOURCE_JSONL" >&2
  exit 1
fi

# 手動轉檔（不使用 Python / jq）: JSONL -> JSON array
awk 'BEGIN{printf "["} NR>1{printf ","} {print} END{printf "]"}' \
  "$SOURCE_JSONL" > "$TARGET_METADATA"

echo "[INFO] 已完成轉檔：$SOURCE_JSONL -> $TARGET_METADATA"

python scripts/topic_pipeline.py review \
  --topic "$TOPIC" \
  --workspace-root "$WORKSPACE_ROOT" \
  --metadata "$TARGET_METADATA" \
  --criteria "$CRITERIA_JSON"
