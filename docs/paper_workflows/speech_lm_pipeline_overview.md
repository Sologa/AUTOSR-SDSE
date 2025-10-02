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

## 5.（可選）Peer-Reviewed 篩選
- 任務：將結果依「是否具同步審核（peer review）」進行過濾。
- 參考文件：`docs/paper_downloaders/peer_review_checklist_dblp_semanticscholar.md`
- 參考測試：`test/integration_live/test_peer_review_filter.py`（會輸出 `arxiv_metadata_peer_reviewed.json`）
- 注意：目前文件僅提供判斷 checklist，尚未有正式腳本整合到主流程。

## 6. LLM Reviewer：Title + Abstract 初篩（第一輪）
- 任務：以 LLM agent 审核 Title/Abstract，快速挑出潛在目標。
- 參考文件：`docs/LatteReview/three_reviewer_workflow_test.md`、`docs/LatteReview/paper_review_data.md`
- 測試實例：`test/integration_live/test_latte_review_three_reviewer_workflow.py`
- 輸出 JSON：`test_artifacts/metadata_harvest/speech_language_models_per_query/latte_review_results_top*.json`

## 7. Forward / Backward Snowballing
- 任務：利用 ASReview datatools 對初篩結果進行前向/後向雪球擴充。
- 參考腳本：`test/speech_lm_per_query_asreview.sh`（步驟 3）、可加 `--skip-backward` 或 `--skip-forward`
- 參考文件：`docs/paper_workflows/speech_lm_per_query_asreview.md`
- 產出：`
  - speech_lm_per_query_asreview_forward.csv
  - speech_lm_per_query_asreview_backward.csv`

## 8. 雪球結果合併去重
- 任務：將 forward/backward 雪球結果合併，並轉回與 `arxiv_metadata.json` 相容的 JSON。
- 參考腳本：`test/speech_lm_snowball_merge.sh`
- 文件：`docs/paper_workflows/speech_lm_snowball_merge.md`
- 產出：`speech_lm_arxiv_snowball_merged.json`

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
| 5 | Peer Review Checklist | `docs/paper_downloaders/peer_review_checklist_dblp_semanticscholar.md`, `test/integration_live/test_peer_review_filter.py` |
| 6 | LLM 初篩 | `docs/LatteReview/three_reviewer_workflow_test.md`, `docs/LatteReview/paper_review_data.md` |
| 7 | 雪球檢索 | `docs/paper_workflows/speech_lm_per_query_asreview.md`, `test/speech_lm_per_query_asreview.sh` |
| 8 | 雪球合併去重 | `docs/paper_workflows/speech_lm_snowball_merge.md`, `test/speech_lm_snowball_merge.sh` |
| 9 | 雪球後再審 | _待補：沿用 LatteReview 文件，另行記錄新流程_ |
| 10 | Full Text 復篩 | _待補：尚未實作，建議後續延伸_ |

## 後續建議
- 若要把步驟 5、9、10 正式整合，建議新增專門腳本與 Live 測試，並將成果補充至此文件與對應模組說明。
- 為減少 API 速率限制的阻塞，可考慮在每個階段加入快取與重試策略，並在日誌 (`logs/YYYY-MM-DD.md`) 中記下執行結果。
- 依需求擴充 `docs/LatteReview/` 或新增 `docs/fulltext_review/`，收錄全文審查的 prompt 設計與工作流實作。

