# literature-review 技能資料讀取與分析報告

## 版本與來源
- 來源 repo: K-Dense-AI/claude-scientific-skills
- 讀取時間: 2026-01-05
- 來源 commit: 9827af22ada9bc5c6865715d07f11588ef8ab321
- 讀取範圍:
  - scientific-skills/literature-review/SKILL.md
  - scientific-skills/literature-review/assets/review_template.md
  - scientific-skills/literature-review/references/citation_styles.md
  - scientific-skills/literature-review/references/database_strategies.md
  - scientific-skills/literature-review/scripts/verify_citations.py
  - scientific-skills/literature-review/scripts/search_databases.py
  - scientific-skills/literature-review/scripts/generate_pdf.py

## 1) 原始資料摘要（重述版本）

### 1.1 技能定位與用途
- 本技能用於系統性文獻回顧、綜整、scoping review、meta-analysis 與文獻搜尋工作。
- 目標是跨多資料庫檢索、主題式綜整、引用驗證，並輸出專業格式的 Markdown 與 PDF。
- 技能描述強調與多個 scientific skills 整合以取得資料庫內容。

### 1.2 強制視覺化要求
- 文獻回顧必須包含至少 1-2 張由 scientific-schematics 產生的圖（例如 PRISMA flow、流程圖、概念框架等）。
- 未包含圖表的回顧被定義為不完整。

### 1.3 核心流程（Phase 1-7）
- Phase 1: 規劃與範疇定義
  - 定義研究問題（如 PICO）
  - 定義範圍、時間、研究型態與納排條件
  - 建立搜尋策略與關鍵詞組合
- Phase 2: 系統性檢索
  - 至少三個資料庫
  - 為每個資料庫記錄搜尋字串、日期、結果數量
- Phase 3: 篩選與納排
  - 去重 → 標題篩選 → 摘要篩選 → 全文篩選
  - 紀錄各階段剔除原因與 PRISMA 流程數量
- Phase 4: 資料抽取與品質評估
  - 抽取研究設計、樣本、結果、限制、資金等
  - 依研究型態選擇品質評估工具（如 Cochrane RoB、Newcastle-Ottawa、AMSTAR 2）
- Phase 5: 綜整與分析
  - 主題式綜整（非逐篇摘要）
  - 比較研究結果、指出爭議與研究缺口
  - 撰寫 Discussion 與未來研究方向
- Phase 6: 引用驗證
  - DOI 驗證（CrossRef）
  - 修正與一致化引用格式
- Phase 7: 文件產出
  - 以 pandoc + xelatex 產出 PDF
  - 檢查圖表、目錄、引文一致性

### 1.4 資料庫與查詢策略
- 支援多資料庫來源（PubMed、bioRxiv/medRxiv、arXiv、Semantic Scholar 等）。
- 強調記錄完整搜尋參數、結果數量與日期。
- 包含 citation chaining（前向/後向引用）與 snowball sampling 的策略說明。

### 1.5 引用格式與驗證
- 提供 APA/Nature/Chicago/Vancouver/IEEE 等引用格式規則。
- DOI 必須驗證並輸出一致引用格式。

### 1.6 產出與品質檢核
- 要求完成 PRISMA flow、納排條件、品質評估、限制與偏誤說明。
- 提供品質檢核清單（如 citation verification、方法透明度）。

### 1.7 依賴與工具
- Python `requests` 為 DOI 驗證必需。
- 系統依賴包含 pandoc 與 xelatex（PDF 產生）。
- 文件中列出可選技能（gget、bioservices、datacommons-client 等）以取得資料。

## 2) 內含資源盤點（具體檔案）

### 2.1 assets/review_template.md
- 目的: 提供完整文獻回顧模板（摘要、方法、結果、討論、附錄）。
- 特點: 包含 PRISMA、品質評估、資料抽取表、排除理由、附錄等結構。

### 2.2 references/citation_styles.md
- 目的: 引用格式規範
- 內容: APA/Nature/Chicago/Vancouver/IEEE 的格式樣式與示例
- 補充: DOI 格式最佳實務與文內引用規則

### 2.3 references/database_strategies.md
- 目的: 多資料庫檢索策略
- 內容: 資料庫清單、查詢語法、PICO、布林運算、去重與篩選流程
- 補充: Citation chaining、snowball sampling、品質控制清單

### 2.4 scripts/search_databases.py
- 功能: 統一搜尋結果格式化、去重、排名、年份範圍篩選、摘要統計
- 輸入: JSON 格式結果
- 輸出: JSON/Markdown/BibTeX
- 限制: 僅處理結果資料，不提供實際搜尋功能

### 2.5 scripts/verify_citations.py
- 功能: 讀取 Markdown 檔，抽取 DOI 並驗證可用性
- 外部依賴: DOI Handle API 與 CrossRef API
- 輸出: citation_report.json 與 APA/Nature 格式引用
- 限制: 僅驗證 DOI；非 DOI 引文不在流程內

### 2.6 scripts/generate_pdf.py
- 功能: 使用 pandoc 與 xelatex 產出 PDF
- 支援: citation style、目錄、章節編號、模板
- 依賴: pandoc + xelatex
- 限制: .bib 存在時才啟用 citeproc

## 3) 可重現性、依賴與風險分析

### 3.1 可重現性要件
- 每個資料庫的搜尋字串、時間、結果數量必須記錄。
- 引用需通過 DOI 驗證。
- PRISMA 與納排條件需完整記錄。

### 3.2 外部依賴風險
- CrossRef/DOI API 可用性影響 verify_citations.py。
- Pandoc/LaTeX 安裝狀態影響 PDF 產出。
- 多資料庫搜尋依賴其他 skills 或 API，未提供統一的憑證管理規範。

### 3.3 視覺化硬性要求
- 文獻回顧必須至少包含 1-2 個 scientific-schematics 圖表。
- 若無圖表，文件被視為不完整。

## 4) 與本地 repo 的對接分析（推論）

### 4.1 對接位置（推論）
- 可對接於 `Topic Pipeline` 的最末端（Snowball/LatteReview 後）作為最終輸出步驟。
- 對應輸入:
  - `workspaces/<topic>/review/latte_review_results.json`
  - `workspaces/<topic>/snowball_rounds/final_included.json/csv`
  - `workspaces/<topic>/criteria/criteria.json`

### 4.2 缺口與需補充項目（推論）
- 本 repo 尚無對等的 citation verification 與 PDF 產出腳本。
- 未提供 review_template 的完整結構與 PRISMA 附錄表格。
- 對於 scientific-schematics 圖表生成，目前 repo 未包含對應工具或產線。

### 4.3 可行整合策略（推論）
- 新增 `docs/skills/literature-review.md` 之外，需新增對應腳本或引用外部工具。
- 在 `docs/pipelines/topic_cli_pipeline_overview.md` 追加「最終文獻回顧輸出」步驟。
- 若要實作 DOI 驗證，需新增 `scripts/verify_citations.py` 或等效模組並加入依賴管理。

## 5) 無法確定事項
- 文檔未提供 gget/bioservices/datacommons-client 的憑證設定方式。
- 文檔未提供 scientific-schematics 的執行環境或 API 金鑰配置方式。

## 6) 對本 repo 的影響結論
- literature-review 提供的是「完整文獻回顧輸出與品質控制」規範與工具範本。
- 本 repo 目前聚焦於「topic → seed → keywords → criteria → review → snowball」的資料產生流程。
- literature-review 可作為本 repo 的最終輸出階段補強，不構成替代。

