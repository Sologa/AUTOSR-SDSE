# 詳細審核報告：Codex CLI Keywords Provider Switch

**審核日期**：2026-01-13（第三次完整審核）  
**審核者**：GitHub Copilot (Claude Opus 4.5)  
**審核範圍**：`docs/specs/001-codex-cli-keywords/` 完整目錄  
**狀態**：✅ 已更新至 v3.0

---

## 審核更新紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| v3.0 | 2026-01-13 | 更新為 pipeline 現況（已建立 codex keywords/review/snowball CLI 支線） |
| v2.0 | 2026-01-13 | 第二次完整審核，確認所有問題已修正 |
| v1.0 | 2026-01-13 | 初次審核，識別 1 Critical + 4 Medium + 2 Minor 問題 |

---

## 一、審核摘要

| 類別 | 問題數 | 狀態 |
|------|--------|------|
| 🔴 Critical | 0 | ✅ 已全部解決 |
| 🟡 Medium | 0 | ✅ 已全部解決 |
| 🔵 Minor | 1 | 建議改善（非必要） |
| ✅ 驗證通過 | 14 | 無需修正 |

### 已解決問題總覽

| 原 Issue ID | 問題描述 | 修正位置 | 狀態 |
|-------------|----------|----------|------|
| C-001 | pyproject.toml 中的 codex 套件衝突 | `sdse-uv/pyproject.toml` | ✅ 已移除錯誤依賴 |
| M-001 | plan.md Python 版本未明確 | `plan.md` 第 15 行 | ✅ 已改為 ">=3.13" |
| M-002 | research.md Open Questions 未解答 | `research.md` | ✅ 已標註 Resolved + Decision 3 |
| M-003 | quickstart.md 缺少 CODEX_BIN 設定 | `quickstart.md` | ✅ 已新增安裝與路徑設定說明 |
| M-004 | tasks.md T010 缺少 --codex-bin 參數 | `tasks.md` T010 | ✅ 已補充完整說明 |
| I-001 | data-model.md command 欄位格式未定義 | `data-model.md` | ✅ 已補充範例格式 |

---

## 二、文件完整性驗證

### 2.1 目錄結構

```
docs/specs/001-codex-cli-keywords/
├── spec.md                      ✅ 存在 (75 行)
├── plan.md                      ✅ 存在 (68 行)
├── tasks.md                     ✅ 存在 (155 行)
├── research.md                  ✅ 存在 (已更新)
├── data-model.md                ✅ 存在 (58 行)
├── quickstart.md                ✅ 存在 (已更新)
├── checklists/
│   └── requirements.md          ✅ 存在 (52 行)
├── contracts/
│   └── api.json                 ✅ 存在 (內部 API，無端點)
└── REVIEW_REPORT.md             ← 本報告
```

### 2.2 引用路徑驗證

| 文件中引用的路徑 | 實際狀態 | 驗證結果 |
|-----------------|----------|---------|
| `src/pipelines/topic_pipeline.py` | 存在 (132KB) | ✅ |
| `src/utils/keyword_extractor.py` | 存在 (43KB, 受保護) | ✅ |
| `src/utils/llm.py` | 存在 (42KB, 受保護) | ✅ |
| `docs/codex/test-keywords/keywords_response_codex.schema.json` | 存在 (2KB) | ✅ |
| `scripts/topic_pipeline.py` | 存在 (22KB) | ✅ |
| `src/utils/codex_cli.py` | 存在 | ✅ |
| `src/utils/codex_keywords.py` | 存在 | ✅ |
| `src/utils/gemini_cli.py` | 存在 | ✅ |
| `resources/schemas/review_response.schema.json` | 存在 | ✅ |

### 2.3 依賴驗證

| 依賴 | 狀態 | 版本 | 備註 |
|------|------|------|------|
| pdfplumber | ✅ 已安裝 | 0.11.9 | PDF 文字提取 |
| openai SDK | ✅ 已安裝 | >=1.108.1 | OpenAI API |
| requests | ✅ 已安裝 | >=2.32.5 | HTTP 請求 |
| codex (錯誤套件) | ✅ 已移除 | N/A | 已從 pyproject.toml 移除 |
| specify-cli | ✅ 已安裝 | Git 來源 | spec-kit 工具 |
| Codex CLI | ⚠️ 需本機安裝 | N/A | `codex exec` 由本機 CLI 提供 |
| Gemini CLI | ⚠️ 需本機安裝 | N/A | review/snowball 需 `gemini` |

---

## 三、已解決問題詳情

### ✅ C-001: pyproject.toml 中的 `codex` 套件衝突【已解決】

**原問題**：
`sdse-uv/pyproject.toml` 中的 `codex>=1.8.14` 依賴指向 **codex-reader**（漫畫閱讀器），而非 **OpenAI Codex CLI**。

