# Topic CLI Pipeline（以主題驅動的端到端串接）

本文件描述本 repo 目前「可落地」的端到端 pipeline，目標是：**只要給一個 `topic`，就能用 CLI 一鍵串接**從 seed surveys → 關鍵詞抽取 → metadata harvest →（可選）criteria →（可選）LatteReview 初篩 →（可選）ASReview + snowballing。

> 重要：此 pipeline 只做「串接與落盤」，底層功能全部重用既有模組（`src/utils/*`），不修改受保護檔案（見 `docs/agent-protected-files.md`）。

---

## 1. 你要解決的痛點（問題定義）

目前 repo 的能力主要散落在：
- `src/utils/paper_workflows.py`：搜尋（arXiv / Semantic Scholar / DBLP）與下載整合
- `src/utils/keyword_extractor.py`：讀 PDF → 抽 `anchor_terms` / `search_terms`
- `src/utils/structured_web_search_pipeline.py`：OpenAI web search → 產生 structured criteria JSON
- `resources/LatteReview/`：Title/Abstract reviewer workflow（live OpenAI）
- `test/speech_lm_results_to_asreview.py`：LatteReview 結果 → ASReview CSV + snowballing

但若沒有「單一入口」把以上串起來，你就會卡在：
- 能跑單一測試主題（例如 Speech LM）並產生 `test_artifacts/`，但**無法用參數化方式改主題重跑**。
- 產物散在 `test_artifacts/`，**缺少固定的 workspace layout**，很難用下游流程接續做事。

---

## 2. 新增的串接入口（CLI）

本 repo 已新增一個 CLI：
- `scripts/topic_pipeline.py`

它會把所有產物寫入 workspace（預設 `workspaces/<topic_slug>/`），避免再把「正式工作資料」塞進 `test_artifacts/`。

> 注意：`--topic` 可放在 subcommand 前或後（例如 `seed --topic ...` 或 `--topic ... seed` 都可）。

### 2.1 Workspace 目錄結構（固定）

以 `--topic "speech language model"` 為例，`topic_slug` 會被正規化（英數/中文保留，其餘轉 `_`）：

```
workspaces/speech_language_model/
  config.json
  seed/
    queries/arxiv.json
    downloads/
      download_results.json
      arxiv/*.pdf
  keywords/
    keywords.json
    keyword_extractor_usage_<timestamp>.json
  harvest/
    arxiv_metadata.json
    semantic_scholar_records.json        # 可選
    dblp_records.json                    # 可選
  criteria/
    criteria.json                        # 可選（內含 structured_payload）
    web_search_notes.txt
    pdf_background.txt                   # pdf+web 才會有
    combined_notes.txt                   # pdf+web 才會有
    formatter_prompt.json                # pdf+web 才會有
    formatter_raw.txt                    # pdf+web 才會有
  review/
    latte_review_results.json            # 可選
  asreview/
    screening_included.csv               # snowball 產物
    snowball_results.csv
    snowball_for_review.csv
```

> `.gitignore` 已新增 `workspaces/`，避免 PDF 與大量 artefacts 被誤提交。

---

## 3. Pipeline 分段與對應模組

### Stage A：Seed Surveys（arXiv）

目的：先找到「綜述/回顧」類 PDF，給 keyword extractor 當輸入。

- API：`paper_workflows.search_arxiv_for_topic` → `paper_workflows.download_records_to_pdfs`
- CLI：
  - `python scripts/topic_pipeline.py seed --topic "<topic>"`
  - 若要對齊「title token AND」的查詢邏輯，可用：
    - `python scripts/topic_pipeline.py seed --topic "<topic>" --scope ti --anchor-mode token_and`
  - 若要完全自行控制 arXiv 的 `search_query`（將忽略 anchors/survey_terms 等參數）：
    - `python scripts/topic_pipeline.py seed --topic "<topic>" --arxiv-raw-query 'ti:("discrete" AND "audio" AND "token") AND (survey OR review)'`
- 重要行為（用於「避免把最新同名 survey 自己拿來當 seed」）：
  - seed 階段會對搜尋到的 survey 標題計算與 `topic` 的相似度；
  - 若找到「標題高度相似」的 survey（預設門檻 `0.8`），會**排除該篇**並只保留**發表時間更早**的 surveys 來下載/抽關鍵字。
  - 你可以用 `--no-cutoff-by-similar-title` 關閉此行為，或用 `--similarity-threshold <0~1>` 調整門檻。
- 產物：
  - `seed/queries/arxiv.json`
  - `seed/queries/seed_selection.json`（肉眼檢視用：cutoff candidate、cutoff date、以及實際被挑去下載的清單）
  - `seed/downloads/arxiv/*.pdf`
  - 若切換搜尋條件，請加 `--no-cache` 以強制重新查詢。

### Stage A.5（新增）：Filter-Seed（LLM 審核）

目的：在進入 keyword extraction 前，讓 LLM 根據 **title + abstract** 判斷是否保留該 seed paper。  
（採用方案 A：**整理 `seed/downloads/arxiv/`，不改 keywords 介面**）

- CLI：
  - `python scripts/topic_pipeline.py filter-seed --topic "<topic>"`
- 產物：
  - `seed/filters/llm_screening.json`
  - `seed/filters/selected_ids.json`
  - `seed/downloads/arxiv_raw/*.pdf`（原始下載）
  - `seed/downloads/arxiv/*.pdf`（僅保留 LLM 判定 yes）

