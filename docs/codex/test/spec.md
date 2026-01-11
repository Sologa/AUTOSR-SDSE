# Feature Specification: Codex/Gemini CLI Review Smoke Test (docs/codex/test)

**Feature Branch**: `[docs-codex-test-review-cli]`  
**Created**: 2026-01-09  
**Status**: Draft  
**Input**: User description: "我想用手動執行scripts 得方式來測試上述的 codex exec 等能不能 work；我想要在 docs/codex/test/ 裡面寫檔；用模仿現在pipeline的方式來寫呼叫 api，但是 api call 替換成執行 shell command \"codex exec\" (gemini 也要)；我想讓模型跑的就是 review workspaces/discrete_audio_tokens_more_than_a_survey 裡面第一次 下載的前5篇paper的流程。來源檔指定為 arxiv_metadata.json；先測單 reviewer，再測完整流程；JuniorNano=gpt-5.1-codex-mini、JuniorMini=Gemini Pro（版本待決定）、SeniorLead=gpt-5.2；criteria 可用既有檔案；輸出命名請協助設計。"

## Execution Flow (main)
```
1. 解析 Input 並萃取：目標資料來源、要測試的 provider、輸出位置
2. 將不明確之處標示為 [NEEDS CLARIFICATION]
3. 產出 User Scenarios 與 Requirements
4. 定義 Key Entities（僅描述資料與關係）
5. Review Checklist 自檢
6. 輸出 spec
```

---

## User Scenarios & Testing (mandatory)

### Primary User Story
作為維護者，我要在不修改正式 pipeline 的前提下，手動執行測試腳本：先以單 reviewer 進行 smoke test，再以完整 workflow（JuniorNano/JuniorMini/SeniorLead）重跑；所有結果寫入 `docs/codex/test/` 以驗證 `codex exec` 與 `gemini` CLI 可行性。

### Acceptance Scenarios
1. **Given** `workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json` 存在，**When** 執行單 reviewer（JuniorNano, `codex exec`）測試腳本，**Then** 在 `docs/codex/test/outputs/<run_id>/` 產出 5 筆結構化結果，含 `evaluation` 與 `reasoning`。
2. **Given** 同一份輸入，**When** 執行單 reviewer（JuniorMini, `gemini`）測試腳本，**Then** 產出 5 筆結構化結果，欄位與 `codex exec` 版本一致。
3. **Given** 單 reviewer 測試完成，**When** 執行完整 workflow（JuniorNano + JuniorMini → SeniorLead），**Then** 產出含 `final_verdict` 或等價欄位的多 reviewer 結果。
4. **Given** criteria 檔案不存在，**When** 執行任一測試腳本，**Then** 使用與 pipeline 等價的預設 criteria 並完成輸出。
5. **Given** 預設 `./.codex/config.toml` 關閉 web search、且未額外指定 `--allow-web-search`，**When** 執行任一 `codex exec` runner，**Then** `run_manifest.json` 中的命令必須包含 `--disable web_search_request` + `-c 'tools.web_search=false'`，並在 `codex exec --json` 產生的 transcript 裡不會出現 `web_search` tool 呼叫。
5. **Given** 測試需要調整 approval/network 或使用非預設 automation，**When** 透過 `--codex-extra-arg` 及 `CODEX_HOME=$PWD/.codex`（指向 repo 內 `.codex/config.toml`），**Then** runner 能在不修改使用者全域設定的前提下執行所需 flag 並鎖定 sandbox 網路行為，且 README/plan 提供相關說明。

### Edge Cases
- 若來源資料少於 5 筆，輸出應包含實際可用筆數並明確記錄不足原因。
- 若任一 paper 缺少 `title` 或 `abstract`，輸出仍需完成且記錄缺失欄位。
- 若 `codex` 或 `gemini` CLI 不可用，需清楚回報錯誤並停止流程。
- 若 Gemini CLI 無法指定模型版本，輸出仍需記錄實際使用的 model 名稱。

---

## Requirements (mandatory)

### Functional Requirements
- **FR-001**：系統 MUST 提供可手動執行的測試入口，且所有檔案寫入 `docs/codex/test/outputs/<run_id>/`（`run_id=YYYYMMDD_HHMMSS`）。
- **FR-002**：系統 MUST 使用本機 CLI 指令 `codex exec` 進行 review 測試。
- **FR-003**：系統 MUST 使用本機 CLI 指令 `gemini` 進行 review 測試。
- **FR-004**：系統 MUST 以與現行 pipeline 一致語意的 review 提示（Title/Abstract + inclusion/exclusion criteria + 1–5 評分）產生輸入。
- **FR-005**：系統 MUST 以 `workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json` 作為來源，並採用檔案內原始順序取前 5 筆；不足 5 筆時取全部。
- **FR-006**：輸出 MUST 保留每篇 paper 的可識別欄位（例如 `arxiv_id`/`title`/`abstract`）。
- **FR-007**：輸出 MUST 為結構化格式，且包含 `evaluation` (1–5) 與 `reasoning`。
- **FR-008**：若 workspace 內不存在 criteria，MUST 套用 pipeline 的預設 criteria 文案。
- **FR-009**：系統 MUST 支援兩種執行模式：單 reviewer smoke test → 完整 workflow（兩位 junior + 一位 senior）。
- **FR-010**：模型對應 MUST 固定為：JuniorNano=`gpt-5.1-codex-mini`、JuniorMini=`Gemini Pro`、SeniorLead=`gpt-5.2`。
- **FR-011**：輸出 MUST 記錄實際使用的 Gemini model 名稱（含版本），以便確認 2.5/3 的實際行為。
- **FR-012**：runner MUST 支援 `--codex-extra-arg`，允許測試者將任意 CLI flag 插入 `codex exec`（例如 `--full-auto`），且 manifest/README 需記錄使用過的 flags 以利重現。
- **FR-013**：系統 MUST 約定一份 repo-local 的 Codex config（`CODEX_HOME=$PWD/.codex`），該配置應包含 sandbox/network 控制（例如 `network_access=false`），讓測試時可在不改動 `~/.codex/config.toml` 的情況下長期鎖網；README 或 docs 需說明如何啟用此設定。
- **FR-014**：Codex runner 預設 MUST 將 `web_search` 工具關閉（透過 repo 設定與 CLI args），並提供 `--allow-web-search` 以在特定 run 解鎖；manifest/README/命令紀錄需反映此政策。

### Key Entities (include if feature involves data)
- **ReviewSource**：代表「前 5 篇 paper」的來源檔案與排序規則。
- **ReviewItem**：單篇 paper 的基本資料（id/title/abstract/metadata）。
- **ProviderRun**：一次 CLI 呼叫（provider 名稱、模型、指令、輸出）。
- **ReviewResult**：單篇 paper 的評分結果（evaluation/reasoning + 原始輸出）。
- **RunManifest**：單次測試的輸入來源、criteria 來源、模型設定、輸出檔案清單。

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
