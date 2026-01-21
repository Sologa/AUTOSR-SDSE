# Seed 流程大改設計：One-pass Cutoff-first Seed（vNext）

> 目的：把 AUTOSR-SDSE 的 seed 流程「大改」為 **one-pass cutoff-first**（不是調參），完全符合 Hard Spec（見下）。
>
> 本文件是 **Codex 的實作規格 + repo 內設計文檔草案**。  
> Codex 在完成實作後，必須把本文件中的所有 `[PERMALINK: ...]` 佔位符替換成 **GitHub permalink（含 commit hash + 行號）**，並把「現況流程拆解」補齊到鉅細靡遺。

---

## 0. Metadata

- Repo：`https://github.com/Sologa/AUTOSR-SDSE`
- 參考基準 commit（請 Codex 先 checkout 再讀檔）：`f797666990ea5066d7b3b31499d647777088cd66`
- Permalink 格式要求：
  - `https://github.com/Sologa/AUTOSR-SDSE/blob/<commit>/<path>#Lx-Ly`
  - 例如：`.../blob/f797666.../docs/seed/seed_flow_current.md#L10-L120`

---

## 1. Hard Spec（不可更改）

### (1) Cutoff-first（Topic → cutoff paper）
- 接收 topic 後，先直接去 arXiv 搜尋，找出 **title 與 topic 同名（normalize 後精確匹配）** 的 cutoff paper。
- cutoff paper 識別至少包含：**arXiv id / title / published(or submitted) date**。
- 若 arXiv 回傳多筆同名：必須有 deterministic tie-break，寫進規格與 code。
- 若找不到同名：必須有 deterministic 處理策略（default：不產生 cutoff.json，後續不套用 cutoff；若提供 override 則以 override 為準）。

### (2) One-shot rewrite topic → search phrases（不可迭代）
- 由 agent/LLM 直接 rewrite topic 成它認為合適的 search phrases（若 topic 非英文，必須先翻譯/改寫為**英文** phrases）。
- **只做一次**：不可 iterative scoring loop、不可候選為空就再跑一輪。
- phrases 中 **禁止**包含任何 survey/review/overview 及其變體/同義（需列出完整 blacklist；code 端做 case-insensitive 檢查與清理）。
- **phrases 必須為英文**：任何包含非 ASCII 字元的 phrase 必須被丟棄並記錄；若最終沒有任何可用 phrases → fail（one-pass，不 rerun）。

### (3) Query 生成（每個 phrase 獨立查 arXiv）
對每個 phrase：
- 把 phrase 拆成 words，做成 OR term：
  - `term = (w1 OR w2 OR ... OR wk)`
- 然後再 AND 上：
  - `(survey OR review OR overview)`
- 生成 `query_i = term AND (survey OR review OR overview)`  
- **每個 phrase 都要單獨查 arXiv**（多個 query，多次搜尋）。

### (4) arXiv 結果硬過濾（只保留 <= cutoff_date）
- 強制剔除 cutoff paper 本身
- 強制剔除 **時間點晚於 cutoff paper** 的所有 paper（只保留 `<= cutoff_date`）
- 必須明確定義用哪個日期欄位（published / submitted / updated），並在文件與 code 中一致。

### (5) One-pass（不可重跑）
以上只做一次（one-pass），不可 seed rewrite 迭代、不可候選為空就再跑一輪等機制。

---

## 2. 背景與現況（必須由 Codex 補齊到「鉅細靡遺」）

> Codex 必須先完整讀完下列檔案，並在本章節補上：
> - 每一步做什麼
> - I/O（輸入輸出檔案路徑、JSON schema）
> - CLI flags / config
> - cache 行為（檔案存在就跳過？hash？）
> - 是否存在 selection/cutoff/rewrite loop、scoring、retry
> - 每個關鍵結論都要附 permalink（含行號）

### 2.1 必讀文件/程式（請逐一引用）
- https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/docs/seed/seed_flow_current.md#L1-L131
- https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/docs/seed/seed_query_rewrite_plan.md#L1-L39
- https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/docs/seed/seed_rewrite_prompt_context.md#L1-L25
- https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/resources/LLM/prompts/seed/seed_query_rewrite.md#L1-L20
- https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L60-L640
- https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L149-L3344
- 任何 arXiv client / query builder / selection / cutoff / cache 相關程式碼：
  - https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1235-L1243
  - https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1314-L1338
  - https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L160-L425
  - https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2126-L2157
  - https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2160-L2220
  - https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2223-L2270

