# Speech Language Model Metadata & Review Pipeline Overview

本文將目前在倉庫中實作的整體流程依 10 個步驟整理成單一管線，並在每一節指向細部文件與腳本，方便你由頭到尾執行或調整。對照流程時，請先於倉庫根目錄啟用 `sdse-uv` 虛擬環境。

## 1. 下載主題綜述（Survey PDFs）
- 任務：取得主題相關的綜述 PDF，供後續 LLM 抽取 anchor/search terms。
- 參考文件：`docs/paper_workflows/end_to_end.md`（步驟一、二）
- 主要工具：`paper_workflows.search_*` + `paper_downloaders.download_*` 或手動挑選。
- 建議保存路徑：`test_artifacts/manual_pipeline/downloads/arxiv/`

## 2. 從 Survey 萃取 Anchor 與 Search Terms
- 任務：使用 LLM 分析已下載的 survey，輸出 `anchor_terms` 與 `search_terms`。
- 參考文件：`docs/paper_workflows/end_to_end.md`（步驟三）、`docs/keyword_extractor/module.md`
- 主要 API：`keyword_extractor.extract_search_terms_from_surveys`
- 產出範例：`test_artifacts/manual_pipeline/keywords.json`

## 3. Anchor × Search Term 組合搜尋主體論文
- 任務：以 Anchor 與 Search Term 的組合（AND / OR）在 arXiv 等來源抓取每組最多 100 筆論文。
- 參考文件：`docs/paper_workflows/end_to_end.md` 之 “Speech LM Metadata 測試模式”、`docs/paper_workflows/module.md`
- 實作範例：整合測試 `test/integration_live/test_speech_lm_metadata_live.py`
- 主要輸出：`test_artifacts/metadata_harvest/speech_language_models/arxiv_metadata.json` 等 JSON。

## 4. 初次去重
- 任務：對多查詢聚合後的紀錄做第一次去重。
- 參考腳本：`test/speech_lm_per_query_asreview.sh`（第 1、2 步）
- 文件說明：`docs/paper_workflows/speech_lm_per_query_asreview.md`
- 產出：`
  - speech_lm_per_query_asreview.csv
  - speech_lm_per_query_asreview_dedup.csv`

## 5. LLM Criteria Consolidation（Web Search + Survey PDF）
- 任務：在 keyword 組合搜尋結果送交 LatteReview 之前，先為 reviewer 準備更完整的 topic 定義與篩選條件。
- 核心流程：
  1. `test/integration_live/test_openai_web_search_structured.py`：經典雙階段（search + formatter）提示，確認 topic 定義與 inclusion/exclusion 欄位。
  2. `test/integration_live/test_openai_web_search_structured_pipeline.py`：以 `CriteriaPipelineConfig` 封裝執行，輸出 `test_artifacts/openai_web_search_structured_pipeline/<topic>/`。
  3. `test/integration_live/test_openai_pdf_augmented_structured_pipeline.py`：先讀取 `test_artifacts/live_downloads/spoken_language_model_assets/arxiv/*.pdf`，擴充背景再與 web search 筆記整合，得到增強版 criteria JSON（`test_artifacts/openai_pdf_augmented_structured_pipeline/<topic>/`）。
- 使用結果：將增強版 JSON 中的 `topic_definition`、`inclusion_criteria` 與 `exclusion_criteria` 匯入 LatteReviewer 設定檔（或手動貼入 prompt），能提高後續初審一致性。
- 注意：三個測試皆為 live OpenAI API 呼叫，執行前務必確認 `.env` 內 `OPENAI_API_KEY` 有效。

## 6.（可選）Peer-Reviewed + 年份篩選
- 任務：以同步審查訊號 + 發表日期範圍雙重條件，過濾主要清單。
- 參考文件：`docs/paper_downloaders/peer_review_checklist_dblp_semanticscholar.md`
- 參考測試：`test/integration_live/test_peer_review_with_year_filter.py`
  - 檔案開頭可設定 `INCLUDE_START_DATE`、`INCLUDE_END_DATE`（空字串代表不設下限/上限）。
  - 進度條透過 stdout 呈現；以 `pytest -s` 執行才能即時看到更新。
  - 輸出：`arxiv_metadata_peer_reviewed.json`
- 注意：篩選依賴 SEMANTIC SCHOLAR、DBLP API；執行前請確認金鑰與速率限制。

## 7. LLM Reviewer：Title + Abstract 初篩（第一輪）
- 任務：以 LLM agent 审核 Title/Abstract，快速挑出潛在目標。
- 建議先以步驟 5 產出的增強版 criteria 填入 reviewer 設定，再執行本步驟。
- 參考文件：`docs/LatteReview/three_reviewer_workflow_test.md`、`docs/LatteReview/paper_review_data.md`
- 測試實例：`test/integration_live/test_latte_review_three_reviewer_workflow.py`
- 輸出 JSON：
  - 全量：`test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_full.json`
  - 指定筆數：`test_artifacts/metadata_harvest/speech_language_models/latte_review_results_step5_top*.json`

