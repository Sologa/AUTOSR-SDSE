# Speech LM 單一查詢資料轉換與 ASReview 流程

## 目的
- 將 `test_artifacts/metadata_harvest/speech_language_models_single_query/semantic_scholar_single_query_metadata.json` 轉換為 ASReview datatools 可直接使用的 CSV。
- 透過 `asreview data dedup` 與 `asreview data snowball` 對轉換後的資料集進行去重與雪球檢索。

## 介面 / 輸入輸出
- **輸入檔**：`semantic_scholar_single_query_metadata.json`（Semantic Scholar Graph API 回傳物件，含 DOI）。
- **輸出檔**：
  - `semantic_scholar_single_query_asreview.csv`（CSV，欄位 `id,title,abstract,doi,url,pdf_url,year,source_anchor,source_term`）。
  - `semantic_scholar_single_query_asreview_dedup.csv`（去重後資料集）。
  - `semantic_scholar_single_query_asreview_forward.csv` / `semantic_scholar_single_query_asreview_backward.csv`（雪球結果，依指令決定方向）。
- **主要工具**：`pytest` 單元測試、`asreview data dedup`、`asreview data snowball`。

> **新增：LatteReview 整體資料集轉換**
>
> - 若需要將 `test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json`（含 `final_verdict` 與 `metadata`）轉成 ASReview CSV，請使用 `test/speech_lm_results_to_asreview.py`：
>   ```bash
>   source sdse-uv/.venv/bin/activate
>   python test/speech_lm_results_to_asreview.py \
>       --input test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json \
>       --metadata test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata.json \
>       --output-dir test_artifacts/metadata_harvest/speech_language_models \
>       --keep-label include \
>       --min-date 2023-01-01 \
>       --max-date 2025-12-31 \
>       --email your_email@example.com
>   ```
>   若使用 `LATTE_REVIEW_TOP_K` 產生 `latte_review_results_step5_top<X>.json`，請將 `--input` 改為對應檔名；`--min-date` / `--max-date` 為選填，會同時套用在 LatteReview 轉換結果與雪球輸出。
>   指令同時會產出 `snowball_for_review.csv`，內容為去重後僅包含尚未在 `screening_included.csv` 出現的雪球候選，供後續 LatteReview 審查使用。
> - 腳本會輸出固定檔名（僅路徑依 topic 不同）：
>   - `screening_included.csv`：LatteReview 結果轉換後的 ASReview CSV，首欄為 `doi`，同時包含 `included`、`final_verdict`、`metadata_json` 等欄位。
>   - `snowball_results.csv`：整合 forward/backward 的雪球結果（可用 `--skip-forward` / `--skip-backward` 控制方向，若無延伸文獻會輸出僅含標頭的空 CSV）。
>   - `snowball_for_review.csv`：從雪球結果去重，排除已在 `screening_included.csv` 出現、缺題摘要或非英文內容的條目，作為後續 LatteReview 審查的待審清單。
> - 若需只產生 CSV 而不做雪球，可加 `--skip-forward --skip-backward`。
> - `--keep-label` 支援多次指定，可用值為 `include` / `exclude` / `needs-review`；未指定時會保留所有審查結果，上例示範僅將「納入」論文送入雪球階段。
> - 雪球階段會逐筆呼叫 OpenAlex API，實測約 10~15 分鐘；程式已內建 429 重試與退避策略，執行時會顯示等待訊息，請避免中途中斷。
> - 針對 5,898 筆雪球候選執行三審流程，OpenAI API 成本約 12 美元，可作為後續規劃預估基準。

## 操作步驟
所有指令請在倉庫根目錄執行，並先啟用 `sdse-uv` 虛擬環境：

```bash
source sdse-uv/.venv/bin/activate
```

1. **轉換 JSON → CSV**（同時執行資料完整性檢查）
   ```bash
   pytest test/unit/test_semantic_scholar_asreview_conversion.py -q
   ```
   - 測試會讀取 JSON、篩出帶 DOI 的紀錄、生成 CSV 並檢查欄位是否缺值、DOI 是否唯一。

2. **去重**（可調整相似度與語言參數）
   ```bash
   asreview data dedup \
     test_artifacts/metadata_harvest/speech_language_models_single_query/semantic_scholar_single_query_asreview.csv \
     -o test_artifacts/metadata_harvest/speech_language_models_single_query/semantic_scholar_single_query_asreview_dedup.csv \
     --similar --threshold 0.98
   ```
   - `--similar` 啟用標題/摘要的模糊比對；`--threshold`（預設 0.98）代表視為重複的相似度臨界值。
   - 若想僅比對標題，可加上 `--title_only`；需要濾除停用詞時，以 `--stopwords_language english`（或其他語言）搭配使用。

3. **雪球檢索**（依需求選擇前向/後向，可加 `--all` 針對全部紀錄）
   ```bash
   # 前向雪球（尋找引用原始文獻的後續研究）
   asreview data snowball \
     test_artifacts/metadata_harvest/speech_language_models_single_query/semantic_scholar_single_query_asreview_dedup.csv \
     test_artifacts/metadata_harvest/speech_language_models_single_query/semantic_scholar_single_query_asreview_forward.csv \
     --forward --email your_email@example.com

   # 後向雪球（補齊原始文獻參考的前序研究）
   asreview data snowball \
     test_artifacts/metadata_harvest/speech_language_models_single_query/semantic_scholar_single_query_asreview_dedup.csv \
     test_artifacts/metadata_harvest/speech_language_models_single_query/semantic_scholar_single_query_asreview_backward.csv \
     --backward --email your_email@example.com
   ```
   - `--email` 可加入 OpenAlex polite pool，提升 API 配額；請替換為個人或團隊信箱。

## 測試要點
- `pytest test/unit/test_semantic_scholar_asreview_conversion.py -q` 必須通過，確保 CSV 欄位齊全且 DOI 唯一。
- 如調整轉換邏輯，需新增對應測資或 mock，避免去除必要欄位。
- 進行雪球時建議先用 `--dry-run`（若未來版本提供）或少量樣本確認，以避免一次產生過多結果。

## 已知限制 / 注意事項
- CSV 內 `abstract` 來源於 Semantic Scholar `metadata.abstract` 或 `tldr.text`；若兩者皆缺，該筆會被過濾掉，可能導致部分資料遺失。
- 雪球檢索仰賴 OpenAlex 服務，網路中斷或限流時指令會失敗；失敗時可重新執行或調整節流策略。
- 去重流程使用標題與 DOI，若未來需支援無 DOI 的紀錄，應擴充測試確保行為合理。

## 參考
- `resources/asreview-datatools/README.md`
- `test/unit/test_semantic_scholar_asreview_conversion.py`
- `docs/paper_workflows/end_to_end.md`
