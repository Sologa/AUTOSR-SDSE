# Codex CLI 單次對話與混合模式實作（投影片式整合）

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

- 最後驗證日期：2026-01-13
- Codex CLI 版本：OpenAI Codex v0.79.0
- 版本來源：`docs/codex/test-keywords/outputs/20260112_213838/codex_keywords.json`

> ⚠️ **重要提醒**：在 `sdse-uv` 虛擬環境中，`codex` 命令可能被另一個套件覆蓋。請使用 `/opt/homebrew/bin/codex` 或設定 `CODEX_BIN` 環境變數。

> 重述版本：本文件整合 `docs/codex/codex_cli_single_turn_report.md` 與 `docs/codex/codex_cli_implementation_report.md`，僅重排與簡化，不改變語義。
> 
> 註記：文中標示「推論」的內容沿用原報告之標註。

## 目錄

- A-1（簡報版）封面
- A-2（簡報版）範圍與前提
- A-3（簡報版）Codex exec 核心能力（重點）
- A-4（簡報版）可替換 vs 暫不替換
- A-5（簡報版）混合模式整合原則
- A-6（簡報版）建議實作層級
- A-7（簡報版）主要風險
- A-8（簡報版）推進順序（建議）
- A-9（簡報版）最小驗證清單
- A-10（簡報版）結論
- B-0（技術完整版）說明
- B-1（技術完整版）單次對話報告：標題頁
- B-1.1 官方已明確的單次對話（codex exec）用法
- B-1.1.1 單次對話入口與 Prompt 來源
- B-1.1.2 結構化輸出與輸出控制
- B-1.1.3 沙箱與權限
- B-1.1.4 連網（Web Search）
- B-1.1.5 認證（CI/非互動）
- B-1.2 單次對話 Prompt 的實際寫法（示例）
- B-1.2.1 直接傳入單句 Prompt（推論）
- B-1.2.2 從 stdin 讀取 Prompt（推論）
- B-1.2.3 產出結構化 JSON（推論）
- B-1.3 與現有 pipeline 的混合模式映射（推論）
- B-1.3.1 可直接改為 codex exec 的步驟（推論）
- B-1.3.2 需額外處理才可改用 codex exec 的步驟（推論）
- B-1.4 建議的最小驗證清單（推論）
- B-1.5 結論
- B-2（技術完整版）混合模式實作報告：標題頁
- B-2.0 範圍與依據
- B-2.0.1 範圍
- B-2.0.2 依據（repo 內）
- B-2.0.3 依據（外部）
- B-2.1 現行 LLM 呼叫盤點（依實作）
- B-2.1.1 Seed rewrite
- B-2.1.2 Filter-seed
- B-2.1.3 Keywords（含 PDF）
- B-2.1.4 Criteria（web / pdf+web）
- B-2.1.5 LatteReview
- B-2.2 受保護檔案限制
- B-2.3 Codex CLI 能力與實作假設
- B-2.3.1 非互動 exec
- B-2.3.2 Web search
- B-2.3.3 認證
- B-2.4 混合模式整合策略（總覽）
- B-2.5 實作細節（逐步驟）
- B-2.5.1 Seed rewrite（可替換）
- B-2.5.2 Filter-seed（可替換）
- B-2.5.3 Keywords（含 PDF，暫不替換）
- B-2.5.4 Criteria（web / pdf+web）
- B-2.5.5 LatteReview（建議新增 Codex CLI provider）
- B-2.6 建議的檔案與 API 變更
- B-2.6.1 新增檔案
- B-2.6.2 修改檔案
- B-2.7 執行指令模板（建議）
- B-2.7.1 Seed rewrite（建議）
- B-2.7.2 Filter-seed（JSON schema，建議）
- B-2.7.3 Criteria（web-only，建議）
- B-2.8 測試與驗證
- B-2.9 風險清單
- B-2.10 推進順序（建議）

---

## A-1（簡報版）封面

- 題目：Codex CLI 單次對話（codex exec）與混合模式整合
- 目的：用投影片格式呈現「能做什麼、怎麼做、有哪些限制」
- 來源：兩份既有報告（單次對話用法 + 混合模式實作盤點）

---

## A-2（簡報版）範圍與前提

