
# 研究型檢索／代理系統與你的 `unified_research_pipeline.py` 契合度評估
更新日期：2025-09-17

> 目標：給定 *research topic* → （A）用 LLM 產生關鍵字與查詢 → （B）從多來源（arXiv／Semantic Scholar／OpenAlex…）大規模抓取 **metadata** → （C）用 LLM 或規則產生**篩選條件**並**打分排序**，挑出 **Top‑K**。同時考量可控性（限制 Agent 自由度）、可擴充性與可再現性。

---

## 評估指標（1–5 分；5=非常符合）
- **Kwd/Query**：是否內建「LLM 產生關鍵字／查詢」與布林語法產生器。  
- **Sources**：是否原生支援多資料源（arXiv、Semantic Scholar、OpenAlex；跨源去重）。  
- **Scoring/Top‑K**：是否提供 LLM／嵌入重排、可合成規則分數（新穎度、被引數、venue）。  
- **Agent 控制**：是否能用模板化步驟／工具權限，降低「走偏」風險。  
- **整合成本**：與你現有 Python 管線整合難度（I/O、schema、授權、維運）。  

> 總分 = 上述五項平均；**建議採用**標記代表可直接形成「最小可用整合（MVP）」。

---

## 總覽表

| 專案 | 核心定位 | Kwd/Query | Sources | Scoring/Top‑K | Agent 控制 | 整合成本 | 契合度 |
|---|---|---:|---:|---:|---:|---:|---:|
| **LitLLM / LitLLMs** | 以 RAG 驅動的文獻回顧工具包；LLM 生關鍵字→檢索→重排→生成 | 5 | 3 | 4 | 4 | 3 | **4.0** |
| **arxiv‑sanity‑preserver** | 經典 arXiv 個人化檢索／相似度推薦 | 2 | 1 | 3 | 4 | 3 | **2.6** |
| **GPT Paper Assistant**（tatsu‑lab） | 每日抓 arXiv → GPT 過濾寄送 | 3 | 1 | 4 | 4 | 4 | **3.2** |
| **Local Citation Network** | OpenAlex/S2/CR/OCC 融合＋引用網路可視化 | 2 | 5 | 2 | 5 | 3 | **3.4** |
| **PaperQA2** | 科學 PDF 高精度 RAG／問答 | 1 | 2 | 3 | 4 | 3 | **2.6** |
| **LangChain Semantic Scholar Tool** | S2 查詢工具（Agent 可用） | 3 | 3 | 2 | 5 | 4 | **3.4** |
| **AI‑Scientist（Sakana）** | 端到端研究代理（含 S2/OpenAlex 檢索、novelty 檢查） | 3 | 4 | 3 | 2 | 2 | **2.8** |
| **SurveyAgent（paper）** | 對話式文獻 survey 系統（知識管理／推薦／問答） | 3 | 2 | 3 | 3 | 2 | **2.6** |
| **Arxiv Assistant 類** | 自動抓 arXiv＋GPT 過濾 | 2 | 1 | 3 | 5 | 4 | **3.0** |

> 註：Sources 分數 1=僅 arXiv；3=可接單一外部 API（如 S2）；5=原生多源＋去重。

---

## 專案逐一評估（含整合建議）

### 1) LitLLM / LitLLMs（**推薦作為檢索→重排主線**）
- **證據**：工具包與論文說明其流程為 *LLM 由摘要生關鍵字 → 檢索 → 提示式重排 → 生成相關工作*，屬 RAG 式工具；有開源代碼與網站。  
- **強項**：天然符合你的 **(A) 關鍵字擴展** 與 **(C) LLM 重排**；可直接拿它的「關鍵字生成＋re‑rank 提示」模組，嵌入你現有 metadata 抓取後端。  
- **缺口**：多資料源與跨源去重非其主打；需要你用 OpenAlex/S2 先抓資料、再交給它重排。  
- **整合建議**：用你現有 `arXiv`＋新接的 `OpenAlex/S2` 抓 **JSONL** → 餵給 LitLLM 的 re‑rank 介面，回寫 `score` 欄位後 **Top‑K**。  
- **契合度**：**4.0/5**（作為重排層很合適；資料擷取層仍由你掌控）。

