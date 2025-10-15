# Paper Workflows 模組

此文件詳述 `src/utils/paper_workflows.py` 提供的搜尋與資源管理工具，協助從多個來源蒐集綜述論文、下載相關 PDF 與 BibTeX，並整合至本地資料夾。模組涵蓋 arXiv、Semantic Scholar 與 DBLP 的查詢輔助、速率限制控制與基礎資料整理。

## 模組定位

- 主要任務：
  - 搜尋：`search_arxiv_for_topic`、`search_semantic_scholar_for_topic`、`search_dblp_for_topic`
  - 下載整合：`download_records_to_pdfs`
  - 輔助函式：`collect_arxiv_ids`、`trim_arxiv_id`、`dblp_key_for_arxiv_id`、`load_records_from_directory` 等。
- 與 `paper_downloaders` 的關係：前者負責搜尋與整合，後者專注於單篇下載。
- 依賴標準函式庫與 `requests`，建議呼叫端共用 `requests.Session` 以提升效能。

## 主要函式說明

### `collect_arxiv_ids(pdf_root: Path) -> list[str]`

- 遞迴掃描 `pdf_root` 下的所有 `.pdf`，透過 `trim_arxiv_id` 解析檔名取得標準化 arXiv ID（保留前 5 位）。
- 回傳排序後的唯一 ID；無法解析的檔案會被忽略。

### `trim_arxiv_id(stem: str) -> str | None`

- 以正規表示式 `(
  \d{4}\.\d{5,})(?:v\d+)?
)` 從檔名擷取 arXiv ID；支援 `v2` 等版本後綴。
- 回傳固定格式 `YYYY.NNNNN`，不包含版本號；匹配失敗時回傳 `None`。

### `dblp_key_for_arxiv_id(arxiv_id: str) -> str`

- 將 `1234.5678` 轉換為 `journals/corr/abs-1234-5678`，便於呼叫 DBLP 下載介面。

### `build_semantic_scholar_query(anchor_terms, search_terms) -> str`

- 將 anchor 與 search terms 分別以 `OR` 串接並加上引號，例如：
  `("spoken language models" OR "speech language model") AND ("survey" OR "systematic review")`
- 結果可直接用於 Semantic Scholar `/graph/v1/paper/search` API。

### `respect_semantic_scholar_rate_limit(api_key_present: bool)`

- 控制呼叫節奏以避免 429：
  - 有 API key：最小間隔 1 秒。
  - 無 API key：最小間隔 3 秒。
- 函式使用 `time.monotonic()` 追蹤上次呼叫時間；多執行緒情境需自行加鎖。

### 搜尋函式

#### `search_arxiv_for_topic`

- 使用 arXiv Atom API，產生 `(ti:"anchor") AND (ti:"term")` 格式的查詢。
- 回傳 `id`、`title`、`summary`、`published` 等欄位。
- 失敗時會拋出 `requests.HTTPError`。

#### `search_semantic_scholar_for_topic`

- 先執行 `respect_semantic_scholar_rate_limit`。
- 呼叫 `/graph/v1/paper/search`，請求欄位固定為 `paperId,title,year,url,authors,openAccessPdf,publicationVenue`。
- 回傳 `payload.get("data", [])`；若未提供 API key，建議降低 `limit`。

#### `search_dblp_for_topic`

- 對 anchor 與 search term 組合逐一呼叫 `https://dblp.org/search/publ/api`。
- `request_pause` 控制兩次請求間的暫停（秒）。
- 回傳整理後的 `key`、`title`、`year`、`url` 字典列表，並自動去重。

### `load_records_from_directory(records_dir: Path) -> dict`

- 嘗試讀取 `arxiv.json`、`semantic_scholar.json`、`dblp.json`；缺少則跳過。
- 適合在重複執行流程時快取搜尋結果以節省 API 配額。

### `download_records_to_pdfs(records_by_source, output_dir, *, session=None, api_key=None) -> dict`

- 整合下載入口：依序對 arXiv、Semantic Scholar、DBLP 的記錄呼叫 `paper_downloaders`。
- 若無 API key，Semantic Scholar 僅處理前兩筆以降低封鎖風險。
- `output_dir` 會建立 `arxiv/`、`semantic_scholar/`、`dblp/` 子資料夾，回傳 `{"arxiv": [DownloadResult, ...], ...}`。

## 動手實作範例

```python
from pathlib import Path
import requests

from src.utils.paper_workflows import (
    search_arxiv_for_topic,
    search_semantic_scholar_for_topic,
    search_dblp_for_topic,
    download_records_to_pdfs,
)

ANCHORS = ["spoken language model", "speech language model"]
TERMS = ["survey", "systematic review"]

session = requests.Session()
try:
    arxiv_records = search_arxiv_for_topic(session, ANCHORS, TERMS, max_results=20)
    semantic_records = search_semantic_scholar_for_topic(session, ANCHORS, TERMS)
    dblp_records = search_dblp_for_topic(session, ANCHORS, TERMS, per_term_limit=15)

    collected = download_records_to_pdfs(
        {
            "arxiv": arxiv_records,
            "semantic_scholar": semantic_records,
            "dblp": dblp_records,
        },
        Path("test_artifacts/tmp_survey_assets"),
        session=session,
    )

    for source, results in collected.items():
        successes = sum(bool(item.pdf_path) for item in results)
        print(source, "pdf success:", successes, "total:", len(results))
finally:
    session.close()
```

## 測試與實務使用

- 單元測試：`pytest -q test/unit/test_paper_workflows_queries.py`
  - 驗證查詢參數、引號處理與速率限制邏輯。
- 整合測試：`pytest -q test/integration_live/test_paper_downloaders_live.py`
  - 先透過 `collect_arxiv_ids` 驗證資料集，接著以搜尋函式加上 `download_records_to_pdfs` 落盤。
  - 測試結果會產生 `test_artifacts/live_queries/<topic>/` 與 `test_artifacts/live_downloads/<topic>_assets/`。

## 注意事項

- Semantic Scholar 速率限制需特別留意；未提供 API key 時請保留足夠間隔或採取節流策略。
- `download_records_to_pdfs` 不會自動重試；若 `DownloadResult.issues` 指出 `rate_limited` 或 `access_blocked`，呼叫端需自行重試或記錄。
- 搜尋結果可能含有重複論文（例如 arXiv 與 DBLP 的對應條目）；後續整合時請根據 `arxiv_id` 或 DOI 去重。
- 模組內所有網路呼叫皆為同步；大量下載時建議以批次或併發框架封裝。

## 延伸閱讀

- `docs/paper_downloaders/module.md`：下載函式與 `DownloadResult` 結構詳解。
- `docs/keyword_extractor/module.md`：了解下載後的 PDF 如何進一步用於關鍵字抽取。
- `test/integration_live/test_paper_downloaders_live.py`：端到端範例流程。







