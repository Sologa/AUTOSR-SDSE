# Pipeline 現況交接（新對話用）

本文件用來在新對話中交代 **目前 pipeline 的實作現況、各階段分歧、輸出路徑、已知問題與近期改動**。內容依據 repo 內文件與程式碼整理（已使用 kit mcp 檢索）。

---

## 0) 如何使用這份文件

- 目的：在新的對話串快速讓 AI 了解「目前做到了哪、哪些地方踩過坑、哪些行為已經改過」。
- 使用方式：把 **「可貼給新對話的 prompt 模板」**那一節直接貼進新的對話即可。

---

## 1) Pipeline 全貌（高階概述）

- Topic CLI pipeline 會把所有產物寫入 `workspaces/<topic_slug>/`（避免把正式資料塞進 `test_artifacts/`）。
- 主要階段順序：**seed →（可選）filter-seed → keywords → harvest →（可選）harvest-other →（可選）criteria →（可選）review →（可選）snowball**。
- snowball 已改為 **迭代式**，每輪會執行 LatteReview，並輸出 `snowball_rounds/round_XX`、全歷史 `review_registry.json`，以及彙整輸出 `final_included.json/csv`。
- keywords 階段會產生 `anchor_terms` 與 `search_terms`，後續 harvest 使用「anchor × search_term」組合查詢。

---

## 2) 各階段輸入 / 輸出 / 分歧條件

### A) seed（主題搜尋與下載 survey）
- 入口：`python scripts/topic_pipeline.py seed --topic "<topic>"`
- 輸出：`workspaces/<topic_slug>/seed/`
- 分歧：
  - 可直接指定 `--arxiv-raw-query` 走 raw query
  - 或用 anchors + survey modifiers 組合查詢
- 輸出/資料夾（重點）：
  - `seed/queries/arxiv.json`
  - `seed/downloads/arxiv/*.pdf`
  - `seed/downloads/arxiv_raw/*.pdf`（若有 filter-seed）

### B) filter-seed（可選；LLM 以 title+abstract 篩選）
- 入口：`python scripts/topic_pipeline.py filter-seed --topic "<topic>"`
- 行為：LLM 判斷 **survey/review/overview** 且主題直接相關才保留
- 輸出：
  - `seed/filters/llm_screening.json`
  - `seed/filters/selected_ids.json`
  - 保留的 PDF 仍在 `seed/downloads/arxiv/`
  - 原始下載保留於 `seed/downloads/arxiv_raw/`

### C) keywords（從 seed PDFs 抽 anchor/search terms）
- 入口：`python scripts/topic_pipeline.py keywords --topic "<topic>"`
- 核心行為：
  - 會讀 seed PDFs，輸出 `keywords.json`
  - **模型固定 gpt-5.2、temperature 固定 1.0**（CLI 參數仍可輸入但會被忽略）
- 重要變更（本次已修正的痛點）：
  - **不再用 topic 變體強制覆寫 anchor**（避免 topic/縮寫污染）
  - 新增 **anchor 清理**：去掉與 topic 同形變體、含標點的 anchor；優先從 PDF/metadata 與 search_terms 取可用 anchor
- 輸出：
  - `workspaces/<topic_slug>/keywords/keywords.json`
  - `workspaces/<topic_slug>/keywords/keyword_extractor_usage_<timestamp>.json`

### D) harvest（arXiv metadata）
- 入口：`python scripts/topic_pipeline.py harvest --topic "<topic>"`
- 行為：以 `(anchor) AND (term)` 組合查詢 arXiv
- 輸出：`workspaces/<topic_slug>/harvest/arxiv_metadata.json`
- 已知現象：
  - **search_terms 若過泛**，仍會引入噪音（這是 arXiv 查詢與詞組匹配的特性，非 anchor 汙染問題）

### E) harvest-other（可選）
- 入口：`python scripts/topic_pipeline.py harvest-other --topic "<topic>"`
- 會補 Semantic Scholar / DBLP（若啟用）

### F) criteria（可選）
- 入口：`python scripts/topic_pipeline.py criteria --topic "<topic>" --mode web|pdf+web`
- 輸出：`workspaces/<topic_slug>/criteria/criteria.json`
- mode 分支：
  - `web`：用 web search 產生規則
  - `pdf+web`：PDF 摘要 + web search

### G) review / snowball（可選）
- review：LatteReview title/abstract 初篩（base review）
- snowball：迭代式 snowball（每輪含 LatteReview），輸出 round_XX 與 `review_registry.json`
- 皆為可選階段；snowball 需要先有 base review 結果

---

## 3) 「已經修改過」的關鍵行為（供新對話知道前因後果）

1) **新增 filter-seed**：
   - LLM 以 title+abstract 判斷是否為 survey/review/overview 且主題直接相關。
   - 為維持 keywords 介面不變，採「原始 PDF 轉移到 arxiv_raw；保留通過的在 arxiv」方案。