### 2.2 現行 seed 流程逐步拆解（模板，Codex 請填滿）
> 請以表格列出每一步（Step 0..N），並把「檔案產物」對齊現行 workspace 結構。

| Step | 名稱 | 入口函式/類別（permalink） | 輸入 | 輸出檔案 | cache 行為 | flags/config | 是否迭代/重試 |
|---|---|---|---|---|---|---|---|
| 0 | 讀 topic / 初始化 workspace + CutoffFinder | https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L955-L1091；https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L342-L425 | topic + cutoff flags | workspace/ + `cutoff/cutoff.json`（僅在有 cutoff 時） | 無 cache（找到 cutoff 時覆寫） | `--topic` / `--workspace-root` / `--seed-mode cutoff-first` / `--cutoff-*` | 否 |
| 1 | seed rewrite（one-shot） | https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3196-L3248 | topic | `seed/queries/seed_rewrite.json` | 無 cache（每次覆寫） | `--seed-rewrite-n` / `--seed-blacklist-mode` / `--seed-rewrite-provider` / `--seed-rewrite-model` | 否 |
| 2 | arXiv 查詢（per phrase） | https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3255-L3291 | phrases | `seed/queries/arxiv.json` | 無 cache | `--seed-arxiv-max-results-per-query` | per-phrase loop（非重試） |
| 3 | seed selection（merge） | https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3309-L3320 | results | `seed/queries/seed_selection.json` | 無 cache | `--seed-max-merged-results` | 否 |
| 4 | filter-seed（若有） | https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2393-L2721 | selection | `seed/filters/llm_screening.json` / `selected_ids.json` / `seed/downloads/ta_filtered/*.pdf` / `seed/downloads/download_results.json` | 既有檔案且未 `--force` → skip | `filter-seed` 子命令參數 | per-paper loop（非重試） |

### 2.3 現行產物與 schema（Codex 請引用範例檔案）
- `cutoff/cutoff.json`（僅在有 cutoff 時）：`https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/workspaces/discrete_audio_tokens_more_than_a_survey/cutoff/cutoff.json#L1-L18`
- `seed/queries/seed_rewrite.json`：`https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_rewrite.json#L1-L40`
- `seed/queries/arxiv.json`：`https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/arxiv.json#L1-L8`
- `seed/queries/seed_selection.json`：`https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/workspaces/discrete_audio_tokens_more_than_a_survey/seed/queries/seed_selection.json#L1-L60`

---

## 3. 新流程設計（Cutoff-first One-pass）

### 3.1 高階流程圖（必須保留在最終文件）

```text
[Input: topic]
    |
    v
[Step 1: CutoffFinder — arXiv exact-title match after normalization]
    |  if found: write
    v
(cutoff/cutoff.json)
    |
    v
[Step 2: PhraseRewriter (LLM one-shot + blacklist clean + English-only)]
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
  append/record per-query results -> (seed/queries/arxiv.json)

    |
    v
[Step 5: Merge + deterministic order]
    |  write
    v
(seed/queries/seed_selection.json)
    |
    v
[Downstream: filter-seed downloads → ta_filtered; pdf_filtered reserved]
```

### 3.2 Step 1：CutoffFinder（topic → cutoff paper）

#### 3.2.1 Title normalization（deterministic）
`normalize_title(s: str) -> str`（需 unit test）
1) Unicode NFKC
2) lower-case
3) 移除/弱化常見 LaTeX 結構（保守、可重現）：
   - 移除 `$...$`、`\(...\)`、`\[...\]`
   - 去掉 `\text{}`, `\mathrm{}`, `\mathbf{}` 等命令（保留內文）
4) 所有非字母數字字元替換為空白
5) 多空白壓成單一空白、trim

**精確匹配定義**：  
`normalize_title(arxiv_title) == normalize_title(topic)`

#### 3.2.2 arXiv cutoff 搜尋策略
- 使用 title 欄位檢索（例如 `ti:"<topic>"` 或 repo 既有語法等價物）以提高同名召回。
- 取得候選後做 normalization equality filter。

#### 3.2.3 同名多筆 deterministic tie-break（必須寫進 code + cutoff.json）
1) 以 `cutoff_date_field`（預設 `published`）**最早**者為 cutoff（升冪）
2) 若日期相同或缺失：以 `arxiv_id` lexicographic 升冪決勝（id 最小）