### Stage B：Keyword Extraction（從 surveys 抽取 anchor/search terms）

目的：讀取 seed PDFs，輸出：
- `anchor_terms`：主題的穩定錨點（例如同義詞/縮寫）
- `search_terms`：依分類整理的 query term（之後做 harvest）

- API：`keyword_extractor.extract_search_terms_from_surveys`
- CLI：
  - `python scripts/topic_pipeline.py keywords --topic "<topic>"`
- 產物：
  - `keywords/keywords.json`
  - `keywords/keyword_extractor_usage_<timestamp>.json`

### Stage C：Metadata Harvest（arXiv）

目的：用 `anchor_terms × search_terms` 做大規模查詢，拉回可用於後續篩選的 metadata（並驗證 PDF 可存取）。

- API：`paper_workflows.search_arxiv_for_topic` → `paper_downloaders.fetch_arxiv_metadata` → `HEAD pdf_url`
- CLI：
  - `python scripts/topic_pipeline.py harvest --topic "<topic>" --start-date 2022-01-01 --end-date 2025-12-31`
- 產物：
  - `harvest/arxiv_metadata.json`

### Stage D（可選）：Other Sources Harvest（Semantic Scholar / DBLP）

目的：同樣用 keyword 組合抓其他來源的 records，供後續人工比對或補件。

- API：`paper_workflows.search_semantic_scholar_for_topic`、`paper_workflows.search_dblp_for_topic`
- CLI：
  - `python scripts/topic_pipeline.py harvest-other --topic "<topic>"`
- 產物：
  - `harvest/semantic_scholar_records.json`
  - `harvest/dblp_records.json`

### Stage E（可選）：Criteria Consolidation（Web / PDF+Web）

目的：為後續 reviewer 準備一致的主題定義與納入/排除規則（structured JSON）。

- API：`structured_web_search_pipeline.run_structured_criteria_pipeline`
- CLI：
  - `python scripts/topic_pipeline.py criteria --topic "<topic>" --mode web --recency-hint "過去3年"`
  - `python scripts/topic_pipeline.py criteria --topic "<topic>" --mode pdf+web --max-pdfs 5`
- 產物：
  - `criteria/criteria.json`（內含 `structured_payload`）

### Stage F（可選）：LatteReview Title/Abstract 初篩

目的：用 LatteReview 三人 workflow 產出每篇 paper 的 `evaluation` 與 `final_verdict`。

- API：`resources.LatteReview.lattereview.workflows.ReviewWorkflow`
- CLI：
  - `python scripts/topic_pipeline.py review --topic "<topic>"`
- 輸入：
  - `harvest/arxiv_metadata.json`
  - `criteria/criteria.json`（若存在，會自動轉成 reviewer 的 inclusion/exclusion 字串）
- 產物：
  - `review/latte_review_results.json`

### Stage G（可選）：ASReview + Snowballing

目的：把 LatteReview 結果轉成 ASReview CSV，並進行 forward/backward snowball。

- 工具：`test/speech_lm_results_to_asreview.py`
- CLI：
  - `python scripts/topic_pipeline.py snowball --topic "<topic>" --email "<you@example.com>"`
- 產物：
  - `asreview/screening_included.csv`
  - `asreview/snowball_results.csv`
  - `asreview/snowball_for_review.csv`

---

## 4. 一鍵跑完整串接（建議先從這裡開始）

```bash
source sdse-uv/.venv/bin/activate
python scripts/topic_pipeline.py run --topic "speech language model" \
  --seed-max-results 25 \
  --seed-download-top-k 5 \
  --max-pdfs 3 \
  --max-terms-per-category 3 \
  --top-k-per-query 100 \
  --start-date 2022-01-01 \
  --end-date 2025-12-31 \
  --with-criteria \
  --criteria-mode pdf+web
```

若你希望一鍵連 LatteReview 與 snowball 也一起跑：

```bash
python scripts/topic_pipeline.py run --topic "<topic>" --with-criteria --with-review --with-snowball
```

---

## 5. 先備條件（環境變數）

- 必要：`.env` 內有 `OPENAI_API_KEY`
  - 用途：keyword extraction（讀 PDF）、criteria、LatteReview
- 選用：`SEMANTIC_SCHOLAR_API_KEY`
  - 用途：提高 Semantic Scholar 查詢速率與減少 429

注意：本 repo 的工具會在執行時自動呼叫 `load_env_file()` 載入 `.env`，**不需要**你手動 `export`。

---

## 6. 測試要點

建議修改後至少驗證：

```bash
source sdse-uv/.venv/bin/activate
ruff check .
pytest -q test/unit/test_paper_workflows_queries.py
pytest -q test/unit/test_openai_provider_messages.py
```

> Live 測試（keyword extractor / web search / LatteReview）會直接呼叫 OpenAI API，成本與時間取決於外部服務狀態。

---

## 7. 已知限制

- `harvest` 目前以 arXiv 為主要 downstream 輸入（與現有 Speech LM pipeline 一致）。
- `review` 會把 structured criteria JSON 轉為字串；格式是「可用於 prompt」而不是機器可驗證的邏輯規則。
- `snowball` 目前沿用 `test/speech_lm_results_to_asreview.py`；若之後要變成正式模組，建議搬到 `src/` 並補上更通用的資料 schema。
