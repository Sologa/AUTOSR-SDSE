# Topic Debug Script（On The Landscape of Spoken Language Models）

## 目的
提供一個可逐步執行的 pipeline 腳本，針對指定 topic 跑完 seed → filter-seed → keywords → harvest → harvest-other → criteria，並先註解 criteria 之後的步驟，方便除錯與逐段驗證。

## 介面 / 參數
- 腳本路徑：`scripts/run_topic_on_the_landscape_spoken_language_models.sh`
- 內部參數：
  - `TOPIC`：固定為 `On The Landscape of Spoken Language Models: A Comprehensive Survey`
- 可自行調整的 CLI 參數：
  - seed / harvest / criteria 等子指令可加 `--max-results`、`--max-pdfs`、`--force` 等參數
- criteria 模式目前固定 `--mode pdf+web`
- seed 會啟用 `--seed-rewrite`（使用 seed rewrite prompt）

## 使用範例
```bash
source sdse-uv/.venv/bin/activate
bash scripts/run_topic_on_the_landscape_spoken_language_models.sh
```

腳本已包含 review 與單回合 snowball（loop, max-rounds=1, retain-registry）。

## 測試要點
- `workspaces/<topic>/seed/` 是否產出 PDF 與查詢檔
- `workspaces/<topic>/keywords/keywords.json` 是否生成
- `workspaces/<topic>/harvest/arxiv_metadata.json` 是否生成
- `workspaces/<topic>/criteria/criteria.json` 是否生成

## 已知限制
- snowball 已啟用；如需更多回合可調整 `--max-rounds`。
- 需要有效的 `.env` 與 `OPENAI_API_KEY` 才能執行 criteria 與 LLM 相關步驟。