- 範圍僅涵蓋 5 個步驟：seed rewrite / filter-seed / keywords / criteria / LatteReview
- 其他 pipeline（harvest、snowball 等）維持現況
- 依據：repo 內程式碼盤點 + OpenAI Codex 官方文件
- 受保護檔案不可改動（影響可動範圍）

---

## A-3（簡報版）Codex exec 核心能力（重點）

- 非互動入口：`codex exec <PROMPT>` 或 `codex exec -`（stdin）
- 輸出控制：`--output-schema`、`--output-last-message`、`--json`
- 連網：`--search` 才會啟用 web search
- 認證：CI/非互動可用 `CODEX_API_KEY`
- 沙箱：非互動預設 read-only，可用 `--sandbox` 調整

指令示意（推論）：
```bash
codex exec "請將以下 JSON 驗證與整理..."
```

---

## A-4（簡報版）可替換 vs 暫不替換

- 可直接替換（純文字流程）：seed rewrite、filter-seed
- 暫不替換（含 PDF 或多階段流程）：keywords、criteria（pdf+web）、LatteReview
- 主要原因：PDF 讀取流程、兩階段輸出一致性、流程本身為多 reviewer

流程示意（推論）：
```text
純文字流程  -> codex exec
含 PDF / 多階段 -> 維持現有 OpenAI API
```

---

## A-5（簡報版）混合模式整合原則

1) 純文字流程優先替換（低風險）
2) 含 PDF 流程暫不替換（需額外工程）
3) LatteReview 以新 provider 接入（不動既有主幹）
4) 全程避免修改受保護檔案

---

## A-6（簡報版）建議實作層級

- 新增 Codex CLI wrapper（subprocess）
- 在 topic pipeline 加入 provider 分支
- 在 LatteReview 增加 codex provider
- 既有 parser 仍保留，確保輸出格式一致

指令示意（推論）：
```bash
cat prompt.txt | codex exec -
```

---

## A-7（簡報版）主要風險

- PDF 流程無法等價替換（缺少直接上傳通道）
- web search 無 domain allowlist（來源品質需控管）
- LatteReview 併發負載高（CLI 呼叫成本）
- Codex CLI 缺少使用量統計回傳（成本追蹤不足）

---

## A-8（簡報版）推進順序（建議）

1) seed rewrite / filter-seed（低風險、容易回退）
2) LatteReview provider（需控併發）
3) criteria web-only（需補規則與輸出一致性）
4) keywords / pdf+web（暫不替換）

---

## A-9（簡報版）最小驗證清單

- seed rewrite：能解析出至少一行片語
- filter-seed：`decision/reason/confidence` 可被既有 parser 驗證
- LatteReview：至少一篇 paper 能完整跑完並產出 `final_verdict`
- 若導入 `--search`，先確認 JSON schema 可被後續解析接受

---

## A-10（簡報版）結論

- `codex exec` 的非互動用法已明確
- 混合模式可行，但需分層落地
- 先做純文字流程，含 PDF/多階段流程需補轉換與驗證層

---

## B-0（技術完整版）說明

- 本段依原報告結構拆成多頁
- 每一頁對應原報告的一個 section/subsection
- 內容保持原意，僅整理為投影片格式

---

## B-1（技術完整版）單次對話報告：標題頁

- 文件來源：`docs/codex/codex_cli_single_turn_report.md`
- 依據：OpenAI Codex 官方文件 + repo 現況（混合模式評估）

---

## B-1.1 官方已明確的單次對話（codex exec）用法

- 本節涵蓋 1.1 ~ 1.5 的官方 CLI 行為
- 內容屬官方明確規格（非推論）

---

## B-1.1.1 單次對話入口與 Prompt 來源

- `codex exec <PROMPT>` 用於非互動執行（腳本/CI）
- `PROMPT` 可直接給字串或用 `-` 從 stdin 讀取
- 可用 `--model` 指定模型

---

## B-1.1.2 結構化輸出與輸出控制

- `--output-schema <FILE>` 套用 JSON Schema，強制輸出 JSON
- `--output-last-message`（`-o`）把最後一則訊息寫入檔案
- `--json` 輸出 JSONL 事件流
- 預設 progress/trace 到 stderr，JSONL 到 stdout 或檔案