2) **keywords 的 anchor 修正**：
   - 問題：當 topic 為論文標題時，LLM 會直接抄題名與亂造縮寫 → harvest 失真。
   - 修正：
     - `use_topic_variants=False`（不再強制塞入 topic 變體）
     - 新增 anchor 清理規則，剔除不合格錨點
     - 最終 anchor 會從 PDF/metadata 與 search_terms 中挑出可用短片語

3) **keywords prompt 已加入 topic 類型判斷**：
   - topic 可能是「研究領域」或「論文標題」
   - 若是論文標題：禁止照搬標題與縮寫

4) **keywords 固定模型/溫度**：
   - `gpt-5.2` + `temperature=1.0`

5) **xhigh reasoning_effort 已加入支援**：
   - `src/utils/llm.py` 允許 `xhigh`
   - 實測 xhigh 可能會非常久（甚至超過 30 分鐘）

6) **criteria 自動加入「同標題排除」**：
   - 若 seed 選擇結果偵測到與 topic 同標題的 cutoff candidate，criteria 會自動排除該標題論文；時間限制僅由程式端 discard，criteria 條款不包含日期。
   - formatter 預設模型更新為 **gpt-5.2**；search 預設模型更新為 **gpt-5.2-chat-latest**（若指定 `gpt-5-search-api`，需改用 `web_search_2025_08_26` 工具版本）。
   - 修正 structured prompt：移除「OR 合併成單條」的矛盾規則，改為使用 `any_of` 表達 OR。
   - 新增來源日期驗證：若來源無法抽取日期或晚於 cutoff，會觸發重跑；超過重試次數將報錯。
   - 系統規則（如排除指定標題/時間 cutoff）允許 source 為 internal 或空白，不要求附網頁來源。

7) **snowball 改為迭代式（每輪含 review）**：
   - 由 `scripts/snowball_iterate.py` 驅動，可多輪迭代。
   - 每輪輸出 `snowball_rounds/round_XX/*`，並更新全歷史 `review_registry.json`。

8) **新增 seed query 改寫機制**：
   - 觸發條件：seed 無 PDF 或 `cutoff_removed_all_candidates`。
   - 使用 `SeedQueryRewriteAgent`（`gpt-5.2`）產生單一片語並重試 seed。
   - 輸出 `seed/queries/seed_rewrite.json`，`download_results.json` 會補上 `rewrite_attempts` / `rewrite_query`。
   - 同名 cutoff 固定啟用（`--no-cutoff-by-similar-title` 會被忽略）。

9) **seed 標題強制過濾**：
   - seed 只保留 title 含 `survey` / `review` / `overview` 的紀錄。

---

## 4) 已知問題 / 風險

- **Harvest 噪音**：
  - 即使 anchor 修好，search_terms 太泛仍會拉入大量無關 paper。
  - 需靠縮小 search_terms 或調整查詢策略。

- **criteria 的 web search 結果**：
  - 來源品質需要人工確認（web 模式會自動列來源）。

---

## 5) 新對話可直接使用的 prompt 模板

```
你是維護這個 repo 的 AI agent，請先閱讀以下 repo 現況與變更摘要，並依此處理後續任務。

【Repo 現況摘要】
- Topic CLI pipeline：seed →（可選）filter-seed → keywords → harvest →（可選）harvest-other →（可選）criteria →（可選）review →（可選）snowball（迭代式，每輪含 LatteReview）
- 所有產物寫入 workspaces/<topic_slug>/
- filter-seed：LLM 以 title+abstract 篩選；只保留 survey/review/overview 且主題直接相關；保留 PDF 於 seed/downloads/arxiv/，原始下載保留於 arxiv_raw/。
- keywords：模型固定 gpt-5.2，temperature 固定 1.0；不再用 topic 變體強制覆寫 anchor；新增 anchor 清理（去掉 topic/標點/亂縮寫），anchor 從 PDF/metadata 與 search_terms 中產出。
- keywords prompt 已加入 topic 類型判斷（研究領域 vs 論文標題）；若是論文標題禁止抄題與縮寫。
- harvest：用 (anchor) AND (term) 查 arXiv；search_terms 太泛仍會造成噪音。
- criteria：mode=web 或 pdf+web，輸出 criteria.json。
- xhigh reasoning_effort 已加入支援，但可能超時。
- snowball：使用 `scripts/snowball_iterate.py` 多輪迭代；每輪輸出 round_XX，累積結果在 `review_registry.json`。

【請求】
1) 請用 kit mcp 讀 repo 相關檔案後再回答。
2) 若需外部 repo/官方資訊，再用 context7 mcp。
3) 先確認目前任務要處理 pipeline 的哪一個階段，再開始修改。
```

---

## 6) 參考文件（repo 內）

- `docs/pipelines/topic_cli_pipeline.md`
- `docs/keywords/spec.md`
- `docs/filter-seed/spec.md`
- `resources/LLM/prompts/keyword_extractor/generate_search_terms.md`
- `src/utils/keyword_extractor.py`
- `src/pipelines/topic_pipeline.py`
- `scripts/topic_pipeline.py`
