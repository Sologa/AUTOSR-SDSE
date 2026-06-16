#!/usr/bin/env bash
set -euo pipefail

source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate

TOPIC='CADS: A Systematic Literature Review on the Challenges of Abstractive Dialogue Summarization'
WORKSPACE_ROOT='workspaces/titlepaper_criteria_review'
WORKSPACE_SLUG='cads_a_systematic_literature_review_on_the_challenges_of_abstractive_dialogue_summarization'
WORKSPACE="$WORKSPACE_ROOT/$WORKSPACE_SLUG"

CUTOFF_JSON="$WORKSPACE/cutoff/cutoff.json"
CRITERIA_JSON="$WORKSPACE/criteria/criteria.json"
METADATA_JSON="$WORKSPACE/harvest/arxiv_metadata.json"

if [[ ! -f "$CUTOFF_JSON" ]]; then
  echo "[ERR] 找不到 cutoff 檔：$CUTOFF_JSON" >&2
  exit 1
fi

if [[ ! -f "$CRITERIA_JSON" ]]; then
  echo "[ERR] 找不到 criteria 檔：$CRITERIA_JSON" >&2
  exit 1
fi

if [[ ! -f "$METADATA_JSON" ]]; then
  echo "[ERR] 找不到 review 輸入 metadata：$METADATA_JSON" >&2
  echo "      目前這個 workspace 沒有 review stage 直接可用的 arxiv_metadata.json。
      review 需要的是 list JSON，不是 JSONL。
      已有 JSONL 在 $WORKSPACE/harvest/ 下（需先轉為對應格式）。" >&2
  exit 1
fi

python scripts/topic_pipeline.py review \
  --topic "$TOPIC" \
  --workspace-root "$WORKSPACE_ROOT" \
  --metadata "$METADATA_JSON" \
  --criteria "$CRITERIA_JSON"