---

## B-1.1.3 沙箱與權限

- 非互動模式預設 read-only sandbox
- 權限可用 `--sandbox` 調整
- 亦可用 `--full-auto` 提升權限

---

## B-1.1.4 連網（Web Search）

- Codex CLI 預設不啟用網路
- 需要連網檢索必須加 `--search`

---

## B-1.1.5 認證（CI/非互動）

- 非互動情境可使用 `CODEX_API_KEY`
- 且僅支援 `codex exec`

---

## B-1.2 單次對話 Prompt 的實際寫法（示例）

- 本節為合成示例（推論）
- 目的：說明非互動模式的常見輸入方式

---

## B-1.2.1 直接傳入單句 Prompt（推論）

```bash
codex exec "請將以下 JSON 驗證與整理..."
```

---

## B-1.2.2 從 stdin 讀取 Prompt（推論）

```bash
cat prompt.txt | codex exec -
```

---

## B-1.2.3 產出結構化 JSON（推論）

```bash
codex exec \
  --output-schema schemas/filter_seed.schema.json \
  --output-last-message outputs/filter_seed.json \
  "請依 schema 輸出 decision/reason/confidence..."
```

---

## B-1.3 與現有 pipeline 的混合模式映射（推論）

- 前提：僅針對 seed rewrite / filter-seed / keywords / criteria / LatteReview
- 其餘流程維持現有 API 呼叫

---

## B-1.3.1 可直接改為 codex exec 的步驟（推論）

- Seed rewrite：現行輸出多行片語，可用 codex exec 輸出行列表達式
- Filter-seed：現行輸出 decision/reason/confidence JSON，可用 `--output-schema`

---

## B-1.3.2 需額外處理才可改用 codex exec 的步驟（推論）

- Keywords（含 PDF）：CLI 未明示 PDF 附件流程；需先轉文字
- Criteria（web / pdf+web）：需自行控兩階段輸出與 JSON schema 一致性
- LatteReview：改成單次 exec 等同改變多 reviewer workflow

---

## B-1.4 建議的最小驗證清單（推論）

- `--output-schema` 驗證輸出符合既有 parser（filter-seed / seed rewrite）
- 驗證 `--output-last-message` 檔案可直接被 pipeline 讀取
- 若導入 `--search`，先驗證輸出 JSON schema 能被後續解析

---

## B-1.5 結論

- `codex exec <PROMPT>` 或 `codex exec -` 用法已明確
- 混合模式可行，但需分層落地
- 純文字流程可優先改，含 PDF/多階段流程需補轉換/驗證層

---

## B-2（技術完整版）混合模式實作報告：標題頁

- 文件來源：`docs/codex/codex_cli_implementation_report.md`
- 前提：已閱讀 repo 內程式碼（排除 sdse-uv/.venv、workspaces、test_artifacts）

---

## B-2.0 範圍與依據

- 本節涵蓋 0.1 ~ 0.3
- 說明可改動範圍與依據來源

---

## B-2.0.1 範圍

- 僅涵蓋 seed rewrite / filter-seed / keywords / criteria / LatteReview
- 其他 pipeline 步驟維持現況

---

## B-2.0.2 依據（repo 內）

- Pipeline 核心：`src/pipelines/topic_pipeline.py`
- LLM Provider：`src/utils/llm.py`（受保護）
- Keyword extractor：`src/utils/keyword_extractor.py`（受保護）
- Structured web search：`src/utils/structured_web_search_pipeline.py`
- OpenAI web search：`src/utils/openai_web_search.py`
- LatteReview：`resources/LatteReview/lattereview/*`
- CLI：`scripts/topic_pipeline.py`、`scripts/run_topic_*.sh`

---

## B-2.0.3 依據（外部）

- `codex exec` 非互動、JSONL、output schema、read-only sandbox 預設、CI 認證
- 參考 OpenAI Codex 官方文件

---

## B-2.1 現行 LLM 呼叫盤點（依實作）

- 本節涵蓋 1.1 ~ 1.5
- 目標：標出 LLM 呼叫位置與可替換面

---

## B-2.1.1 Seed rewrite

