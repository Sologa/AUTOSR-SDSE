# Reference Graph（文件）

這份文件描述 `target_papers/_toolbox/reference_graph/` 的定位、介面與使用方式，用來在每個 survey workspace 產生 reference citation graph。

---

## 目的

將某篇 survey 的 reference list 視為固定 node 集合，補出 reference 之間的 citation 關係，產出整張 directed graph 並依 A/B/C（或 U）上色，方便快速檢視主幹、孤立群與引用結構。

---

## 介面/參數

CLI 入口：

- `python target_papers/_toolbox/reference_graph/build_reference_graph.py`

必要參數：

- `--slug <survey_slug>`：決定 input/output 路徑

常用可選參數：

- `--workspace_root <path>`：預設 `workspaces/titlepaper_criteria_review`
- `--metadata_json <path>`：覆寫輸入 `arxiv_metadata.json`
- `--out_dir <path>`：覆寫輸出資料夾
- `--labels <path>`：labels CSV/JSON
- `--review_json <path>`：review JSON（含 ABC 與 criteria_screening）
- `--label_mode <auto|labels|abc|screening|both>`：使用 review JSON 時的 label 模式（`auto` 預設為 `both`）
- `--default_label <str>`：未提供 labels 時的預設 label（預設 `U`）
- `--no_title_search`：停用 title search fallback
- `--enable_title_fuzzy`：reference 映射啟用 title fuzzy
- `--cache_dir <path>`：快取資料夾
- `--show_labels`：HTML/DOT 顯示 node 文字
- `--hier_dir <UD|DU|LR|RL>`：HTML hierarchical 方向
- `--limit <N>`：僅處理前 N 個 node（debug）

預設輸入：

- `workspaces/titlepaper_criteria_review/<survey_slug>/harvest/arxiv_metadata.json`

預設輸出：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/`

---

## 使用範例

基本用法：

```bash
python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug discrete_audio_tokens_more_than_a_survey
```

指定 labels：

```bash
python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug on_the_landscape_of_spoken_language_models_a_comprehensive_survey \
  --labels workspaces/titlepaper_criteria_review/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/graph/labels.csv
```

同一個 HTML 切換 ABC / Included-Excluded：

```bash
python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug discrete_audio_tokens_more_than_a_survey \
  --review_json workspaces/titlepaper_criteria_review/discrete_audio_tokens_more_than_a_survey/review/arxiv2506.10274_references_ABC_plus_criteria_screening.json \
  --label_mode both
```
HTML 左上角會顯示切換選單與對應 legend。

---

## 測試要點

- 輸入檔存在且可解析（`arxiv_metadata.json` 為 JSON array）
- 執行後輸出包含 `reference_graph.html`、`nodes.csv`、`edges.csv`、`stats.json`
- `stats.json` 的 `n_nodes` 等於 reference list 去重後的數量
- 查不到 paper 時不會中止，仍可產出孤立 node
- 快取目錄內有對應的 API 回應 JSON
- 未提供 `--show_labels` 時，HTML 仍不顯示 node 文字且保留 directed arrows

---

## 已知限制

- citation 關係完全依賴 Semantic Scholar Graph API 的覆蓋率
- title search 與 fuzzy 映射受限於候選集合，存在誤配風險
- 僅在 reference list 內建圖，不會新增外部 node
- 不解析 PDF，不做更深層的 disambiguation
- cycles 會被視覺化壓縮在同一層；若仍難以閱讀，建議改用 `--hier_dir LR` 或 `--show_labels`
