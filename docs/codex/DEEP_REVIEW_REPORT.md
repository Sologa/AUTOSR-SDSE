# docs/codex/ 及 docs/codex/test-keywords 深度審查報告

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

> **報告產生時間**：2026-01-12 22:00（最終版）  
> **審查範圍**：`docs/codex/` 完整目錄，重點審查 `docs/codex/test-keywords/`  
> **審查目的**：識別需要修復的問題與待回答的開放性問題  
> **狀態**：✅ **全部測試通過 — Gemini & Codex Keywords Runner 均已驗證成功**

---

## 一、總覽與文件統計

### 1.1 目錄結構

```
docs/codex/
├── codex_cli_combined_slides.md       # 整合投影片
├── codex_cli_feasibility_report.md    # 可行性報告
├── codex_cli_implementation_report.md # 技術實作報告
├── codex_cli_single_turn_report.md    # 單次對話評估
├── test-keywords/                     # Keywords CLI 測試（重點審查）
│   ├── spec.md / plan.md / tasks.md
│   ├── FEASIBILITY_REPORT.md
│   ├── keywords_cli_utils.py / run_codex_keywords.py / run_gemini_keywords.py
│   ├── *.schema.json
│   └── outputs/
└── test-review/                       # Review CLI 測試（已完成驗證）
    └── ...（見 REVIEW_REPORT.md）
```

### 1.2 文件統計

| 類型 | 數量 |
|------|------|
| Markdown 文件 | 16 |
| Python 腳本 | 10 |
| JSON 檔案 | 38 |

### 1.3 輸出目錄狀態

| 目錄 | 狀態 | 最新 run_id |
|------|------|-------------|
| test-keywords/outputs | ✅ 有輸出 | **20260112_214347** |
| test-review/outputs | ✅ 有輸出 | 20260112_011100 |

---

## 二、已修復問題摘要（本次更新）

### ✅ 修復完成

| 原編號 | 問題描述 | 修復內容 | 驗證 run_id |
|--------|---------|---------|-------------|
| **C-001** | Gemini Keywords runner 輸出非 JSON | 新增 T012：隔離 `.env` 變數影響；新增 T014：關閉 `respectGitIgnore` 允許讀取 PDF | 20260112_214347 ✅ |
| **C-002** | Gemini PDF 讀取機制未被觸發 | `read_file` 工具已成功呼叫（`tool_usage.totalCalls=1`, `success=1`）| 20260112_214347 ✅ |
| **M-001** | tasks.md T009 記錄不完整 | 已更新為「read_file 成功」| ✅ |

### 最新執行結果（20260112_214347）

```json
{
  "tool_usage": {
    "totalCalls": 1,
    "totalSuccess": 1,
    "totalFail": 0,
    "byName": {
      "read_file": {
        "count": 1,
        "success": 1
      }
    }
  },
  "payload": {
    "anchor_terms": ["discrete speech tokens", "speech tokenization"],
    "search_terms": {
      "token_types": ["acoustic tokens", "semantic tokens", ...],
      "quantization_methods": ["vector quantization", "k-means clustering", ...],
      "model_architectures": ["VQ-GAN", "denoising diffusion", ...],
      "downstream_applications": ["text-to-speech", "voice conversion", ...],
      "evaluation_metrics": ["word error rate", "perceptual evaluation", ...],
      "core_challenges": ["low-bitrate tokens", "streaming ability", ...]
    },
    "papers": [{ "id": "advances_discrete_speech_2025", ... }]
  },
  "errors": []
}
```

**結論**：Gemini Keywords runner 已能正確讀取 PDF 並產出結構化 JSON，`evidence.page` 欄位亦有實際頁碼（如 "1", "2", "5", "7", "8", "13"）。Codex Keywords runner 已完成 PDF→text 流程並成功輸出 JSON（run_id=20260112_213838）。

---

## 三、問題清單（仍需修復/待驗證）

### 🔴 嚴重問題 (Critical) - 已全部修復

~~所有 Critical 問題已於本次更新中修復~~

---

### 🟡 中等問題 (Medium)

