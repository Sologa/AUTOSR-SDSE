# Speech LM 多查詢資料轉換、去重與雪球腳本

## 目的
- 將 `test_artifacts/metadata_harvest/speech_language_models_per_query/arxiv_per_query_metadata.json` 轉換為 ASReview 可讀取的 CSV。
- 使用 `asreview data dedup` 對多查詢聚合的資料進行去重管理。
- 透過 `asreview data snowball` 取得前向與後向雪球檢索結果，輔助後續人工審查。

## 介面 / 參數
- 腳本位置：`test/speech_lm_per_query_asreview.sh`
- 主要參數：
  - `--input PATH`：輸入 JSON 路徑（預設為上列檔案）。
  - `--output-dir DIR`：輸出目錄（預設沿用輸入檔所在資料夾）。
  - `--basename NAME`：自訂輸出檔名前綴（預設為 `speech_lm_per_query`）。
  - `--email ADDRESS`：提供給 OpenAlex 的聯絡信箱，建議填入以取得 polite pool。
  - `--threshold VALUE`：去重相似度門檻（預設 `0.98`）。
  - `--skip-forward` / `--skip-backward`：分別略過前向或後向雪球。
- 產出檔案（位於輸出目錄）：
  - `<basename>_asreview.csv`
  - `<basename>_asreview_dedup.csv`
  - `<basename>_asreview_forward.csv`
  - `<basename>_asreview_backward.csv`

## 使用範例
```bash
source sdse-uv/.venv/bin/activate
bash test/speech_lm_per_query_asreview.sh \
  --input test_artifacts/metadata_harvest/speech_language_models_per_query/arxiv_per_query_metadata.json \
  --email your_email@example.com
```

- 若只想執行後向雪球，可追加 `--skip-forward`。
- 如需另存於專案以外的位置，可搭配 `--output-dir ~/workspace/tmp-results`。

## 測試要點
- 腳本執行前需存在輸入 JSON，且資料需包含可解析的 DOI；若缺失會直接中止。
- 更新去重或轉換邏輯時，可比照 `test/unit/test_semantic_scholar_asreview_conversion.py` 撰寫對應的 Python 單元測試，確保欄位與 DOI 唯一性。
- 建議在主要流程前，先以 `--skip-forward --skip-backward` 驗證轉換與去重是否成功，再進行雪球呼叫。

## 已知限制 / 注意事項
- 腳本使用內嵌 Python 腳本轉換 JSON → CSV；若 JSON 結構變更需同步調整轉換邏輯。
- 雪球流程仰賴 OpenAlex API，若未提供 `--email` 可能遭遇較嚴格的速率限制。
- 目前僅針對含 DOI 的紀錄輸出；無 DOI 資料將被忽略，需要另行擴充時請補充處理規則與測試。
- 腳本會先嘗試以 DOI 向 OpenAlex 查詢；若失敗則以標題近似比對找回 `openalex_id`，確保能進行雪球。
- 若最終仍無法取得任何 OpenAlex ID，腳本會略過雪球並輸出僅含欄位表頭的 CSV。