#### 3.2.4 找不到同名（default 策略）
- **default：不產生 cutoff.json**，後續流程不套用 cutoff。
- 若需指定 cutoff，可使用：
  - `--cutoff-arxiv-id <id>` 或
  - `--cutoff-title-override "<exact title>"`
- 不做 fuzzy match（除非明確旗標開啟，且必須 deterministic）

#### 3.2.5 cutoff.json（v2）Schema（範例）
```json
{
  "schema_version": "cutoff.v2",
  "topic_input": "Discrete Audio Tokens",
  "topic_normalized": "discrete audio tokens",
  "date_field": "published",
  "tie_break": ["published_asc", "arxiv_id_asc"],
  "cutoff": {
    "arxiv_id": "2401.01234",
    "title": "Discrete Audio Tokens",
    "title_normalized": "discrete audio tokens",
    "published": "2024-01-03T00:00:00Z",
    "updated": "2024-01-05T00:00:00Z",
    "primary_category": "cs.SD",
    "authors": ["..."],
    "url_abs": "https://arxiv.org/abs/2401.01234"
  },
  "candidates_same_title": [
    { "arxiv_id": "2401.01234", "published": "2024-01-03T00:00:00Z" }
  ],
  "errors": []
}
```

---

### 3.3 Step 2：PhraseRewriter（LLM one-shot）

#### 3.3.1 要求
- 一次性：輸入 topic → 輸出 N 個 **英文** phrases
- 不可 iterative scoring loop / retry
- phrases 禁止含 survey/review/overview 及其同義變體（見 blacklist）
- phrases 必須為英文：任何包含非 ASCII 字元的 phrase 必須丟棄並記錄；若 `phrases_clean` 最終為空 → **fail**（one-pass，不 rerun）

#### 3.3.2 英文限定（deterministic；強制）
**English-only 定義（default，強制）**
- phrase 在完成 blacklist 清理與空白正規化後，必須同時滿足：
  - 全字串只含 ASCII 可列印字元（U+0020..U+007E）
  - 至少包含 1 個英文字母（`[A-Za-z]`）
- 不符合者：直接丟棄（不嘗試 transliteration / 翻譯），並在 `seed_rewrite.json` 記錄 `reason` 與原文。

> 註：LLM prompt 必須要求輸出英文 phrases；英文限定檢查是最後防線，用於保證 seed query 嚴格英文且可重現。

#### 3.3.3 Blacklist（英文；規格與 code 必須一致；case-insensitive）
> 目標：phrase 不能包含任何「survey/review/overview」概念或其同義（即使是以別的詞彙表達）。

**英文核心 + 常見變體（建議以 regex + word boundary 實作）**
- survey / surveys / surveying / surveyed
- review / reviews / reviewing / reviewed
- overview / overviews
- tutorial / tutorials
- state of the art / state-of-the-art / sota
- literature review / systematic review / scoping review
- meta analysis / meta-analysis / meta-analytic
- taxonomy / taxonomies
- roadmap / road map
- primer / perspective / revisit / revisiting
- comprehensive
- 片語：a survey of / an overview of / a review of

#### 3.3.4 清理策略（deterministic）
- default：`clean`
  1) normalize whitespace（trim + collapse spaces）
  2) blacklist 命中片段替換為空白（case-insensitive）
  3) 再次 normalize whitespace
  4) 英文限定檢查（3.3.2）
  5) 清理後為空 → 丟棄該 phrase
- 若提供 `--seed-blacklist-mode=fail`（可選）：任一 phrase 命中 blacklist → 立即 fail（one-pass，不 rerun）
- 若 `phrases_clean` 最終為空：**fail**（one-pass，不 rerun）

#### 3.3.5 seed_rewrite.json（v2）Schema（範例）
```json
{
  "schema_version": "seed_rewrite.v2",
  "topic_input": "Discrete Audio Tokens",
  "provider": "openai|codex-cli",
  "model": "string",
  "n_requested": 5,
  "phrases_raw": [
    "discrete audio tokenization for speech generation",
    "survey of discrete audio tokens",
    "<NON_ASCII_PHRASE>"
  ],
  "english_only": {
    "enabled": true,
    "dropped": [
      { "phrase": "<NON_ASCII_PHRASE>", "reason": "non_ascii" }
    ]
  },
  "blacklist": {
    "mode": "clean",
    "patterns": ["survey", "review", "overview", "tutorial", "state of the art", "sota", "..."],
    "hits": [
      { "phrase": "survey of discrete audio tokens", "matched": ["survey"] }
    ]
  },
  "phrases_clean": [
    "discrete audio tokenization for speech generation"
  ],
  "errors": []
}
```

