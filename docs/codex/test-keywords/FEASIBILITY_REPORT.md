# Codex/Gemini CLI Keywords Smoke Test 可行性報告（docs/codex/test-keywords）

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

## 範圍與依據

### 範圍
- 目標：評估以 **codex exec** 與 **gemini** CLI 建立「keywords 抽取」的 smoke test，可獨立於正式 pipeline。
- 限制：不修改 `src/` 與受保護檔案；所有檔案落在 `docs/codex/test-keywords/`。

### 依據（repo 內）
- Pipeline 現況：`docs/pipelines/pipeline_handoff.md`
- Keywords 規格：`docs/keywords/spec.md`
- Keyword Extractor 模組：`docs/keyword_extractor/module.md`、`docs/keyword_extractor/關鍵詞抽取流程與提示詞.md`
- Prompt 模板：`resources/LLM/prompts/keyword_extractor/generate_search_terms.md`
- 程式碼：`src/utils/keyword_extractor.py`、`src/pipelines/topic_pipeline.py`
- 既有 CLI 測試樣式：`docs/codex/test-review/*`
- 受保護檔案清單：`docs/agent-protected-files.md`

### 外部查詢動機與渠道
- 動機：確認 **codex exec** 與 **gemini** CLI 的「非互動執行、JSON 輸出、工具與 PDF 輸入能力」是否可支援 keywords 測試。
- 渠道：OpenAI Codex 官方文件、Gemini CLI 官方文件與官方 repo（raw docs）、Microsoft Learn（Codex CLI on Azure）。

---

## 現行 Keywords Pipeline 摘要（repo 內）

- `extract_keywords_from_seed_pdfs()` 會固定使用 `gpt-5.2`、`temperature=1.0`，並透過 `LLMService.read_pdf()` 逐篇讀取 PDF，再聚合成 `keywords.json`。
- `keyword_extractor` 會：
  - 以檔名推斷 arXiv id，並補齊 metadata（title/abstract/year/url）。
  - 以 prompt 模板輸出 `anchor_terms`、分類化 `search_terms`、以及 `papers[*].detected_keywords`。
  - 驗證 titles/abstracts 必須與 metadata 完全一致。
- 以上流程依賴 PDF 讀取能力；該能力目前封裝在受保護檔案 `src/utils/llm.py`。

---

## CLI 能力查核（外部來源）

### Codex CLI（codex exec）
- **非互動模式**：`codex exec` 支援 scripted/CI 執行。來源：
  - https://developers.openai.com/codex/cli/reference
  - https://developers.openai.com/codex/cli/features
- **結構化輸出**：`--output-schema` 可輸出符合 JSON Schema 的結果，`--json` 可輸出 JSONL 事件流。來源：
  - https://developers.openai.com/codex/sdk
  - https://developers.openai.com/codex/cli/reference
- **Sandbox / Web Search**：預設 read-only sandbox，需使用 `--full-auto` 或 config 才能開放寫入；Web Search 需顯式啟用，並可由 config 控制。來源：
  - https://developers.openai.com/codex/sdk
  - https://developers.openai.com/codex/cli/features
- **檔案輸入（PDF）**：官方 CLI 文件僅明示圖片附件（PNG/JPEG），未見 PDF 直接附件或 PDF 解析說明。來源：
  - https://developers.openai.com/codex/cli/features

**結論**：
- `codex exec` 支援非互動與 JSON 輸出，可用於 keywords 測試的「結果輸出與 schema 驗證」部分。
- **PDF 直接輸入能力無外部依據，無法確定**。

### Gemini CLI（gemini）
- **Headless 模式與 JSON 輸出**：`--prompt/-p`、`--output-format json` 支援 headless 與結構化輸出；可透過 stdin 將檔案內容導入。來源：
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/cli/headless.md
- **工具與檔案讀取**：`read_file` 工具支援 PDF，會回傳 base64 `inlineData` 供模型使用。來源：
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/tools/file-system.md
- **工具開關**：`tools.core`（allowlist）與 `tools.exclude`（blocklist）可在 `.gemini/settings.json` 控制。來源：
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/get-started/configuration.md
- **Web Search 工具名稱**：`google_web_search`。來源：
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/tools/web-search.md

