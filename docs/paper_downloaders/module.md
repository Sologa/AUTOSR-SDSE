# Paper Downloaders 模組

本文檔說明 `src/utils/paper_downloaders.py` 提供的下載工具與例外狀況，協助從 arXiv、Semantic Scholar 與 DBLP 收集 PDF 與 BibTeX 內容。除非特別註明，所有範例皆預設在專案根目錄並於 `sdse-uv` 虛擬環境啟用後執行。

## 模組概覽

- 主要公開 API：
  - `download_arxiv_paper(arxiv_id, output_dir, *, session=None, timeout=30) -> DownloadResult`
  - `download_semantic_scholar_paper(paper_id, output_dir, *, session=None, api_key=None, timeout=30) -> DownloadResult`
  - `download_dblp_entry(dblp_key, output_dir, *, session=None, timeout=30) -> DownloadResult`
  - `fetch_arxiv_metadata(arxiv_id, *, session=None, timeout=30) -> dict`
- 基礎類型：
  - `DownloadResult`：封裝來源 (`source`)、識別碼 (`identifier`)、原始 `metadata` 字典、`pdf_path` / `bibtex_path` 結果路徑，以及 `issues`（列表，紀錄無法取得的資源）。
- 例外：
  - `PaperDownloadError`：表示遠端記錄不存在或回應格式不可用，通常需由呼叫端決定是否忽略或重試。

所有函式皆採用 `requests.Session`，若未傳入會自動建立並於函式結束時關閉；因此建議在大量下載時由呼叫端共用 `Session` 以降低 TCP 握手成本。

## 依賴與環境

- 直接依賴標準函式庫與 `requests`；無需額外安裝。
- Semantic Scholar API 支援匿名請求，但需遵守速率限制（每 3 秒 1 次）；提供 `SEMANTIC_SCHOLAR_API_KEY` 後可提高速率（約 1 秒 1 次）。
- 下載結果會写入 `output_dir`：若目錄不存在會自動建立。

## 函式說明

### `download_arxiv_paper`

- **輸入**：
  - `arxiv_id`：`str`，標準 arXiv ID，例如 `2401.01234` 或 `2401.01234v2`（函式內部會自動刪除版本號）。
  - `output_dir`：`Path` 或 `str`，儲存下載內容的資料夾。
  - 可選參數 `session`、`timeout`。
- **流程**：
  1. 呼叫 `_fetch_arxiv_metadata` 抓取 Atom feed；若記錄不存在會丟出 `PaperDownloadError`。
  2. 透過 metadata 中的 `pdf_url` 下載 PDF；若回傳 401/403/404/410/418/451 等，會在 `issues` 中紀錄而不視為致命錯誤。
  3. 呼叫 `_fetch_arxiv_bibtex` 取得 BibTeX；若缺失則在 `issues` 加上 `reason: missing`。
  4. 產生 `DownloadResult`，其中 `pdf_path` / `bibtex_path` 可能為 `None`，視下載是否成功。
- **常見錯誤**：
  - `PaperDownloadError`：ID 不存在或回傳不可解析的 XML。
  - `requests.HTTPError`：網路錯誤或超時。

### `fetch_arxiv_metadata`

- **用途**：取得單篇 arXiv 的標題、摘要、作者、類別、PDF 連結等基本欄位。
- **流程**：
  1. 呼叫 `https://export.arxiv.org/api/query` 解析 Atom feed。
  2. 若 feed 未提供 DOI 連結，會額外抓取 `https://export.arxiv.org/abs/{arxiv_id}`，從 `id="arxiv-doi-link"` 的 `<a>` 標籤解析 DataCite DOI（形式 `https://doi.org/10.48550/arXiv.xxx`）。
  3. 回傳包含 DOI（若成功解析）、PDF URL、landing URL 的字典。
- **注意**：若鏡像頁面也缺少 DOI 或被暫時封鎖，函式會繼續回傳 `doi: None`，交由呼叫端決定是否重試或改用其他來源。

### `download_semantic_scholar_paper`

- **輸入**：
  - `paper_id`：`str`，可接受 `Semantic Scholar` 自身 ID 或 `arXiv:NNNN.NNNNN`。
  - `output_dir`：下載位置。
  - 參數 `session`、`api_key`、`timeout`。
- **流程**：
  1. `_fetch_semantic_scholar_metadata` 呼叫 `/graph/v1/paper/{paper_id}`，並依官方教學組合 `_SEMANTIC_SCHOLAR_FIELDS`，一次取得標題、摘要、刊物資訊、開放取用資訊、作者細節（含 `authors.name/affiliations/hIndex/...`）、DOI/外部 ID、引用統計、`tldr`、`embedding` 等欄位。
  2. 若 API 回覆 429（速率限制），函式會回傳 `DownloadResult` 並在 `issues` 註記 `rate_limited`，不丟例外，以利呼叫端重試或排程。
  3. 解析 metadata 產生 `author_names`、`external_id_entries` / `external_id_map`、`doi_candidates`、`tldr_text`、`pdf_candidates`、`best_pdf_url` 等輔助欄位，以利後續流程快速取用完整資訊。
  4. 按序檢查 `pdf_candidates`（整合 `openAccessPdf.url` 與由 `externalIds` 推導的 arXiv PDF；若 API 回傳 `pdfUrls` 也會併入），任一路徑成功即寫入 `output_dir / f"{safe_stem}.pdf"`，所有失敗原因會記錄在 `issues`。
  5. 檢查 `citationStyles` 是否提供 `bibtex`；存在時寫入 `metadata['bibtex_entry']` 並存成 `.bib`，否則在 `issues` 中標記缺失。
