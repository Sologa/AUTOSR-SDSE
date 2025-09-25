# Spec-Kit 使用指南

> 本指南針對倉庫內 `resources/spec-kit/` 所提供的版本撰寫，協助你在本地或遠端環境以 Specification-Driven Development (SDD) 流程工作。

## 1. 概述：Spec-Kit 與 Specification-Driven Development
- **Spec-Kit** 是一套讓規格文件成為主導產出的工具鏈，透過可執行的模板與腳本，讓 AI / LLM 依照結構化流程生成規格、計畫、任務與程式碼。
- **Specification-Driven Development** 將「規格」視為主要資產：產品意圖以自然語言與模板表達，技術實作則從規格與實作計畫推導而來。
- 本倉庫已內建完整模板、腳本與 CLI (`specify`) 原始碼，可離線檢視並依需求調整。

## 2. 系統需求與前置準備
- Python 3.11 以上 (`resources/spec-kit/pyproject.toml` 指定 `requires-python = ">=3.11"`)
- [uv](https://github.com/astral-sh/uv) 或 pipx（推薦使用 `uvx` 直接執行 CLI）
- Git（`specify init` 預設會嘗試初始化 git repository）
- 至少一種支援的 AI Coding Agent：Claude、Gemini、Copilot、Cursor、Qwen、OpenCode、Windsurf 等
- 能夠存取 GitHub 的環境（若需下載模板或使用 GitHub API，可透過 `--github-token` 提供 token）
- 建議先執行 `specify check` 以確認必要工具均已準備好

## 3. 安裝與更新 Specify CLI
```bash
# 使用 uvx 從 GitHub 取得最新版本並初始化專案
uvx --from git+https://github.com/github/spec-kit.git specify init <PROJECT_NAME>

# 或使用 uv 安裝後再呼叫
uv tool install --from git+https://github.com/github/spec-kit.git specify-cli
specify init <PROJECT_NAME>

# 更新已安裝的 specify-cli
uv tool upgrade specify-cli
```
- 如需 PowerShell 腳本支援，初始化時可加上 `--script ps`。
- 若環境受企業 Proxy / TLS 限制，可視情況添加 `--skip-tls` 或設定 `--github-token`。
- 需在現有目錄建立專案時使用 `specify init --here`。

### 常用初始化參數
| 參數 | 說明 |
|------|------|
| `--ai <assistant>` | 指定 AI 助手（`claude`、`gemini`、`copilot`、`cursor`、`qwen`、`opencode`、`windsurf`）|
| `--script {sh,ps}` | 選擇 Shell 腳本版本（預設 `sh`，對應 Bash/Zsh）|
| `--ignore-agent-tools` | 略過代理程式檢查（適合無法安裝特定 IDE 外掛的環境）|
| `--no-git` | 初始化時不建立 git repository |
| `--here` | 在當前資料夾建立專案，不新增子目錄 |
| `--debug` | 輸出除錯資訊，協助排查安裝或執行問題 |
| `--github-token <token>` | 提供 GitHub Token 以提升 API 配額、支援私有網路 |

## 4. 初始化後的專案結構
執行 `specify init` 後會生成以下核心目錄與檔案（此倉庫的參考版本位於 `resources/spec-kit/`）：
- `.specify/`：放置命令模板、代理設定與 Hook 腳本
  - `.specify/templates/plan-template.md`、`.specify/templates/tasks-template.md` 等為生成計畫與任務的基底
- `memory/`：儲存專案憲章（`constitution.md`）、開發共識與常駐上下文
- `specs/`：依功能分支儲存產出之規格、計畫與任務
  - 例如 `specs/003-chat-system/spec.md`、`plan.md`、`tasks.md`、`contracts/`
- `scripts/`：對 `/plan`、`/tasks`、`/implement` 指令執行前置檢查與環境設定
  - Bash 版本位於 `scripts/bash/`，PowerShell 版本位於 `scripts/powershell/`
- `templates/`：提供規格與命令輸出的原始模板（本倉庫對應 `resources/spec-kit/templates/`）
- `media/`、`docs/`：說明文件與輔助素材

> 若要調整模板，可直接修改 `.specify/templates/` 內檔案；更新後的模板會在下次執行指令時生效。

## 5. 核心 Slash 指令工作流
初始化後，所有開發流程皆透過 Slash 指令驅動。以下說明主要指令、輸入與輸出。

### 5.1 `/constitution` 建立開發憲章
- **目的**：明確專案的工程原則、品質標準與治理規範
- **輸出**：`memory/constitution.md`（模板參考 `resources/spec-kit/memory/constitution.md`）
- **建議流程**：
  1. 說明你想遵循的工程文化或約束（例：測試覆蓋率、部署流程）
  2. 檢查最終文件是否包含治理條款與版本資訊
  3. 將憲章視為後續指令的約束基礎

### 5.2 `/specify` 撰寫功能規格
- **目的**：從使用者或產品需求出發，建立完整 PRD
- **輸入**：產品/功能描述（聚焦於「做什麼」「為什麼」）
- **輸出**：`specs/<branch>/spec.md`，使用模板 `resources/spec-kit/templates/spec-template.md`
- **要點**：
  - 必填「User Scenarios」「Functional Requirements」「Review Checklist」等區塊
  - 對不確定的需求使用 `[NEEDS CLARIFICATION: ...]` 標記
  - 規格保持技術中立，不提前指定框架或實作細節

### 5.3 `/plan` 建立技術實作計畫
- **目的**：將規格轉換為技術決策、架構設計與分工
- **輸入**：技術偏好、既有系統約束、預期資料模型等
- **輸出**：在對應功能目錄產生 `plan.md`、`research.md`、`data-model.md`、`contracts/`、`quickstart.md`
- **執行流程**：
  1. 指令會先執行 `scripts/bash/setup-plan.sh`（或 PowerShell 等價腳本）確保環境就緒
  2. 使用 `.specify/templates/plan-template.md` 將規格拆解為多階段產出
  3. 完成後檢查「Progress Tracking」是否全數勾選、是否有錯誤訊息

### 5.4 `/tasks` 生成執行任務列表
- **目的**：把計畫轉換成具體、可依賴執行的任務
- **輸入**：既有的 `plan.md`、`data-model.md`、`contracts/` 等資料
- **輸出**：`tasks.md`，模板位於 `resources/spec-kit/templates/commands/tasks.md`
- **任務規範**：
  - 任務依階段排序：Setup → Tests → Core → Integration → Polish
  - 平行任務加註 `[P]`，同檔案變動須維持序列
  - 每項任務需清楚指出檔案與目標（例：`T004 Implement src/service.py`)`

### 5.5 `/implement` 依任務執行開發
- **目的**：根據任務列表與計畫實作程式碼
- **輸入**：`tasks.md`、`plan.md`、`data-model.md`、`contracts/` 等
- **流程**：
  1. 前置腳本 `scripts/bash/check-implementation-prerequisites.sh` 會確認檔案完整性
  2. 依 `tasks.md` 中的階段與依賴逐一執行，並在完成後將任務標記為 `[X]`
  3. 測試任務應於對應實作任務之前完成（維持 TDD）
  4. 結束前確定所有必要任務完成、測試通過並符合規格

> 在 CLI 中亦可使用 `specify check` 來驗證環境，確保 Slash 指令執行時不會因缺少工具而中斷。

## 6. 自訂與擴充
- **調整模板**：
  - 覆寫 `.specify/templates/` 內的 Markdown 模板即可改變 LLM 生成內容的結構與語氣
  - 例如修改 `plan-template.md` 以加入公司特定的安全與部署要求
- **自訂腳本**：
  - Bash 腳本位於 `scripts/bash/`，可依作業系統需求調整環境檢查、檔案生成邏輯
  - PowerShell 腳本位於 `scripts/powershell/`，適用於 Windows 或混合環境
- **代理整合**：
  - `.specify/scripts/` 底下可放置自訂腳本以支援額外指令
  - 若使用 Cursor、Windsurf 等 IDE，可參考 `resources/spec-kit/scripts/bash/update-agent-context.sh` 了解如何同步上下文資訊
- **版本控管**：
  - 調整模板或腳本時建議建立分支，更新 `docs/` 中的操作手冊（如本指南）供團隊成員參考

## 7. 常見問題與排除建議
- **指令失敗或卡住**：加上 `--debug` 重新執行觀察詳盡日誌
- **Git 相關錯誤**：若不需 Git 初始化，可在 `specify init` 時加上 `--no-git`
- **公司網路限制**：
  - 使用 `--github-token` 或設定 `GH_TOKEN` / `GITHUB_TOKEN` 以避免 API 速率限制
  - 需要忽略 TLS 檢查時，可加上 `--skip-tls`（僅在安全環境下使用）
- **AI Agent 未能讀取上下文**：確認 IDE 或代理已載入 `.specify/` 下的規則檔；必要時執行 `scripts/bash/update-agent-context.sh`
- **模板未更新**：刪除舊的 `specs/<branch>/` 產物後重新執行 `/plan` 或 `/tasks` 即可套用新模板

## 8. 與本倉庫的關聯
- 本專案的所有 Spec-Kit 資源皆保留在 `resources/spec-kit/`，可作為離線參考或自訂的起點
- 若僅需閱讀說明文件，可參考：
  - `resources/spec-kit/README.md`：官方快速上手
  - `resources/spec-kit/spec-driven.md`：SDD 理念與流程深度解析
  - `resources/spec-kit/SUPPORT.md`：支援與求助管道
- 建議將本指南與上述文件一併提供給團隊，作為導入 Spec-Kit 的教學手冊

## 9. 推薦的下一步
1. 依照 `/constitution → /specify → /plan → /tasks → /implement` 流程，在實際功能分支上演練一次
2. 視團隊需求調整 `.specify/templates/` 與 `scripts/`，並更新 `docs/` 中相關文件
3. 透過 `specify check` 建立自動檢查流程，確保每位成員環境一致

---
本指南旨在提供一個結構化、可操作的 Spec-Kit 使用說明。若後續流程或模板有重大調整，請同步更新 `docs/spec-kit-guide.md`。
