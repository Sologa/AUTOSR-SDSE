# Codex CLI 混合模式實作報告（基於全量程式碼盤點）

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。
> 補充：上述規範僅適用 `docs/codex/test-*` 手動測試；正式 pipeline 與 CI 請以 `AGENTS.md` 為準（包含 API key 與測試政策）。

- 最後驗證日期：2026-01-13
- Codex CLI 版本：OpenAI Codex v0.79.0
- 版本來源：`docs/codex/test-keywords/outputs/20260112_213838/codex_keywords.json`

> ⚠️ **重要提醒**：在 `sdse-uv` 虛擬環境中，`codex` 命令可能被另一個 Python 套件（codex-reader）覆蓋。請使用完整路徑 `/opt/homebrew/bin/codex` 或設定環境變數 `export CODEX_BIN=/opt/homebrew/bin/codex`。程式碼中的 `resolve_codex_bin()` 函數會自動處理此問題。

> 本報告在「已閱讀 repo 內全部程式碼檔案（*.py, *.sh，排除 sdse-uv/.venv、workspaces、test_artifacts）」的前提下撰寫，並以 `docs/codex/codex_cli_single_turn_report.md` 為前置基礎。

## 0) 範圍與依據

### 0.1 範圍
- 僅涵蓋：**seed rewrite / filter-seed / keywords / criteria / LatteReview** 五個步驟。
- 其餘 pipeline 步驟（harvest、snowball 等）維持現況不動。

### 0.2 依據（repo 內）
- Pipeline 核心：`src/pipelines/topic_pipeline.py`
- LLM Provider 層：`src/utils/llm.py`（受保護檔案）
- Keyword extractor：`src/utils/keyword_extractor.py`（受保護檔案）
- Structured web search：`src/utils/structured_web_search_pipeline.py`
- OpenAI web search：`src/utils/openai_web_search.py`
- LatteReview：`resources/LatteReview/lattereview/*`
- CLI：`scripts/topic_pipeline.py`、`scripts/run_topic_*.sh`

### 0.3 依據（外部）
- OpenAI Python SDK README（Responses API 呼叫方式，對應 `src/utils/llm.py`）：https://raw.githubusercontent.com/openai/openai-python/main/README.md
- Codex CLI 非互動模式（`codex exec` / JSONL / output schema / sandbox / CODEX_API_KEY）：https://developers.openai.com/codex/noninteractive
- Codex CLI 模型選擇（`--model`/`-m`）：https://developers.openai.com/codex/models
- Codex CLI sandbox/approval：https://developers.openai.com/codex/security
- Codex CLI 設定參考（含 `features.web_search_request`）：https://developers.openai.com/codex/config-reference

## 1) 現行 LLM 呼叫盤點（依實作）

### 1.1 Seed rewrite
- `src/pipelines/topic_pipeline.py: SeedQueryRewriteAgent.rewrite_query()`
- 使用 `LLMService().chat(...)`，輸入由 `resources/LLM/prompts/seed/seed_query_rewrite.md` 組裝。

### 1.2 Filter-seed
- `src/pipelines/topic_pipeline.py: filter_seed_papers_with_llm()`
- 使用 `LLMService().chat(...)`，輸入由 `resources/LLM/prompts/filter_seed/llm_screening.md` 組裝；必要時用 fallback prompt。

### 1.3 Keywords（含 PDF）
- 入口：`src/pipelines/topic_pipeline.py: extract_keywords_from_seed_pdfs()`
- 真正 LLM 呼叫在 `src/utils/keyword_extractor.py: extract_search_terms_from_surveys()`
  - `LLMService.read_pdf(...)` 逐篇讀 PDF
  - `LLMService.chat(...)` 做 aggregate

### 1.4 Criteria（web / pdf+web）
- 入口：`src/pipelines/topic_pipeline.py: generate_structured_criteria()`
- Web path：`src/utils/structured_web_search_pipeline.py` -> `openai_web_search` provider
- PDF background：`LLMService.read_pdfs(...)` 讀 PDF
- Formatter：`LLMService.chat(...)` 產 JSON

### 1.5 LatteReview
- 入口：`src/pipelines/topic_pipeline.py: run_latte_review()`
- 使用 `resources/LatteReview/lattereview/providers/openai_provider.py`（Async OpenAI Chat Completions），**非** `LLMService`。

## 2) 受保護檔案限制（直接影響可改動範圍）

受保護檔案（不可改）：
- `src/utils/llm.py`
- `src/utils/keyword_extractor.py`
- `src/utils/env.py`
- `src/utils/paper_downloaders.py`
- `src/utils/paper_workflows.py`