**修正後內容**（`sdse-uv/pyproject.toml`）：
```toml
dependencies = [
    "dotenv>=0.9.9",
    "openai>=1.108.1",
    "pdfplumber",
    "requests>=2.32.5",
    "specify-cli",
]
```

**驗證**：`codex>=1.8.14` 已從 dependencies 中移除 ✅

---

### ✅ M-001: plan.md 中 Python 版本標記【已解決】

**原問題**：`plan.md` 中將 Python 版本標記為 `NEEDS CLARIFICATION`

**修正後內容**：
```markdown
**Language/Version**: Python >=3.13
```

**驗證**：已明確指定 Python 版本 ✅

---

### ✅ M-002: research.md Open Questions【已解決】

**原問題**：Open Questions 未補充答案

**修正後內容**：
- Open Questions 已標註為 `(Resolved)`
- 新增 **Decision 3: CODEX_BIN 環境變數**

**驗證**：所有問題已解答，新增第三項決策 ✅

---

### ✅ M-003: quickstart.md 缺少 CODEX_BIN 設定【已解決】

**原問題**：未說明如何設定 Codex CLI 路徑

**新增內容**：
- **Codex CLI 安裝**：說明透過 Homebrew 安裝
- **Codex CLI 路徑設定**：說明 CODEX_BIN 環境變數設定方式

**驗證**：quickstart.md 已包含完整安裝與路徑設定說明 ✅

---

### ✅ M-004: tasks.md T010 缺少參數說明【已解決】

**原問題**：T010 未提及 `--codex-bin` 參數

**修正後內容**：
```markdown
- [ ] T010 [P] [US1] Update `scripts/topic_pipeline.py` keywords subcommand:
  - Add `--codex-bin` argument for explicit Codex CLI path
  - Update help text to document `provider=codex-cli` usage
  - Document `--model` default for codex-cli
```

**驗證**：T010 任務描述已補充完整 ✅

---

### ✅ I-001: data-model.md command 欄位格式【已解決】

**原問題**：`KeywordRunRecord.command` 格式未定義

**修正後內容**：
```markdown
- command: string[] (e.g., `["/opt/homebrew/bin/codex", "exec", "-", "--model", "..."]`)
```

**驗證**：已補充範例格式 ✅

---

## 四、剩餘建議項目（非必要）

### 🔵 I-002: checklists/requirements.md 驗證命令格式【建議】

**檔案位置**：`docs/specs/001-codex-cli-keywords/checklists/requirements.md`  
**問題類型**：格式可改善（非必要）

**現況**：
checklist 已包含驗證命令（CHK008-CHK010），格式正確可用。

**現行格式範例**：
```markdown
- [ ] CHK008 codex-cli 輸出與既有 keywords schema 相容
  - 驗證命令：`python -c "import json; d=json.load(open(...)); assert all(...)"`
```

**評估**：現行格式可接受，無需強制修正。實作階段可依需要調整。

**狀態**：✅ 可接受（建議項目）

---

## 五、與現有程式碼的一致性檢查

### 5.1 extract_keywords_from_seed_pdfs() 現況

**位置**：`src/pipelines/topic_pipeline.py`  
**狀態**：已完成 `codex-cli` 分支接入，OpenAI 路徑維持硬鎖行為。

**現況摘要**：
- `provider=codex-cli` 時走 `run_codex_cli_keywords()`，使用傳入的 `model`，不套用 `gpt-5.2/temperature` hard lock。
- `provider=openai` 時維持既有硬鎖：`model=gpt-5.2`、`temperature=1.0`。
- `codex-cli` 路徑支援 `codex-bin/codex-home/codex-extra-arg` 與 `reasoning_effort`（透過 `CODEX_HOME` config 暫時覆寫）。

### 5.2 scripts/topic_pipeline.py 參數現況

**位置**：`scripts/topic_pipeline.py`  
**狀態**：已新增 keywords 的 codex CLI 參數與 review provider 參數。

**新增重點**：
- keywords：`--provider` 增加 `codex-cli`，並新增 `--codex-bin/--codex-home/--codex-extra-arg/--codex-allow-web-search`
- review：新增 `--provider`、`--junior-*-model`、`--junior-*-reasoning-effort`、`--codex-schema` 等

### 5.3 review/snowball CLI 接入摘要

**位置**：
- `src/pipelines/topic_pipeline.py`：新增 `run_cli_review()`（codex exec + gemini）
- `scripts/snowball_iterate.py`：新增 `--review-provider` 等參數以支援 snowball review

**狀態**：已接入，輸出格式維持 `latte_review_results.json` 相容結構。

---

## 六、驗證檢查表

以下項目已於本次審核中驗證通過：

