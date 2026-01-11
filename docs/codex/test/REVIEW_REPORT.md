# Codex/Gemini CLI Review Smoke Test 深度 Review 報告

> 報告產生時間：2026-01-11
> Review 範圍：`docs/codex/` 及 `docs/codex/test/` 完整文檔與程式碼

---

## 一、文檔架構總覽

### 1.1 docs/codex/ 主目錄文檔

| 檔案 | 用途 | 品質評估 |
|------|------|---------|
| [codex_cli_combined_slides.md](docs/codex/codex_cli_combined_slides.md) | 整合投影片，呈現 Codex CLI 能力與混合模式策略 | ⭐⭐⭐⭐⭐ 結構清晰，重述標註明確 |
| [codex_cli_implementation_report.md](docs/codex/codex_cli_implementation_report.md) | 技術實作報告，基於全量程式碼盤點 | ⭐⭐⭐⭐⭐ 涵蓋 5 步驟 + 受保護檔案限制 |
| [codex_cli_single_turn_report.md](docs/codex/codex_cli_single_turn_report.md) | Codex CLI 單次對話評估 | ⭐⭐⭐⭐ 官方 + 推論內容標註清楚 |

### 1.2 docs/codex/test/ 測試子目錄

| 檔案 | 用途 | 狀態 |
|------|------|------|
| [README.md](docs/codex/test/README.md) | 使用說明 | ✅ 完整 |
| [spec.md](docs/codex/test/spec.md) | 功能規格書 | ✅ 14 項 FR 皆明確 |
| [plan.md](docs/codex/test/plan.md) | 實作計劃 | ✅ 3 Phase 規劃 |
| [tasks.md](docs/codex/test/tasks.md) | 任務追蹤 | ✅ 已同步 |
| [config.md](docs/codex/test/config.md) | Codex CLI 配置說明 | ✅ CODEX_HOME + sandbox 控制 |

---

## 二、程式碼架構與品質分析

### 2.1 核心程式碼檔案

| 檔案 | 行數 | 責任 | 品質評分 |
|------|------|------|---------|
| `review_cli_utils.py` | 405 | 共用工具函式庫 | ⭐⭐⭐⭐⭐ |
| `run_codex_single.py` | 210 | Codex 單 reviewer runner | ⭐⭐⭐⭐ |
| `run_gemini_single.py` | 156 | Gemini 單 reviewer runner | ⭐⭐⭐⭐ |
| `run_full_workflow.py` | 381 | 完整 workflow runner | ⭐⭐⭐⭐⭐ |
| `validate_review_output.py` | 101 | Review 輸出驗證器 | ⭐⭐⭐⭐ |
| `validate_run_manifest.py` | 68 | Manifest 驗證器 | ⭐⭐⭐⭐ |

### 2.2 程式碼品質觀察

#### ✅ 優點

1. **模組化設計**：`review_cli_utils.py` 統一封裝 CLI 呼叫、JSON 處理、criteria 解析
2. **型別標註完整**：所有函式使用 `typing` 模組標註參數與回傳型別
3. **錯誤處理穩健**：CLI 呼叫失敗時返回 `(None, raw, error)` 三元組，不會崩潰
4. **可配置性高**：支援 `--codex-extra-arg`、`--allow-web-search`、`--codex-bin` 等參數
5. **遵守專案規範**：不修改 `src/` 或正式 pipeline，所有輸出寫入 `docs/codex/test/outputs/`

#### ⚠️ 可改進項目

1. **硬編碼路徑**：預設 metadata 路徑硬編碼為特定 workspace

### 2.3 JSON Schema 設計

| Schema 檔案 | 用途 | 驗證狀態 |
|-------------|------|---------|
| `review_output.schema.json` | 驗證 review 輸出結構 | ✅ |
| `review_response.schema.json` | CLI 回應 schema（傳給 `--output-schema`） | ✅ |
| `run_manifest.schema.json` | manifest 結構驗證 | ✅ |

---

## 三、測試結果分析（run_id: 20260110_090000）

### 3.1 執行摘要

| 項目 | 結果 |
|------|------|
| 執行時間 | 2026-01-11T16:22:30.792846 |
| 輸入來源 | `workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json` |
| 處理筆數 | 5 篇 |
| criteria 來源 | workspace（`workspaces/discrete_audio_tokens_more_than_a_survey/criteria/criteria.json`） |
| 錯誤數 | 0 |