- **常見錯誤**：
  - `requests.HTTPError`：API 回傳 4xx/5xx（非速率限制）；呼叫端應捕捉處理。
  - PDF 連結無效：會在 `issues` 中看到 `reason: access_blocked` 或 `missing`。
- **速率與 API key**：
  - 未提供 `api_key` 時建議控制節奏（參考 `paper_workflows.respect_semantic_scholar_rate_limit`）。
  - 提供 API key 後可提高速率，同時保留授權頭 `x-api-key`。

### `download_dblp_entry`

- **輸入**：
  - `dblp_key`：`str`，例如 `journals/corr/abs-2401-01234`。
  - `output_dir`：儲存路徑。
  - `session`、`timeout`。
- **流程**：
  1. `_fetch_dblp_metadata` 呼叫 `https://dblp.org/rec/{dblp_key}.rdf`，完整剖析 RDF：除了標題、年份、作者外，還會整理 `datacite:hasIdentifier`（拆解 scheme 與 value）、`dblp:ee` 電子版連結、`dblp:bibtexType`、`dblp:publishedIn*`、`dblp:numberOfCreators` 等欄位，並將整棵 RDF 子樹寫入 `metadata['raw_fields']` 供人工檢視。
  2. `metadata['pdf_candidates']` 會綜合 `document_urls` 與所有 `dblp:ee` 連結，挑選第一個 `.pdf` 下載；若未找到符合條件的 URL，會在 `issues` 中紀錄並保留所有嘗試過的連結。
  3. 呼叫 `_fetch_dblp_bibtex` 下載 BibTeX；若 404 則視為缺失並紀錄。
- **常見錯誤**：
  - `PaperDownloadError`：RDF 無對應記錄。
  - `requests.HTTPError`：網路失敗。

- **輸出重點欄位**：
  - `metadata['identifiers']`：列出每個 identifier scheme（含 `scheme_short`）與對應值，可直接取得 DOI、arXiv ID 等資訊。
  - `metadata['identifier_map']`：以 scheme 為鍵的快取，例如 `identifier_map['doi']`。
  - `metadata['electronic_editions']` / `metadata['electronic_edition_urls']`：完整蒐集 `dblp:ee` 連結及其屬性。
  - `metadata['raw_fields']`：保留 RDF 子節點的遞迴結構（包含屬性與子節點），方便比對官方說明或追蹤缺漏欄位。

## DownloadResult 結構

```python
DownloadResult(
    source="arxiv|semantic_scholar|dblp",
    identifier="...",
    metadata={...},               # 原始 JSON/字典
    pdf_path=Path | None,         # 成功下載的 PDF 路徑
    bibtex_path=Path | None,      # 成功下載的 BibTeX 路徑
    issues=[{                     # 可能為空列表
        "asset": "pdf" | "bibtex" | "metadata",
        "reason": "access_blocked" | "missing" | "rate_limited" | ...,
        "status_code": 404,
        "url": "https://..."
    }, ...]
)
```

呼叫端可透過 `issues` 決定後續補救措施（例如重試、改用鏡像、忽略缺失）。

## 使用範例

以下範例展示如何批次下載三個來源的資料，並在失敗時記錄問題而不中斷：

```python
from pathlib import Path
import requests

from src.utils.paper_downloaders import (
    download_arxiv_paper,
    download_dblp_entry,
    download_semantic_scholar_paper,
)

OUTPUT_DIR = Path("test_artifacts/tmp_downloads")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
try:
    arxiv = download_arxiv_paper("2401.01234", OUTPUT_DIR / "arxiv", session=session)
    print("arXiv PDF:", arxiv.pdf_path)
    print("Issues:", arxiv.issues)

    semantic = download_semantic_scholar_paper(
        "arXiv:2401.01234",
        OUTPUT_DIR / "semantic",
        session=session,
        api_key=None,
    )
    print("Semantic Scholar BibTeX:", semantic.bibtex_path)

    dblp = download_dblp_entry(
        "journals/corr/abs-2401-01234",
        OUTPUT_DIR / "dblp",
        session=session,
    )
    print("DBLP Issues:", dblp.issues)
finally:
    session.close()
```

## 測試與驗證

- 單元測試：`pytest -q test/test_paper_downloaders.py`
  - 使用 mock session 驗證 metadata 解析與檔案寫入。
- 整合測試：`pytest -q test/integration_live/test_paper_downloaders_live.py`
  - 需要實際網路連線與 arXiv/Semantic Scholar/DBLP 服務。
  - 測試會於 `test_artifacts/live_downloads/` 產生摘要檔案，並處理速率限制。
- 整合測試：`pytest -q test/integration_live/test_dblp_full_metadata.py`
  - 實際呼叫 DBLP RDF 介面並下載 metadata，全量內容會寫入 `test_artifacts/metadata_harvest/dblp_full/` 供人工檢視。
- 整合測試：`pytest -q test/integration_live/test_semantic_scholar_full_metadata.py`
  - 依官方教學取得 Semantic Scholar 全欄位 metadata，結果寫入 `test_artifacts/metadata_harvest/semantic_scholar_full/`，可直接檢視 API 回應與派生欄位。

## 已知限制與注意事項

- 速率限制：Semantic Scholar 未使用 API key 時易受 429；建議於批次流程中搭配 `respect_semantic_scholar_rate_limit`（詳見 `paper_workflows` 模組）。
- arXiv PDF 若遇到版權保護（401/403/451 等），函式不會重試；呼叫端需自行處理（例如改用鏡像或人工下載）。
- DBLP 的 PDF 連結並非保證存在；通常至少可取得 BibTeX。
- 下載流程未執行檔案校驗（checksum）；如需核對完整性，請於呼叫端加上額外檢查。




