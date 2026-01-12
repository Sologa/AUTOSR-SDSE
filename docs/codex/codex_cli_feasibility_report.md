# Codex/Gemini CLI 可行性報告（基於 repo 現況）

## 範圍與依據

### 範圍
- 僅評估在現行 pipeline API 呼叫之外，以 Codex CLI / Gemini CLI 執行任務的可行性。
- 主要對象：seed rewrite、filter-seed、keywords、criteria、LatteReview。

### 依據與檢核方式（repo 內）
- Pipeline 交接與流程：`docs/pipelines/pipeline_handoff.md`、`docs/pipelines/topic_cli_pipeline.md`、`docs/pipelines/topic_cli_pipeline_overview.md`
- 主要程式碼：`src/pipelines/topic_pipeline.py`、`src/utils/llm.py`、`src/utils/keyword_extractor.py`、`src/utils/structured_web_search_pipeline.py`
- Codex/Gemini CLI 測試與規格：`docs/codex/codex_cli_single_turn_report.md`、`docs/codex/codex_cli_implementation_report.md`、`docs/codex/test/README.md`、`docs/codex/test/REVIEW_REPORT.md`、`docs/codex/test/review_cli_utils.py`
- 受保護檔案：`docs/agent-protected-files.md`

### 外部查詢動機與渠道
- Codex CLI 非互動模式與輸出旗標：`https://developers.openai.com/codex/noninteractive/`
- Codex CLI sandbox/approval 安全設定：`https://developers.openai.com/codex/security`
- Codex CLI config reference（含 web_search_request 與 sandbox_mode）：`https://developers.openai.com/codex/config-reference`
- Gemini CLI headless 與 JSON 輸出：`https://github.com/google-gemini/gemini-cli`、`https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/cli/headless.md`
- 失敗來源：`https://platform.openai.com/docs/guides/codex` 回傳 403，內容無法確定

---

## 現行架構與進度（摘要）
- 主流程由 `scripts/topic_pipeline.py` 串接，核心邏輯在 `src/pipelines/topic_pipeline.py`。
- 主要階段：seed →（可選）filter-seed → keywords → harvest →（可選）criteria →（可選）LatteReview →（可選）迭代式 snowball。
- `keywords` 與 `criteria (pdf+web)` 依賴 `LLMService.read_pdf(s)` 讀取 PDF。
- LatteReview 使用 `resources/LatteReview` 的 OpenAI provider，非 `LLMService`。
- 受保護檔案不可修改：`src/utils/llm.py`、`src/utils/keyword_extractor.py` 等（見 `docs/agent-protected-files.md`）。

---

## docs/codex 現況
- `docs/codex/test` 已提供可手動執行的 Codex/Gemini CLI smoke test：
  - `docs/codex/test/run_codex_single.py`
  - `docs/codex/test/run_gemini_single.py`
  - `docs/codex/test/run_full_workflow.py`
- 已有實測輸出：`docs/codex/test/outputs/20260110_090000/`，並通過 validator。
- `docs/codex/test/config.md` 規範 `CODEX_HOME` 與 repo-local `.codex/config.toml`。

---

## CLI 可行性矩陣

| 階段 | 可行性結論 | 依據 |
| --- | --- | --- |
| Seed rewrite | 可行 | 純文字輸入/輸出，既有 `_parse_seed_rewrite_phrase` 可維持解析規格；不需修改受保護檔案（`src/pipelines/topic_pipeline.py`）。 |
| Filter-seed | 可行 | 可用 `codex exec --output-schema` 或 `gemini --output-format json` 產 JSON；既有 `_parse_decision_payload` 可直接沿用。 |
| Keywords | 不可等價替換 | 依賴 PDF 讀取與 `src/utils/keyword_extractor.py`（受保護）；CLI 無外部證據支援 PDF 直傳。 |
| Criteria（web-only） | 有條件 | 需重建兩階段 prompt 與驗證規則；CLI web search 旗標與 domain allowlist 的支援度無法確定（外部來源未明示）。 |
| Criteria（pdf+web） | 不可等價替換 | 依賴 `LLMService.read_pdfs`；CLI PDF 讀取無外部依據。 |
| LatteReview | 有條件 | 可新增 CLI provider 或使用 `docs/codex/test` 既有 runner；需節流併發。 |

---

## 建議落地順序
1) Seed rewrite / filter-seed：在 `src/pipelines/topic_pipeline.py` 增加 CLI 分支，維持現有 parser 與輸出格式。
2) LatteReview：新增 CLI provider 或包裝 `docs/codex/test/review_cli_utils.py`，並降低並發。
3) Criteria（web-only）：在確認 CLI web search 能力與輸出一致性後再投入。

---

## 風險與限制
- **CLI web search 能力無法確定**：外部來源僅說明 config `features.web_search_request`，未提供 CLI 旗標與 allowlist 對等機制。
- **PDF 流程不可等價**：keywords / criteria(pdf+web) 依賴 PDF，CLI 無外部證據支援。
- **成本/用量統計缺口（推論）**：CLI 輸出未必包含可供 `LLMUsageTracker` 記錄的 token/cost 欄位。
- **併發成本（推論）**：CLI 子程序呼叫在高並發下會增加延遲與資源成本。

---

## 驗證策略（最小集合）
- Seed rewrite：輸出至少 1 行片語，且可被 `_parse_seed_rewrite_phrase` 接受。
- Filter-seed：JSON 僅含 decision/reason/confidence，且可被 `_parse_decision_payload` 接受。
- LatteReview：至少 1 篇 paper 走完完整流程並產生 `final_verdict`。
- 使用現有工具驗證：`docs/codex/test/validate_review_output.py`、`docs/codex/test/validate_run_manifest.py`。

---

## 外部來源
- OpenAI Codex 非互動模式：`https://developers.openai.com/codex/noninteractive/`
- OpenAI Codex 安全與 sandbox：`https://developers.openai.com/codex/security`
- OpenAI Codex 設定參考：`https://developers.openai.com/codex/config-reference`
- Gemini CLI README：`https://github.com/google-gemini/gemini-cli`
- Gemini CLI headless 模式：`https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/cli/headless.md`
- 失敗來源（403）：`https://platform.openai.com/docs/guides/codex`
