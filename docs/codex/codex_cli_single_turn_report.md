# Codex CLI 單次對話（codex exec）與混合模式評估報告

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

- 最後驗證日期：2026-01-13
- Codex CLI 版本：OpenAI Codex v0.79.0
- 版本來源：`docs/codex/test-keywords/outputs/20260112_213838/codex_keywords.json`

> ⚠️ **重要提醒**：在 `sdse-uv` 虛擬環境中，`codex` 命令可能被另一個套件覆蓋。請使用 `/opt/homebrew/bin/codex` 或設定 `CODEX_BIN` 環境變數。

> 本報告依據 OpenAI 官方 Codex 文件整理單次對話（non-interactive）用法，並結合 repo 現況提出混合模式評估。外部來源僅使用 OpenAI 官方文件。
> 外部來源（OpenAI 官方）：
> - https://developers.openai.com/codex/noninteractive
> - https://developers.openai.com/codex/models
> - https://developers.openai.com/codex/security
> - https://developers.openai.com/codex/config-reference

## 1) 官方已明確的單次對話（codex exec）用法

### 1.1 單次對話的入口與 Prompt 來源
- `codex exec <PROMPT>` 用於非互動執行（腳本/CI），官方示例以命令列字串作為 prompt。https://developers.openai.com/codex/noninteractive
- 可用 `--model`/`-m` 指定模型（包含 `codex exec`）。https://developers.openai.com/codex/models

### 1.2 結構化輸出與輸出控制
- `--output-schema <FILE>` 可套用 JSON Schema；`--output-last-message`（`-o`）可把最後一則訊息寫入檔案。https://developers.openai.com/codex/noninteractive
- `--json` 會輸出 JSON Lines（JSONL）事件流以供腳本消費。https://developers.openai.com/codex/noninteractive

### 1.3 沙箱與權限
- `codex exec` 的非互動模式預設在 **read‑only sandbox** 執行；可用 `--sandbox` 或 `--full-auto` 調整權限。https://developers.openai.com/codex/noninteractive
- Sandbox/approval 規範請依官方安全文件。https://developers.openai.com/codex/security

### 1.4 連網（Web Search）
- Web search 工具開關可透過 `features.web_search_request` 設定。https://developers.openai.com/codex/config-reference

### 1.5 認證（CI/非互動）
- 非互動情境可使用 `CODEX_API_KEY`。https://developers.openai.com/codex/noninteractive

## 2) 單次對話 Prompt 的實際寫法（示例）

> 以下為使用方式示例，屬於 CLI 使用方式的合成示例（推論）。

### 2.1 直接傳入單句 Prompt
```bash
codex exec "請將以下 JSON 驗證與整理..."
```

### 2.2 指定模型
```bash
codex exec --model gpt-5.1 "請將以下 JSON 驗證與整理..."
```

### 2.3 產出結構化 JSON
```bash
codex exec \
  --output-schema schemas/filter_seed.schema.json \
  --output-last-message outputs/filter_seed.json \
  "請依 schema 輸出 decision/reason/confidence..."
```

## 3) 與現有 pipeline 的混合模式映射（推論）

> 前提：僅針對 **seed rewrite / filter-seed / keywords / criteria / LatteReview** 五個步驟。其餘仍維持現有 API 呼叫。

### 3.1 可直接改為 `codex exec` 的步驟（文字輸入/輸出）
- **Seed rewrite**：現行輸出為多行片語（`SeedQueryRewriteAgent`）；可用 `codex exec` 讀 prompt 模板並輸出行列表達式。
- **Filter‑seed**：現行輸出 `decision/reason/confidence` JSON；可用 `--output-schema` 強制格式一致並直接落盤。

### 3.2 需額外處理才可改用 `codex exec` 的步驟
- **Keywords（含 PDF）**：CLI 文件僅明示圖像附件與文字 prompt；未見 PDF 附件流程。若要用 `codex exec`，需先將 PDF 轉成純文字再輸入（推論）。
- **Criteria（web / pdf+web）**：若要用 web search，需先確認 `features.web_search_request` 設定並補足來源與 schema 驗證（推論）。
- **LatteReview**：現行為多 reviewer workflow；改成單次 `codex exec` 等同改變流程（需重設 prompt 與合併規則）（推論）。

## 4) 建議的最小驗證清單（推論）
- 用 `codex exec --output-schema` 驗證輸出是否完全符合現有 parser（`filter_seed` 與 `seed rewrite`）。
- 驗證 `--output-last-message` 的檔案內容是否可直接被現有 pipeline 讀取。
- 若要啟用 web search，先確認 `features.web_search_request` 與輸出 schema 的相容性。

## 5) 結論
- **單次對話 Prompt 的官方用法已明確**：`codex exec <PROMPT>` 可搭配 `--output-schema` 與 `--output-last-message` 落盤結果。https://developers.openai.com/codex/noninteractive
- **混合模式可行，但需分層落地**：純文字流程可優先改成 `codex exec`；含 PDF 或多階段 structured 的流程需先補上轉換/驗證層（推論）。
