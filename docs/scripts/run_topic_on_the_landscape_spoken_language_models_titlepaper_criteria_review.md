# run_topic_on_the_landscape_spoken_language_models_titlepaper_criteria_review

## 目的
以「On The Landscape of Spoken Language Models: A Comprehensive Survey」為主題，使用單篇標題論文 PDF 產出 criteria，並以已整理的 title+abstract metadata 進行 review。

## 介面/參數
- 指令：`bash scripts/run_topic_on_the_landscape_spoken_language_models_titlepaper_criteria_review.sh`
- 內部固定參數：
  - `TOPIC`: On The Landscape of Spoken Language Models: A Comprehensive Survey
  - `WORKSPACE_ROOT`: workspaces/titlepaper_criteria_review
  - `WORKSPACE_SLUG`: on_the_landscape_of_spoken_language_models_a_comprehensive_survey
  - `METADATA_PATH`: `workspaces/titlepaper_criteria_review/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/harvest/arxiv_metadata.json`

## 使用範例
```bash
bash scripts/run_topic_on_the_landscape_spoken_language_models_titlepaper_criteria_review.sh
```

## 測試要點
- `seed/downloads/ta_filtered` 中應存在 `2504.08528v1.pdf` 作為 criteria 的 PDF 來源。
- `harvest/arxiv_metadata.json` 為 JSON array，且每筆需包含 `metadata.title` 與 `metadata.summary`。
- criteria 產出路徑：`criteria/criteria.json`。
- review 產出路徑：`review/latte_review_results.json`。

## 已知限制
- review 只依賴 `arxiv_metadata.json` 的 title+abstract，若缺漏會直接略過。
- criteria 的 web search 需要可用的網路與有效金鑰設定。