- `src/pipelines/topic_pipeline.py: SeedQueryRewriteAgent.rewrite_query()`
- 使用 `LLMService().chat(...)`
- Prompt：`resources/LLM/prompts/seed/seed_query_rewrite.md`

---

## B-2.1.2 Filter-seed

- `src/pipelines/topic_pipeline.py: filter_seed_papers_with_llm()`
- 使用 `LLMService().chat(...)`
- Prompt：`resources/LLM/prompts/filter_seed/llm_screening.md`
- 必要時用 fallback prompt

---

## B-2.1.3 Keywords（含 PDF）

- 入口：`src/pipelines/topic_pipeline.py: extract_keywords_from_seed_pdfs()`
- LLM 呼叫：`src/utils/keyword_extractor.py: extract_search_terms_from_surveys()`
  - `LLMService.read_pdf(...)` 逐篇讀 PDF
  - `LLMService.chat(...)` 做 aggregate

---

## B-2.1.4 Criteria（web / pdf+web）

- 入口：`src/pipelines/topic_pipeline.py: generate_structured_criteria()`
- Web path：`src/utils/structured_web_search_pipeline.py` -> `openai_web_search`
- PDF background：`LLMService.read_pdfs(...)`
- Formatter：`LLMService.chat(...)` 產 JSON

---

## B-2.1.5 LatteReview

- 入口：`src/pipelines/topic_pipeline.py: run_latte_review()`
- 使用 `resources/LatteReview/lattereview/providers/openai_provider.py`
- 非 `LLMService`

---

## B-2.2 受保護檔案限制

- 受保護檔案不可改：
  - `src/utils/llm.py`
  - `src/utils/keyword_extractor.py`
  - `src/utils/env.py`
  - `src/utils/paper_downloaders.py`
  - `src/utils/paper_workflows.py`
- 直接結論：
  - 無法在 `LLMService` 內加新 provider
  - 若導入 Codex CLI 必須在 pipeline 層或 LatteReview provider 層新增路徑

---

## B-2.3 Codex CLI 能力與實作假設

- 本節涵蓋 3.1 ~ 3.3
- 用於界定可替換的 API 能力範圍

---

## B-2.3.1 非互動 exec

- `codex exec` 適用於 CI/腳本
- 預設 read-only sandbox
- 可輸出 JSONL、支援 `--output-schema` 與 `-o`

---

## B-2.3.2 Web search

- `codex exec --search` 可啟用 web search
- 無 `allowed_domains` 對等參數（能力差異）

---

## B-2.3.3 認證

- CI/exec 模式可用 `CODEX_API_KEY`

---

## B-2.4 混合模式整合策略（總覽）

- 原則：
  1) 純文字流程優先替換（seed rewrite / filter-seed）
  2) 含 PDF 流程暫不替換（keywords / criteria pdf+web）
  3) LatteReview 以新 provider 接入
  4) 全程避免修改受保護檔案
- 建議的實作層級：
  - Codex CLI wrapper（subprocess）
  - topic pipeline provider 分支
  - LatteReview provider

---

## B-2.5 實作細節（逐步驟）

- 本節涵蓋 5.1 ~ 5.5
- 逐步驟說明替換策略與限制

---

## B-2.5.1 Seed rewrite（可替換）

- 現況：`SeedQueryRewriteAgent.rewrite_query()` 用 `LLMService.chat()`
- 建議：
  - `topic_pipeline.py` 新增 `use_codex_cli` 或 `provider="codex-cli"` 分支
  - 新增 `codex_exec(...)` wrapper（例如 `src/utils/codex_cli.py`）
  - 用既有 `_build_seed_rewrite_prompt()` 產 prompt；`codex exec -` 讀 stdin
  - 仍用 `_parse_seed_rewrite_phrase()` 解析
- 預期輸出：不改 `seed_rewrite.json` 結構

---

## B-2.5.2 Filter-seed（可替換）

- 現況：`filter_seed_papers_with_llm()` 用 `LLMService.chat()`
- 建議：
  - 新增 `provider == "codex-cli"` 分支
  - `--output-schema` 強制輸出：`decision/reason/confidence`
  - `--output-last-message` 直接落盤，再用 `_parse_decision_payload()` 驗證
  - fallback prompt 同樣走 codex exec
