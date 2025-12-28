# Snowballing 與 Review 架構說明

> 本文件描述目前 repo 內的 snowballing 與 review 實作流程，並提出調整方案。所有路徑皆以 workspace 目錄為基準。

## 1) 現行架構（依程式碼）

### 1.1 Review（LatteReview）

- 入口：`python scripts/topic_pipeline.py review --topic "<topic>"`
- 主要輸入：
  - `harvest/arxiv_metadata.json` 或指定的 metadata JSON
  - `criteria/criteria.json`
- 主要輸出：
  - `review/latte_review_results.json`
- 重要行為：
  - 若 `criteria.json` 內含 `exclude_title` 或 `cutoff_before_date`，會在 review 前直接標記為 discard（不送 LLM）。
  - `skip_titles_containing` 預設為 `survey`，標題包含該字串者會被跳過（不進 LLM review）。
  - Review 僅處理 **有摘要** 的條目（無摘要會被略過）。

### 1.2 Snowballing（ASReview + OpenAlex）

- 入口：`python scripts/topic_pipeline.py snowball --topic "<topic>"`
- 主要輸入：
  - `review/latte_review_results.json`
  - `harvest/arxiv_metadata.json`（或指定的 metadata JSON）
- 主要輸出（固定覆寫在 `asreview/`）：
  - `asreview/screening_included.csv`
  - `asreview/snowball_results_raw.csv`
  - `asreview/snowball_results.csv`
  - `asreview/snowball_for_review.csv`
- 重要行為：
  - 只用 **include** 作為 snowball 種子（預設 `--keep-label include`）。
  - snowball 結果內部去重（依 DOI / OpenAlex / 標題 / arXiv / 標題正規化）。
  - `snowball_for_review.csv` **只會和當次 `screening_included.csv` 去重**。
  - 不會和「前一階段 review 全部結果」或「前一階段 snowball 結果」做去重。
  - 每次跑 snowball 會覆寫 `asreview/` 下同名檔案，**不同 round 的結果會混寫/被覆蓋**。
  - snowball 來源日期欄位為 `publication_date`；`--max-date/--min-date` 會用此欄位判斷。
  - 非英文與缺題/摘要的過濾使用啟發式（非絕對語言偵測）。
  - **不含任何自動迭代**；每輪 snowball 需要人工手動重跑。

## 2) 現行架構的問題

1. **跨階段去重不足**：
   - 第二次（或之後）snowball 的候選，只會和「該輪 include 種子」去重，
     無法排除「先前已 review 過（include/exclude/discard）」的條目。
   - 這會導致 **已排除的 paper 再次出現**，增加重複 review 成本。

2. **不同 round 結果混在一起**：
   - 目前所有 round 都寫入 `asreview/`，
     導致無法可靠追蹤每一輪的 raw / filter / for_review。

3. **去重策略不完整**：
   - 目前去重只針對當輪候選與當輪 include 種子，
     未涵蓋「所有硬性規則過濾後的剩餘 paper」。
   - 目前沒有「全歷史 registry」記錄，無法避免排除過的 paper 反覆出現。

4. **缺乏自動迭代與停止條件**：
   - 目前只能人工重跑下一輪，無法 reproducible 地控制迭代邏輯。

## 3) 建議的調整架構（符合需求）

### 3.1 每輪結果獨立存放（不可混）

建議固定結構：

```
workspaces/<topic>/snowball_rounds/
  round_01/
    seeds_screening_included.csv
    snowball_results_raw.csv
    snowball_results.csv
    snowball_for_review.csv
    candidates_for_review.json
    latte_review_results.json
    round_meta.json
  round_02/
    ...
```

### 3.2 每輪 review 前先做「全歷史去重」

**目標**：每次 snowballing 後，在 review 前先排除「前面回合累計已處理過的 paper（含硬性 discard 與 exclude）」。

建議新增「全歷史 registry」：

- `workspaces/<topic>/snowball_rounds/review_registry.json`
- 內容包含**所有回合累計**已處理過的 paper（include/exclude/hard_exclude 等），
  並保留去重用的 keys（openalex_id / doi / arxiv_id / normalized_title）。

**流程建議（順序固定）：**

1) snowball raw → `snowball_results_raw.csv`
2) 依日期與硬性規則過濾 → `snowball_results.csv`
3) **去重（跨所有歷史 registry；排除已 include / exclude / hard_exclude）**
4) 產出 `snowball_for_review.csv`
5) 轉成 `candidates_for_review.json`
6) review
7) 將 review 結果寫回 registry（include/exclude/hard_exclude/needs_enrichment 等）

### 3.3 Seed 使用規則（符合「每輪 review 後再 snowball」）

每輪 seed 僅使用「上一輪 review 的 include」，不混入 exclude。若需要提高召回，可引入 `seed_only` 類別（例如 survey 類）做為擴展種子，但不納入 final include。

### 3.4 清楚定義「硬性規則」的集合

硬性規則建議固定：

