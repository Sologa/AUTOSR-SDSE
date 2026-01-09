# Codex CLI 單次對話（codex exec）與混合模式評估報告

> 本報告依據 OpenAI 官方 Codex 文件整理單次對話（non-interactive）用法，並結合 repo 現況提出混合模式評估。外部來源僅使用 OpenAI 官方文件。

## 1) 官方已明確的單次對話（codex exec）用法

### 1.1 單次對話的入口與 Prompt 來源
- `codex exec <PROMPT>` 用於非互動執行（腳本/CI），`PROMPT` 可直接給字串或用 `-` 從 stdin 讀取。citeturn0open0
- 可用 `--model` 指定模型。citeturn0open0

### 1.2 結構化輸出與輸出控制
- `--output-schema <FILE>` 可套用 JSON Schema，強制輸出為 JSON；`--output-last-message`（`-o`）可把最後一則訊息寫入檔案。citeturn0open0
- `--json` 會輸出 JSONL 事件流；預設把 progress/trace 寫到 stderr，JSONL 寫到 stdout 或檔案。citeturn0open1

### 1.3 沙箱與權限
- `codex exec` 的非互動模式預設在 **read‑only sandbox** 執行；若要變更權限可使用 `--sandbox`（或 `--full-auto` 提升權限）。citeturn0open1

### 1.4 連網（Web Search）
- Codex CLI **預設不啟用網路**；需要連網檢索必須加 `--search`。citeturn0open2

### 1.5 認證（CI/非互動）
- 非互動情境可使用 `CODEX_API_KEY`，且**僅支援 `codex exec`**。citeturn0open1

## 2) 單次對話 Prompt 的實際寫法（示例）

> 以下為使用方式示例，屬於 CLI 使用方式的合成示例（推論）。

### 2.1 直接傳入單句 Prompt
```bash
codex exec "請將以下 JSON 驗證與整理..."
```

### 2.2 從 stdin 讀取 Prompt
```bash
cat prompt.txt | codex exec -
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
- **Criteria（web / pdf+web）**：可用 `codex exec --search` 觸發 web search，但需自行控制兩階段結構化輸出、來源欄位與 JSON schema 一致性（推論）。
- **LatteReview**：現行為多 reviewer workflow；改成單次 `codex exec` 等同改變流程（需重設 prompt 與合併規則）（推論）。

## 4) 建議的最小驗證清單（推論）
- 用 `codex exec --output-schema` 驗證輸出是否完全符合現有 parser（`filter_seed` 與 `seed rewrite`）。
- 驗證 `--output-last-message` 的檔案內容是否可直接被現有 pipeline 讀取。
- 若要導入 `--search`，先驗證輸出 JSON schema 是否能被 `structured_web_search_pipeline` 的後續解析接受。

## 5) 結論
- **單次對話 Prompt 的官方用法已明確**：`codex exec <PROMPT>` 或 `codex exec -`，可搭配 `--output-schema` 與 `--output-last-message` 落盤結果。citeturn0open0turn0open1
- **混合模式可行，但需分層落地**：純文字流程可優先改成 `codex exec`；含 PDF 或多階段 structured 的流程需先補上轉換/驗證層（推論）。