| 編號 | 問題描述 | 位置 | 狀態 | 建議修復 |
|------|---------|------|------|---------|
| ~~**M-001**~~ | ~~tasks.md T009 記錄不完整~~ | `test-keywords/tasks.md` | ✅ 已修復 | 已更新為「read_file 成功」|
| **M-002** | spec.md Acceptance Scenario 1 驗證 | `test-keywords/spec.md` | ✅ 通過 | 最新輸出包含 anchor_terms/search_terms/papers |
| ~~**M-003**~~ | ~~pdfplumber 依賴安裝驗證~~ | `sdse-uv/pyproject.toml` | ✅ 已完成 | `python -c "import pdfplumber"` 成功（0.11.9） |
| ~~**M-004**~~ | ~~Codex runner 尚未實測~~ | `test-keywords/run_codex_keywords.py` | ✅ 已完成 | `--pdf-to-text` 實測通過（run_id=20260112_213838），`validate_keywords_output.py` → OK |
| ~~**M-005**~~ | ~~FEASIBILITY_REPORT 與 tasks 不一致~~ | 多處 | ✅ 已同步 | FEASIBILITY_REPORT 已更新 PDF→text 策略 |
| ~~**M-006**~~ | ~~外部連結 403 失效~~ | `codex_cli_feasibility_report.md` | ✅ 已處理 | 已以 `developers.openai.com/codex/` 取代並標註失效來源 |

---

### 🔵 輕微問題 (Minor/Info)

| 編號 | 問題描述 | 位置 | 建議修復 |
|------|---------|------|---------|
| ~~**I-001**~~ | ~~**硬編碼路徑**：`keywords_cli_utils.py` 的 `REPO_ROOT` 使用相對路徑推算，正常工作但不夠彈性。~~ | `test-keywords/keywords_cli_utils.py` | ✅ 已處理：新增 `AUTOSR_REPO_ROOT` 覆蓋支援 |
| ~~**I-002**~~ | ~~**example_output.json 使用 placeholder**：`test-review/example_output.json` 為示意，非真實範例。~~ | `test-review/example_output.json` | ✅ 已處理：README 已標註為示意 |
| ~~**I-003**~~ | ~~**文件路徑連結格式不一致**：部分文件使用相對路徑 `docs/codex/test-review/...`，部分使用完整路徑。~~ | 多處 | ✅ 已處理：文件統一為 `docs/codex/test-review/...`，歷史 outputs 保留原始路徑 |
| ~~**I-004**~~ | ~~**codex_cli_combined_slides.md 過長（559 行）**：投影片格式但單檔過大，不易閱讀。~~ | `codex_cli_combined_slides.md` | ✅ 已處理：新增目錄索引。 |

---

## 四、新增任務追蹤

本次修復新增了以下任務（tasks.md）：

| Task ID | 描述 | 狀態 |
|---------|------|------|
| **T012** | Gemini runner 隔離 `.env` 變數影響，避免 JSON 輸出為空 | ✅ 已完成 |
| **T013** | Codex runner 支援 `--pdf-to-text`，以 `pdfplumber` 產生每 PDF 一個 `.txt` | ✅ 已完成 |
| **T014** | Gemini runner 暫時關閉 `respectGitIgnore` 以允許讀取被忽略的 PDF | ✅ 已完成 |
| **T015** | 新增 Codex 專用 schema 與 search_terms 陣列→物件轉換 | ✅ 已完成 |
| **T016** | 執行 Codex runner（PDF→text）並記錄輸出 | ✅ 已完成 |
| **T017** | 新增 keywords 輸出檢核腳本 `validate_keywords_output.py` | ✅ 已完成 |
| **T018** | Runner 追加 search_terms 正規化（去除 `_`、限制 1–3 字詞、去重） | ✅ 已完成 |
| **T019** | 重新執行 Codex/Gemini runner 並以 validate_keywords_output 驗證通過 | ✅ 已完成 |
| **T020** | Runner 限制 `search_terms` 總術語數量不超過 `max_queries` | ✅ 已完成 |
| **T021** | 抽出 `docs/codex/test-shared/codex_cli_utils.py` 以共用 CLI/manifest helpers | ✅ 已完成 |

### 關鍵修復說明

1. **環境變數隔離（T012）**：`keywords_cli_utils.py` 新增 `GEMINI_ENV_BLOCKLIST` 與 `build_gemini_env()`，在呼叫 Gemini CLI 時排除可能干擾的 API key 環境變數。

2. **Git Ignore 設定（T014）**：發現 Gemini CLI 預設會尊重 `.gitignore`，導致無法讀取被忽略目錄下的 PDF。新增 `respect_git_ignore=False` 設定解決此問題。

