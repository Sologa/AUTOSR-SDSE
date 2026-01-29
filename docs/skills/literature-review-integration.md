# literature-review 與本 repo 整合報告

## 版本與讀取範圍
- 報告日期：2026-01-05
- 外部來源（literature-review）：K-Dense-AI/claude-scientific-skills
  - 來源 commit：9827af22ada9bc5c6865715d07f11588ef8ab321
  - 讀取檔案：
    - scientific-skills/literature-review/SKILL.md
    - scientific-skills/literature-review/assets/review_template.md
    - scientific-skills/literature-review/references/citation_styles.md
    - scientific-skills/literature-review/references/database_strategies.md
    - scientific-skills/literature-review/scripts/verify_citations.py
    - scientific-skills/literature-review/scripts/search_databases.py
    - scientific-skills/literature-review/scripts/generate_pdf.py
- 本地 repo 讀取範圍（逐檔閱讀）：
  - scripts/topic_pipeline.py
  - src/pipelines/topic_pipeline.py
  - src/utils/structured_web_search_pipeline.py
  - src/utils/openai_web_search.py
  - docs/pipelines/topic_cli_pipeline.md
  - docs/pipelines/topic_cli_pipeline_overview.md
  - docs/pipelines/pipeline_handoff.md
  - docs/pipelines/criteria_prompt_alignment.md
  - docs/pipelines/harvest_query_plan.md
  - docs/pipelines/cutoff_policy.md
  - docs/pipelines/review_discard_reason.md
  - docs/pipelines/seed_topic_variants.md
  - docs/pipelines/topic_debug_script.md
  - docs/llm/provider-layer.md
  - docs/llm/openai_web_search.md
  - docs/keyword_extractor/module.md
  - docs/keywords/spec.md
  - docs/filter-seed/spec.md
  - docs/paper_workflows/module.md
  - docs/snowballing/architecture.md
- 未逐字閱讀的範圍：
  - workspaces/、target_papers/、test_artifacts/ 等大量產出資料
  - 二進位與大型資料檔（PDF、圖檔、壓縮檔）

## 1) literature-review 技能內容（重述版本）

### 1.1 目的與定位
- 以系統性方法完成文獻回顧：跨資料庫檢索、主題式綜整、引用驗證、輸出 Markdown/PDF。
- 內建完整流程建議（PICO、搜尋策略、納排、品質評估、PRISMA）。

### 1.2 強制要求
- 每份文獻回顧必須包含 1–2 張以上的視覺化圖表（要求使用 scientific-schematics）。

### 1.3 核心流程（Phase 1–7）
1. 規劃與範疇：定義問題、範圍、搜尋策略、納排條件。
2. 系統性檢索：至少 3 個資料庫，記錄搜尋字串、日期、結果數量。
3. 篩選與納排：去重 → 標題 → 摘要 → 全文，並記錄排除原因與 PRISMA 流程數字。
4. 資料抽取與品質評估：萃取研究設計、樣本、結果、限制、COI；使用 RoB / NOS / AMSTAR 2 等。
5. 綜整與分析：以主題式綜整與批判分析為主，避免逐篇摘要。
6. 引用驗證：DOI 與 CrossRef 驗證，統一引用格式。
7. 產出：以模板產生 Markdown 與 PDF。

### 1.4 內含資源
- assets/review_template.md：完整文獻回顧模板（含 PRISMA、附錄、品質評估表）。
- references/citation_styles.md：APA/Nature/Chicago/Vancouver/IEEE 引用規則。
- references/database_strategies.md：多資料庫搜尋策略與查詢範例。
- scripts/search_databases.py：去重、排序、格式化、統計摘要。
- scripts/verify_citations.py：DOI 驗證與引用格式生成。
- scripts/generate_pdf.py：pandoc + xelatex 產生 PDF。

### 1.5 依賴
- Python：requests（用於 DOI 驗證）
- 系統：pandoc、xelatex

## 2) 本地 repo 現況摘要（重述版本）

### 2.1 主要流程與入口
- 入口 CLI：scripts/topic_pipeline.py
- 主流程：seed →（可選）filter-seed → keywords → harvest →（可選）harvest-other →（可選）criteria →（可選）review →（可選）snowball
- 主要輸出：workspaces/<topic_slug>/ 內含各階段產物

