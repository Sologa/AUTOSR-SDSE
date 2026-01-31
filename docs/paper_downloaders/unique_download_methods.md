# Unique Paper 下載方式總覽

本文件整理目前專案中實際使用/嘗試過的 **unique 下載來源**（對應 `title_abstracts_sources.jsonl` 與 `title_abstracts_source_trace.jsonl`），讓後續新主題能依同樣方式補齊 paper 的 title/abstract（必要時再抓 PDF/BibTeX）。

## 共通原則

- 盡量從一手來源取得 title/abstract；若只拿到 landing page，需標記 `source` 與 `source_id` 以利追溯。
- 保留查詢歷程（成功/失敗）於 trace，避免重複查詢。
- 若 abstract 缺失，明確標註 `abstract_present: false` 與原因。

## 來源與下載方式（依唯一來源分組）

### arxiv
- 適用：有 arXiv ID 或可由標題精準匹配。
- 入口：`https://export.arxiv.org/api/query?id_list=<arxiv_id>`
- 下載：`https://export.arxiv.org/pdf/<arxiv_id>.pdf`、`https://arxiv.org/bibtex/<arxiv_id>`
- 輸出建議：`source=arxiv`、`source_id=<arxiv_id>`。

### semantic_scholar
- 適用：多數論文可用 title 搜尋後取得 paperId。
- 入口：`/graph/v1/paper/search?query=<title>` 找 paperId，再用 `/graph/v1/paper/<paperId>?fields=title,abstract,year,authors,externalIds,openAccessPdf`。
- 輸出建議：`source=semantic_scholar`、`source_id=<paperId>`。

### dblp
- 適用：計算機領域會議/期刊；可由 title 搜尋到 DBLP key。
- 入口：`https://dblp.org/search/publ/api?q=<title>&format=json` → `https://dblp.org/rec/<dblp_key>.rdf`
- 下載：`https://dblp.org/rec/<dblp_key>.bib?download=1`
- 輸出建議：`source=dblp`、`source_id=<dblp_key>`。

### openalex
- 適用：跨領域補充 metadata 或 DOI 對齊。
- 入口：`https://api.openalex.org/works?search=<title>`（可搭配 `select=title,abstract,doi,ids`）。
- 輸出建議：`source=openalex`、`source_id=<openalex_id>`。

### crossref
- 適用：有 DOI 或需要由 title 反查 DOI；常用於補對 DOI。
- 入口：`https://api.crossref.org/works?query.title=<title>` 或 `filter=doi:<doi>`。
- 注意：abstract 常缺失，僅作補充來源。

### acl_anthology
- 適用：ACL/EMNLP/NAACL 等 NLP 會議。
- 入口：以 Anthology 索引或 paper landing page 取得 metadata；必要時由 BibTeX/頁面 metadata 取 abstract。
- 注意：部分年份或資源沒有 abstract。

### lrec_conf
- 適用：LREC 會議論文。
- 入口：LREC proceedings/summary pages（依年份與 paper 編號尋找）。
- 輸出建議：`source=lrec_conf`、`source_id=lrecYYYY:<paper_id>`。

### rfc_editor
- 適用：IETF RFC 文件（如 codec 標準）。
- 入口：`https://www.rfc-editor.org/rfc/rfcXXXX`，頁面含 Abstract。
- 輸出建議：`source=rfc_editor`、`source_id=RFCXXXX`。

### bsi
- 適用：BSI 標準文件（產品頁）。
- 入口：`https://knowledge.bsigroup.com/` 的產品頁面。
- 注意：常只有摘要描述或購買資訊；若無 abstract，需標記缺失。

### github
- 適用：僅有專案 repo、無正式論文或摘要時。
- 入口：GitHub repo README / description。
- 注意：屬於替代性來源，需標明 `source=github` 與 repo path。

### huggingface
- 適用：資料集或模型卡描述補充。
- 入口：`https://huggingface.co/datasets/<repo>` 或模型卡頁面。
- 注意：屬於替代性來源，需標明 `source=huggingface`。

### keithito
- 適用：LJ Speech dataset 官方頁。
- 入口：`https://keithito.com/LJ-Speech-Dataset/`。
- 注意：屬於資料集描述來源，需標明 `source=keithito`。

### zenodo
- 適用：研究資料集或技術報告存放於 Zenodo。
- 入口：`https://zenodo.org/api/records/?q=title:"<title>"` 或對應 record 頁。
- 注意：abstract 通常在 `description` 欄位；若缺失需標記。

## 建議流程（精簡）

1. 先用 `arxiv` / `semantic_scholar` / `dblp` 取得正式 metadata。
2. 若未命中或缺 abstract，再嘗試 `openalex` / `crossref`。
3. 若仍缺失，依領域嘗試 `acl_anthology` / `lrec_conf` / `rfc_editor`。
4. 最後以 `github` / `huggingface` / `keithito` / `bsi` / `zenodo` 做替代性補足。

## 腳本使用（collect_title_abstracts_priority.py）

本腳本會依本文件的來源優先序自動查詢並輸出三個 JSONL 檔案。

### 直接執行（預設路徑）
```bash
python scripts/collect_title_abstracts_priority.py
```

### 指定輸入與輸出目錄
```bash
python scripts/collect_title_abstracts_priority.py \
  --input target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/reference_oracle.jsonl \
  --output-dir target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/title_abstract
```

### 重要參數
- `--resume`: 續跑（預設 true），會略過已成功匹配的項目。
- `--min-similarity`: 模糊比對最低門檻（預設 0.9）。
- `--allow-fuzzy`: 允許模糊比對（預設 true）。
- `--limit`: 只處理前 N 筆，適合除錯。

### 輸出檔案
- `title_abstracts_metadata.jsonl`
- `title_abstracts_sources.jsonl`
- `title_abstracts_source_trace.jsonl`

### 環境變數
- `SEMANTIC_SCHOLAR_API_KEY`：提高 Semantic Scholar 速率與穩定性。
- `GITHUB_TOKEN`：提高 GitHub 搜尋 API 可用額度。

## 來源紀錄格式建議

- `source`: 來源標籤（上列之一）
- `source_id`: 來源內部識別（例如 arXiv ID、paperId、DBLP key、RFC 編號）
- `source_url`: 若來源可直接定位，請存放 landing page

## 參考文件（官方或一手來源）

- arXiv API: https://info.arxiv.org/help/api/user-manual.html
- Semantic Scholar Graph API: https://api.semanticscholar.org/api-docs/graph
- OpenAlex Works API: https://docs.openalex.org/
- Crossref REST API: https://api.crossref.org/swagger-ui/index.html