- 注意：不得新增 offline fallback，失敗直接報錯

---

## B-2.5.3 Keywords（含 PDF，暫不替換）

- 原因：
  - `keyword_extractor.py` 為受保護檔案
  - 依賴 `LLMService.read_pdf()`
  - CLI 未提供 PDF 上傳；若改成「PDF 轉文字」需新增解析與依賴
- 結論：維持現行 OpenAI API 路徑

---

## B-2.5.4 Criteria（web / pdf+web）

- web-only 可評估：
  - 新增 `--criteria-provider codex-cli`
  - 走 `codex exec --search`
  - 需維持兩階段輸出與 JSON schema 一致性
  - `allowed_domains` 無 CLI 對應參數（需 prompt 補強，推論/風險）
- pdf+web 暫不替換：
  - 依賴 `LLMService.read_pdfs()`
  - 改寫需新增 PDF 抽取器與 formatting pipeline

---

## B-2.5.5 LatteReview（建議新增 Codex CLI provider）

- 現況：`openai_provider.py` 直接呼叫 OpenAI SDK
- 建議：新增 `codex_cli_provider.py`
  - 實作 `get_response()` / `get_json_response()`
  - `asyncio.create_subprocess_exec()` 執行 `codex exec`
  - `response_format` 若為 dict 或 Pydantic，轉成 JSON Schema 給 `--output-schema`
  - 回傳 text/JSON + cost placeholder
- 併發限制：`max_concurrent_requests=50` 建議先降 5–10

---

## B-2.6 建議的檔案與 API 變更

- 本節涵蓋 6.1 ~ 6.2
- 說明新增與修改檔案清單

---

## B-2.6.1 新增檔案

- `src/utils/codex_cli.py`
  - 封裝 `codex exec` 呼叫、stdout/stderr 收集、timeout、JSON 解析
- `resources/LatteReview/lattereview/providers/codex_cli_provider.py`
  - LatteReview provider 介面實作

---

## B-2.6.2 修改檔案

- `src/pipelines/topic_pipeline.py`
  - seed rewrite / filter-seed 增加 provider 分支
  - criteria 增加 codex-cli 選項（僅 web 模式）
- `scripts/topic_pipeline.py`
  - 新增 CLI 參數：`--seed-provider`、`--filter-provider`、`--criteria-provider`、`--review-provider`
- `resources/LatteReview/lattereview/providers/__init__.py`
  - 匯出 `CodexCLIProvider`

---

## B-2.7 執行指令模板（建議）

- 本節涵蓋 7.1 ~ 7.3
- 屬流程示意（推論）

---

## B-2.7.1 Seed rewrite（建議）

```bash
codex exec - \
  --model gpt-5.2 \
  --sandbox read-only \
  --ask-for-approval never \
  --output-last-message /tmp/seed_rewrite.txt
```

---

## B-2.7.2 Filter-seed（JSON schema，建議）

```bash
codex exec - \
  --model gpt-5-mini \
  --sandbox read-only \
  --ask-for-approval never \
  --output-schema resources/schemas/filter_seed.schema.json \
  -o /tmp/filter_seed.json
```

---

## B-2.7.3 Criteria（web-only，建議）

```bash
codex exec - \
  --search \
  --model gpt-5.2-chat-latest \
  --sandbox read-only \
  --ask-for-approval never \
  -o /tmp/criteria_notes.txt
```

---

## B-2.8 測試與驗證

- 最小驗證：
  - Seed rewrite：能解析出至少一行片語
  - Filter-seed：`decision/reason/confidence` 符合 `_parse_decision_payload()`
  - LatteReview：至少一篇 paper 能走完整 workflow 並產出 `final_verdict`
- 文件補充（建議）：
  - `docs/codex/` 加入使用說明與參數表
  - `docs/pipelines/` 補充 codex-cli provider 行為差異

---

## B-2.9 風險清單

- PDF 流程無法等價替換
- web search 無 domain allowlist
- LatteReview 併發負載高
- Codex CLI 無 token/cost 回傳

---

## B-2.10 推進順序（建議）

1) seed rewrite / filter-seed
2) LatteReview 新 provider
3) criteria web-only
4) keywords / pdf+web 暫不替換
