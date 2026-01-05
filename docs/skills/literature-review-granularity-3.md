# literature-review 粒度 3：任務清單級（可指派）

> 目的：把「高階里程碑」拆成可直接指派的工作包。每項包含：輸入、輸出、驗收條件、依賴。

## T1. 決策與規格落盤
- 內容：確認插入點、citation style 預設、圖表是否強制、PDF 失敗行為
- 輸入：使用者決策
- 輸出：`docs/skills/literature-review-decisions.md`
- 驗收：文件列出 4 項決策與日期
- 依賴：無

## T2. 新增 pipeline 模組
- 內容：新增 literature-review 核心流程模組
- 輸入：workspace 產物（criteria/harvest/review/snowball）
- 輸出：`src/pipelines/literature_review.py`
- 驗收：
  - 提供 `run_literature_review(workspace, ...)` 或等效入口
  - 可讀取 `workspaces/<topic>` 既有產物
- 依賴：T1

## T3. CLI 入口與 topic pipeline 串接
- 內容：新增 CLI 子指令與 run flag
- 輸入：`--topic`、`--workspace-root`、`--with-literature-review`
- 輸出：
  - `scripts/literature_review.py`（新增）
  - `scripts/topic_pipeline.py`（新增 subcommand / flag）
- 驗收：
  - `python scripts/topic_pipeline.py literature-review --topic "..."` 可執行
  - `run --with-literature-review` 會觸發該 stage
- 依賴：T2

## T4. 匯入與整理模板/規範資源
- 內容：引入 literature-review 的模板與規範檔
- 輸入：外部 skill 檔案（template / citation / database strategies）
- 輸出：
  - `resources/literature_review/review_template.md`
  - `resources/literature_review/citation_styles.md`
  - `resources/literature_review/database_strategies.md`
- 驗收：三個檔案存在且可讀
- 依賴：T1

## T5. 產生 review.md（主體內容）
- 內容：以模板產生 review.md 並填入可自動化欄位
- 輸入：
  - `criteria/criteria.json`
  - `harvest/arxiv_metadata.json`
  - `review/latte_review_results.json`（或 snowball final）
- 輸出：`workspaces/<topic>/literature_review/review.md`
- 驗收：
  - 檔案存在
  - 含 PRISMA 數字、納排條件摘要、主題式綜整段落
- 依賴：T2, T4

## T6. 產生 PRISMA 統計與 search_results
- 內容：計算各階段數量並整理搜尋結果清單
- 輸入：seed/harvest/review/snowball 產物
- 輸出：
  - `workspaces/<topic>/literature_review/prisma_summary.json`
  - `workspaces/<topic>/literature_review/search_results.md`
- 驗收：
  - PRISMA JSON 含各階段計數
  - search_results.md 有條列式文獻清單
- 依賴：T2, T4

## T7. DOI 驗證與引用報告
- 內容：整合 verify_citations.py 並輸出 citations_report
- 輸入：review.md 或 final_included metadata
- 輸出：`workspaces/<topic>/literature_review/citations_report.json`
- 驗收：
  - 驗證報告生成
  - DOI 失敗時流程直接報錯（不 silent fallback）
- 依賴：T2, T4, T5

## T8. PDF 產出
- 內容：整合 generate_pdf.py 並生成 review.pdf
- 輸入：review.md、citation style
- 輸出：`workspaces/<topic>/literature_review/review.pdf`
- 驗收：
  - 若環境有 pandoc/xelatex → 產出 PDF
  - 若缺依賴 → 明確報錯（是否允許只輸出 Markdown 取決於 T1 決策）
- 依賴：T2, T4, T5, T7

## T9. 圖表產生（scientific-schematics）
- 內容：產生至少 1–2 張圖表（如 PRISMA flow）
- 輸入：PRISMA 統計、search strategy
- 輸出：`workspaces/<topic>/literature_review/figures/*`
- 驗收：
  - 至少 1 張圖檔存在
  - review.md 內有引用圖表
- 依賴：T5, T6, T1（是否強制）

## T10. 文件更新
- 內容：更新 pipeline 文件與使用說明
- 輸入：新增 stage 的行為與 CLI
- 輸出：
  - `docs/pipelines/topic_cli_pipeline.md`（新增 stage）
  - `docs/skills/literature-review-implementation-details.md`（補充實作變更）
- 驗收：文件與實作一致
- 依賴：T2, T3

## T11. 測試與驗證
- 內容：新增最小可行驗證流程
- 輸入：既有 workspace 範例
- 輸出：
  - integration 記錄或測試腳本（需符合「不得 mock」規範）
- 驗收：
  - review.md / prisma_summary / citations_report 可產生
- 依賴：T5–T8

