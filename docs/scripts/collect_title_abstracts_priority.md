# collect_title_abstracts_priority

## 目的
依照 `docs/paper_downloaders/unique_download_methods.md` 的來源優先序，從 `reference_oracle.jsonl` 以 title 搜尋補齊 `title` + `abstract`，並輸出三個 JSONL 檔案（metadata / sources / trace）。

## 介面/參數
- 指令：`python scripts/collect_title_abstracts_priority.py`
- 主要參數：
  - `--input`: 來源 `reference_oracle.jsonl` 路徑
  - `--output-dir`: 輸出資料夾（產出三個 JSONL）
  - `--allow-fuzzy`: 是否允許模糊比對（預設 true）
  - `--min-similarity`: 模糊比對最低 Jaccard 相似度
  - `--resume`: 續跑模式（預設 true）
  - `--checkpoint-every`: 每處理 N 筆就重寫輸出（預設 1）
  - `--limit`: 只處理前 N 筆（除錯用）

## 來源優先序
1. arXiv
2. Semantic Scholar
3. DBLP
4. OpenAlex
5. Crossref
6. ACL Anthology
7. LREC proceedings
8. RFC Editor
9. BSI
10. GitHub
11. HuggingFace
12. Keithito
13. Zenodo

## 輸出
- `title_abstracts_metadata.jsonl`
- `title_abstracts_sources.jsonl`
- `title_abstracts_source_trace.jsonl`

輸出格式與既有 `workspaces/.../review/title_abstracts_*.jsonl` 一致。

## 使用範例
```bash
python scripts/collect_title_abstracts_priority.py \
  --input target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/reference_oracle.jsonl \
  --output-dir target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/title_abstract
```

## 測試要點
- 先用 `--limit 5` 確認輸出格式與 trace 正常。
- 確認 `title_abstracts_metadata.jsonl` 中沒有 `abstract: null`。
- 確認 `title_abstracts_source_trace.jsonl` 的查詢步驟順序符合優先序。

## 已知限制
- 部分來源僅提供 title 或 description，若無 abstract 會繼續往下查。
- LREC 來源依 OpenAlex landing page 觸發，若該欄位缺失可能無法命中。
- GitHub / HuggingFace / BSI 等屬替代來源，內容多為 description 而非正式論文摘要。
- 標題 token 數少於 7 時只接受精確匹配，避免短標題模糊誤配。
- 會先移除 TeX 命令與結尾年份再組成查詢字串，降低查詢失真。
