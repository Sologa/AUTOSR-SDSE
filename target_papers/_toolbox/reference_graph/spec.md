# Reference Graph MVP：規格書（給 Codex / Copilot 實作用）

本文件定義一個 **最小可行（MVP）** 的「reference graph」產生器：  
輸入是某篇 survey 的 `reference list`（已被你現有 pipeline 轉成 `arxiv_metadata.json`），輸出是一張 **以 reference 為 node 的 directed citation graph**，並能把 node 依照 A/B/C（或 U）上色。

> 重要：本 MVP 追求「好維護、少依賴、少魔法」，避免過度工程。

---

## 0. 固定前提 / 你的需求約束（已確認）

1. **MVP**：只要能畫整張圖 + 2/3 種顏色即可，不需要複雜功能。
2. **Node 集合嚴格等於 reference list**（不額外新增外部 paper 當 node）。
3. **每個 node 只有一種 label**（single-label）。
4. **Node ID 使用 bib key**（`metadata.key`），但繪圖預設 **不顯示 key**（畫面太亂）。
5. **Graph 是有向**；有 cycle 也接受（不強制 DAG）。
6. 你不在意日期、也不做時間排序。
7. 輸出固定放：`workspaces/titlepaper_criteria_review/<survey_slug>/graph/`
8. 你要看「整張圖」，不做 sampling / filtering。

---

## 1. 檔案位置（必須照這個放）

### 1.1 工具本體（code + spec + prompt）
放在：

- `target_papers/_toolbox/reference_graph/`

其中至少包含：

- `build_reference_graph.py`（主程式，CLI 入口）
- `requirements.txt`
- `README.md`
- `spec.md`（本檔）
- `codex_prompt.md`（給 Codex 的指令模板）
- `.gitignore`（忽略 `.cache/` 等）

### 1.2 文件
放在：

- `docs/reference_graph/`

### 1.3 輸出位置（每個 survey 一份）
固定：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/`

---

## 2. 輸入資料格式

### 2.1 主要輸入：`arxiv_metadata.json`

路徑預設：

- `workspaces/titlepaper_criteria_review/<survey_slug>/harvest/arxiv_metadata.json`

格式（以你提供的檔案為準）：

- JSON array，每個元素至少包含：
  - `metadata.title`（string）
  - `metadata.key`（string；bib key）
  - `metadata.source`（string；例如 `arxiv` / `semantic_scholar` / `openalex` / `crossref`）
  - `metadata.source_id`（string；例如 arXiv 版本號 / S2 paperId / DOI / OpenAlex URL）
  - `metadata.arxiv_id`（string；若有）
  - `arxiv_id`（頂層也可能有；有就用）

> 注意：你的 harvest 目前只存 title+abstract（summary），這已足夠做 citation graph。  
> 我們不需要下載 PDF。

### 2.2 可選輸入：labels 檔（上色）
支援兩種：

- CSV：`key,label`
- JSON：`{ "<bibkey>": "A", ... }`

建議放在：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/labels.csv`

若未提供 labels，全部使用同一個預設 label（例如 `U`）。

---

## 3. 你最在意的核心：如何得到 citation 關係（edge）

### 3.1 我們要的 edge 定義
對 reference list 內任兩篇 paper A、B：

- 若 A 的 references 清單裡包含 B  
  ⇒ 建立 directed edge：**A → B**

### 3.2 取得 references 的資料來源
預設使用：

- **Semantic Scholar Graph API**

理由：  
它能直接查到每篇 paper 的 reference list，且支援用 arXiv/DOI/paperId 查詢。

### 3.3 Paper 對應策略（先 ID、再 title）
對每個 node（reference paper），要先找到它在 S2 上的「paper 身分」。

優先順序（越上面越穩）：

1. **Semantic Scholar paperId**  
   - 若 `metadata.source == "semantic_scholar"` 且有 `metadata.source_id`  
   - 直接把 `source_id` 當 paperId 使用

2. **DOI**
   - 若 `metadata.source_id` 看起來是 DOI（例：以 `10.` 開頭）  
   - 用 `DOI:<doi>` 當查詢 id

3. **arXiv**
   - 若有 `metadata.arxiv_id` 或頂層 `arxiv_id`  
   - 用 `arXiv:<arxiv_id>` 當查詢 id（不要帶 v1/v2）

4. **title search（最後手段）**
   - 用 `metadata.title` 去 S2 的 search endpoint
   - 取 top-K（例如 5）結果，用 normalize title / fuzzy 相似度挑最像的一個
   - 若低於門檻（例如 90/100）則視為查不到

### 3.4 把 S2 references 映射回你的 node 集合（非常關鍵）
S2 回傳的每個 reference item 通常會帶：

- `paperId`
- `title`
- `externalIds`（可能含 DOI、ArXiv）

我們需要把它映射回你 reference list 的某個 bib key。  
請用以下順序比對（越上面越穩）：

1. DOI（case-insensitive）
2. ArXiv ID
3. paperId
4. title exact normalize
5. title fuzzy（可選；避免誤配）

