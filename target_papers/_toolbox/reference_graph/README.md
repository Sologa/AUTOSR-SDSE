# Reference Graph Toolbox（MVP）

> 目的：把「某篇 survey 的 reference list」視為 **node 集合**，再用公開的 citation 資料源（預設：Semantic Scholar Graph API）去補出 **reference 之間互相引用** 的 directed graph，並輸出一個可互動、可上色（A/B/C）的整張圖。

---

## 你會得到什麼

對於任意 survey slug，例如：

- `discrete_audio_tokens_more_than_a_survey`
- `on_the_landscape_of_spoken_language_models_a_comprehensive_survey`

只要該 survey 已經有：

- `workspaces/titlepaper_criteria_review/<survey_slug>/harvest/arxiv_metadata.json`

就可以生成：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/reference_graph.html`（互動視覺化、支援 hover 顯示 title）
- `nodes.csv / edges.csv`（可 debug / 可丟到別的工具）
- `reference_graph.graphml`（可丟 Gephi / Cytoscape）
- `reference_graph.dot`（若你想用 Graphviz 產 PNG/SVG）
- `stats.json`（命中率、找不到 paper 的數量等）

---

## 檔案放置位置（已固定）

本工具全部放在：

- `target_papers/_toolbox/reference_graph/`

文件放在：

- `docs/reference_graph/`

輸出固定放在：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/`

---

## 安裝（刻意保持簡單）

建議在 repo root 建一個 venv（你也可以用你習慣的方式）：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 用 .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r target_papers/_toolbox/reference_graph/requirements.txt
```

---

## API Key（可有可無，但建議有）

Semantic Scholar Graph API 在沒有 key 的情況下也能用，但 rate limit 會比較緊。

你可以把 key 放在 repo root 的 `.env`（你已經有，只是沒 commit）：

```bash
S2_API_KEY=xxxxxxxxxxxxxxxx
```

程式會依序嘗試讀取下列環境變數（任一個存在即可）：

- `S2_API_KEY`
- `SEMANTIC_SCHOLAR_API_KEY`

---

## 一鍵生成（兩個 slug 範例）

在 repo root 執行：

```bash
python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug discrete_audio_tokens_more_than_a_survey

python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug on_the_landscape_of_spoken_language_models_a_comprehensive_survey
```

---

## Label / 上色（A/B/C）

### 方式 1：不提供 labels（預設全部同色）
你目前還沒有分群結果，所以這是最簡單的模式：全部 node 都會是同一種 label（預設 `U`）。

### 方式 2：提供 `labels.csv`（每個 node 一種 label）

建立檔案：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/labels.csv`

格式：

```csv
key,label
agostinelli2023musiclm,A
berant2013semantic,B
warstadt2020blimp,C
```

然後執行：

```bash
python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug <survey_slug> \
  --labels workspaces/titlepaper_criteria_review/<survey_slug>/graph/labels.csv
```

> 注意：你的 node ID 嚴格等於 reference list 的 `bib key`（`arxiv_metadata.json` 裡的 `metadata.key`）。

---

## 你最在意的點：citation 關係怎麼來？

**我們不靠 PDF，也不靠你手動寫 edge。**  
我們做的是：

1. 先把每篇 reference paper 對應到 Semantic Scholar 上的一個 paper（用 arXiv ID / DOI / 或 title search）。
2. 對每篇 reference paper 呼叫 Semantic Scholar 的 `references` API，拿到它「引用了哪些 paper」的清單。
3. 把那些被引用的 paper 和你的 reference list 做比對（DOI / arXiv / paperId / title），如果命中，就建立 edge：  
   **A → B**（表示 A cites B）

這樣就能把「你的 reference list 內部」的 citation network 建起來：  
有些 paper 完全不引用其他 reference（或查不到資料）就會變成孤立 node，這是預期行為。

---

## 產出檔案一覽

輸出路徑：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/`

檔案：

- `reference_graph.html`：主要給人看的互動圖（hierarchical layout；hover 有 title）
- `reference_graph.dot`：Graphviz DOT（可自行轉 SVG/PNG）
- `reference_graph.graphml`：給 Gephi/Cytoscape
- `nodes.csv`：node 表（key/title/source/id/label 等）
- `edges.csv`：edge 表（src_key,dst_key,match_type）
- `stats.json`：統計（命中率、找不到 paper 的數量、API 呼叫數、快取命中等）
- `run.log`：本次執行 log（debug 用）

---

## 常見問題

### 1) 用 title 查 Semantic Scholar，查不到怎麼辦？
程式策略是「先用 ID、再用 title」。

- 有 arXiv ID：直接用 `arXiv:<id>` 查（最穩）
- 有 DOI：用 `DOI:<doi>`（也很穩）
- 都沒有：才會用 title search（不保證 100%）

查不到時該 node 仍會保留在 graph 裡，只是它出不來外部 references，因此 edge 可能比較少或沒有。

### 2) Graph 有 cycle 怎麼辦？
允許。你也說 cycle 無所謂。視覺化仍會畫出 directed edges。

### 3) 我不要顯示 bibkey（太亂）
預設就是不顯示 node label；你可以在 hover tooltip 看到 title / key。

---

## 開發 / 維護原則（刻意不複雜）
- 單一腳本 + 少量依賴
- 不引入資料庫（只用 JSON cache）
- 不做「全功能 SR 工具」：只做 reference list 內部 citation graph + 上色 + 可視化