### 2) arxiv‑sanity‑preserver（**傳統檢索與相似度排序的基線**）
- **證據**：提供追蹤新文、相似度排序、個人化推薦與書籤；專注 arXiv。  
- **強項**：成熟的 **TF‑IDF/相似度索引＋個人化** 架構，易於借鏡「非 LLM 的穩定排序」；可做你 **ScoringEngine** 的一個維度（語義/傳統混合）。  
- **缺口**：僅 arXiv、無 LLM 關鍵字擴展與多源去重。  
- **整合建議**：複製其「相似度向量化＋倒排索引」思路，當作規則分數（`sim_score`）的一部分。  
- **契合度**：**2.6/5**（良好基線，不是成品方案）。

### 3) GPT Paper Assistant（tatsu‑lab）
- **證據**：每天拉取 arXiv 新文，按使用者準則由 GPT 過濾，支援寄送與存檔。  
- **強項**：**(C) LLM 過濾/打分 → Top‑K** 的最短路徑，腳本化清楚、易改。  
- **缺口**：仍然 **僅 arXiv**；規模化與多源整合需自行擴充。  
- **整合建議**：把其「LLM 篩選提示」抽出，當作你的 `ScoringEngine.llm_score()`。  
- **契合度**：**3.2/5**（好用的 LLM 打分樣板）。

### 4) Local Citation Network（**多來源整合＋引用圖譜**）
- **證據**：以 **OpenAlex／Semantic Scholar／Crossref／OpenCitations** 做 metadata 融合與本地引用網路視覺化；開源網頁版。  
- **強項**：正中你 **(B) 多源抓取與去重** 的痛點；能輸出可下游處理的資料。  
- **缺口**：不含 LLM 關鍵字擴展／打分；偏可視化與資料整備。  
- **整合建議**：重用其 **DOI/ID 對齊與去重策略**；先做「聚合層」，再接你的打分層。  
- **契合度**：**3.4/5**（補齊多源基建的首選）。

### 5) PaperQA2（Future House）
- **證據**：定位為科學文獻 **高精度 RAG**（對 PDF 問答／證據對齊），並有「超人級表現」之結果頁與 GitHub。  
- **強項**：適合當你流程的 **下游驗證／深讀**（例如對 Top‑K 逐篇自動抽要點、找矛盾）。  
- **缺口**：不是 metadata 收集器；(A)(B) 需求需另補。  
- **整合建議**：在你選出 Top‑K 後，觸發 PaperQA2 生成「可引用摘要／實驗要點」，存回 JSON。  
- **契合度**：**2.6/5**（屬下游輔助）。

### 6) LangChain Semantic Scholar Tool（**建構 Agent 的工具**）
- **證據**：LangChain 提供 **Semantic Scholar API Tool** 與 `APIWrapper`，可直接掛到 Agent。  
- **強項**：讓你很容易控「Agent 只能呼叫 S2 搜索」；便於權限沙箱化與可再現。  
- **缺口**：僅是**工具層**；需要你自己組裝關鍵字產生、去重、打分。  
- **整合建議**：用 LangGraph/LC Agent 包一條 **受限計畫**：`gen_keywords -> query(S2/OpenAlex) -> dedup -> score -> topK`。  
- **契合度**：**3.4/5**（優秀的積木）。

### 7) AI‑Scientist（Sakana）
- **證據**：官方 README 指出支援 **Semantic Scholar** 與 **OpenAlex** 作文獻檢索／新穎性檢查；亦有 v2 與官方說明頁。  
- **強項**：涵蓋 **(A)(B)(C)** 但目標是「端到端做研究、寫論文」；示範「novelty 檢查」流程。  
- **缺口**：系統龐大、自由度高；若僅做文獻收集/排序，會顯過度。  
- **整合建議**：只取其 **S2/OpenAlex 查詢與新穎性檢查段落**；其餘維持你現有管線。  
- **契合度**：**2.8/5**（概念驗證好，但落地成本高）。

