# Codex 實作指令（請原樣貼給 Codex，不要改）

你是 repo 改造工程師。請使用 MCP（github / context7 / kit）在下列 repo 上完成大改：

- Repo：`https://github.com/Sologa/AUTOSR-SDSE`
- 目標：把 seed 流程改成 **One-pass Cutoff-first Seed**，完全符合 Hard Spec（禁止迭代/重跑）。

---

## 0) 先決條件（必須做到）
1) 先 checkout / 讀取基準 commit：`f797666990ea5066d7b3b31499d647777088cd66`
2) 你必須先完整讀完並理解下列檔案（逐一用 GitHub permalink：commit hash + 行號引用）：
   - `docs/seed/seed_flow_current.md`
   - `docs/seed/seed_query_rewrite_plan.md`
   - `docs/seed/seed_rewrite_prompt_context.md`
   - `resources/LLM/prompts/seed/seed_query_rewrite.md`
   - `scripts/topic_pipeline.py`
   - `src/pipelines/topic_pipeline.py`
   - 所有讀寫這些檔案的地方：
     - `seed/queries/arxiv.json`
     - `seed/queries/seed_rewrite.json`
     - `seed/queries/seed_selection.json`
     - `cutoff/cutoff.json`
     - `seed/downloads/download_results.json`
     - `seed/filters/llm_screening.json`
     - `seed/filters/selected_ids.json`

---

## 1) 你必須先用 repo 內搜尋定位（至少用這些關鍵字）
- `SeedQueryRewriteAgent`
- `rewrite_candidates`
- `seed_rewrite.json`
- `arxiv.json`
- `seed_selection.json`
- `cutoff.json`
- `arxiv` / `query` / `client`
- `score` / `scoring` / `iteration` / `loop` / `retry` / `fallback`
- `download_results.json`
- `llm_screening.json` / `selected_ids.json`

---

## 2) 修改規格來源（你要遵守）
請以此文件作為實作規格與待補齊的設計文檔：

- `AUTOSR_SDSE_seed_cutoff_first_spec.md`（此檔案在本次任務附件中提供；你完成實作後必須把其中所有 `[PERMALINK: ...]` 補齊成真實行號 permalink）
- 必須保留文件內的 ASCII 流程圖（不可刪；因部分環境不支援 Mermaid）

---

## 3) Hard Spec（不可更改）
(1) Cutoff-first：topic -> arXiv exact-title match (normalize equality) 找 cutoff paper  
    - 多筆同名：deterministic tie-break  
    - 找不到：deterministic default（建議 fail + 要求 `--cutoff-arxiv-id`）
(2) One-shot rewrite：topic -> N phrases（只做一次，禁止 iterative scoring loop）  
    - phrases 禁止包含 survey/review/overview 及同義；code 端 case-insensitive 檢查與清理  
    - **phrases 必須為英文（English-only）**：任何包含非 ASCII 字元的 phrase 必須被丟棄並記錄；若最後沒有任何可用 phrases → fail（one-pass，不 rerun）
(3) 每 phrase 生成 query_i：`(w1 OR ... OR wk) AND (survey OR review OR overview)`  
    - 每個 query_i 單獨查 arXiv（多次搜尋）
(4) 硬過濾：
    - 剔除 cutoff 本身  
    - 剔除 date > cutoff_date（只保留 <= cutoff_date）  
    - 明確定義 date_field（published/submitted/updated）且 code/doc 一致
(5) One-pass：不可重跑、不可候選為空 rerun、不可 rewrite 迭代

---

## 4) 你必須實作的項目（務必真的改 code + 跑測試）
1) 新增 `--seed-mode {legacy,cutoff-first}`（建議保留 legacy 以利回滾）
2) 新增 cutoff override flags：
   - `--cutoff-arxiv-id`
   - `--cutoff-title-override`
   - `--cutoff-date-field`
3) 修改 seed rewrite prompt 與解析：
   - `resources/LLM/prompts/seed/seed_query_rewrite.md` 改成輸出 JSON（phrases array）
   - 加 blacklist 清理（case-insensitive）
4) 新增/改造 arXiv query builder：符合硬規格 OR+AND
5) 新增 cutoff hard filter（exclude cutoff + date filter）
6) 更新/擴充 workspace 產物 schema（建議加 `schema_version`，維持向後相容）
7) 新增測試：
   - unit tests：mock arXiv 回應、tie-break、blacklist、query builder、date filter
   - integration test：用真實 topic 跑到輸出檔案，驗證 cutoff filter 正確
8) 跑 `pytest`（必須在輸出中附上實際命令與結果摘要）
9) 更新 docs：
   - 更新 `docs/seed/seed_flow_current.md`（新流程為主，legacy 為附錄）
   - 更新/補齊 `AUTOSR_SDSE_seed_cutoff_first_spec.md`（把所有 permalinks 填滿）

---

## 5) 最終輸出（你必須輸出以下 4 段）
A) 變更摘要（逐條對應 Hard Spec）  
B) 修改過的檔案列表（每檔案說明 + permalink：commit hash + 行號）  
C) 如何在本機重現（安裝/執行/測試命令可 copy-paste）  
D) PR/commit 說明（title + bullets）

---

## 6) 實作時注意
- 任何 iteration/scoring/retry loop 一律移除或放到 legacy mode
- 所有 deterministic 規則（tie-break、blacklist、tokenization、排序）都要寫進 code + docs
- cutoff-first mode 下 seed 只能輸出 **英文** phrases/tokens/query；非 ASCII 一律丟棄並記錄
- 所有日期欄位的選擇（published/updated/submitted）必須一致，並寫入 cutoff.json
