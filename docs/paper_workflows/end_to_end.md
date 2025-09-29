# 綜述資料蒐集到關鍵詞抽取的端到端指南

本指南示範如何結合 `paper_workflows`、`paper_downloaders` 與 `keyword_extractor` 模組，從主題搜尋、資源下載到關鍵詞抽取，建立完整的流程。所有指令預設在專案根目錄並啟用 `sdse-uv` 虛擬環境後執行。

## 先備條件

- `.env` 已配置 `OPENAI_API_KEY`（用於關鍵詞抽取與部份整合測試）。
- 可選：`SEMANTIC_SCHOLAR_API_KEY`（提高搜尋速率、減少 429）。
- 具備網路連線權限。

## 步驟一：搜尋候選文獻

1. 建立 Python 腳本或互動環境：

```python
from pathlib import Path
import requests

from src.utils.paper_workflows import (
    search_arxiv_for_topic,
    search_semantic_scholar_for_topic,
    search_dblp_for_topic,
    download_records_to_pdfs,
    load_records_from_directory,
)

ANCHOR_TERMS = ["spoken language model", "speech language model"]
SEARCH_TERMS = ["survey", "review", "overview"]
OUTPUT_ROOT = Path("test_artifacts/manual_pipeline")
QUERY_CACHE = OUTPUT_ROOT / "queries"
DOWNLOAD_DIR = OUTPUT_ROOT / "downloads"

QUERY_CACHE.mkdir(parents=True, exist_ok=True)

session = requests.Session()
try:
    cached = load_records_from_directory(QUERY_CACHE)
    if cached:
        records = cached
    else:
        records = {
            "arxiv": search_arxiv_for_topic(session, ANCHOR_TERMS, SEARCH_TERMS, max_results=25),
            "semantic_scholar": search_semantic_scholar_for_topic(
                session,
                ANCHOR_TERMS,
                SEARCH_TERMS,
            ),
            "dblp": search_dblp_for_topic(session, ANCHOR_TERMS, SEARCH_TERMS, per_term_limit=20),
        }
        for source, payload in records.items():
            (QUERY_CACHE / f"{source}.json").write_text(
                __import__("json").dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    results = download_records_to_pdfs(records, DOWNLOAD_DIR, session=session)
finally:
    session.close()
```

2. 成品：
   - `queries/` 內含 `arxiv.json`、`semantic_scholar.json`、`dblp.json`。
   - `downloads/` 下建立 `arxiv/`、`semantic_scholar/`、`dblp/` 子資料夾與對應 PDF/BibTeX。
   - `DownloadResult` 物件若有 `issues`，請審視 `reason` 與 `status_code`，決定重試或忽略。

## 步驟二：準備關鍵詞抽取所需的 PDF

- 依 `keyword_extractor` 要求，PDF 檔名需包含 arXiv ID，例如 `2401.01234_overview.pdf`。
- 若從 Semantic Scholar / DBLP 下載的檔案缺乏 arXiv ID，可透過:

```python
from pathlib import Path
from src.utils.paper_workflows import trim_arxiv_id

download_dir = Path("test_artifacts/manual_pipeline/downloads/semantic_scholar")
for pdf in download_dir.glob("*.pdf"):
    arxiv_id = trim_arxiv_id(pdf.stem)
    if not arxiv_id:
        print("檔名缺少 arXiv ID:", pdf)
```

- 若無法從檔名取得 arXiv ID，可改以 `paper_downloaders.download_arxiv_paper` 直接從 arXiv 重新下載。

## 步驟三：執行關鍵詞抽取

```python
from pathlib import Path

from src.utils.keyword_extractor import ExtractParams, extract_search_terms_from_surveys

PDFS = sorted(Path("test_artifacts/manual_pipeline/downloads/arxiv").glob("*.pdf"))[:3]
params = ExtractParams(
    topic="spoken language model surveys",
    max_queries=40,
    include_ethics=False,
    seed_anchors=["spoken language model"],
    reasoning_effort="medium",
)

result = extract_search_terms_from_surveys(
    PDFS,
    provider="openai",
    model="gpt-5",
    params=params,
    max_output_tokens=128000,
    reasoning_effort="medium",
)

print("anchor_terms:", result.get("anchor_terms"))
print("categories:", list(result.get("search_terms", {}).keys()))
```

- 產出的 JSON 可寫入 `test_artifacts/manual_pipeline/keywords.json` 供後續查詢。
- 若 API 回應格式錯誤，函式會自動觸發 fallback 合併；詳見 `docs/keyword_extractor/module.md`。

## 步驟四：檢查與追蹤

- 檢查 `test_artifacts/manual_pipeline/downloads/**/` 的檔案是否完整，若 `issues` 指出 `access_blocked` 或 `missing`，可考慮後續補件。
- `keyword_extractor` 會自動寫入 `test_artifacts/keyword_extractor_live/keyword_extractor_usage_<timestamp>.json`，方便追蹤 token 消耗。
- 建議將流程結果記錄於 `logs/YYYY-MM-DD.md`，包含主題、下載筆數、關鍵詞抽取狀態。

## Verifying with Tests

在大幅修改流程或升級依賴後，請執行：

```bash
uv run --project sdse-uv pytest -q test/unit/test_paper_workflows_queries.py
uv run --project sdse-uv pytest -q test/test_paper_downloaders.py
# 若允許 live 測試：
uv run --project sdse-uv pytest -q test/integration_live/test_paper_downloaders_live.py
uv run --project sdse-uv pytest -q test/integration_live/test_keyword_extractor_live.py
```

## 常見問題

- **Semantic Scholar 429**：未提供 API key 時請調高 `request_pause` 或減少 `limit`。
- **arXiv PDF 缺失**：若 `issues` 顯示 `access_blocked`，代表該論文不提供 PDF（或需人工授權）；可在筆記中標示待補。
- **keyword_extractor 驗證失敗**：通常是 PDF 檔案與 metadata 不符，請確認檔名正確、無重複或缺頁。

## 參考資料

- `docs/paper_workflows/module.md`
- `docs/paper_downloaders/module.md`
- `docs/keyword_extractor/module.md`
- 測試檔：`test/integration_live/test_paper_downloaders_live.py`、`test/integration_live/test_keyword_extractor_live.py`