---

### 3.4 Step 3：Query Builder（per phrase）

#### 3.4.1 Tokenization（deterministic；英文 token only）
- 前置條件：`phrases_clean` 已通過 **英文限定**（3.3.2）
- phrase 先把非字母數字替換為空白，再壓空白
- 依空白切 tokens
- tokens 全部轉小寫，並只保留符合 `^[a-z0-9]+$` 的 token（其餘丟棄並記錄）
- 去除空 token
- 依出現順序去重（避免 OR term 重複）
- 若 token 數過多（例如 >32）：可截斷並記錄（或 fail；default 建議截斷）

#### 3.4.2 Query 組法（硬規格）
- `term = (w1 OR w2 OR ... OR wk)`
- `query_i = term AND (survey OR review OR overview)`
- 每個 query_i 必須單獨呼叫 arXiv search

---

### 3.5 Step 4：Hard Filter（cutoff exclusion + cutoff_date）

#### 3.5.1 必須排除
- `arxiv_id == cutoff.arxiv_id` → drop
- `paper_date > cutoff_date` → drop
- 保留：`paper_date <= cutoff_date`

#### 3.5.2 日期欄位（必須一致）
- default：`published`
- CLI 可覆蓋：`--cutoff-date-field published|updated|submitted`（僅允許 repo 真的有的欄位）
- 缺日期：default **剔除**並記錄（避免不小心放過晚於 cutoff 的 paper）

---

### 3.6 arxiv.json（v2）Schema（範例）

```json
{
  "schema_version": "seed_arxiv_queries.v2",
  "cutoff_ref": {
    "arxiv_id": "2401.01234",
    "date_field": "published",
    "cutoff_date": "2024-01-03T00:00:00Z"
  },
  "queries": [
    {
      "phrase": "discrete audio tokenization for speech generation",
      "tokens": ["discrete", "audio", "tokenization", "speech", "generation"],
      "query": "(discrete OR audio OR tokenization OR speech OR generation) AND (survey OR review OR overview)",
      "requested_max_results": 50,
      "raw_results_count": 50,
      "filtered": {
        "excluded_cutoff_id": 1,
        "excluded_after_cutoff": 12,
        "excluded_missing_date": 0,
        "kept": 37
      },
      "results_kept": [
        {
          "arxiv_id": "2309.00001",
          "title": "...",
          "published": "2023-09-01T00:00:00Z",
          "updated": "2023-09-10T00:00:00Z",
          "url_abs": "https://arxiv.org/abs/2309.00001"
        }
      ]
    }
  ],
  "errors": []
}
```

---

### 3.7 Step 5：Merge → seed_selection.json（v2）

#### 3.7.1 Merge policy（deterministic）
- union 去重（key = arxiv_id）
- sort（default）：`published desc`, tie-break `arxiv_id asc`
- cap：`--seed-max-merged-results`（default 200）

#### 3.7.2 seed_selection.json（v2）Schema（範例）
```json
{
  "schema_version": "seed_selection.v2",
  "cutoff_ref": { "arxiv_id": "2401.01234", "cutoff_date": "2024-01-03T00:00:00Z", "date_field": "published" },
  "selection_policy": {
    "merge": "union",
    "sort": ["published_desc", "arxiv_id_asc"],
    "max_total": 200
  },
  "selected": [
    { "arxiv_id": "2312.00002", "published": "2023-12-02T00:00:00Z", "source_queries": [0, 2] }
  ]
}
```

---

## 4. CLI / Config 變更

### 4.1 新增 flags（建議）
- `--seed-mode {legacy,cutoff-first}`
- `--cutoff-arxiv-id <id>`
- `--cutoff-title-override "<title>"`
- `--cutoff-date-field {published,updated,submitted}`（default published；實際允許值依 repo arXiv 欄位）
- `--seed-rewrite-n <N>`（default 5）
- `--seed-blacklist-mode {clean,fail}`（default clean）
- `--seed-arxiv-max-results-per-query <M>`（default 50）
- `--seed-max-merged-results <K>`（default 200）

