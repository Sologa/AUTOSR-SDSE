# LatteReview 三人協作測試

## 目的
提供一個最小化的 `ReviewWorkflow` 實例，驗證兩位 junior reviewer（`gpt-5-nano`, `gpt-4.1-mini`）與一位 senior reviewer（`gpt-5`）能夠在同一回合中審查《A Survey of Speech Language Models》相關論文，並以 `TitleAbstractReviewer` 產生含 `evaluation`、`reasoning` 的結構化結果。

## 介面與參數
- 測試檔位置：`test/integration_live/test_latte_review_three_reviewer_workflow.py`
- 輸入資料：`test_artifacts/metadata_harvest/speech_language_models_per_query/arxiv_per_query_metadata.json`
  - 測試會過濾掉標題含有 `survey` 的條目，避免在撰寫 survey 時引用其他 survey；`LATTE_REVIEW_TOP_K` 可限制筆數，未設定時則處理整份資料
- reviewer 建立方式：呼叫 `_build_title_abstract_reviewer(name, model, reasoning, backstory)`，底層使用 `TitleAbstractReviewer` 與 `OpenAIProvider`
- 納入/排除條件：
  - `inclusion_criteria`: 聚焦 speech language model／speech foundation model 的建構、訓練、應用或評估
  - `exclusion_criteria`: 排除僅含傳統 ASR/TTS 或與 speech language models 無關的 NLP 研究
- `ReviewWorkflow` 採兩個 round：Round A 由兩位 junior 先審查，Round B 透過 `filter` 僅在 junior 評分不一致（或同為 3 分）時觸發 senior 復審；初始化方式：`ReviewWorkflow.model_validate`，`context` 必須包含資料表欄位資訊避免 Pydantic 驗證失敗
- 參數化選項：
  - `LATTE_REVIEW_TOP_K`（環境變數，選填）可限制最多處理的條目數；未設定時預設處理全量資料
  - 測試結果會輸出至 `test_artifacts/metadata_harvest/speech_language_models/`
    - 全量：`latte_review_results_step5_full.json`
    - 指定筆數：`latte_review_results_step5_top<X>.json`，其中 `X` 為實際審查的資料筆數
  - 每筆結果會附上 `final_verdict` 欄位，根據 senior 或 junior 的最終評分回傳「納入 / 排除 / 需再評估」及來源說明
  - 原始 `metadata` 欄位會完整保留於輸出，以便追蹤作者、發表年份等詳細資訊

## 使用範例
```bash
source sdse-uv/.venv/bin/activate
# export LATTE_REVIEW_TOP_K=20  # 依需求限制筆數；未設定時預設全量
pytest test/integration_live/test_latte_review_three_reviewer_workflow.py -k speech_language_models
```
測試會直接呼叫 OpenAI `gpt-5-nano`, `gpt-4.1-mini`, `gpt-5` 模型，請先於 `.env` 設定 `OPENAI_API_KEY`。

## 測試要點
- 三位 reviewer 都需回傳 `output`, `evaluation`, `reasoning` 欄位
- `evaluation` 必須介於 1–5，代表 Title/Abstract 評估尺度（1: 完全排除；5: 完全納入）
- 若兩位 junior 評分一致且 ≥4（或差距小於複審條件），Round B `SeniorLead` 欄位會保持 `NaN`；僅在 `filter` 判斷需要時才會填入結果
- Senior reviewer 使用 `cot` reasoning，以便檢查長推理輸出
- `final_verdict` 會優先採用 senior 評分；若未複審則以 junior 評分平均後取整數來推導決策

## 已知限制
- 測試完全仰賴即時 OpenAI API 呼叫，執行時間與成本取決於外部服務
- `ReviewWorkflow` 目前僅在單一 round 中驗證協作；若要引入多 round 依賴，需要額外調整 workflow schema 驗證邏輯
- 測試為了匯入 LatteReview provider 套件，會動態建立 `litellm`、`tokencost`、`ollama`、`google-genai` 的防呆 stub；若實際需要這些 provider，請在環境中安裝正式套件
- `TitleAbstractReviewer` 若在呼叫 OpenAI 時發生例外，現在會輸出完整 traceback 並在達到重試上限後立即終止流程，方便定位 API 或授權問題