**直接結論**：
- 無法在 `LLMService` 內加新 provider，不能改 `keyword_extractor.py` 的 PDF LLM 邏輯。
- 若要導入 Codex CLI，必須在 **pipeline 層**或 **LatteReview provider 層**新增路徑，避免修改受保護檔案。

## 3) Codex CLI 能力與實作假設（官方文件）

### 3.1 非互動 exec
- `codex exec` 用於 scripts/CI；支援 `--output-schema`、`--output-last-message`、`--json`（JSONL）。https://developers.openai.com/codex/noninteractive
- `codex exec` 預設 read-only sandbox，可用 `--sandbox`/`--full-auto` 調整。https://developers.openai.com/codex/noninteractive
- 可用 `--model`/`-m` 指定模型。https://developers.openai.com/codex/models

### 3.2 web search
- 工具開關以 `features.web_search_request` 為主，官方未提供 domain allowlist 參數。https://developers.openai.com/codex/config-reference

### 3.3 認證
- CI/非互動可用 `CODEX_API_KEY`。https://developers.openai.com/codex/noninteractive

## 4) 混合模式整合策略（總覽）

**原則**
1) **純文字流程優先替換**（seed rewrite / filter-seed）。
2) **含 PDF 流程暫不替換**（keywords / criteria pdf+web），維持 OpenAI API。
3) **LatteReview 以新 provider 接入**，不動 `LLMService`。
4) **OpenAI API 路徑保持現況**（`LLMService` 與 LatteReview OpenAI provider 不改），僅新增可切換的 codex-cli 選項。
5) 全程避免修改受保護檔案。

**建議的實作層級**
- 新增 **Codex CLI wrapper**（Python subprocess，可由 `docs/codex/test-shared/codex_cli_utils.py` 抽取/改寫）
- 在 `topic_pipeline.py` 加入 **codex 分支**
- 在 LatteReview 新增 **codex provider**

## 5) 實作細節（逐步驟）

### 5.1 Seed rewrite（可替換）

**現況**：`SeedQueryRewriteAgent.rewrite_query()` 使用 `LLMService.chat()`。

**建議做法**：
- 在 `src/pipelines/topic_pipeline.py` 內新增 `use_codex_cli` 或 `provider="codex-cli"` 分支。
- 實作 `codex_exec(prompt, *, model, output_schema_path=None, codex_extra_args=None)` wrapper（新檔案，例如 `src/utils/codex_cli.py`，可參考 `docs/codex/test-shared/codex_cli_utils.py`）。
- 使用既有 `_build_seed_rewrite_prompt()` 產生 prompt，然後 `codex exec -` 讀 stdin。
- 仍使用既有 `_parse_seed_rewrite_phrase()` 解析結果，確保規格一致。

**預期輸出**：不改 `seed_rewrite.json` 結構。

### 5.2 Filter‑seed（可替換）

**現況**：`filter_seed_papers_with_llm()` 使用 `LLMService.chat()` 回傳 JSON，再由 `_parse_decision_payload()` 驗證。

**建議做法**：
- 在 `filter_seed_papers_with_llm()` 中新增 `provider == "codex-cli"` 分支。
- 使用 `--output-schema` 強制輸出（需新增 schema 檔案）：
  ```json
  {"decision": "yes|no", "reason": "string", "confidence": 0~1}
  ```
- 從 stdout 解析 JSON，再用 `_parse_decision_payload()` 驗證。
- fallback prompt 同樣可走 codex exec。

**注意**：不得新增 offline fallback；失敗時應直接報錯（符合專案規則）。

### 5.3 Keywords（含 PDF，已導入 pipeline）

**現況**：
- pipeline 已新增 `provider=codex-cli` 支線（`src/pipelines/topic_pipeline.py: extract_keywords_from_seed_pdfs`）。
- codex-cli 走 `src/utils/codex_keywords.py`：
  - 以 `pdfplumber` 轉出 `workspaces/<topic>/keywords/codex_text/*.txt`
  - 使用 `codex exec` + `resources/schemas/keywords_response_codex.schema.json`
  - 將 `search_terms` 陣列格式轉回 `{category: [terms]}`
  - 產出 `keywords.json` 與 `keyword_cli_usage_<timestamp>.json`
- OpenAI path 維持 `gpt-5.2` + `temperature=1.0`（不變）。