- `cutoff_before_date`（日期）
- `exclude_title`（同名論文排除）
- `language`（非英文條目排除，使用啟發式）
- `has_title_and_abstract`（缺題/摘要排除）

**這些條件必須在 review 前就先過濾。**

### 3.5 迭代方式（必須支援兩種）

為了可重現且可控，snowballing 必須改為「迭代式執行」，提供兩種模式：

1) **loop 模式（固定輪數）**
   - 使用 `for` 迴圈，直接指定 `--max-rounds N`。
   - 每輪：snowball → hard filters → registry dedup → candidates_for_review → review → 更新 registry → 進下一輪。

2) **while 模式（停止條件為 OR）**
   - 使用 `while` 迴圈，停止條件為：  
     `raw_count >= raw_threshold` **或** `included_total >= included_threshold`  
     （任何一個條件達成就停止；`included_total` 指 **累計至最新回合** 的 included 總數，包含第一回合的 review 結果）。
   - 兩個閾值必須由參數注入：  
     `--stop-raw-threshold`、`--stop-included-threshold`
   - 若兩者皆未達成，繼續下一輪。

> 注意：為避免無限迭代，建議 while 模式仍保留 `--max-rounds` 作為安全上限。

### 3.6 可重現腳本（必須）

到 snowball 為止的行為必須由腳本驅動（不要手動拼接），確保可重跑與可追溯。

## 4) 建議的實作修改點（最小可行）

1) `test/speech_lm_results_to_asreview.py`
   - 新增 `--registry` 參數
   - 在 `generate_snowball_review_candidates()` 增加跨 registry 去重
   - registry 去重需只排除 **final 類**（include/exclude/hard_exclude），避免把資料不足類型永久排除

2) `src/pipelines/topic_pipeline.py`
   - `run_snowball_asreview()` 新增 `--round` 與 `--registry` 參數
   - 輸出改為 `snowball_rounds/round_XX/` 目錄

3) 新增一個小工具（可放 `scripts/` 或 `test/`）：
   - `update_snowball_registry.py`
   - 從 `latte_review_results.json` 抽取去重 keys
   - 合併到 `review_registry.json`

4) 新增 review 專用候選資料（避免 CSV/JSON 來回不一致）
   - `candidates_for_review.json`：由 `snowball_for_review.csv` 轉成 review 用 JSON
   - 欄位至少包含 title/abstract/published/doi/openalex_id（對齊目前 review 輸入）

5) 新增可重現的「迭代腳本」
   - 新增 `scripts/snowball_iterate.py`（或同等腳本）
   - 參數包含：
     - `--mode loop|while`
     - `--max-rounds N`（loop/while 都可用）
     - `--stop-raw-threshold X`
     - `--stop-included-threshold Y`
     - `--round-dir snowball_rounds/round_XX`
     - `--registry review_registry.json`
   - 腳本需負責：
     - 從上一輪 include 產生 seeds
     - 產出 round_XX 目錄的完整輸出
     - 記錄 `round_meta.json`

## 5) 下一步建議

如果你同意這個結構，我可以：

1) 先把既有 round1/round2 的結果整理進 `snowball_rounds/round_01` / `round_02`
2) 加上 registry 去重與 candidates_for_review.json
3) 以新腳本重跑 snowball（loop/while 皆可）

## 5.1 實作步驟清單（順序）

1) 取得上一輪 include 作為 seeds  
2) 執行 snowball，產生 `snowball_results_raw.csv`  
3) 依硬性規則過濾（日期 / 語言 / 缺題摘要 / 同名）→ `snowball_results.csv`  
4) 讀取 `review_registry.json`，排除已 include / exclude / hard_exclude  
5) 產出 `snowball_for_review.csv`  
6) 轉成 `candidates_for_review.json`（統一 review 輸入格式）  
7) LatteReview → `latte_review_results.json`  
8) 更新 `review_registry.json`（累計 include/exclude/hard_exclude）  
9) 更新 `round_meta.json`（含 raw_count / for_review / included_total 等）  
10) 依 loop / while 規則決定是否進入下一輪  

## 6) 補強點（基於現有程式可落地）

1) **registry 狀態拆分**（避免把缺資料永久封死）
   - final：`include` / `exclude` / `hard_exclude`
   - non-final：`needs_enrichment` / `error` / `temp_discard`
   - 去重時僅排除 final + hard_exclude

2) **`skip_titles_containing=survey` 改為可配置**
   - 預設關閉或改成 `seed_only`（保留作為種子，避免完全跳過）

3) **criteria 變更保護**
   - registry 內可加 `criteria_hash` 欄位
   - 若 hash 不同，`hard_exclude` 可重新評估

4) **去重 key 的優先序與命中來源**
   - 優先序：openalex_id > doi > arxiv_id > title
   - 記錄 `matched_by`，便於追查誤殺

5) **每輪 meta 記錄**
   - 每輪產出 `round_meta.json`，含：seed_count、raw_count、filtered_count、dedup_removed、for_review_count、review_outcome
