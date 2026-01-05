# literature-review 粒度 4：逐步操作流程（可直接照做）

> 本文件將整合流程拆成逐步操作與對應檔案，適合直接作為實作 runbook。

## Step 0：確認決策（先寫入決策文件）
- 建立/更新：`docs/skills/literature-review-decisions.md`
- 必填項：
  1. 插入點：review 後或 snowball 後
  2. citation style 預設值（APA / Nature / Vancouver / IEEE）
  3. scientific-schematics 圖表是否強制
  4. 缺少 pandoc/xelatex 時是否允許只輸出 Markdown

## Step 1：新增 resources 資源
- 建立資料夾：`resources/literature_review/`
- 新增檔案：
  - `resources/literature_review/review_template.md`
  - `resources/literature_review/citation_styles.md`
  - `resources/literature_review/database_strategies.md`
- 來源：literature-review skill 原始檔案（保持內容一致）

## Step 2：新增核心 pipeline 模組
- 新增：`src/pipelines/literature_review.py`
- 必備功能：
  - `run_literature_review(workspace, *, options)`
  - 載入 `.env`（呼叫 `load_env_file()`）
  - 解析 workspace 產物並產出 `literature_review/` 目錄

## Step 3：新增 CLI 入口
- 新增：`scripts/literature_review.py`
- 修改：`scripts/topic_pipeline.py`
  - 新增 `literature-review` subcommand
  - `run` 子指令新增 `--with-literature-review`
- 驗證：
  - `python scripts/topic_pipeline.py literature-review --topic "<topic>"` 可執行

## Step 4：選擇 base 清單
- 輸入候選：
  1. `workspaces/<topic>/snowball_rounds/final_included.json`
  2. `workspaces/<topic>/review/latte_review_results.json`
- 規則：
  - 若 (1) 存在 → 使用 (1)
  - 否則使用 (2) 中 `final_verdict == include` 的清單
  - 兩者皆無 → 直接報錯

## Step 5：產出 PRISMA 統計
- 建議輸入：
  - `seed/queries/seed_selection.json`
  - `harvest/arxiv_metadata.json`
  - `review/latte_review_results.json`
  - `snowball_rounds/*/round_meta.json`
- 輸出：`workspaces/<topic>/literature_review/prisma_summary.json`
- 若欄位缺失：填入 `null` 並記錄 `missing_fields`

## Step 6：產出 search_results.md
- 輸入：`harvest/arxiv_metadata.json`（必要）
- 若存在：`harvest/semantic_scholar_records.json`、`harvest/dblp_records.json` 可併入
- 輸出：`workspaces/<topic>/literature_review/search_results.md`

## Step 7：產出 review.md
- 以 `resources/literature_review/review_template.md` 為模板
- 自動填入：
  - Topic、日期、PRISMA 數字、納排條件摘要、結果概覽
- 輸出：`workspaces/<topic>/literature_review/review.md`

## Step 8：引用驗證
- 若 review.md 中有 DOI：
  - 執行 `verify_citations.py`
  - 產出 `citations_report.json`
- 無 DOI：
  - 仍建立 `citations_report.json`，`total_dois=0`
- 任何 DOI 驗證失敗 → 直接報錯（不得 silent fallback）

## Step 9：圖表生成（若強制）
- 若決策為「強制」：
  - 產出至少 1–2 張圖
  - 存於 `workspaces/<topic>/literature_review/figures/`
  - review.md 必須引用圖檔
- 若未強制：可略過但需在輸出狀態註記

## Step 10：PDF 產出
- 若系統有 pandoc + xelatex：
  - 執行 `generate_pdf.py` 產出 `review.pdf`
- 若缺依賴：
  - 若允許 Markdown-only → 記錄 `pdf_status=skipped_missing_deps`
  - 否則直接報錯

## Step 11：文件更新
- 更新：`docs/pipelines/topic_cli_pipeline.md`（新增 stage 說明）
- 更新：`docs/skills/literature-review-implementation-details.md`（同步變更）

## Step 12：測試與驗證
- 最小驗證：
  - 確認 `review.md`、`prisma_summary.json`、`citations_report.json` 產出
- 若有 PDF：確認 `review.pdf` 存在且可讀

## Step 13：日誌
- 依規範追加 `logs/YYYY-MM-DD.md`

