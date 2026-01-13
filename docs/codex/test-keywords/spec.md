# Feature Specification: Codex/Gemini CLI Keywords Smoke Test (docs/codex/test-keywords)

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

**Feature Branch**: `[docs-codex-test-keywords-cli]`  
**Created**: 2026-01-12  
**Status**: Draft  
**Input**: User description: "請先依 docs/codex/test-review 風格補齊 spec.md / plan.md / tasks.md / runner / schema；然後先確定 Codex CLI 的 PDF 輸入策略（是否允許 PDF→text 前處理依賴），指定要用的 topic 與 PDF 範例集合，先做 Gemini CLI 的 PDF 讀取實測。"

## Execution Flow (main)
```
1. 解析 Input 並萃取：目標資料來源、CLI 供應商、輸出位置
2. 將不明確之處標示為 [NEEDS CLARIFICATION]
3. 產出 User Scenarios 與 Requirements
4. 定義 Key Entities（僅描述資料與關係）
5. Review Checklist 自檢
6. 輸出 spec
```

---

## User Scenarios & Testing (mandatory)

### Primary User Story
作為維護者，我要在不修改正式 pipeline 的前提下，以 Codex CLI / Gemini CLI 讀取 seed PDFs 並產生 keywords 結構化輸出，所有結果寫入 `docs/codex/test-keywords/` 以驗證 CLI 可行性與 PDF 讀取能力。本測試固定主題為 `discrete audio tokens more than a survey`，workspace 為 `workspaces/discrete_audio_tokens_more_than_a_survey/`。

### Acceptance Scenarios
1. **Given** `workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/arxiv/2502.06490.pdf` 存在，**When** 執行 Gemini keywords runner，**Then** 在 `docs/codex/test-keywords/outputs/<run_id>/` 產出 `gemini_keywords.json`，包含 `anchor_terms`、`search_terms`、`papers[*].detected_keywords`。
2. **Given** 已提供對應 PDF 的純文字輸入（PDF→text），**When** 執行 Codex keywords runner，**Then** 在 `docs/codex/test-keywords/outputs/<run_id>/` 產出 `codex_keywords.json` 且 JSON 符合 schema。
3. **Given** 未允許或未提供 PDF→text 前處理，**When** 執行 Codex keywords runner，**Then** runner 必須明確報錯並停止。
4. **Given** 任一 runner 成功執行，**When** 完成輸出，**Then** `run_manifest.json` 必須記錄輸入 PDF、prompt 路徑、CLI 命令與 tool policy。
5. **Given** Gemini runner 預設禁用 `google_web_search`，**When** 執行 runner，**Then** `run_manifest.json` 需記錄實際 tool policy。

### Edge Cases
- PDF 清單少於預期數量時，輸出應標記實際使用數量。
- PDF 檔名無法解析 arXiv id 時，流程必須停止並回報錯誤。
- `codex` 或 `gemini` CLI 不可用時，流程必須回報錯誤並停止。
- Gemini CLI 回傳 JSON 缺少 `response` 時，流程必須回報錯誤。

---

## Requirements (mandatory)

### Functional Requirements
- **FR-001**：系統 MUST 提供可手動執行的 keywords 測試入口，且輸出寫入 `docs/codex/test-keywords/outputs/<run_id>/`。
- **FR-002**：系統 MUST 使用 `resources/LLM/prompts/keyword_extractor/generate_search_terms.md` 作為提示模板。
- **FR-003**：系統 MUST 以 `workspaces/discrete_audio_tokens_more_than_a_survey/seed/downloads/arxiv/` 作為預設輸入來源，可限制筆數。
- **FR-004**：輸出 MUST 包含 `anchor_terms`、分類化 `search_terms`、與 `papers[*].detected_keywords`。
- **FR-005**：輸出 MUST 保留每篇 paper 的 `title`/`abstract`，且內容需對齊 metadata。
- **FR-006**：系統 MUST 產出 `keywords_response.schema.json`、`keywords_output.schema.json`、`run_manifest.schema.json`。
- **FR-007**：Gemini runner MUST 支援 `--gemini-allow-web-search` 並記錄 tool policy。
- **FR-008**：Codex runner MUST 支援 `--codex-extra-arg`，預設關閉 `web_search_request`。
- **FR-009**：系統 MUST 在啟動時載入 repo `.env`。
- **FR-010**：Codex runner MUST 支援 PDF→text 前處理輸入；前處理依賴採用 `pdfplumber`。若未允許或未提供，必須明確報錯。
- **FR-011**：系統 MUST 不修改 `src/` 與正式 pipeline。
- **FR-012**：PDF→text 產出的純文字 MUST 保存於 `docs/codex/test-keywords/outputs/<run_id>/`，每個 PDF 對應一個獨立文字檔，檔名沿用 PDF 檔名（例如 `2502.06490.txt`）。
- **FR-013**：PDF→text 抽取範圍 MUST 為全文。
- **FR-014**：Codex CLI `--output-schema` 必須使用 `search_terms` 陣列格式（`{category, terms}`）以符合嚴格 schema；runner 必須轉換回 `search_terms` 物件格式再寫入輸出。
- **FR-015**：Runner 必須對 `search_terms` 做最小正規化（去除 `_`、限制為 1–3 字詞、去重），以符合提示詞約束。
- **FR-016**：Runner 必須確保 `search_terms` 總術語數量不超過 `max_queries`。

### Key Entities (include if feature involves data)
- **KeywordSource**：輸入 PDF 清單與對應 arXiv metadata。
- **KeywordPrompt**：由 prompt 模板與 metadata 組成的 CLI 輸入。
- **KeywordPayload**：`anchor_terms`、`search_terms`、`papers[*].detected_keywords` 的結構化結果。
- **RunManifest**：輸入來源、prompt 路徑、CLI 命令與輸出檔案清單。

---

## Open Questions
（無）

---

## Review & Acceptance Checklist

### Content Quality
- [ ] 無實作細節（語言/框架/檔案結構）
- [ ] 專注使用者需求與驗證目標
- [ ] User Scenarios 完整且可測
- [ ] 需求條款皆可測試

### Requirement Completeness
- [ ] 無未解 [NEEDS CLARIFICATION]
- [ ] 成功條件可量化
- [ ] 範圍界線清楚（不改正式 pipeline）
- [ ] 依賴與限制已揭露

---

## Execution Status
- [ ] User description parsed
- [ ] Ambiguities marked
- [ ] User scenarios defined
- [ ] Requirements generated
- [ ] Entities identified
- [ ] Review checklist passed