## 8. Forward / Backward Snowballing
- 任務：利用 ASReview datatools 對初篩結果進行前向/後向雪球擴充。
- 參考腳本：`test/speech_lm_results_to_asreview.py`（預設同時進行 forward/backward，亦可用 `--skip-forward` / `--skip-backward` 控制）。
- 參考文件：`docs/paper_workflows/speech_lm_asreview_pipeline.md`
- 建議：轉換 LatteReview 結果時以 `python test/speech_lm_results_to_asreview.py --keep-label include` 保留「納入」論文作為雪球輸入，避免排除項目影響後續擴充。
- 產出：`snowball_results.csv`（固定檔名，存放於各 topic 路徑下）。
- 額外產出：`snowball_for_review.csv`（去重後僅保留未在 `screening_included.csv` 出現、且具英文題名/摘要的雪球候選）。
- 備註：OpenAlex 雪球呼叫量大，約需 10~15 分鐘；指令會在限流時自動退避重試。全量 5,898 筆候選經三審審查，OpenAI API 成本約 12 美元。
- 小技巧：`test/speech_lm_results_to_asreview.py` 支援 `--min-date` / `--max-date`，可同時限制轉換與雪球輸出的發表日期範圍。

## 8. 雪球結果合併去重
- 任務：將 forward/backward 雪球結果合併，並轉回與 `arxiv_metadata.json` 相容的 JSON。
- 參考腳本：`test/speech_lm_snowball_merge.sh`
- 文件：`docs/paper_workflows/speech_lm_snowball_merge.md`
- 產出：`speech_lm_arxiv_snowball_merged.json`
- 提醒：若前一步已透過 `speech_lm_results_to_asreview.py` 取得單一的 `snowball_results.csv`，可視需求跳過此步驟或僅用作補強。

## 9. LLM Reviewer：合併後資料再做 Title + Abstract 初篩
- 任務：對合併後的新候選，再執行 LLM reviewer 初篩。
- 目前狀態：尚未實作；可沿用步驟 6 的 LatteReview workflow，輸入改用雪崩合併後结果。
- 建議紀錄：在 `docs/LatteReview/three_reviewer_workflow_test.md` 或新文件中補充設計與結果。

## 10. LLM Reviewer：Full Text 復篩（TODO）
- 任務：對通過初篩的候選下載全文後，請 LLM 执行深入審查。
- 目前狀態：尚未實作；建議之後在此文件補充設計草案以及相關腳本位置。

## 相關文件一覽

| 步驟 | 主題 | 文件 / 測試 / 腳本 |
| --- | --- | --- |
| 1 | 下載綜述 | `docs/paper_workflows/end_to_end.md`, `paper_workflows/module.md` |
| 2 | Anchor/Search Terms | `docs/paper_workflows/end_to_end.md`, `docs/keyword_extractor/module.md` |
| 3 | 主體搜尋 | `docs/paper_workflows/end_to_end.md`, `test/integration_live/test_speech_lm_metadata_live.py` |
| 4 | 初次去重 | `docs/paper_workflows/speech_lm_per_query_asreview.md`, `test/speech_lm_per_query_asreview.sh` |
| 5 | Criteria Consolidation | `test/integration_live/test_openai_web_search_structured.py`, `test/integration_live/test_openai_web_search_structured_pipeline.py`, `test/integration_live/test_openai_pdf_augmented_structured_pipeline.py` |
| 6 | Peer Review Checklist | `docs/paper_downloaders/peer_review_checklist_dblp_semanticscholar.md`, `test/integration_live/test_peer_review_with_year_filter.py` |
| 7 | LLM 初篩 | `docs/LatteReview/three_reviewer_workflow_test.md`, `docs/LatteReview/paper_review_data.md` |
| 8 | 雪球檢索 | `docs/paper_workflows/speech_lm_asreview_pipeline.md`, `test/speech_lm_results_to_asreview.py` |
| 9 | 雪球合併去重 | `docs/paper_workflows/speech_lm_snowball_merge.md`, `test/speech_lm_snowball_merge.sh` |
| 10 | 雪球後再審 | _待補：沿用 LatteReview 文件，另行記錄新流程_ |
| 11 | Full Text 復篩 | _待補：尚未實作，建議後續延伸_ |

## 後續建議
- 若要把步驟 5、9、10 正式整合，建議新增專門腳本與 Live 測試，並將成果補充至此文件與對應模組說明。
- 為減少 API 速率限制的阻塞，可考慮在每個階段加入快取與重試策略，並在日誌 (`logs/YYYY-MM-DD.md`) 中記下執行結果。
- 依需求擴充 `docs/LatteReview/` 或新增 `docs/fulltext_review/`，收錄全文審查的 prompt 設計與工作流實作。