### 4.2 廢棄/移除（Codex 需依現行 flags 寫出清單）
現行 flags（permalink）：
- seed 子命令（cutoff-first + legacy）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L80-L179
- run 子命令（cutoff-first + legacy）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L339-L409

legacy-only / cutoff-first 不採用的 flags（迭代/重試/舊查詢行為）：
- seed 子命令：`--max-results`/`--scope`/`--boolean-operator`/`--anchor-operator`/`--anchor-mode`/`--no-cache`/`--cutoff-by-similar-title`/`--similarity-threshold`  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L87-L137
- seed 子命令：`--seed-rewrite`/`--seed-rewrite-max-attempts`/`--seed-rewrite-preview`（迭代式 rewrite）  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L139-L161
- run 子命令：`--seed-*` legacy 查詢與 rewrite 旗標（對應 seed 子命令）  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L345-L382

legacy vs cutoff-first 切換：
- `--seed-mode`（seed 子命令）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L80-L86
- `--seed-mode`（run 子命令）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L339-L344
- dispatch（cutoff-first → `seed_surveys_from_arxiv_cutoff_first`；legacy → `seed_surveys_from_arxiv`）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L465-L509

---

## 5. 需要修改的 code 範圍（精確函式與行號）

### 5.1 `scripts/topic_pipeline.py`（CLI）
- permalink：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L60-L509
- 新增/調整 flags（cutoff-first）：
  - `--seed-mode` / `--cutoff-*` / `--seed-rewrite-n` / `--seed-blacklist-mode` / `--seed-arxiv-max-results-per-query` / `--seed-max-merged-results`  
    https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L80-L179
  - run 子命令對應 `--seed-*`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L339-L409
- 切換入口：`seed_surveys_from_arxiv_cutoff_first` vs `seed_surveys_from_arxiv`  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/scripts/topic_pipeline.py#L465-L509