### 3.2 各 runner 驗證結果

```
=== codex_single.json === OK ✅
=== gemini_single.json === OK ✅
=== full_workflow.json === OK ✅
=== run_manifest.json  === OK ✅
```

### 3.3 Review 結果一致性分析

| arxiv_id | 論文標題 | Codex (JuniorNano) | Gemini (JuniorMini) | Full Workflow Verdict |
|----------|---------|-------------------|---------------------|----------------------|
| 1706.07793 | Personalized Acoustic Modeling by Weakly Supervised Multi-Task Deep Learning using Acoustic Tokens Discovered from Unlabeled Data | 5 | 5 | **include (junior:5)** |
| 2206.07086 | Synthesizing Mathematical Identities with E-Graphs | 1 | 1 | **exclude (junior:1)** |
| 2206.09680 | Misspelling Semantics In Thai | 1 | 1 | **exclude (junior:1)** |
| 2206.12117 | Self Supervised Learning for Few Shot Hyperspectral Image Classification | 1 | 1 | **exclude (junior:1)** |
| 2206.13680 | Attention-based conditioning methods using variable frame rate for style-robust speaker verification | 1 | 1 | **exclude (junior:1)** |

**一致性**：5/5 篇論文的評分完全一致（100%），兩個 reviewer 對於 discrete audio tokens 主題的判斷高度一致。

### 3.4 Senior Reviewer 觸發分析

根據 `_should_run_senior()` 邏輯：
- 當兩位 junior 評分相同且 ≥4 時，不觸發 senior
- 當評分不同且至少一方 ≥3 時，觸發 senior
- 當評分皆為 3 時，觸發 senior

本次執行中，所有 5 篇論文的 junior 評分完全一致（5/5 或 1/1），因此 **SeniorLead 未被觸發**，`rounds.B` 皆為空物件。

---

## 四、CLI 命令與安全性分析

### 4.1 實際執行命令（from run_manifest.json）

```bash
# commands 共 5 筆（依 manifest 紀錄順序）
gemini --output-format json --model gemini-2.5-pro
/opt/homebrew/bin/codex exec --disable web_search_request - --model gpt-5.1-codex-mini --output-schema /Users/xjp/Desktop/Survey-with-LLMs/Survey-for-survey-review-with-LLMs/AUTOSR-SDSE/docs/codex/test/review_response.schema.json
gemini --output-format json --model gemini-2.5-pro
/opt/homebrew/bin/codex exec --disable web_search_request - --model gpt-5.2 --output-schema /Users/xjp/Desktop/Survey-with-LLMs/Survey-for-survey-review-with-LLMs/AUTOSR-SDSE/docs/codex/test/review_response.schema.json
/opt/homebrew/bin/codex exec --disable web_search_request - --model gpt-5.1-codex-mini --output-schema /Users/xjp/Desktop/Survey-with-LLMs/Survey-for-survey-review-with-LLMs/AUTOSR-SDSE/docs/codex/test/review_response.schema.json
```
> 註：commands 為 runner 記錄的命令清單；順序對應 gemini_single → full_workflow → codex_single。SeniorLead 本次未產出 Round B 評審結果（見 3.4），但命令仍被記錄在清單中。

### 4.2 安全性檢核

| 檢核項目 | 狀態 | 說明 |
|----------|------|------|
| Web search 預設關閉 | ✅ | `features.web_search_request=false`（repo-local config）且命令含 `--disable web_search_request` |
| CODEX_HOME 隔離 | ✅ | 文檔說明使用 repo-local `.codex/` |
| Sandbox 控制 | ✅ | config.toml 設定 `network_access=false` |
| 密鑰不外洩 | ✅ | 輸出 JSON 不含 API key |

---

## 五、文檔完整性審查

### 5.1 Spec 與 Plan 一致性