**差異與限制**：
- codex-cli 目前採「單次 prompt + 多篇文字塊」形式，未執行 OpenAI path 的逐篇聚合與多重驗證流程。
- `search_terms` schema 需走陣列→dict 轉換；已在 `run_codex_cli_keywords()` 完成。
- reasoning effort 需透過 `CODEX_HOME` config（`model_reasoning_effort`）設定，pipeline 以暫時覆寫方式支援。

**結論**：CLI keywords 已在正式 pipeline 以「可切換 provider」方式導入，OpenAI 路徑保持原樣。

### 5.4 Criteria（web / pdf+web）

**web-only 方案（可評估）**
- 可新增 `--criteria-provider codex-cli`，並確保 `features.web_search_request` 允許 web search。
- 需要自行維持兩階段（notes -> formatter）與 JSON schema 一致性。
- `allowed_domains` / `tool_type` 等目前無 CLI 對應參數，需在 prompt 中補強規則（屬推論與風險）。

**pdf+web 方案（暫不替換）**
- 目前依賴 `LLMService.read_pdfs()`（OpenAI Responses API）。
- 改寫需新增 PDF 文本抽取器與新的 formatting pipeline，規模較大。

### 5.5 Review（已透過 CLI workflow 導入）

**現況**：
- pipeline 以 `run_cli_review()`（codex exec + gemini）接入 review/snowball，不依賴 LatteReview provider。
- 輸出維持 `latte_review_results.json` 相容欄位。

**後續選項**：
- 若需回到 LatteReview workflow，可再評估新增 `codex_cli_provider.py`。

## 6) 建議的檔案與 API 變更（不觸碰受保護檔案）

### 6.1 新增檔案（已落地）
- `src/utils/codex_cli.py`
  - 封裝 `codex exec` 呼叫、stdout/stderr 收集、timeout、JSON 解析（可參考 `docs/codex/test-shared/codex_cli_utils.py`）。
- `src/utils/gemini_cli.py`
  - Gemini CLI 執行與 `.gemini/settings.json` 暫時覆寫。
- `resources/schemas/review_response.schema.json`
  - review CLI `--output-schema` 使用。

### 6.2 修改檔案（已落地）
- `src/pipelines/topic_pipeline.py`
  - keywords 增加 `codex-cli` provider 分支。
  - 新增 `run_cli_review()`（codex exec + gemini）。
  - criteria 增加 reasoning effort 參數（search/formatter/pdf）。
- `scripts/topic_pipeline.py`
  - keywords/review 增加 codex-cli 相關旗標。
  - criteria 增加 reasoning effort 旗標。
- `scripts/snowball_iterate.py`
  - review provider / model / reasoning effort 旗標。

## 7) 執行指令模板（建議）

> 以下示例對齊 `docs/codex/test-shared/codex_cli_utils.py` 的最小介面；其餘旗標請以 `codex exec --help` 為準。

### 7.1 Seed rewrite
```bash
codex exec - \
  --model gpt-5.2
```

### 7.2 Filter‑seed（JSON schema，待評估）
- `resources/schemas/filter_seed.schema.json` 尚未導入；此段保留作為後續評估用。

### 7.3 Criteria（web-only）
```bash
codex exec - \
  --model gpt-5.2-chat-latest
```

## 8) 測試與驗證

**最小驗證**
- Seed rewrite：能解析出至少一行片語。
- Filter‑seed：`decision/reason/confidence` 符合 `_parse_decision_payload()`。
- Review（CLI）：至少一篇 paper 能走完整 workflow 並產出 `final_verdict`。

**建議新增測試（文件層）**
- `docs/codex/` 加入使用說明與參數表。
- `docs/pipelines/` 補充「codex-cli provider」行為差異。

## 9) 風險清單（需明確確認）

- **PDF 流程無法等價替換**：Codex CLI 未提供 PDF 上傳通道。
- **web search 無 domain allowlist**：可能影響 criteria 來源品質與規則一致性。
- **LatteReview 併發負載**：CLI 逐條呼叫成本與延遲明顯高於 SDK。
- **使用量統計缺口**：Codex CLI 無 token/cost 回傳，需另行記錄或接受缺失。

## 10) 推進順序（建議）

1) **Seed rewrite / filter-seed** 先行（低風險，易回退）。
2) **LatteReview** 新 provider（中風險，需控制併發）。
3) **Criteria web-only** 嘗試（高風險，需補足 domain 控制與規則驗證）。
4) **Keywords / pdf+web** 暫不替換（高成本）。

---

> 若你要我直接落地實作，請指定優先順序與允許修改的檔案清單（特別是受保護檔案是否放行）。