### 5.2 `src/pipelines/topic_pipeline.py`（seed 主流程）
- permalink：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L149-L3344
- CutoffFinder（exact-title + tie-break + v2 schema）：
  - `_resolve_cutoff_date_field(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L160-L167
  - `_extract_date_value(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L170-L186
  - `_collect_cutoff_candidates(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L216-L250
  - `_select_cutoff_candidate(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L253-L268
  - `_build_cutoff_payload(...)`（cutoff.json v2 + backward fields）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L271-L339
  - `_find_cutoff_paper(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L342-L425
- Title normalization（LaTeX + unicode）：`_normalize_title_for_match(...)`  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1235-L1243
- Rewrite JSON + blacklist + English-only：
  - `_parse_seed_rewrite_payload(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1818-L1832
  - `_validate_seed_phrase_english(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1854-L1862
  - `_clean_seed_rewrite_phrases(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1865-L1905
  - `SeedQueryRewriteAgent.rewrite_phrases(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2067-L2119
- Query builder（OR+AND）：
  - `_tokenize_seed_phrase_for_query(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2126-L2149
  - `_build_seed_query_from_tokens(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2152-L2157
- Hard filter（有 cutoff 時套用 cutoff id + cutoff_date）：`_filter_seed_records_by_cutoff(...)`  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2160-L2220
- Merge（deterministic）：`_merge_seed_query_results(...)`  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2223-L2270
- Downstream 適配（v2 schema 讀取）：
  - `_load_seed_records_index(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1564-L1613
  - `_load_seed_candidate_ids(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2318-L2348
  - `filter_seed_papers_with_llm(...)`（cutoff_ref 排除）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2393-L2721
- Legacy 保留：`seed_surveys_from_arxiv(...)`  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2725-L3131
- 新增主流程：`seed_surveys_from_arxiv_cutoff_first(...)`  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3134-L3344
- 新 schema 產物（v2）：
  - `cutoff.json`（僅在有 cutoff 時）：`_build_cutoff_payload(...)`（`schema_version: cutoff.v2`）  
    https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L271-L339
  - `seed_rewrite.json`：`seed_rewrite.v2` payload  
    https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3234-L3248
  - `seed/queries/arxiv.json`：`seed_arxiv_queries.v2` payload  
    https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3294-L3301
  - `seed_selection.json`：`seed_selection.v2` payload  
    https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3309-L3320
  - `seed/downloads/download_results.json`：seed manifest（`download_pdfs: false`；filter-seed 另行寫入下載結果）  
    https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L3322-L3329

### 5.3 arXiv client / query builder / cache
- `_search_arxiv_with_query(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1314-L1338
- `_build_seed_query_from_tokens(...)`：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L2152-L2157
- `_load_seed_records_index(...)`（v2 arxiv.json 讀取）：https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/src/pipelines/topic_pipeline.py#L1564-L1613

### 5.4 Prompts
- `resources/LLM/prompts/seed/seed_query_rewrite.md`（JSON phrases）：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/resources/LLM/prompts/seed/seed_query_rewrite.md#L1-L20
- `resources/LLM/prompts/seed/seed_query_rewrite_legacy.md`（legacy prompt）：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/resources/LLM/prompts/seed/seed_query_rewrite_legacy.md#L1-L41

### 5.5 文件
- `docs/seed/seed_flow_current.md`：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/docs/seed/seed_flow_current.md#L1-L131
- `docs/seed/seed_query_rewrite_plan.md`：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/docs/seed/seed_query_rewrite_plan.md#L1-L39
- `docs/seed/seed_rewrite_prompt_context.md`：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/docs/seed/seed_rewrite_prompt_context.md#L1-L25
- `docs/seed/cutoff_first_seed.md`：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/docs/seed/cutoff_first_seed.md#L1-L38

### 5.6 測試
- `test/unit/test_seed_cutoff_first.py`：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/test/unit/test_seed_cutoff_first.py#L1-L161
- `test/integration_live/test_seed_cutoff_first_live.py`：  
  https://github.com/Sologa/AUTOSR-SDSE/blob/f797666990ea5066d7b3b31499d647777088cd66/test/integration_live/test_seed_cutoff_first_live.py#L1-L63

---

## 6. Edge Cases（default 行為必須 deterministic）

- cutoff 找不到同名：不產生 cutoff.json，後續無 cutoff（可用 override 指定）
- cutoff 多筆同名：tie-break = earliest date then smallest id
- 某 phrase 查詢無結果：記錄但不重跑
- phrases 全被 blacklist 清掉：fail（one-pass）
- phrases 含非 ASCII（非英文）：丟棄並記錄；若最後無可用 phrases：fail（one-pass）
- cutoff_date 缺失：fail（或要求換 date_field）
- result 缺 date：有 cutoff 時剔除並記錄
- normalization 問題（符號/大小寫/LaTeX）：unit tests 覆蓋

---

## 7. 測試計畫

### 7.1 Unit tests（mock arXiv）
- normalize_title（含 LaTeX / 標點）
- cutoff finder：exact match + tie-break
- blacklist clean / fail mode
- English-only enforcement（non-ASCII phrase drop + fail-if-empty）
- query builder 格式硬規格
- cutoff filter（有 cutoff 時）：exclude cutoff id、exclude after cutoff_date、inclusive <=

### 7.2 Integration test（真實 topic）
- 跑 topic pipeline 直到產出：
  - `cutoff/cutoff.json`（僅在有 cutoff 時）
  - `seed/queries/seed_rewrite.json`
  - `seed/queries/arxiv.json`
  - `seed/queries/seed_selection.json`
- 驗證：
  - 有 cutoff 時，selection 不含 cutoff_id
  - 有 cutoff 時，selection 全部 paper_date <= cutoff_date（用 date_field）
  - arxiv.json 統計正確（excluded_after_cutoff 等）

---

## 8. 風險與回滾

- 下游 stage schema 兼容：建議加入 `schema_version` 並寫 adapter（或保持舊欄位不破壞）
- 候選變少：保留 legacy mode 便於對照
- 日期欄位選擇：以 published 為 default，cutoff.json 寫死 date_field 便於追溯

---

## 9. Implementation SOP（Codex 必須照這個順序做）

1) 先讀完現行 docs + code，補齊第 2 章現況拆解（含 permalinks）
2) 新增 `--seed-mode cutoff-first`
3) 實作 CutoffFinder（+ normalize_title + tie-break + cutoff.json v2）
4) 改造 SeedQueryRewriteAgent：one-shot + blacklist + seed_rewrite.json v2
5) 實作 per-phrase query builder & arXiv search（多 query）
6) 實作 hard filter（exclude cutoff + date filter）
7) merge + seed_selection.json v2
8) 確保 downstream stages 不崩（必要時加 adapter）
9) 新增 tests（unit + integration），跑 `pytest`
10) 更新 docs（本文件 + seed_flow_current.md），並把所有 `[PERMALINK: ...]` 填滿
