# Speech LM 暫時性全流程指令

> 所有指令皆預設在倉庫根目錄 (`AUTOSR-SDSE/`) 下執行，並已啟用 `sdse-uv` 虛擬環境：
>
> ```bash
> source sdse-uv/.venv/bin/activate
> export WEB_SEARCH_SURVEY_TOPIC="speech language model"
> export WEB_SEARCH_RECENCY_HINT="過去3年"
> # 依需求設定其他參數，例如：
> # export LATTE_REVIEW_TOP_K=20  # 未設定時預設處理全量
> ```
>
> 請確認 `.env` 內 `OPENAI_API_KEY`、`SEMANTIC_SCHOLAR_API_KEY` 等金鑰有效，所有 live 測試都會呼叫真實服務並產生費用。

## 0. 前置資料確認

1. （選擇性）若需重新下載官方 curations，可跑 downloader 測試以驗證三方來源：
   ```bash
   pytest -q test/integration_live/test_paper_downloaders_live.py
   ```
   - 依賴 `resources/datasets/arxiv_papers/` 內既有清單，結果保存於 `test_artifacts/live_downloads/`。
2. 確認 survey PDF 是否已就緒：
   ```bash
   ls test_artifacts/live_downloads/spoken_language_model_assets/arxiv/*.pdf
   ```
   若不存在，可從手動蒐集或下載測試輸出中擷取。

## 1. Survey → Anchor/Search Terms

1. 以 1–2 份 survey 產生初始關鍵詞：
   ```bash
   pytest -q test/integration_live/test_keyword_extractor_live.py::test_extract_search_terms_single_pdf
   ```
2. 以多份 survey 統整最終 `anchor_terms` 與 `search_terms`：
   ```bash
   pytest -q test/integration_live/test_keyword_extractor_live.py::test_extract_search_terms_multi_pdf
   ```
   - 產出：`test_artifacts/keyword_extractor_live/single_*.json`、`multi_*.json`
   - 後續 `test_speech_lm_metadata_live.py` 預設讀取最新一份 multi JSON，若要換檔請更新 `TERMS_PAYLOAD`。

## 2. 依關鍵詞抓取主體論文

1. 以 Anchor × Search Term 組合查詢 arXiv / Semantic Scholar：
   ```bash
   pytest -q test/integration_live/test_speech_lm_metadata_live.py
   ```
   - 產出：`test_artifacts/metadata_harvest/speech_language_models/*.json`
   - 若只想測一組查詢，可先設定 `export SPEECH_LM_SINGLE_QUERY_MODE=1` 再執行。
2. （選擇性）逐查詢保存結果：
   ```bash
   pytest -q test/integration_live/test_speech_lm_per_query_metadata_live.py
   ```
   - 於 `test_artifacts/metadata_harvest/speech_language_models_per_query/` 下輸出每組查詢的 JSON。

## 3. Consolidated Criteria（LatteReviewer 前置）

LatteReviewer 實際使用的 criteria 來自下列主流程；前兩個測試僅作為 prompt 與輸出格式的參考。

- 參考：快速檢視傳統單階段結果
  ```bash
  pytest -q test/integration_live/test_openai_web_search_structured.py
  ```
- 參考：檢視雙階段管線的 raw notes 與 formatter prompt
  ```bash
  pytest -q test/integration_live/test_openai_web_search_structured_pipeline.py
  ```
- 主流程：讀取 survey PDF，與 web search 筆記整合後產生最終 JSON（LatteReviewer 實際使用）
  ```bash
  pytest -q test/integration_live/test_openai_pdf_augmented_structured_pipeline.py
  ```
  - 產出路徑：`test_artifacts/openai_pdf_augmented_structured_pipeline/<topic_slug>/`
  - 從 `criteria_*.json` 取出 `topic_definition`、`inclusion_criteria`、`exclusion_criteria`，更新 LatteReviewer reviewer 設定。

## 4. Peer-Reviewed 過濾（選擇性）

- 若需限制同行審查論文，可執行：
```bash
pytest -q -s test/integration_live/test_peer_review_with_year_filter.py
```
- 檔案頂端的 `INCLUDE_START_DATE` / `INCLUDE_END_DATE` 可調整日期範圍（空字串代表不設界線）。
- 預設讀取 `test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata.json`
- 產出：`arxiv_metadata_peer_reviewed.json`

