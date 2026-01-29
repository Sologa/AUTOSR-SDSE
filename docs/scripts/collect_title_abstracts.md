# collect_title_abstracts

## 目的
將 `reference_oracle.jsonl` 內的論文補齊 `title` + `abstract`，輸出成單一 JSONL 檔案。來源預設使用 arXiv，必要時可啟用 Semantic Scholar 作為補齊來源。可重跑以續跑未完成項目。

## 介面/參數
- 指令：`python scripts/collect_title_abstracts.py`
- 主要參數：
  - `--input`: 來源 `reference_oracle.jsonl` 路徑
  - `--output`: 輸出 JSONL 路徑
  - `--allow-fuzzy`: 允許 arXiv 模糊比對（預設關閉）
  - `--min-similarity`: 模糊比對最低 Jaccard 相似度門檻
  - `--arxiv-max-results`: 每個 title 在 arXiv 搜尋時的候選上限
  - `--use-semantic-scholar`: 啟用 Semantic Scholar 補齊缺漏項目
  - `--semantic-scholar-api-key`: Semantic Scholar API key（或使用 `SEMANTIC_SCHOLAR_API_KEY`）
  - `--semantic-max-results`: Semantic Scholar 搜尋候選上限
  - `--checkpoint-every`: 每處理 N 筆就重寫輸出（預設 1，便於中途中斷續跑）
  - `--sleep`: 兩次外部請求間的休眠秒數
  - `--limit`: 只處理前 N 筆（除錯用）

## 使用範例
```bash
python scripts/collect_title_abstracts.py \
  --input target_papers/discrete_audio_tokens_more_than_a_survey/reference_oracle.jsonl \
  --output workspaces/discrete_audio_tokens_more_than_a_survey/title_abstracts.jsonl

# 補齊 arXiv 找不到的項目（Semantic Scholar）
python scripts/collect_title_abstracts.py \
  --input target_papers/discrete_audio_tokens_more_than_a_survey/reference_oracle.jsonl \
  --output workspaces/discrete_audio_tokens_more_than_a_survey/title_abstracts.jsonl \
  --use-semantic-scholar
```

## 測試要點
- 有 arXiv ID 的項目會走 arXiv API，`title`/`abstract` 能成功回填。
- 無 arXiv ID 的項目會以 title 走 arXiv 搜尋；`--allow-fuzzy` 未開啟時只接受精確標題比對。
- 啟用 `--use-semantic-scholar` 時，會以 Semantic Scholar 進一步補齊缺漏項目。
- 輸出 JSONL 筆數與輸入筆數一致。

## 已知限制
- arXiv 搜尋結果可能不含對應條目，該筆會留下 `abstract: null` 並標記 `missing_reason`。
- 模糊比對可能引入錯配，預設關閉。
- Semantic Scholar 回傳可能沒有 abstract 或年份，該筆仍會被標記為缺漏或在 review 時被 cutoff 規則淘汰。
