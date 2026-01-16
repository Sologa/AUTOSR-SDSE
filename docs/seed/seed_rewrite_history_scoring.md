# Seed Rewrite History 與多候選 Scoring

## 目的
強化 seed rewrite 迭代的可用性：每輪改寫加入歷史摘要，並一次產生多組候選以 metadata dry-run 評分，選出最有機會產生 seed 的查詢再進入下載流程。

## 介面/參數
- 程式入口：`src/pipelines/topic_pipeline.py` → `seed_surveys_from_arxiv()`
- Prompt：`resources/LLM/prompts/seed/seed_query_rewrite.md`
- 相關參數：
  - `--seed-rewrite`
  - `--seed-rewrite-max-attempts`
  - `--seed-rewrite-model`
  - `--seed-rewrite-reasoning-effort`
  - `--seed-rewrite-preview`

## 使用範例
```bash
source sdse-uv/.venv/bin/activate || source sdse-uv/bin/activate
TOPIC='Discrete Audio Tokens: More Than a Survey!'
python scripts/topic_pipeline.py seed --topic "$TOPIC" \
  --seed-rewrite \
  --seed-rewrite-max-attempts 10 \
  --seed-rewrite-model gpt-5.2 \
  --seed-rewrite-reasoning-effort xhigh \
  --no-cache
```

## 測試要點
- `seed_rewrite.json` 應包含多候選輸出、每輪候選的統計與被選中者。
- 每輪在 dry-run 階段不應覆寫 `seed_selection.json` 或 `download_results.json`。
- 最終選中候選應能產生非空的 `seed_pdfs`（若有符合的 arXiv records）。

## 已知限制
- 仍保留原有 cutoff 規則，若唯一命中為 self-match，仍可能被移除。
- 若提示詞或 LLM 產生的候選過於相似，仍有機率導致 recall 不足。
- 現階段僅對 arXiv metadata 進行 scoring，未納入 Semantic Scholar/DBLP 的回饋。
