# speech_lm_snowball_merge.sh

## 目的

將 `speech_lm_arxiv_asreview_forward.csv` 與 `speech_lm_arxiv_asreview_backward.csv` 合併去重，輸出為結構與 `arxiv_metadata.json` 相容的 JSON 內容，方便沿用既有的後續處理流程或交叉來源整併。

## 介面 / 參數

- `--forward PATH`：指定 forward 雪球輸入路徑，預設為 `test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_asreview_forward.csv`。
- `--backward PATH`：指定 backward 雪球輸入路徑，預設為 `test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_asreview_backward.csv`。
- `--output PATH`：輸出 JSON 路徑，預設為 `test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_snowball_merged.json`。
- `--anchor LABEL`：輸出 JSON `anchor` 欄位值，預設為 `snowballing`，可依需求覆寫。
- `--search-term TXT`：輸出 JSON `search_term` 欄位值，預設為 `speech-language-models`。
- `-h` / `--help`：顯示說明。

## 使用範例

```bash
source sdse-uv/.venv/bin/activate
./test/speech_lm_snowball_merge.sh \
  --forward test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_asreview_forward.csv \
  --backward test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_asreview_backward.csv \
  --output test_artifacts/metadata_harvest/speech_language_models/speech_lm_arxiv_snowball_merged.json
```

腳本會讀取 CSV、以 `openalex_id → DOI → 標題` 的優先順序建立別名並去重，最後輸出為 `arxiv_metadata.json` 同款結構的 JSON 陣列。`metadata.snowball_sources` 會記錄每筆資料來自 forward、backward 或兩者。

## 測試要點

- 需於 `sdse-uv` 虛擬環境內執行，並確保 `python` 可用。
- 建議先備份或複製輸入 CSV，以免覆寫造成資料流失。
- 對大型資料集（>250k 筆）預期執行時間約 2–3 分鐘，可搭配 `time` 觀察。
- 輸出完成後，可用 `head` 或撰寫簡短 Python 腳本檢查 JSON 結構是否包含 `anchor`、`search_term`、`search_record`、`metadata` 等欄位。

## 已知限制

- 仍需載入完整 JSON 至記憶體後寫出，若要處理遠大於現有規模的資料集，可能需要後續優化。
- `referenced_works` 欄位來源為 CSV 字串；若格式異常（非 list 表示），會以最接近的方式還原，但無法保證完全一致。
- 目前僅針對 forward/backward 雪球輸出設計，若要合併其他來源需先將其轉為同樣欄位集合。