### 2.2 既有關鍵產物
- seed：seed/queries、seed/downloads
- keywords：keywords/keywords.json
- harvest：harvest/arxiv_metadata.json
- criteria：criteria/criteria.json、web_search_notes.txt
- review：review/latte_review_results.json
- snowball：snowball_rounds/* 與 review_registry.json

### 2.3 既有 LLM 與 web search 能力
- LLM Provider Layer 支援 OpenAI Responses API 與 PDF 讀取
- criteria 可選 web 或 pdf+web

## 3) 對齊與差距分析

### 3.1 既有能力對應 literature-review
- 多資料庫搜尋：本 repo 目前有 arXiv + Semantic Scholar + DBLP（harvest / harvest-other）。
- 納排與審稿：filter-seed + review + snowball
- 條件規則：criteria JSON

### 3.2 目前缺口
- 無正式「文獻回顧」輸出階段（模板、PRISMA、摘要/討論/結論輸出）。
- 無 DOI 驗證、引用格式化、PDF 產出腳本。
- 無強制圖表產生流程（scientific-schematics 相關）。
- 缺少「多資料庫搜尋結果整合」的統一格式化輸出（僅有 harvest JSON）。

## 4) 整合設計（推論）

### 4.1 新增 Stage：literature-review
- 位置：snowball（或 review）完成後，作為最終輸出。
- 目的：將既有資料彙整成標準化文獻回顧文件。

### 4.2 建議輸入
- workspaces/<topic>/review/latte_review_results.json
- workspaces/<topic>/snowball_rounds/final_included.json 或 final_included.csv
- workspaces/<topic>/criteria/criteria.json
- workspaces/<topic>/harvest/arxiv_metadata.json

### 4.3 建議輸出（新子目錄）
```
workspaces/<topic>/literature_review/
  review.md
  review.pdf               # 若 pandoc/xelatex 可用
  figures/                 # PRISMA/流程圖等
  citations_report.json
  search_results.md
  prisma_summary.json
```

### 4.4 新增 CLI 介面（推論）
- `python scripts/topic_pipeline.py literature-review --topic "<topic>"`
- `python scripts/topic_pipeline.py run --with-literature-review`

### 4.5 對應 literature-review 內建腳本
- search_databases.py → 對應 harvest / harvest-other 輸出整理
- verify_citations.py → 對應 final_included + metadata 中 DOI 驗證
- generate_pdf.py → 對應 review.md → review.pdf

## 5) 整合步驟建議（推論）

1) 讀取 workspace 產物
- 讀取 final_included（雪崩或 review）作為主要收錄清單
- 讀取 criteria.json 轉成納排條件摘要
- 讀取 harvest metadata 補齊 DOI / URL / 摘要

2) 產生 review.md（基於 assets/review_template.md）
- 填寫摘要、方法、結果與主題式綜整
- PRISMA numbers 根據各階段產物數量自動填入

3) 引用驗證
- 以 verify_citations.py 驗證 DOI 並輸出 citations_report.json

4) 圖表產生（如需強制）
- 若導入 scientific-schematics，產出 PRISMA / 流程圖放入 figures/

5) PDF 產出
- 若 pandoc/xelatex 可用，生成 review.pdf

## 6) 需新增或調整的檔案（推論）

### 6.1 建議新增
- scripts/literature_review.py（或放入 src/pipelines/）
- docs/skills/literature-review-integration.md（本文件）
- docs/pipelines/topic_cli_pipeline.md 增補 literatrue-review stage 說明

### 6.2 建議導入（可選）
- 從 literature-review skill 引入腳本：verify_citations.py、generate_pdf.py、search_databases.py
- 從 literature-review skill 引入模板：review_template.md

## 7) 風險與限制

- PDF 產出依賴 pandoc/xelatex；若環境未安裝需降級為僅輸出 Markdown。
- DOI 驗證依賴外部 API；若 API 不可用需明確報錯（不可 silent fallback）。
- 強制圖表需求需配合 scientific-schematics 的實際可用性，否則會造成流程無法完成。

## 8) 驗證與測試建議（推論）

- 以既有 topic workspace 驗證生成 `literature_review/` 產物
- 檢查 review.md 是否包含 PRISMA、納排、主題式綜整
- 確認 citations_report.json 有完整 DOI 驗證結果

## 9) 待使用者確認事項

1. 是否要強制「必須有圖表」的規則？
2. 需要支援的 citation style（APA/Nature/Vancouver/IEEE）是哪一種？
3. 是否允許新增 pandoc/xelatex 依賴？
4. literature-review stage 應插入在 review 之後還是 snowball 完成後？
