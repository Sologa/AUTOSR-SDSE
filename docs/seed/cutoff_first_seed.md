# Cutoff-first Seed

## 目的
將 seed 流程改為 cutoff-first one-pass：先找 cutoff paper（找不到同名則不產生 cutoff），再用 LLM 產生 English-only phrases，逐句查詢並在有 cutoff 時做硬過濾。

## 介面 / 參數
- `--seed-mode cutoff-first`
- `--cutoff-arxiv-id`
- `--cutoff-title-override`
- `--cutoff-date-field {published,updated,submitted}`
- `--seed-rewrite-n`
- `--seed-blacklist-mode {clean,fail}`
- `--seed-arxiv-max-results-per-query`
- `--seed-max-merged-results`
- `--seed-rewrite-provider / --seed-rewrite-model / --seed-rewrite-reasoning-effort`
- `--seed-rewrite-codex-*`

## 使用範例
```bash
source sdse-uv/.venv/bin/activate
python scripts/topic_pipeline.py seed \
  --topic "Discrete Audio Tokens: More Than a Survey!" \
  --seed-mode cutoff-first \
  --cutoff-arxiv-id 2506.10274 \
  --seed-rewrite-n 3 \
  --seed-arxiv-max-results-per-query 10
```

## 測試要點
- cutoff exact-title match + tie-break（未命中同名則跳過 cutoff）
- rewrite JSON parsing + blacklist + English-only drop
- query builder OR+AND 格式
- cutoff filter（exclude cutoff + date > cutoff_date；僅在有 cutoff 時）

## 已知限制
- 需要有效的 `OPENAI_API_KEY` 或 Codex CLI 設定。
- phrases 全被清除時會直接 fail（one-pass，不重跑）。
- seed 階段不下載 PDF；需在 filter-seed 後取得 `seed/downloads/ta_filtered/`。