只有映射成功才加 edge；映射不到就忽略（因為 node 集合不能擴張）。

---

## 4. 產出（Outputs）

輸出目錄固定：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/`

必產出：

1. `reference_graph.html`  
   - 互動視覺化（pyvis/vis-network）
   - **hierarchical layout**（長得像 DAG）
   - node 預設 **不顯示 label 文字**（空字串），僅用顏色區分
   - hover tooltip 顯示：title、bibkey、arxiv/doi 等

2. `nodes.csv`  
   欄位建議：
   - `key`（bibkey；node id）
   - `title`
   - `label`（A/B/C/U）
   - `source`
   - `source_id`
   - `arxiv_id`（若有）
   - `doi`（若能解析到）

3. `edges.csv`  
   欄位：
   - `src_key`
   - `dst_key`
   - `match_type`（doi/arxiv/paperId/title_exact/title_fuzzy）

4. `reference_graph.graphml`（NetworkX GraphML）
5. `reference_graph.dot`（Graphviz DOT）
6. `stats.json`
   - `n_nodes`, `n_edges`
   - `n_papers_resolved`（能對應到 S2 的數量）
   - `n_papers_unresolved`
   - `n_edges_by_match_type`
   - `api_calls`、`cache_hits` 等

7. `run.log`（文字 log）

---

## 5. CLI 介面（務必簡單）

最少要支援：

- `--slug <survey_slug>`（必填；決定 input/output 路徑）
- `--workspace_root <path>`（預設 `workspaces/titlepaper_criteria_review`）
- `--metadata_json <path>`（可選；預設由 slug 推得）
- `--out_dir <path>`（可選；預設由 slug 推得）
- `--labels <path>`（可選）
- `--default_label <str>`（預設 `U`）
- `--no_title_search`（可選；停用 title search fallback；預設啟用）
- `--enable_title_fuzzy`（可選；更積極用 title fuzzy 對 reference 做映射，會增加 edge 但有誤配風險）
- `--cache_dir <path>`（預設 `target_papers/_toolbox/reference_graph/.cache`）
- `--overwrite`（預設 True；覆寫同名輸出檔）

---

## 6. 快取（避免 API 反覆打爆 / 可重現）

### 6.1 原則
- **所有外部 API 回應都要 cache**
- cache key 由請求 URL + query 參數構成
- cache 存成 JSON 檔（一個 request 一個檔）就好，不用 DB

### 6.2 位置
預設：

- `target_papers/_toolbox/reference_graph/.cache/semantic_scholar/`

---

## 7. 依賴（刻意最少）

`requirements.txt` 建議只放：

- `requests`
- `python-dotenv`
- `tqdm`
- `networkx`
- `pyvis`
- `rapidfuzz`（可選，但建議，title fuzzy matching 用；沒裝就退回 `difflib`）

不要引入：
- 資料庫
- 大型 framework
- 需要系統編譯的套件（例如 pygraphviz）

---

## 8. 錯誤處理與可觀測性

### 8.1 常見錯誤
- S2 搜不到 paper（title 太短、或格式怪）
- API rate limit / 429
- 網路錯誤

### 8.2 行為
- 搜不到：保留 node，但不產 edge
- rate limit：sleep/backoff（簡單即可）
- 全程把失敗原因記到 `run.log` 與 `stats.json`

---

## 9. 最小測試（不要過度）

建議加一個小測試模式（可選）：

- `--limit N`：只跑前 N 個 node（debug 用）
- `--dry_run`：不打 API，只讀 cache（若 cache 已有）

---

## 10. 交付清單（你要生成的檔案）

請確保 repo 內新增：

- `target_papers/_toolbox/reference_graph/build_reference_graph.py`
- `target_papers/_toolbox/reference_graph/requirements.txt`
- `target_papers/_toolbox/reference_graph/README.md`
- `target_papers/_toolbox/reference_graph/spec.md`
- `target_papers/_toolbox/reference_graph/codex_prompt.md`
- `target_papers/_toolbox/reference_graph/.gitignore`
- `docs/reference_graph/README.md`

---

## 11. 尚未釐清但可能會影響準確性的問題（後續你可以再回答）

> 這些不是阻擋 MVP 的問題，但會影響命中率/視覺效果。

1. 你的 `.env` 裡 Semantic Scholar key 的變數名稱是哪個？（目前程式會支援 `S2_API_KEY` 與 `SEMANTIC_SCHOLAR_API_KEY`）
2. 你希望 label 顏色固定對應嗎？（例如 A=紅、B=藍、C=綠）  
   - MVP 可以用內建 mapping；但若你希望可客製，需加一個 `label_colors.json`。
3. 你對「title fuzzy matching 的誤配」容忍度？  
   - 越 aggressive 命中越高，但可能誤配。MVP 預設保守（門檻高）。
4. 你希望 hover tooltip 顯示哪些欄位？（目前預設 title + key + IDs）
