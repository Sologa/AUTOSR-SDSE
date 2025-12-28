# Snowballing 與 Review 架構說明

> 本文件描述目前 repo 內的 snowballing 與 review 實作流程，並提出調整方案。所有路徑皆以 workspace 目錄為基準。

## 1) 現行架構（實作現況，依程式碼）

### 1.1 Review（LatteReview）

- 入口：`python scripts/topic_pipeline.py review --topic "<topic>"`
- 主要輸入：
  - `harvest/arxiv_metadata.json` 或指定的 metadata JSON
  - `criteria/criteria.json`
- 主要輸出：
  - `review/latte_review_results.json`
- 重要行為：
  - 若 `criteria.json` 內含 `exclude_title` 或 `cutoff_before_date`，會在 review 前直接標記為 discard（不送 LLM），並寫入 `final_verdict = "discard (...)"`。
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

## 3) 建議的調整架構（符合你要求）

### 3.1 每輪結果獨立存放（不可混）

建議固定結構：

```
workspaces/<topic>/snowball_rounds/
  round_01/
    seeds_screening_included.csv
    snowball_results_raw.csv
    snowball_results.csv
    snowball_for_review.csv
    latte_review_results.json
  round_02/
    ...
```

### 3.2 每輪 review 前先做「全歷史去重」

**目標**：每次 snowballing 後，在 review 前先排除「所有已被硬性規則處理過的 paper」。

建議新增「全歷史 registry」：

- `workspaces/<topic>/snowball_rounds/review_registry.json`
- 內容包含所有已處理過的 paper（include/exclude/hard_exclude 等），
  並保留去重用的 keys（openalex_id / doi / arxiv_id / normalized_title）。

**流程建議（順序固定）：**

1) snowball raw → `snowball_results_raw.csv`
2) 依日期與硬性規則過濾 → `snowball_results.csv`
3) **去重（跨所有歷史 registry）**
4) 產出 `snowball_for_review.csv`
5) review
6) 將 review 結果寫回 registry（include/exclude/hard_exclude/needs_enrichment 等）

### 3.3 Seed 使用規則（符合「每輪 review 後再 snowball」）

每輪 seed 僅使用「上一輪 review 的 include」，不混入 exclude。若需要提高召回，可引入 `seed_only` 類別（例如 survey 類）做為擴展種子，但不納入 final include。

### 3.4 清楚定義「硬性規則」的集合

硬性規則建議固定：

- `cutoff_before_date`（日期）
- `exclude_title`（同名論文排除）
- `language`（非英文條目排除，使用啟發式）
- `has_title_and_abstract`（缺題/摘要排除）

**這些條件必須在 review 前就先過濾。**

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

---

## 5) 下一步建議

如果你同意這個結構，我可以：

1) 先把 round1/round2 的結果整理進 `snowball_rounds/round_01` / `round_02`
2) 加上 registry 去重
3) 加上 candidates_for_review.json
4) 按新的流程重跑 round2 → 再 review

---

## 6) 綜合外部建議但以現有程式為準的補強點

以下建議是基於現有程式碼可落地的調整，避免「round 多了後不可追溯」。

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