- [x] `sdse-uv/pyproject.toml` 不含 `codex>=1.8.14`
- [x] `plan.md` 明確指定 Python >=3.13
- [x] `research.md` Open Questions 標記為 Resolved
- [x] `research.md` 包含 Decision 3 (CODEX_BIN)
- [x] `quickstart.md` 包含 Codex CLI 安裝說明
- [x] `quickstart.md` 包含 CODEX_BIN 設定說明
- [x] `tasks.md` T010 包含 --codex-bin 相關說明
- [x] `data-model.md` command 欄位包含格式範例
- [x] 所有引用的既有檔案路徑存在
- [x] `src/utils/codex_cli.py` / `src/utils/codex_keywords.py` / `src/utils/gemini_cli.py` 存在
- [x] `resources/schemas/keywords_response_codex.schema.json` / `resources/schemas/review_response.schema.json` 存在
- [x] `docs/pipelines/keywords_codex_cli.md` / `docs/pipelines/review_codex_cli.md` 存在
- [x] `scripts/run_topic_discrete_audio_tokens_full_codex_cli.sh` 存在
- [x] 所有計畫建立的新檔案尚不存在（預期行為）
- [x] `checklists/requirements.md` 包含驗證命令
- [x] `contracts/api.json` 正確標示無外部 API 端點

---

## 七、驗證腳本

```bash
#!/usr/bin/env bash
# 儲存為 /tmp/verify_spec_fixes.sh

set -euo pipefail
cd /Users/xjp/Desktop/Survey-with-LLMs/Survey-for-survey-review-with-LLMs/AUTOSR-SDSE

echo "=== 1) 檢查 codex 依賴是否已移除 ==="
if grep -q 'codex>=' sdse-uv/pyproject.toml; then
  echo "[FAIL] codex 依賴仍存在於 pyproject.toml"
  exit 1
else
  echo "[PASS] codex 依賴已移除"
fi

echo ""
echo "=== 2) 檢查 plan.md Python 版本 ==="
if grep -q 'NEEDS CLARIFICATION' docs/specs/001-codex-cli-keywords/plan.md; then
  echo "[FAIL] plan.md 仍有 NEEDS CLARIFICATION"
  exit 1
else
  echo "[PASS] plan.md 已更新"
fi

echo ""
echo "=== 3) 檢查 research.md Open Questions ==="
if grep -q 'Resolved' docs/specs/001-codex-cli-keywords/research.md; then
  echo "[PASS] research.md Open Questions 已標記為 Resolved"
else
  echo "[FAIL] research.md 尚未更新"
  exit 1
fi

echo ""
echo "=== 4) 檢查 quickstart.md CODEX_BIN 說明 ==="
if grep -q 'CODEX_BIN' docs/specs/001-codex-cli-keywords/quickstart.md; then
  echo "[PASS] quickstart.md 包含 CODEX_BIN 說明"
else
  echo "[FAIL] quickstart.md 缺少 CODEX_BIN 說明"
  exit 1
fi

echo ""
echo "=== 5) 檢查 tasks.md T010 ==="
if grep -q 'codex-bin' docs/specs/001-codex-cli-keywords/tasks.md; then
  echo "[PASS] tasks.md T010 包含 codex-bin 說明"
else
  echo "[FAIL] tasks.md T010 缺少說明"
  exit 1
fi

echo ""
echo "=== ✅ 所有驗證通過 ==="
```

---

## 八、結論

經過第三次完整審核，確認 keywords codex-cli 已導入 pipeline，並補齊 review/snowball CLI 支線與測試腳本。

| 優先級 | 原問題數 | 已解決 | 剩餘 |
|--------|----------|--------|------|
| 🔴 Critical | 1 | 1 | 0 |
| 🟡 Medium | 4 | 4 | 0 |
| 🔵 Minor | 2 | 1 | 1 (建議項目) |

**結論**：Spec 文件與現行實作一致，可進入實際執行驗證階段。

**下一步**：依 `scripts/run_topic_discrete_audio_tokens_full_codex_cli.sh` 逐步執行並確認輸出。

---

## 九、附錄

### A. 相關檔案路徑

```
docs/specs/001-codex-cli-keywords/
├── spec.md
├── plan.md
├── tasks.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
├── contracts/api.json
└── REVIEW_REPORT.md          ← 本報告

docs/pipelines/
├── keywords_codex_cli.md
└── review_codex_cli.md

scripts/
└── run_topic_discrete_audio_tokens_full_codex_cli.sh

src/utils/
├── codex_cli.py
├── codex_keywords.py
└── gemini_cli.py

sdse-uv/
└── pyproject.toml            ← C-001 已修正

docs/codex/test-shared/
└── codex_cli_utils.py        ← resolve_codex_bin() 參考實作
```

### B. 受保護檔案（禁止修改）

依據 `AGENTS.md` 第 11 節，以下檔案受保護：
- `src/utils/llm.py`
- `src/utils/keyword_extractor.py`
- `src/utils/env.py`

實作時需新增檔案（如 `codex_cli.py`、`codex_keywords.py`），而非修改受保護檔案。

---

**報告結束**
