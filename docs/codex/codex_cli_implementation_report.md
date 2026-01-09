# Codex CLI 混合模式實作報告（基於全量程式碼盤點）

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
- Codex CLI 非互動模式、JSONL、output schema、read‑only sandbox 預設、CI 認證（`CODEX_API_KEY`）等規格，參考 OpenAI Codex 官方文件（詳見既有報告與下方實作假設）。

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
- `src/utils/keyword_extractor.py`

**直接結論**：
- 無法在 `LLMService` 內加新 provider，不能改 `keyword_extractor.py` 的 PDF LLM 邏輯。
- 若要導入 Codex CLI，必須在 **pipeline 層**或 **LatteReview provider 層**新增路徑，避免修改受保護檔案。

## 3) Codex CLI 能力與實作假設（與前一份報告一致）

### 3.1 非互動 exec
- `codex exec` 適用於 CI/腳本，預設 read‑only sandbox；可輸出 JSONL、支援 `--output-schema` 與 `-o` 落盤。

### 3.2 web search
- `codex exec --search` 可啟用 web search 工具，但沒有與現行 `WebSearchOptions.allowed_domains` 對等的參數（屬於能力差異）。

### 3.3 認證
- CI/exec 模式可用 `CODEX_API_KEY`。

## 4) 混合模式整合策略（總覽）

**原則**
1) **純文字流程優先替換**（seed rewrite / filter-seed）。
2) **含 PDF 流程暫不替換**（keywords / criteria pdf+web），維持 OpenAI API。
3) **LatteReview 以新 provider 接入**，不動 `LLMService`。
4) 全程避免修改受保護檔案。

**建議的實作層級**
- 新增 **Codex CLI wrapper**（Python subprocess）
- 在 `topic_pipeline.py` 加入 **codex 分支**
- 在 LatteReview 新增 **codex provider**

## 5) 實作細節（逐步驟）

### 5.1 Seed rewrite（可替換）

**現況**：`SeedQueryRewriteAgent.rewrite_query()` 使用 `LLMService.chat()`。

**建議做法**：
- 在 `src/pipelines/topic_pipeline.py` 內新增 `use_codex_cli` 或 `provider="codex-cli"` 分支。
- 實作 `codex_exec(prompt, *, model, output_schema_path=None, output_path=None, search=False, sandbox="read-only")` wrapper（新檔案，例如 `src/utils/codex_cli.py`）。
- 使用既有 `_build_seed_rewrite_prompt()` 產生 prompt，然後 `codex exec -` 讀 stdin。
- 仍使用既有 `_parse_seed_rewrite_phrase()` 解析結果，確保規格一致。

**預期輸出**：不改 `seed_rewrite.json` 結構。

### 5.2 Filter‑seed（可替換）

**現況**：`filter_seed_papers_with_llm()` 使用 `LLMService.chat()` 回傳 JSON，再由 `_parse_decision_payload()` 驗證。

**建議做法**：
- 在 `filter_seed_papers_with_llm()` 中新增 `provider == "codex-cli"` 分支。
- 使用 `--output-schema` 強制輸出：
  ```json
  {"decision": "yes|no", "reason": "string", "confidence": 0~1}
  ```
- `--output-last-message` 直接落盤；再用 `_parse_decision_payload()` 驗證。
- fallback prompt 同樣可走 codex exec。

**注意**：不得新增 offline fallback；失敗時應直接報錯（符合專案規則）。

### 5.3 Keywords（含 PDF，暫不替換）

**原因**：
- `keyword_extractor.py` 為受保護檔案，且內部依賴 `LLMService.read_pdf()`。
- Codex CLI **未提供 PDF 上傳能力**；若改成「本地 PDF 轉文字再 prompt」，需要新增解析程式與依賴，且屬行為改寫。

**結論**：維持現行 OpenAI API 路徑。

### 5.4 Criteria（web / pdf+web）

**web-only 方案（可評估）**
- 可新增 `--criteria-provider codex-cli`，走 `codex exec --search`。
- 需要自行維持兩階段（notes -> formatter）與 JSON schema 一致性。
- `allowed_domains` / `tool_type` 等目前無 CLI 對應參數，需在 prompt 中補強規則（屬推論與風險）。

**pdf+web 方案（暫不替換）**
- 目前依賴 `LLMService.read_pdfs()`（OpenAI Responses API）。
- 改寫需新增 PDF 文本抽取器與新的 formatting pipeline，規模較大。

### 5.5 LatteReview（建議新增 Codex CLI provider）

**現況**：`resources/LatteReview/lattereview/providers/openai_provider.py` 直接呼叫 OpenAI SDK。

**建議**：新增 `codex_cli_provider.py`：
- 實作與 `OpenAIProvider` 同介面的 `get_response()`、`get_json_response()`。
- 內部使用 `asyncio.create_subprocess_exec()` 執行 `codex exec`。
- 若 `response_format` 為 dict 或 Pydantic schema，直接生成 JSON Schema 給 `--output-schema`。
- 回傳時保留原流程所需欄位（text/JSON + cost placeholder）。

**併發限制**：
- LatteReview `max_concurrent_requests=50` 對 CLI 可能過高；建議先降至 5–10。

## 6) 建議的檔案與 API 變更（不觸碰受保護檔案）

### 6.1 新增檔案
- `src/utils/codex_cli.py`
  - 封裝 `codex exec` 呼叫、stdout/stderr 收集、timeout、JSON 解析。
- `resources/LatteReview/lattereview/providers/codex_cli_provider.py`
  - LatteReview provider 介面實作。

### 6.2 修改檔案
- `src/pipelines/topic_pipeline.py`
  - seed rewrite / filter-seed 增加 provider 分支。
  - criteria 增加 codex-cli 選項（僅 web 模式）。
- `scripts/topic_pipeline.py`
  - 新增 CLI 參數：`--seed-provider`、`--filter-provider`、`--criteria-provider`、`--review-provider`。
- `resources/LatteReview/lattereview/providers/__init__.py`
  - 匯出 `CodexCLIProvider`。

## 7) 執行指令模板（建議）

> 以 read-only 為預設；若需要寫檔，改用 `--sandbox workspace-write`。

### 7.1 Seed rewrite
```bash
codex exec - \
  --model gpt-5.2 \
  --sandbox read-only \
  --ask-for-approval never \
  --output-last-message /tmp/seed_rewrite.txt
```

### 7.2 Filter‑seed（JSON schema）
```bash
codex exec - \
  --model gpt-5-mini \
  --sandbox read-only \
  --ask-for-approval never \
  --output-schema resources/schemas/filter_seed.schema.json \
  -o /tmp/filter_seed.json
```

### 7.3 Criteria（web-only）
```bash
codex exec - \
  --search \
  --model gpt-5.2-chat-latest \
  --sandbox read-only \
  --ask-for-approval never \
  -o /tmp/criteria_notes.txt
```

## 8) 測試與驗證

**最小驗證**
- Seed rewrite：能解析出至少一行片語。
- Filter‑seed：`decision/reason/confidence` 符合 `_parse_decision_payload()`。
- LatteReview：至少一篇 paper 能走完整 workflow 並產出 `final_verdict`。

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
