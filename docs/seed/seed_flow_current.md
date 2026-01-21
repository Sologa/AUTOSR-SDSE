# Seed 流程完整復盤（Cutoff-first 為主）

本文件以 **現行程式碼（含 cutoff-first 與 legacy 兩種模式）** 為準，描述 seed 階段的輸入、流程與產物。

> 範圍：`python scripts/topic_pipeline.py seed`（以及後續可選的 `filter-seed`）。
> 來源：`src/pipelines/topic_pipeline.py`、`scripts/topic_pipeline.py`。

---

## 1) 輸入與核心參數

### 1.1 cutoff-first 模式（one-pass，預設建議）
- `--seed-mode cutoff-first`
- `--cutoff-arxiv-id`：手動指定 cutoff paper id
- `--cutoff-title-override`：用指定 title 取代 topic 進行 exact-title match
- `--cutoff-date-field`：`published|updated|submitted`（submitted 會映射到 published）
- `--seed-rewrite-n`：LLM 產生片語數量上限
- `--seed-blacklist-mode`：`clean|fail`
- `--seed-arxiv-max-results-per-query`：每個 phrase 的 arXiv 查詢上限
- `--seed-max-merged-results`：合併後保留筆數上限
- `--seed-rewrite-provider / --seed-rewrite-model / --seed-rewrite-reasoning-effort`：改寫 LLM 設定
- `--seed-rewrite-codex-*`：Codex CLI 參數（選用）

### 1.2 legacy 模式（舊流程，保留回滾）
- `--seed-mode legacy`
- `--max-results / --scope / --boolean-operator / --anchor-operator / --anchor-mode`
- `--cutoff-by-similar-title / --similarity-threshold`
- `--seed-rewrite / --seed-rewrite-max-attempts / --seed-rewrite-preview`（迭代式 rewrite）
- `--no-cache`（重用或忽略 `seed/queries/arxiv.json`）

---

## 2) 核心輸出與檔案

- `workspaces/<topic_slug>/seed/queries/arxiv.json`：每個 phrase 的 arXiv 查詢結果（v2，含 per-query filtered 統計）
- `workspaces/<topic_slug>/seed/queries/seed_rewrite.json`：rewrite 產物（v2，JSON phrases + blacklist + English-only 記錄）
- `workspaces/<topic_slug>/seed/queries/seed_selection.json`：合併後候選（v2，cutoff_ref 可為 null）
- `workspaces/<topic_slug>/cutoff/cutoff.json`：cutoff metadata（v2；僅在找到 cutoff 時寫入）
- `workspaces/<topic_slug>/seed/downloads/download_results.json`：下載結果（由 filter-seed 產生；seed 不下載）
- `workspaces/<topic_slug>/seed/downloads/ta_filtered/*.pdf`：title+abstract 篩選後下載（filter-seed）
- `workspaces/<topic_slug>/seed/downloads/pdf_filtered/`：保留給下載後複審（目前不寫入）
- `workspaces/<topic_slug>/seed/filters/llm_screening.json` / `selected_ids.json`：filter-seed 產物（選用）

---

## 3) cutoff-first 流程（one-pass）

1) **CutoffFinder**
   - `topic` 先做 arXiv exact-title match（normalize equality）。
   - 多筆同名：最早日期 + arXiv id lexicographic tie-break。
   - 找不到同名：不產生 `cutoff.json`，後續流程不套用 cutoff。
   - 找到 cutoff：產出 `cutoff/cutoff.json`（v2，含 `date_field`）。

2) **One-shot rewrite（JSON phrases）**
   - LLM 產生英文 phrases（只做一次；不可重跑）。
   - blacklist（survey/review/overview 等）清理或 fail（視 `--seed-blacklist-mode`）。
   - 非 ASCII phrases 丟棄並記錄；若最終為空 → fail。
   - 產出 `seed/queries/seed_rewrite.json`（v2）。

3) **Per-phrase query builder**
   - 每個 phrase 拆 token → `(w1 OR ... OR wk) AND (survey OR review OR overview)`。
   - 每個 query_i 單獨查 arXiv。

4) **Hard filter（cutoff-first）**
   - 排除 cutoff 本身。
   - 排除 `paper_date > cutoff_date`（只保留 `<= cutoff_date`）。
   - 缺日期 → 排除並記錄（僅在有 cutoff 時）。

5) **Merge → seed_selection.json（v2）**
   - union 去重（key=arxiv_id）。
   - sort：`date_field desc` + `arxiv_id asc`。
   - cap：`--seed-max-merged-results`。

6) **Filter-Seed（選用，獨立 stage）**
   - 只用 title/abstract 篩選（不讀 PDF）。
   - 排除 cutoff paper（避免回流；無 cutoff 時略過）。
   - 通過者下載到 `seed/downloads/ta_filtered/`。

---

## 4) cutoff-first ASCII 流程圖

```text
[Input: topic]
    |
    v
[Step 1: CutoffFinder — arXiv exact-title match]
    |  if found: write
    v
(cutoff/cutoff.json)
    |
    v
[Step 2: PhraseRewriter (LLM one-shot + blacklist + English-only)]
    |  write
    v
(seed/queries/seed_rewrite.json)
    |
    v
FOR EACH phrase_i:
  |
  v
  [Step 3: Build query_i = (w1 OR ... OR wk) AND (survey OR review OR overview)]
        |
        v
  [arXiv search(query_i)]
        |
        v
  [Step 4: Hard filter — exclude cutoff_id; exclude date > cutoff_date]
        |
        v
  append/record -> (seed/queries/arxiv.json)

    |
    v
[Step 5: Merge + deterministic order]
    |  write
    v
(seed/queries/seed_selection.json)
```

---

## Appendix A) legacy 模式摘要（保留回滾）

- 先用 topic variants + survey modifiers 產生單一 query。
- 使用 cache（`seed/queries/arxiv.json`）或重新查詢。
- Title filter + similarity cutoff（exact title / similarity threshold）。
- 若候選為空或 cutoff 移除全部 → 進入 LLM rewrite（多輪候選 + scoring + 重跑）。
- 產物沿用 `seed_selection.json` / `seed_rewrite.json` / `download_results.json`（legacy schema）。

> legacy 模式完整細節請參考舊文件與程式碼註解；cutoff-first 為目前主流程。
