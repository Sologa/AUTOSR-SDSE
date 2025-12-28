# Iterative Snowballing（rounds + registry）

## 目的
- 讓 snowballing 結果以 `round_XX` 目錄隔離保存，避免混寫。
- 使用全歷史 `review_registry.json` 去重（排除 include / exclude / hard_exclude）。
- 在 review 前建立 `candidates_for_review.json`，統一 LatteReview 輸入。
- 提供可重現的 loop / while 迭代腳本。

## 介面 / 參數

### 1) 迭代腳本：`scripts/snowball_iterate.py`

必要參數：
- `--topic`：topic 字串
- `--mode loop|while`

常用參數：
- `--max-rounds N`：最大回合數（loop/while 皆可用）
- `--stop-raw-threshold X`：while 模式停止門檻（raw_count）
- `--stop-included-threshold Y`：while 模式停止門檻（累計 include）
- `--min-date / --max-date`：套用到 snowball 硬性過濾
- 若未指定 `--max-date` 且 `criteria.json` 含 `cutoff_before_date`，snowball 會自動套用 `max_date = cutoff_before_date - 1 day`
- `--review-top-k`：限制每輪送 LatteReview 的筆數（省成本）
- `--skip-titles-containing`：review 階段跳過標題包含字串（預設 survey）
- `--registry`：指定 `review_registry.json`
- `--retain-registry`：保留既有 registry（預設會清空並以 base review 重建）
- `--bootstrap-review`：指定初始 review 結果（預設 workspace/review/latte_review_results.json）

### 2) Registry 更新工具：`scripts/update_snowball_registry.py`

必要參數：
- `--review-results`：LatteReview 輸出 JSON
- `--registry`：`review_registry.json`

選用參數：
- `--criteria`：criteria.json（用於計算 criteria_hash）
- `--round`：round index
- `--source`：來源標記（預設 latte_review）

### 3) Snowball 單輪：`python scripts/topic_pipeline.py snowball`

新增參數：
- `--round`：round index（預設 1）
- `--registry`：`review_registry.json` 路徑

## 輸出結構（每輪）

```
workspaces/<topic>/snowball_rounds/
  review_registry.json
  final_included.json
  final_included.csv
  round_01/
    screening_included.csv
    snowball_results_raw.csv
    snowball_results.csv
    snowball_for_review.csv
    candidates_for_review.json
    dedup_report.json
    latte_review_results.json
    round_meta.json
  round_02/
    ...
```

## 使用範例

### Loop 模式（固定回合）

```bash
source sdse-uv/.venv/bin/activate
python scripts/snowball_iterate.py \
  --topic "discrete audio tokens more than a survey" \
  --mode loop \
  --max-rounds 2 \
  --min-date 2018-01-01 \
  --max-date 2025-12-31
```

### While 模式（停止條件 OR）

```bash
source sdse-uv/.venv/bin/activate
python scripts/snowball_iterate.py \
  --topic "discrete audio tokens more than a survey" \
  --mode while \
  --max-rounds 5 \
  --stop-raw-threshold 200 \
  --stop-included-threshold 30
```

### 僅更新 registry

```bash
source sdse-uv/.venv/bin/activate
python scripts/update_snowball_registry.py \
  --review-results workspaces/<topic>/review/latte_review_results.json \
  --registry workspaces/<topic>/snowball_rounds/review_registry.json \
  --criteria workspaces/<topic>/criteria/criteria.json
```

## 測試要點
- round 目錄必須獨立，不可混寫。
- 去重 key 優先序：openalex_id > doi > arxiv_id > title。
- registry 僅排除 include / exclude / hard_exclude；hard_exclude 需比對 criteria_hash。
- `candidates_for_review.json` 必須在 review 前建立。
- `round_meta.json` 必須包含 seed_count / raw_count / filtered_count / dedup_removed / for_review_count / review_outcome。

## 已知限制
- while 模式仍保留 `--max-rounds` 作為安全上限。
- criteria_hash 只影響 hard_exclude 是否參與去重。
- LatteReview 需要 `OPENAI_API_KEY`；若要省成本可使用 `--review-top-k`。
