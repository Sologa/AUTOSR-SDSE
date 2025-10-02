# Peer-Review Verification Checklist (DBLP + Semantic Scholar)
_Aim: Decide whether a given record represents a **peer-reviewed** conference/journal publication (vs a preprint)._

> 判斷原則：**只要找到一個明確的「正向」訊號（例如出版社 DOI、正式會議/期刊名稱或出版連結），即可判定為 peer-reviewed**。若完全找不到正向訊號，才視為 preprint。負向訊號（如 `10.48550/arXiv.*`）僅供參考，不會覆蓋既有的正向結果。

---

## A) DBLP metadata — checks
- [ ] **`record_tag`**:  
  - Expect *Journal Articles* / *Conference and Workshop Papers* for peer-reviewed items → **正向訊號**。  
  - 若為 **`Informal`** 則為 **負向提示**（僅供參考）。
- [ ] **`journal` / `venue`**:  
  - Recognized **journal name** or **conference name** → **正向訊號**。  
  - **`CoRR`** → arXiv CS repository → **負向提示**。
- [ ] **`dblp_key`** prefix:  
  - `conf/<series>/...` 或 `journals/<name>/...`（非 `corr`）→ **正向訊號**。  
  - `journals/corr/...` → arXiv entry → **負向提示**。
- [ ] **Pagination / container details**:  
  - 有 **頁碼**、**卷期** 或 **「In: Proceedings of …」** → **正向訊號**。  
  - 欠缺上述資訊 → **無法判定**，需尋找其他正向線索。
- [ ] **`doi` / `document_urls`**:
  - **Publisher DOI**（`10.1145/...`, `10.1109/...`, `10.21437/...` 等）→ **強烈正向訊號**。  
  - **arXiv DOI**（`10.48550/arXiv.*`）或僅有 arXiv/CoRR 連結 → **負向提示**。
- [ ] **`published_in_stream`**:
  - `https://dblp.org/streams/conf/<series>`、`.../journals/<name>`（非 corr）→ **正向訊號**。  
  - `.../streams/journals/corr` → **負向提示**。

> Optional DBLP fields to glance at: `source_rdf/rec` page, `electronic_edition_urls`, `pdf_candidates` (publisher vs arXiv).


## B) Semantic Scholar metadata — checks
- [ ] **`publicationVenue.type` & `publicationVenue.name`**:  
  - `type: "conference"` 與可辨識的會議名稱、或具名 **journal** → **正向訊號**。  
  - 名稱缺失/未知 → 需要其他線索。
- [ ] **`venue` (string) / `bibtex_entry.booktitle`**:  
  - `venue` / `booktitle` 出現已知的會議 → **正向訊號**。
- [ ] **`journal.name`**:  
  - 具名期刊且有卷期 → **正向訊號**。  
  - `journal: ArXiv`、`volume: abs/...` → **負向提示**。
- [ ] **`doi` / `doi_candidates`**:  
  - Publisher DOI (`10.1145/...`, `10.1109/...`, `10.21437/...`) → **強烈正向訊號**。  
  - `10.48550/arXiv.…` → **負向提示**。
- [ ] **PDF / links (`best_pdf_url`, `pdf_candidates`, `openAccessPdf.url`)**:  
  - **Publisher/Proceedings** 下載連結（IEEE Xplore、ACM DL、ISCA Archive…）→ **正向訊號**。  
  - Only arXiv links → **負向提示**。
- [ ] **Volume/Issue/Pages** (if present in metadata or publisher page):  
  - 具體 **頁碼** 或 **卷期** → **正向訊號**；缺少時需尋找其他線索。
- [ ] **`publicationTypes`**:
  - 可能噪音，僅供輔助。

---

## C) How to decide quickly
1. 先找 **正向訊號**：出版社 DOI、具名會議/期刊、正式出版頁面等任一出現即可判定為 peer-reviewed。  
2. 若僅找到 **負向提示**（例如 arXiv DOI、`CoRR`、只有 arXiv 連結）且沒有任何正向訊號，才視為 preprint。  
3. 同一紀錄如同時混合 arXiv 與正式出版資訊，可保留正向訊號並追蹤正式版本來源。