| spec.md FR 編號 | 需求描述 | plan.md 對應 | 實作狀態 |
|-----------------|---------|-------------|---------|
| FR-001 | 輸出至 `outputs/<run_id>/` | ✅ Phase 3.1 | ✅ 已實作 |
| FR-002 | 使用 `codex exec` | ✅ Phase 3.3 | ✅ 已實作 |
| FR-003 | 使用 `gemini` CLI | ✅ Phase 3.3 | ✅ 已實作 |
| FR-004 | Review prompt 與 pipeline 一致 | ✅ Phase 1.2 | ✅ 已實作 |
| FR-005 | 取 arxiv_metadata.json 前 5 筆 | ✅ Phase 0 | ✅ 已實作 |
| FR-006 | 保留 paper 識別欄位 | ✅ Phase 1.3 | ✅ 已實作 |
| FR-007 | 結構化輸出含 evaluation/reasoning | ✅ Phase 1.3 | ✅ 已實作 |
| FR-008 | criteria 讀取 fallback | ✅ Phase 3.4 T008 | ✅ 已實作 |
| FR-009 | 單 reviewer → 完整 workflow 兩模式 | ✅ Phase 3.3-3.4 | ✅ 已實作 |
| FR-010 | 模型對應固定 | ✅ Phase 0 | ✅ 已實作 |
| FR-011 | 記錄 Gemini model_used | ✅ Phase 1.3 | ✅ 已實作 |
| FR-012 | --codex-extra-arg 支援 | ✅ Phase 1.2 | ✅ 已實作 |
| FR-013 | CODEX_HOME 配置 | ✅ config.md | ✅ 已實作 |
| FR-014 | web_search 預設關閉 | ✅ config.md | ✅ 已實作 |

### 5.2 Tasks 完成狀態

> 註：`tasks.md` 已同步更新，以下以勾選狀態呈現。

| Task ID | 描述 | 狀態 |
|---------|------|------|
| T001 | review_output.schema.json | ✅ |
| T002 | run_manifest.schema.json | ✅ |
| T003 | validate_review_output.py | ✅ |
| T004 | validate_run_manifest.py | ✅ |
| T005 | run_codex_single.py | ✅ |
| T006 | run_gemini_single.py | ✅ |
| T007 | run_full_workflow.py | ✅ |
| T008 | criteria fallback | ✅ |
| T009 | README 使用說明 | ✅ |
| T010 | 範例輸出 | ✅（example_output.json） |
| T011 | config.md | ✅ |
| T012 | web_search 驗證 | ✅（run_manifest + outputs 檢核） |

---

## 六、發現的問題與建議

### 6.1 問題清單

| 編號 | 嚴重度 | 問題描述 | 建議修復 |
|------|--------|---------|---------|
| P-001 | 🔵 Info | example_output.json 使用 placeholder criteria | 可考慮使用真實範例或標註「示意」 |

### 6.2 改進建議

1. **範例輸出**：將 example_output.json 改為真實樣例或標註「示意」
2. **自動化驗證**：新增腳本自動檢查輸出不含 `web_search` tool entry

---

## 七、總結評分

| 評估維度 | 評分 | 說明 |
|----------|------|------|
| 文檔完整性 | ⭐⭐⭐⭐⭐ | spec/plan/tasks/config/README 齊全 |
| 程式碼品質 | ⭐⭐⭐⭐ | 結構良好，仍有硬編碼路徑與示意範例輸出 |
| 測試結果 | ⭐⭐⭐⭐⭐ | 100% 驗證通過，輸出格式符合 schema |
| 安全性 | ⭐⭐⭐⭐⭐ | web_search 預設關閉，sandbox 配置正確 |
| 一致性 | ⭐⭐⭐⭐⭐ | spec ↔ plan ↔ code ↔ output 一致 |

**整體評分：⭐⭐⭐⭐ (4.6/5)**

---

## 八、驗證執行紀錄（2026-01-11 18:46 +0800）

```
python docs/codex/test/validate_review_output.py docs/codex/test/outputs/20260110_090000/codex_single.json
python docs/codex/test/validate_review_output.py docs/codex/test/outputs/20260110_090000/gemini_single.json
python docs/codex/test/validate_review_output.py docs/codex/test/outputs/20260110_090000/full_workflow.json
python docs/codex/test/validate_run_manifest.py docs/codex/test/outputs/20260110_090000/run_manifest.json
```

> 註：本次未執行 ruff/mypy/py_compile 等靜態或語法檢查。

---

*報告由 Codex 修訂，最後驗證時間：2026-01-11 18:46 +0800*
