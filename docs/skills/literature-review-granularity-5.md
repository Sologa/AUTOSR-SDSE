# literature-review 粒度 5：行為規則級（詳細規格）

> 本文件列出「必須/不得/允許」的行為規則，供實作時直接對照。

## 1) 觸發條件
- 只有在以下條件之一成立時執行 literature-review：
  1. `python scripts/topic_pipeline.py literature-review --topic "..."`
  2. `python scripts/topic_pipeline.py run --with-literature-review`

## 2) Base 清單解析規則
- 優先順序固定：
  1. `snowball_rounds/final_included.json`
  2. `review/latte_review_results.json` 中 `final_verdict == include`
- 兩者皆不存在 → 直接報錯
- Base 清單不得為空；若為空 → 直接報錯

## 3) 必要輸入
- 必須存在：
  - `harvest/arxiv_metadata.json`
- 若缺少 → 直接報錯

## 4) 可選輸入
- 可選存在：
  - `criteria/criteria.json`
  - `harvest/semantic_scholar_records.json`
  - `harvest/dblp_records.json`
  - `review/latte_review_results.json`
- 缺少可選輸入時仍可繼續，但必須在 `literature_review/` 內輸出 `missing_inputs` 記錄。

## 5) PRISMA 統計規則
- `prisma_summary.json` 必須包含下列欄位（缺值填 null）：
  - seed_found
  - seed_downloaded
  - harvest_total
  - review_screened
  - review_included
  - snowball_rounds
  - snowball_included_total
- 若無法解析對應資料 → 欄位設為 null 並列入 `missing_fields`。

## 6) search_results.md 生成規則
- 來源以 `harvest/arxiv_metadata.json` 為主。
- 若有 semantic scholar / dblp → 允許追加，但必須標記來源。
- 條目排序規則：
  1. 年份（新到舊）
  2. 標題字母序

## 7) review.md 生成規則
- 必須使用 `resources/literature_review/review_template.md` 作為骨架。
- 必須填入：
  - Topic
  - PRISMA 統計摘要
  - 納排條件摘要（若有 criteria.json）
  - 主題式綜整段落（不可逐篇摘要）
- 若缺 criteria.json → 在「方法」段落標示「criteria 缺失」。

## 8) DOI 驗證規則
- 若 review.md 中存在 DOI → 必須執行驗證。
- 若未找到 DOI：仍需輸出 `citations_report.json`，`total_dois=0`。
- 任何 DOI 驗證失敗 → 直接報錯，不得 fallback。

## 9) 圖表規則
- 若決策為「強制圖表」：
  - 至少 1 張圖必須產生
  - review.md 必須引用圖檔
  - 無圖 → 直接報錯
- 若未強制：允許跳過，但必須輸出 `figures_status=skipped`。

## 10) PDF 規則
- 若有 pandoc + xelatex：必須產生 `review.pdf`。
- 若缺依賴：
  - 若決策允許「Markdown-only」→ 記錄 `pdf_status=skipped_missing_deps`
  - 否則直接報錯

## 11) 錯誤處理
- 缺少必要檔案 → 立即報錯。
- 任一外部 API 失敗（DOI 驗證）→ 立即報錯。
- 不得 silent fallback、不得 mock。

## 12) 輸出目錄規則
- 必須建立：`workspaces/<topic>/literature_review/`
- 必須包含：
  - review.md
  - prisma_summary.json
  - citations_report.json
  - search_results.md
- 若有圖表：必須有 `figures/` 子目錄。