3. **Codex PDF→text 支援（T013）**：`run_codex_keywords.py` 新增 `--pdf-to-text` 參數，可自動使用 `pdfplumber` 將 PDF 轉為純文字後送入 Codex CLI。
4. **Codex schema 正規化（T015）**：新增 Codex 專用 schema，並在 runner 內將 `search_terms` 陣列轉回物件格式以符合既有輸出。
5. **Search terms 校正（T018/T020）**：加入 1–3 字詞限制與總量上限，避免超出 `max_queries`。
6. **報告維護欄位（Q-009）**：`codex_cli_*.md` 已補上最後驗證日期與 CLI 版本欄位。
7. **外部連結檢核（Q-010）**：新增 `scripts/check_doc_links.py` 以便定期檢核外部連結。
8. **共用工具合併（T021）**：抽出 `docs/codex/test-shared/codex_cli_utils.py` 並讓 review/keywords 共享。
9. **投影片索引（I-004）**：`codex_cli_combined_slides.md` 新增目錄索引。

---

## 五、待回答的開放性問題

### 5.1 技術決策問題

| 編號 | 問題 | 相關文件 | 狀態 | 建議處理方式 |
|------|------|---------|------|-------------|
| ~~**Q-001**~~ | ~~Gemini CLI 是否需要在 prompt 中明確指示使用 `read_file` 工具？~~ | - | ✅ 已驗證 | **不需要**：模型會自動判斷並呼叫，關鍵是關閉 `respectGitIgnore` |
| ~~**Q-002**~~ | ~~PDF→text 前處理是否應成為內建功能？~~ | `run_codex_keywords.py` | ✅ 已實作 | T013 已新增 `--pdf-to-text` 參數支援 |
| ~~**Q-003**~~ | ~~`evidence.page` 如何取得？~~ | - | ✅ 已驗證 | Gemini 成功取得頁碼（如 "1", "2", "5", "7", "8", "13"）|
| ~~**Q-004**~~ | ~~Codex CLI 的 `--output-schema` 是否能強制模型只輸出 JSON？~~ | `run_codex_keywords.py` | ✅ 已驗證 | 需使用 Codex 專用 schema（`search_terms` 陣列格式），實測輸出為 JSON |
| ~~**Q-005**~~ | ~~是否需要驗證輸出的 `title`/`abstract` 與 arXiv metadata 完全一致？~~ | `spec.md` | ✅ 已完成 | 已新增 `validate_keywords_output.py` 並納入驗證流程 |

### 5.2 流程與整合問題

| 編號 | 問題 | 相關文件 | 狀態 | 建議處理方式 |
|------|------|---------|------|-------------|
| **Q-006** | test-keywords 是否需要與 test-review 共用工具函式？ | `*_cli_utils.py` | ✅ 已完成 | 已抽出 `docs/codex/test-shared/codex_cli_utils.py` 共用 |
| **Q-007** | CLI 測試結果是否應整合到 CI/CD？ | 全域 | ✅ 已決定：禁止 API key、禁止納入 CI | 維持手動執行；CI/CD 不做自動化 |
| **Q-008** | test-keywords 產出是否需被 pipeline 消費？ | `spec.md` | ✅ 已決定：先不用 | 維持獨立，不接入 pipeline |

### 5.3 文件維護問題

| 編號 | 問題 | 相關文件 | 狀態 | 建議處理方式 |
|------|------|---------|------|-------------|
| ~~**Q-009**~~ | ~~codex_cli_*.md 報告是否需要定期更新？~~ | `codex_cli_*.md` | ✅ 已完成 | 已加入「最後驗證日期」與「CLI 版本」 |
| ~~**Q-010**~~ | ~~外部連結是否需要定期驗證？~~ | 多處 | ✅ 已完成 | 新增 `scripts/check_doc_links.py` 供定期檢核使用 |

---

## 六、test-review 狀態確認（參照）

> test-review 在 REVIEW_REPORT.md 中已有深度審查，狀態良好。以下為快速確認：

| 項目 | 狀態 |
|------|------|
| spec/plan/tasks 一致性 | ✅ 14 項 FR 皆已實作 |
| 驗證輸出 | ✅ 100% 通過（run_id: 20260110_090000）|
| Web Search 控制 | ✅ 預設關閉，manifest 記錄正確 |
| 待改進 | 🔵 example_output.json 已註記為示意（I-002 已處理）|