## 5. LatteReviewer 初審（Title + Abstract）

1. 確認 reviewer 設定已引用步驟 3 的最新 criteria（可編輯 `resources/LatteReview` 內對應設定或覆蓋測試檔常數）。
2. 執行三審流程：
   ```bash
   pytest -q test/integration_live/test_latte_review_three_reviewer_workflow.py
   ```
   - 預設輸入：`test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata_peer_reviewed.json`
  - 產出：
    - 全量：`test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json`
   - 指定筆數：`test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_top<筆數>.json`
  - 可用 `LATTE_REVIEW_TOP_K` 限制審查筆數，若未設定則預設處理全量資料。

## 6. 轉換結果供 Snowballing 使用

1. 透過轉換腳本一次完成 include 篩選、去重、OpenAlex 補齊與雪球擴充：
   ```bash
   python test/speech_lm_results_to_asreview.py \
     --input test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json \
     --metadata test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata_peer_reviewed.json \
     --keep-label include \
     --min-date 2023-01-01 \
     --max-date 2025-12-31 \
     --output-dir test_artifacts/metadata_harvest/speech_language_models \
     --email you@example.com
  ```
   - 指令會輸出：
     - `screening_included.csv`
     - `snowball_results.csv`（forward/backward 皆啟用）
     - `snowball_for_review.csv`（已排除與初審清單重複、非英文或缺題摘要的雪球候選，供後續 LatteReview 使用）
   - 若想跳過特定方向，可加上 `--skip-forward` 或 `--skip-backward`
   - `--email` 建議填入可用信箱以降低 OpenAlex 限流
   - 若僅想產出 CSV 而略過雪球，可在執行後手動刪除 `snowball_results.csv` 或加上 `--skip-forward --skip-backward`
   - `--min-date` / `--max-date` 支援 YYYY 或 YYYY-MM-DD，會同時套用在 LatteReview 轉換、雪球輸出與 `snowball_for_review.csv`
   - 雪球結果會自動去除缺標題/摘要或非英文內容的紀錄
   - 若使用 `LATTE_REVIEW_TOP_K`，記得將 `--input` 換成對應的 `latte_review_results_step5_top<筆數>.json`

## 7. LatteReviewer 對雪崩結果再審

1. 針對固定 DOI 子集重審：
   ```bash
   pytest -q test/integration_live/test_latte_review_snowball_subset.py
   ```
   - 編輯 `TARGET_DOIS` 指定需人工檢查的候選；包含 `INCLUSION_CRITERIA`、`EXCLUSION_CRITERIA` 可同步更新至步驟 3 的 JSON。
2. 全量雪球結果審查：
 ```bash
  pytest -q -s test/integration_live/test_latte_review_snowball_screening.py
  ```
  - 可設定 `LATTE_REVIEW_TOP_K` 只跑前 K 筆；未設定則預設全量。
  - 建議加上 `-s` 觀察即時進度條與審查提示。

## 8. 後續分析（選擇性）

- `test/integration_live/test_screening_paper_count.py`：統計各階段累積篇數。
- `pytest -q test/integration_live/test_semantic_scholar_full_metadata.py`：補抓進階欄位。
- `pytest -q test/integration_live/test_dblp_full_metadata.py`：補抓 DBLP 詳細資料。
- `pytest -q test/integration_live/test_paper_downloaders_live.py`：實際下載 arXiv / Semantic Scholar / DBLP 的 PDF 與BibTeX，驗證訓練資源是否可取得。
- `python test/tools/download_speechlm_pdfs.py [--max-snowball N]`：下載初審與雪崩審查通過的 PDF，並輸出 `test_artifacts/SpeechLM_pdfs/bib_metadata.json`（整併題名、摘要、BibTeX）。

---

每次調整 reviewer criteria 或雪崩篩選條件，建議同步在 `docs/paper_workflows/speech_lm_pipeline_overview.md`、`logs/YYYY-MM-DD.md` 留下註記，方便未來回溯與比較。EOF
