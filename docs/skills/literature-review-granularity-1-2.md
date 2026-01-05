# literature-review 粒度 1–2 規劃清單

## 粒度 1：高階里程碑（順序）
1. 設計與規格確認（插入點、引用格式、圖表要求、PDF 失敗行為）
2. 新增 literature-review stage 入口與落盤（CLI + workspace）
3. 彙整輸入與報告生成（review.md、PRISMA 統計）
4. 引用驗證流程（DOI 驗證與報告）
5. 輸出格式與視覺化（PDF 產出、圖表）
6. 測試與文件更新（日誌與 docs）

## 粒度 2：功能模組級（檔案/模組）
1. Pipeline 核心模組
   - src/pipelines/literature_review.py（新增）
   - src/pipelines/topic_pipeline.py（掛載新 stage）
2. CLI 入口
   - scripts/literature_review.py（新增）
   - scripts/topic_pipeline.py（新增 subcommand/flag）
3. 資源模板與規範
   - resources/literature_review/review_template.md
   - resources/literature_review/citation_styles.md
   - resources/literature_review/database_strategies.md
4. 腳本工具
   - scripts/verify_citations.py
   - scripts/search_databases.py
   - scripts/generate_pdf.py
5. 文件與說明
   - docs/pipelines/topic_cli_pipeline.md（新增 stage 說明）
   - docs/skills/literature-review-implementation-details.md（已建立）
6. 輸出位置（workspace）
   - workspaces/<topic>/literature_review/
