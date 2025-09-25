# 規格驅動開發手把手指南（繁體中文）

## 1. 快速回顧：SDD 流程全貌
Specification-Driven Development（SDD）以「規格」為開發起點。典型節奏是 `/constitution → /specify → /plan → /tasks → /implement`。其中 `/specify` 產出的 `spec.md` 定義了產品目標、人機互動、驗收標準，後續計畫與程式碼都以它為依據。完成 docs/spec-kit-guide.md 的初始化後，你的環境已具備官方模板、腳本與 CLI，接下來只要按照下列步驟撰寫規格即可。

## 2. 正式寫 spec 前的準備
1. **釐清需求來源**：收集產品需求、商業目標、使用者痛點，整理成簡明的自然語言描述（約 5–10 行即可）。
2. **確認輸入資料**：若有 API 契約、既有系統限制、法規或營運指標，把重點條列起來，後續放進 Spec 的「Non-Functional Requirements」或「Dependencies」。
3. **決定規格目標範圍**：Spec 不討論具體實作細節，只關注「要達成什麼」與「成功條件」。把技術選型或實作細節留給 `/plan` 階段。

## 3. 使用 `/specify` 指令的實際流程
1. 在專案根目錄開啟終端機，執行 `specify /specify "<你的需求描述>"`（大部分介面會直接提供 Slash 指令輸入框）。
2. 系統會自動執行 `.specify/scripts/bash/create-new-feature.sh`：
   - 建立功能專用分支（例 `feature/003-your-feature`）。
   - 在 `specs/<branch>/` 之下放入模板化的 `spec.md`。
3. 指令完成後，打開新增的 `spec.md`，依模板各節填寫內容。常見欄位對應如下：
   - **Overview / Goal**：用 2–3 句描述功能價值與使用者情境。
   - **User Scenarios**：每個情境包含觸發條件、操作步驟、期待結果。
   - **Functional Requirements**：以編號條列，每點對應可驗證的系統行為。
   - **Non-Functional Requirements**：延遲、可靠度、權限控管等約束。
   - **Open Questions / Risks**：列出尚未釐清的假設並標記 `[NEEDS CLARIFICATION]`。
   - **Review Checklist**：把未來 code review 時要檢查的項目具體寫出（例如「是否覆蓋 X 個邊界條件測試」）。
4. 完成後，重新檢查是否語句具體可驗收、需求之間沒有矛盾，並確保沒有跳到實作細節。

> **提示**：如果需求量大，可以在 `spec.md` 中加上「Out of Scope」區段，明確說明哪些想法暫不處理，避免後續誤解。

## 4. 沒經驗如何判斷內容是否足夠？
- **可驗證性**：每個需求都要能被 QA/自動測試清楚驗證。若描述太抽象，補上案例或量化指標。
- **邊界條件**：針對錯誤路徑、多語/多角色等變化提供最少一個情境。
- **使用者視角**：用戶故事語法如「當…我想…因此…」，幫助團隊快速對齊價值。
- **與既有系統關聯**：若會影響現有模組，標注對應檔案或服務名稱，方便 `/plan` 階段展開影響分析。
- **共用詞彙表**：若有專有名詞或縮寫，建議在 Spec 中加「Definitions」章節簡述。

## 5. 編輯 `.codex/prompts` 的最佳做法
`.codex/prompts` 目錄儲存的是 Slash 指令對應的提示詞，採用 YAML Front Matter + Markdown 主體。例如 `specify.md` 包含下列重點：
- `description` 說明這個 prompt 的用途。
- 主體描述了指令在呼叫腳本、讀取模板、寫檔案時的注意事項。

調整方式建議如下：
1. **複製原檔備份**：在修改前先複製一份（例：`cp .codex/prompts/specify.md .codex/prompts/specify.backup.md`）。
2. **保留程式化步驟**：涉及腳本指令（如 `create-new-feature.sh`）的部分不要刪除，否則 Slash 指令無法正常運作。只能在「如何組織內容」、「語氣」、「產物格式」上調整。
3. **新增或調整指示**：你可以在 Markdown 主體補充更多說明，例如要求 LLM 產生更詳細的 Acceptance Criteria，或指定要使用繁體中文。建議以清楚的條列與 Imperative 語氣撰寫。
4. **同步模板**：若 prompt 引導改變了輸出格式，記得同時更新 `.specify/templates/` 的對應檔，讓 CLI 寫出來的 Markdown 結構相容。
5. **測試修改**：修改後執行一次相關 Slash 指令，確認流程仍可順利建立分支與檔案。

## 6. 是否可以以中文撰寫規格？
可以。Spec-Kit 並未限制語言，模板大多為英文標題，你可以保留英文標題並在內容使用繁體中文。若團隊成員熟悉中文，或後續 Agent 也能理解中文，直接用中文撰寫即可；若需要雙語對照，可在每段後面附上英文翻譯或關鍵字，以利跨團隊協作。

## 7. 建議的日常實踐
- 完成 `spec.md` 後請邀請產品/設計/工程夥伴共同審閱，透過 Review Checklist 確認每個需求都有驗收方式。
- 當需求有變更時，先更新 Spec 再觸發 `/plan` 或 `/tasks`，確保開發計畫永遠追隨最新規格。
- 保持 `.codex/prompts` 與 `.specify/templates/` 版本控管，並在 docs/ 目錄更新變更記錄，維持團隊文件同步。

---
若有更多細節想擴充，可以此文為基礎補充企業特定流程（例如權限審批、資安審查），讓整個 SDD 工具鏈與內部治理完全對齊。
