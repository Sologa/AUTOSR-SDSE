# 給 Codex 的 Prompt（Reference Graph MVP）

你正在協助我在 repo 裡新增一個 **Reference Graph（MVP）** 工具，用來把某篇 survey 的 **reference list**（每篇 reference 一個 node）串成一張 directed citation graph，並依照 A/B/C（或 U）上色。

---

## 背景與資料來源

- 我有一個 AutoSR / Automatic Survey Generation 的 pipeline。
- 每篇 survey 都會有 workspace：
  - `workspaces/titlepaper_criteria_review/<survey_slug>/`
- 其中 `harvest/arxiv_metadata.json` 是我既有腳本產生的 reference metadata（title+abstract，並可能包含 arXiv/DOI/S2 paperId）。

我要做的事情很單純：  
**用外部 citation 資料源（預設 Semantic Scholar）把 reference list 裡面 paper 互相引用的關係補出來，畫一張整張圖。**

---

## 必須遵守的路徑規範（不要寫死 survey，只能用 slug 參數）

### 工具位置（code + spec + prompt）
請把所有工具檔案放在：

- `target_papers/_toolbox/reference_graph/`

### 文件位置
文件放：

- `docs/reference_graph/`

### 輸出位置（每個 survey 一份）
輸出固定寫到：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/`

---

## 功能需求（MVP、不要過度工程）

1. Node 集合嚴格等於 reference list（不新增外部 node）
2. Directed graph；允許 cycle
3. Node ID = bib key（`metadata.key`），但 **視覺化預設不顯示 bibkey**
4. 每個 node 只有一種 label（single-label）
5. 沒有 labels 檔時全部同色（預設 label=U）
6. 要輸出互動圖（HTML），且看起來要像 DAG（hierarchical layout）
7. 安裝與依賴要簡單（不要用需要系統編譯的套件、不要資料庫）

---

## 最重要：citation 關係怎麼拿到？

請使用 **Semantic Scholar Graph API**：

- 對每篇 reference paper，先用 arXiv/DOI/paperId 對應到 S2 上的 paper
- 再抓該 paper 的 `references`
- 把 references 映射回我的 reference list（用 DOI / ArXiv / paperId / title）

建立 edge：A → B（A cites B），只保留 B 也在 reference list 的情況。

---

## 交付物

請新增並提交以下檔案（內容需一致、可直接跑）：

- `target_papers/_toolbox/reference_graph/build_reference_graph.py`
- `target_papers/_toolbox/reference_graph/requirements.txt`
- `target_papers/_toolbox/reference_graph/README.md`
- `target_papers/_toolbox/reference_graph/spec.md`
- `target_papers/_toolbox/reference_graph/codex_prompt.md`
- `target_papers/_toolbox/reference_graph/.gitignore`
- `docs/reference_graph/README.md`

---

## CLI 範例（必須能跑）

```bash
python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug discrete_audio_tokens_more_than_a_survey

python target_papers/_toolbox/reference_graph/build_reference_graph.py \
  --slug on_the_landscape_of_spoken_language_models_a_comprehensive_survey
```

labels 範例：

- `workspaces/titlepaper_criteria_review/<survey_slug>/graph/labels.csv`

```csv
key,label
someBibKey,A
anotherBibKey,B
```

---

## 品質要求（請注意）

- 請加 cache（避免一直打 API）
- 查不到 paper 不要報錯退出：保留孤立 node
- log 與 stats 要可 debug
- 程式碼要乾淨、好維護、不要拆太多層資料結構

你可以直接照 `target_papers/_toolbox/reference_graph/spec.md` 實作。