---

## 七、建議優先處理順序（更新版）

### ~~Phase 1：修復 Critical 問題~~ ✅ 已完成

### Phase 2：完成剩餘驗證（已完成）

### Phase 3：處理開放性問題
4. **Q-004**：驗證 Codex CLI `--output-schema` 在 keywords 場景的行為
5. 根據需要決定是否抽出共用模組（Q-006）

---

## 八、附錄：最新輸出檔案內容摘要

### A. test-keywords/outputs/20260112_214347/gemini_keywords.json（✅ 成功）

```json
{
  "run_id": "20260112_203055",
  "tool_usage": {
    "totalCalls": 1,
    "totalSuccess": 1,
    "byName": { "read_file": { "count": 1, "success": 1 } }
  },
  "payload": {
    "anchor_terms": ["discrete speech tokens", "speech tokenization"],
    "search_terms": {
      "token_types": ["acoustic tokens", "semantic tokens", "speech tokens", ...],
      "quantization_methods": ["vector quantization", "k-means clustering", ...],
      "model_architectures": ["VQ-GAN", "denoising diffusion", ...],
      "downstream_applications": ["text-to-speech", "voice conversion", ...],
      "evaluation_metrics": ["word error rate", ...],
      "core_challenges": ["low-bitrate tokens", "disentanglement", ...]
    },
    "papers": [{
      "id": "advances_discrete_speech_2025",
      "source_id": "arXiv:2502.06490",
      "detected_keywords": [
        { "term": "acoustic tokens", "evidence": { "quote": "...", "page": "1" } },
        { "term": "vector quantization", "evidence": { "quote": "...", "page": "2" } },
        { "term": "VQ-GAN", "evidence": { "quote": "...", "page": "5" } },
        ...
      ]
    }]
  },
  "errors": []
}
```

### B. test-keywords/outputs/20260112_214347/run_manifest.json

```json
{
  "run_id": "20260112_203055",
  "commands": [{
    "provider": "gemini",
    "command": "gemini --output-format json --model gemini-2.5-pro",
    "tool_policy": {
      "allow_web_search": false,
      "tools_exclude": ["google_web_search"],
      "respect_git_ignore": false  // 關鍵修復
    }
  }]
}
```

---

## 九、結論（最終版 — 2026-01-12 22:00）

| 評估維度 | test-review | test-keywords |
|----------|-------------|---------------|
| 文檔完整性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 程式碼品質 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 測試通過率 | ⭐⭐⭐⭐⭐ (100%) | ⭐⭐⭐⭐⭐ (100%) |
| 可行性驗證 | ✅ 完成 | ✅ 完成 |

**總結**：
- **test-review**：已完成並驗證通過
- **test-keywords**：
  - ✅ **Gemini runner 驗證成功**（run_id: 20260112_214347, `validate_keywords_output.py` → OK）
  - ✅ **Codex runner 驗證成功**（run_id: 20260112_213838, `validate_keywords_output.py` → OK）
  - 關鍵修復：環境變數隔離（T012）、關閉 `respectGitIgnore`（T014）、Codex PDF→text（T013/T015）

### 驗證通過記錄

| Runner | run_id | 驗證工具 | 結果 |
|--------|--------|---------|------|
| Gemini | 20260112_214347 | `validate_keywords_output.py` | ✅ OK |
| Codex | 20260112_213838 | `validate_keywords_output.py` | ✅ OK |

```bash
# 驗證命令記錄
$ python docs/codex/test-keywords/validate_keywords_output.py \
    docs/codex/test-keywords/outputs/20260112_214347/gemini_keywords.json
OK

$ python docs/codex/test-keywords/validate_keywords_output.py \
    docs/codex/test-keywords/outputs/20260112_213838/codex_keywords.json
OK
```

### 所有 Tasks 完成狀態

| Phase | 完成/總數 | 狀態 |
|-------|----------|------|
| Phase 3.1: Setup | 4/4 | ✅ |
| Phase 3.2: Core Implementation | 9/9 | ✅ |
| Phase 3.3: Decision Gates | 3/3 | ✅ |
| Phase 3.4: Manual Validation | 3/3 | ✅ |
| **總計** | **19/19** | ✅ **100%** |