**結論**：
- Gemini CLI 有明確的 PDF 讀取工具能力，可用於 keywords 測試的「PDF 輸入」需求。

---

## 可行性結論（以 test-keywords 為目標）

### 結論摘要
- **Gemini CLI：可行**（依據 `read_file` 支援 PDF 與 headless JSON 輸出）。
- **Codex CLI：部分可行**（JSON 輸出可行；**PDF 輸入無外部依據，無法確定**）。

### 可行性矩陣
| 能力 | Codex CLI (codex exec) | Gemini CLI (gemini) | 依據 |
| --- | --- | --- | --- |
| 非互動執行 | ✅ | ✅ | OpenAI Codex CLI / Gemini CLI headless doc |
| JSON 輸出 | ✅（`--output-schema`） | ✅（`--output-format json`） | OpenAI Codex SDK / Gemini headless doc |
| PDF 讀取 | 無法確定 | ✅（`read_file` 支援 PDF） | OpenAI Codex CLI features / Gemini file-system tools doc |
| Web Search 控制 | ✅（config + `--search`） | ✅（`tools.core` / `tools.exclude`） | OpenAI Codex CLI features / Gemini config doc |

---

## test-keywords 最小設計（擬）

> 本節為「可行性報告中最小設計草案」，不等同於最終 spec/plan/tasks。

### 目標
- 以 **codex exec** 與 **gemini** CLI 產生 `keywords.json` 等價結構，驗證 CLI 在「關鍵詞抽取」流程的可用性。

### 輸入
- 來源：`workspaces/<topic_slug>/seed/downloads/arxiv/*.pdf`（與 pipeline 一致）。
- Metadata：沿用 `keyword_extractor` 的 arXiv metadata 匯入邏輯（以檔名推斷 arXiv id）。

### 輸出（建議）
- `docs/codex/test-keywords/outputs/<run_id>/keywords.json`
- `docs/codex/test-keywords/outputs/<run_id>/run_manifest.json`

### 執行模式（建議）
1) **Gemini PDF 模式（可行）**
   - CLI 以 `read_file` 讀 PDF，prompt 使用 `generate_search_terms.md`。
   - 以 `--output-format json` 產出結構化結果，再由 runner 解析/驗證。

2) **Codex 文字模式（需先處理 PDF）**
   - 以 `pdfplumber` 將 PDF 轉為純文字，再以 `codex exec` 送入 prompt。
   - 純文字輸出存放於 `docs/codex/test-keywords/outputs/<run_id>/`，每個 PDF 一個 `.txt`，檔名沿用 PDF 檔名。

### 風險與限制
- **Codex CLI PDF 讀取**：官方文件未說明 PDF 直接輸入，**無法確定**。
- **PDF 轉文字依賴**：已決定使用 `pdfplumber`；安裝需透過 `uv sync`（禁止自動安裝）。
- **Codex JSON Schema 限制**：`search_terms` 需改為 `{category, terms}` 陣列格式以通過 `--output-schema`；runner 需再轉回物件格式。
- **JSON schema 差異**：Gemini `--output-format json` 會包 `response` 與 `stats`；若需與 `keywords.json` 相同結構，需額外解析/驗證層（屬實作設計）。

---

## 後續建議
1) 先以 **Gemini CLI** 做 PDF 讀取測試，確認 `read_file` 對 PDF 的行為與輸出是否可被解析成 `keywords.json`。
2) **Codex CLI** 無等價 PDF 直讀能力時，採用 `pdfplumber` 進行 PDF→text 前處理。
3) 後續實作依 `docs/codex/test-review` 風格維持一致（spec/plan/tasks/runner/schema 已完成）。

---

## 外部來源
- OpenAI Codex CLI reference：https://developers.openai.com/codex/cli/reference
- OpenAI Codex CLI features：https://developers.openai.com/codex/cli/features
- OpenAI Codex SDK（output-schema / json）：https://developers.openai.com/codex/sdk
- Gemini CLI headless：https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/cli/headless.md
- Gemini CLI configuration：https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/get-started/configuration.md
- Gemini CLI tools (web search)：https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/tools/web-search.md
- Gemini CLI file system tools（read_file / PDF）：https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/tools/file-system.md
- Microsoft Learn：Codex with Azure OpenAI（`codex exec`/config）：https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/codex?view=foundry-classic
