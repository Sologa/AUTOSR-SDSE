# literature-review 整合實作過程（詳版）

> 本文件為「實作流程」細化版本，目標是讓 repo 可以在既有 pipeline 後端新增 literature-review 產出階段。
> 內容依據本 repo 現況與 literature-review 原始規範整理；標註「推論」者為建議設計，需使用者確認。

## 0) 前置條件與限制

- 必須遵守 `AGENTS.md` 的規範：
  - 不修改受保護檔案（見 `docs/agent-protected-files.md`）。
  - 不在未取得同意下新增依賴或安裝工具。
  - `.env` 中的金鑰需由流程在初始化階段載入。
- 本 repo 已具備：seed/keywords/harvest/criteria/review/snowball 的 pipeline。
- literature-review 原始規範要求：
  - 產出文獻回顧文件（Markdown + PDF）。
  - 進行 DOI 驗證與引用格式化。
  - 強制 1–2 張以上視覺化圖表（使用 scientific-schematics）。

## 1) 新增 Stage：literature-review（推論）

### 1.1 Stage 位置
- 推論：新增於 snowball 後（最終輸出）。
- 替代方案（推論）：若使用者不跑 snowball，則使用 review 結果作為輸出基礎。

### 1.2 Stage 入口
- CLI 新增：
  - `python scripts/topic_pipeline.py literature-review --topic "<topic>"`
  - `python scripts/topic_pipeline.py run --with-literature-review`

## 2) 輸入與輸出契約（推論）

### 2.1 必要輸入
- `workspaces/<topic>/criteria/criteria.json`
- `workspaces/<topic>/harvest/arxiv_metadata.json`

### 2.2 可選輸入
- `workspaces/<topic>/review/latte_review_results.json`
- `workspaces/<topic>/snowball_rounds/final_included.json`
- `workspaces/<topic>/snowball_rounds/final_included.csv`

### 2.3 輸出目錄
```
workspaces/<topic>/literature_review/
  review.md
  review.pdf                  # 若系統依賴允許
  figures/
  citations_report.json
  search_results.md
  prisma_summary.json
```

## 3) 實作步驟（詳版）

### Step 1：初始化與環境載入
- 呼叫 `load_env_file()` 載入 `.env`。
- 確認 workspace 是否存在，不存在則拋出錯誤。

### Step 2：選擇 base 清單
- 若 `snowball_rounds/final_included.json` 存在 → 使用該檔。
- 否則若 `review/latte_review_results.json` 存在 → 使用 `final_verdict` 為 include 的清單。
- 若兩者皆無 → 報錯並停止。

### Step 3：建立 PRISMA 數字（推論）
- 來源：
  - Seed: `seed/queries/seed_selection.json`
  - Harvest: `harvest/arxiv_metadata.json`
  - Review: `review/latte_review_results.json`
  - Snowball: `snowball_rounds/*/round_meta.json`
- 產出 `prisma_summary.json`：記錄各階段數量與排除原因。

### Step 4：產出 search_results.md
- 使用 harvest metadata 整理成 Markdown：
  - 可直接移植 literature-review 的 `search_databases.py` 或等效格式化。

### Step 5：套用 review_template.md
- 將 literature-review 的 `assets/review_template.md` 拷貝成 `review.md`。
- 填入：
  - topic、日期、review type、PRISMA、方法描述、結果概覽。
  - 以「主題式綜整」填寫結果段落（避免逐篇摘要）。

### Step 6：引用驗證
- 從 review.md 提取 DOI（或使用 existing metadata 內 DOI）。
- 執行 `verify_citations.py`：
  - 產生 `citations_report.json`。
- 若 DOI 驗證失敗 → 直接報錯，不做 silent fallback。

### Step 7：圖表產生（推論）
- 若要符合 literature-review 要求，需生成至少 1–2 張圖：
  - PRISMA flow 或流程圖。
- 若 scientific-schematics 無法使用 → 報錯並停止（符合原始規範）。

### Step 8：PDF 產出
- 若 pandoc + xelatex 可用 → 使用 `generate_pdf.py` 生成 `review.pdf`。
- 若不可用 → 報錯或僅輸出 Markdown（需使用者確認）。

## 4) 檔案與模組建議（推論）

### 4.1 新增模組
- `src/pipelines/literature_review.py`：主流程封裝
- `scripts/literature_review.py`：CLI wrapper

### 4.2 新增資源
- `resources/literature_review/review_template.md`
- `resources/literature_review/citation_styles.md`
- `resources/literature_review/database_strategies.md`

## 5) 錯誤處理規範

- 缺少必要檔案 → 立即報錯。
- DOI 驗證失敗 → 立即報錯。
- 圖表產生缺失 → 立即報錯（若規範要求強制）。
- 不允許自動 fallback 或離線替代流程。

## 6) 測試與驗證（推論）

- 新增 integration test：
  - 驗證 `review.md` 是否產出、PRISMA 欄位是否填入。
  - 驗證 citations_report.json 產生。
- 測試仍需遵守「不得 mock」原則。

## 7) 文件更新（推論）

- `docs/pipelines/topic_cli_pipeline.md`：新增 literature-review stage 說明與 CLI。
- `docs/skills/literature-review.md`：補上整合入口與限制。

## 8) 待使用者確認事項

1. literature-review stage 應插入在 review 後還是 snowball 後？
2. citation style 預設值（APA / Nature / Vancouver / IEEE）。
3. 若缺 pandoc/xelatex 是否允許只輸出 Markdown？
4. 是否強制要求 scientific-schematics 圖表？

