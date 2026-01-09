# DBLP Title 回查 arXiv（Backfill）

## 目的
- 以 DBLP 搜尋結果的 title 作為查詢，回查 arXiv 取得完整 metadata（含摘要）。
- 嚴格採用「標題正規化後完全一致」的比對規則，降低誤合併風險。
- 產出的最終資料寫回 `workspaces/<topic>/harvest/arxiv_metadata.json`。

## 介面 / 參數
- 入口（掛在 harvest-other）：
  - `python scripts/topic_pipeline.py harvest-other --topic "<topic>" --dblp-title-arxiv`
- 參數：
  - `--dblp-title-arxiv`：啟用 DBLP title 回查。
  - `--dblp-title-arxiv-max-results`：每個 title 的 arXiv 查詢上限（預設 10）。
  - `--request-pause`：每次查詢間隔秒數（預設 0.3）。
  - `--force`：若已存在 `dblp_title_arxiv_matches.json`，仍強制重跑。

## 使用範例
```bash
python scripts/topic_pipeline.py harvest-other \
  --topic "Discrete Audio Tokens: More Than a Survey!" \
  --dblp-title-arxiv \
  --dblp-title-arxiv-max-results 10
```

## 測試要點
- `harvest/dblp_records.json` 存在且為 list。
- `harvest/arxiv_metadata.json` 會被更新（新增或補上 DBLP title 來源的 queries）。
- 嚴格標題一致：只會新增「標題正規化後完全一致」的 arXiv 記錄。
- 產出 `harvest/dblp_title_arxiv_matches.json`，可檢視各筆狀態與查詢結果。

## 已知限制
- DBLP 不提供摘要；此步驟只能透過 title 回查 arXiv。
- 嚴格標題一致會漏掉標題有細微差異的情況。
- 仍受 arXiv API 查詢頻率限制，過量可能被拒絕。
- 若 `dblp_records.json` 缺少 title，該筆會被跳過。