### 8) SurveyAgent（paper／網站）
- **證據**：論文與官網闡述三模組（知識管理／推薦／問答）；**開源程式碼未明**（多為概念與評估）。  
- **強項**：與你的目標流程對齊度高（特別是推薦與對話式篩選）。  
- **缺口**：若無可用實作，需自行實現。  
- **整合建議**：參考其**模組邏輯**來拆分你的 scoring 與交互層。  
- **契合度**：**2.6/5**（理念契合；代碼可得性存疑）。

### 9) Arxiv Assistant 類（多個）
- **證據**：如 `tatsu-lab/gpt_paper_assistant`、`wzk1015/Arxiv-Assistant` 等，都是 **抓 arXiv→GPT 篩選→Top‑K/通知**。  
- **強項**：**最短路**打分流程；可直接作為你 scoring prompt 的模板。  
- **缺口**：單源、規模化要自己補。  
- **整合建議**：抽出其 **prompt 與評分輸出 schema**，融入你的管線。  
- **契合度**：**3.0/5**。

---

## 結論與建議的「拼裝式方案」
- **檢索與重排主線**：以 **LitLLM / LitLLMs** 的「LLM 關鍵字→重排」做 **(A)+(C)**；  
- **多源聚合與去重**：用 **Local Citation Network** 的多源思路，落地到 **OpenAlex + Semantic Scholar** 的 API；  
- **Agent 工具化**：用 **LangChain Semantic Scholar Tool**（+ OpenAlex REST/`pyalex`）限制 Agent 權限；  
- **基線排序**：借鏡 **arxiv‑sanity** 的傳統相似度，與 LLM 重排混合；  
- **下游深讀**：對 Top‑K 交給 **PaperQA2** 生成「可引用摘要＋要點＋對比表」。

> 這樣你仍保留對 **資料擷取與規則打分** 的主導（可控、可復現），又能在「關鍵字擴展／重排／深讀」三節點享受 LLM 的品質提升。

---

## 参考／來源
- LitLLM / LitLLMs：論文與開源（流程含 LLM 產生關鍵字→檢索→重排→生成）。  
  - arXiv（2024/02）；OpenReview 修訂；GitHub & 網站。  
- arxiv‑sanity‑preserver：GitHub README（相似度排序、個人化、僅 arXiv）。  
- GPT Paper Assistant（tatsu‑lab）：GitHub README（每天抓取與 GPT 過濾）。  
- Local Citation Network：GitHub 頁面與說明（OpenAlex/S2/CR/OCC 整合）。  
- PaperQA2：Future House 專案頁與 GitHub（科學 PDF 高精度 RAG）。  
- LangChain Semantic Scholar Tool：官方文件與 APIWrapper。  
- AI‑Scientist：GitHub README 與官方說明頁（S2/OpenAlex 檢索、新穎性檢查）。  
- Arxiv Assistant 類：`wzk1015/Arxiv-Assistant` 等。

---

## 下一步（最小可用整合，1–2 天工作量）
1. 新增 `sources_openalex.py`、`sources_semanticscholar.py`：抓取→統一 schema→**DOI/arXivID 去重**。  
2. 新增 `keyword_gen.py`：以 LLM 產生 must/should/synonyms/exclude 與三源查詢語法。  
3. 新增 `scoring.py`：`rel`（嵌入/LLM）、`recency`、`log_citations`、`venue_bonus` → `total_score`。  
4. 建立 `rerank_litllm.py`：把 LitLLM 的 re‑rank 提示整合進來（可切換 on/off）。  
5. 寫 `main.py`：topic→多源抓→去重→打分→Top‑K 輸出（JSONL/CSV）。
