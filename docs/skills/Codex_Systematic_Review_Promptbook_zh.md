# Codex 系統性文獻回顧（Systematic Review）Paper 生成 Prompt 手冊（中文）

版本：v1.0    日期：2026-01-06

## 核心規範（必讀）
- 不得捏造引用：不得編造論文、作者、年份、期刊、DOI、URL。缺資料只能寫 TODO 並列入缺口清單。
- 透明可重現：每一步都要留下命令、輸入/輸出檔案、時間戳與中間產物（log）。
- PRISMA 導向：寫作結構要能對應 PRISMA 2020 的 Methods/Results 等項目，並能產出 PRISMA flow diagram。
- 清楚的納排與理由：screening 必須能回溯「為何排除」；至少要有一份 excluded_studies_with_reasons。
- 證據分級/品質評估：至少要有一種品質/風險評估方案（醫學類可用 RoB2/ROBINS-I；CS/SE 可用 Kitchenham-style quality checklist）。
- 避免過度結論：若證據不足，只能用「可能/推測」並標註證據不足。

## Prompt Pack（逐步貼給 Codex）
### Prompt 00：總控角色與硬規則（一定要先貼）
```text
你現在是我的「Systematic Review 論文生成總控 coding agent（Codex）」。

目標：在此 repo 內，針對 TOPIC="<填入你的主題>"，建立可重現的系統性文獻回顧流程，並輸出一篇 systematic review / survey 型 paper 草稿（paper.md + 可選 paper.pdf）。

硬性規則（必須遵守）：
1) 不得捏造任何引用：不得編造論文、作者、年份、期刊、DOI、URL。若缺資訊，只能標註 TODO 並寫入 PAPER_DIR/todo_missing_sources.md。
2) 所有「事實性主張/比較/結論」都要有引用支持；證據不足只能寫成推測並明確註記。
3) 全流程可重現：每一步都要記錄命令、輸入/輸出、結果統計到 PAPER_DIR/build_log.md。
4) 產出 PRISMA flow diagram 所需的計數（至少記在 records/prisma_counts.json），並生成 flow 圖（figures/）。
5) 最終輸出至少 2 張論文級圖：PRISMA flow + 方法/分類或趨勢圖。圖檔放 PAPER_DIR/figures/。
6) 所有產物都放在 TOPIC_WS 之下，不要改動 repo 其他不相關區域。

工作方式：
- 你要逐步執行我接下來給的 prompts。
- 每完成一個 prompt，就回報：做了什麼、改了哪些檔案（路徑）、如何重現（命令）。

先做兩件事：
A) 讀取並確認 repo 目前是否已有 workspaces/<topic>，若沒有就建立 TOPIC_WS 目錄結構（protocol/ records/ extraction/ synthesis/ paper/）。
B) 將你推斷出的 TOPIC_WS 與 PAPER_DIR 實際路徑寫入 PAPER_DIR/build_log.md（第一行就寫）。
```

### Prompt 01：讀規範文件（PRISMA/Kitchenham）並建立 PRISMA 任務對照表
```text
請在 TOPIC_WS/protocol/ 產生一份 prisma_checklist_mapping.md，目的：把 PRISMA 2020 的 Methods/Results 報告項目對應到「我們要產出的檔案與章節」。

要求：
1) 不要逐字貼上 PRISMA checklist（可用自己的話摘要）。
2) 用表格格式：PRISMA item 類別 | 我們要在 paper.md 哪一節處理 | 需要哪些中間產物（例如 search_strategy.md / screening_fulltext.csv / prisma_counts.json 等）
3) 同時補充：若我們在 Computer Science/Software Engineering 領域，哪些部分可用 Kitchenham/Charters（planning/conducting/reporting）框架補強（例如 quality checklist）。

完成後回報：prisma_checklist_mapping.md 路徑 + 你做的主要對照點（5-10 條）。
```

### Prompt 02：Repo 探勘（找到 pipeline 入口與 workspace 輸出）
```text
請在 repo 根目錄完成探勘，並把結果寫到 PAPER_DIR/build_log.md（新增一節「Repo Recon」）：

1) 找到主要 pipeline 的入口腳本與用法（例如 scripts/topic_pipeline.py 或等效），執行 --help 並摘要主要參數。
2) 找到是否已有 literature review stage（例如 scripts/literature_review.py、src/pipelines/literature_review.py 或類似）。
3) 列出目前 workspaces/ 下有哪些 topic workspace（用 ls 或 find），以及每個 workspace 的子資料夾結構概覽（只列 2 層深度即可）。
4) 找到 review / snowball / criteria / harvest 的實際檔名（不要假設）。用 find + grep 來確認。

最後回報：
- pipeline 入口與示範命令
- 你找到的實際檔名（例如 final_included.json 的真實路徑）
```

### Prompt 03：環境檢查與可用性（PDF 產生/引用驗證）
```text
請檢查環境並把命令與結果寫入 PAPER_DIR/build_log.md（新增一節「Env Check」）：

- python --version
- pip --version（或 uv/pdm）
- 是否有 requirements.txt / pyproject.toml
- pandoc --version
- xelatex --version

若缺 pandoc 或 xelatex：
1) 在 build_log.md 寫出缺什麼與原因（找不到命令）。
2) 提供可行安裝方式（依 OS 推斷；若無法安裝就明確說明）。
3) 在後續流程一律啟用「Markdown-only」模式，仍要輸出 paper.md。

另外：
- 若你有辦法做 DOI/CrossRef 驗證（需要網路），先測試一個已知 DOI 的查詢；如果不能，就在 build_log.md 註記「引用未驗證」。
```

### Prompt 04：定義研究問題（RQ）與範圍（PICOS/CS adaptation）
```text
請在 TOPIC_WS/protocol/protocol.md 先寫「研究問題與範圍」草稿（只寫這一段，不要先寫 Methods 全文）：

1) 產出 1 個主研究問題（Primary RQ）+ 3-6 個子問題（Sub RQs）。
2) 同時給兩種 framing，二選一（你要推薦其中一個）：
   - PICOS（Population/Intervention/Comparator/Outcome/Study design）
   - CS/ML 專用 framing（Domain/Task/Method/Dataset/Metric）
3) 明確定義：
   - 研究對象（什麼算在範圍內、什麼不算）
   - 時間範圍（DATE_RANGE）
   - 研究類型（conference/journal/arxiv、實驗/實作/使用者研究/benchmark 等）

輸出：
- 更新 TOPIC_WS/protocol/protocol.md（新增章節：1. Objectives & Research Questions）

回報我：
- Primary RQ + Sub RQs
- 你建議使用哪個 framing（PICOS 或 CS/ML）與理由
```

### Prompt 05：制定納入/排除標準（Eligibility Criteria）與排除理由分類表
```text
請在 TOPIC_WS/protocol/protocol.md 增加「Eligibility Criteria」章節，包含：

1) Inclusion criteria（至少 6 條）
2) Exclusion criteria（至少 8 條）
3) 排除理由 taxonomy（用於 full-text screening）：
   - 請設計 8-12 個「排除理由代碼」（例如 E1: Not about TOPIC, E2: Not peer-reviewed, E3: No empirical evaluation ...）
   - 每個代碼要有一句定義與 1 個例子（用泛化例子，不要捏造真實 paper）

同時請建立：
- TOPIC_WS/records/excluded_with_reasons.csv（先寫 header，包含：paper_id,title,year,source,reason_code,reason_text,reviewer,notes）

回報：
- 你定義的排除理由代碼列表（E1..）
```

### Prompt 06：制定 protocol 其餘 Methods（搜尋、篩選、抽取、品質、綜整）
```text
請把 TOPIC_WS/protocol/protocol.md 補齊一份「可執行」的 protocol（對齊 PRISMA 2020 Methods），必須包含：

A) Information sources（資料庫/來源清單 DB_LIST + 最後檢索日期欄位）
B) Search strategy（每個資料庫至少 1 組布林查詢字串；並說明如何調整語法差異）
C) Selection process（title/abstract vs full-text；如何判定；如何記錄；建議雙人覆核或一致性檢查）
D) Data collection process（如何抽取欄位、如何處理缺失）
E) Data items（抽取欄位定義：至少 15 個欄位，需含 year/venue/task/method/dataset/metric 等）
F) Quality / risk of bias assessment（若非醫學：採用 quality checklist；若是介入研究：RoB2/ROBINS-I）
G) Synthesis methods（narrative synthesis + taxonomy；若有可比結果再談 meta-analysis）
H) Reporting bias / certainty（可選：說明是否做 publication bias 或 GRADE；若不做要說明原因）

要求：
- 全文要以「我們將會...」的 protocol 口吻撰寫（不是回顧結果）。
- 任何你不確定能做的事情，都要寫成「若可取得資料則...，否則...」並在 PAPER_DIR/todo_missing_sources.md 記錄限制。

完成後回報：
- protocol.md 的章節目錄（TOC）
```

### Prompt 07：建立 search_strategy.md（可直接複製到投稿附錄）
```text
請建立 TOPIC_WS/protocol/search_strategy.md，內容要能直接放到 paper 附錄/補充材料：

1) DB_LIST 列表（每個資料庫寫：平台名稱、查詢欄位、最後檢索日期）
2) 每個資料庫一段「完整查詢字串」
3) 你如何把同一組概念轉成不同資料庫語法（例如 title/abstract 限定、年份篩選）
4) 你如何做去重（dedup）與版本管理（arXiv vs conference extended version）

注意：不要捏造你沒有真的查過的資料庫結果數量；數量統計會在後面由流程產生。

完成後回報：search_strategy.md 的路徑 + 你設計的核心查詢式（至少 1 組）。
```

### Prompt 08：執行 pipeline 的 harvest/搜尋（或匯入既有結果）並保存原始 records
```text
請根據你在 Prompt 02 找到的 pipeline 用法，完成「文獻蒐集」並保存原始 records：

情境 A：repo 已有自動蒐集（harvest）功能
- 用 TOPIC 跑到能在 TOPIC_WS/records/raw/ 取得每個來源的原始匯出（JSON/CSV 都可）
- 把每次執行命令與時間戳寫入 PAPER_DIR/build_log.md

情境 B：repo 沒有自動蒐集，只有後處理
- 你就建立 records/raw/ 的占位檔案與 README，說明需要手動匯入哪些來源（例如 Semantic Scholar export / arXiv API dump）
- 不要自行捏造 raw records 內容

最後必須產出：
- TOPIC_WS/records/raw/（至少有 README.md）
- TOPIC_WS/records/raw_sources_manifest.json（列出來源名稱、檔案名、檢索日期、筆數：若未知筆數就填 null）

回報：你走的是 A 或 B，以及目前 raw_sources_manifest.json 的內容摘要。
```

### Prompt 09：合併與去重（dedup）產生 merged_dedup.csv
```text
請把 records/raw/ 的各來源結果合併並去重，輸出到：

- TOPIC_WS/records/merged_dedup.csv

要求：
1) 去重策略要寫入 PAPER_DIR/build_log.md（新增一節「Dedup」）：
   - 主要 key：DOI > arXiv id > (title normalize + year)
   - title normalize 規則（lowercase、去標點、空白壓縮）
2) merged_dedup.csv 至少包含欄位：
   paper_id,title,authors,year,venue,doi,arxiv_id,url,source,abstract
3) 產出去重統計到 TOPIC_WS/records/prisma_counts.json：
   - n_identified_total
   - n_after_dedup

注意：若 raw 資料不足導致無法去重，請在 build_log.md 寫明並保留最保守策略（不亂合併）。

回報：去重前後筆數與你採用的 key 優先級。
```

### Prompt 10：Title/Abstract 篩選（第一階段）輸出 screening_title_abstract.csv
```text
請執行第一階段篩選（Title/Abstract screening），輸出：

- TOPIC_WS/records/screening_title_abstract.csv

要求：
1) 對 merged_dedup.csv 每一筆給決策：include / exclude / maybe
2) 若 exclude，必須填 reason_code（用 Prompt 05 的 E1..）
3) 若 include 或 maybe，reason_code 可空，但 notes 要寫簡短理由
4) 產出統計到 prisma_counts.json：
   - n_screened_title_abstract
   - n_excluded_title_abstract
   - n_passed_to_fulltext（include + maybe）

注意：
- 如果你要用 LLM 自動判斷，必須保留判斷依據（例如符合哪些 inclusion criteria）。
- 若抽象不足（無 abstract），先標記 maybe，留待 full-text。

回報：三種決策的數量與最常見的 3 個排除理由代碼。
```

### Prompt 11：Full-text 取得與篩選（第二階段）輸出 screening_fulltext.csv
```text
請執行第二階段篩選（Full-text screening），輸出：

- TOPIC_WS/records/screening_fulltext.csv

要求：
1) 對 passed_to_fulltext 的每篇，嘗試取得 full text（PDF 或 HTML）。
   - 若拿不到全文：標記 status=unavailable_fulltext，並寫入 excluded_with_reasons.csv（reason_code 建議用一個專用代碼，例如 E_FT0）
2) 若全文可得：做 include / exclude 最終決策，exclude 必須有 reason_code + reason_text
3) 將所有被排除的 paper 寫入 excluded_with_reasons.csv（累積追加）
4) 更新 prisma_counts.json：
   - n_fulltext_sought
   - n_fulltext_not_retrieved
   - n_fulltext_assessed
   - n_excluded_fulltext
   - n_included_final

回報：最終 included 數量與 full-text 排除理由分佈（前 5 名）。
```

### Prompt 12：生成 PRISMA flow diagram（figures/prisma_flow.*）
```text
請用 TOPIC_WS/records/prisma_counts.json 的計數生成 PRISMA 2020 flow diagram 圖：

- 輸出到 PAPER_DIR/figures/prisma_flow.pdf（優先）或 prisma_flow.png
- 同時把產圖程式放到 PAPER_DIR/scripts/make_prisma_flow.py

要求：
1) 圖中所有數字必須來自 prisma_counts.json（不可手寫臆測）
2) 圖要有清楚標題與註腳（註明最後檢索日期）
3) 在 PAPER_DIR/build_log.md 記錄產圖命令與輸出檔

回報：圖檔路徑 + 你如何從 prisma_counts.json 映射到每個框。
```

### Prompt 13：建立資料抽取 schema（extraction_schema.json）
```text
請建立 TOPIC_WS/extraction/extraction_schema.json，用來規範抽取欄位（data items）。

要求：
1) 至少 15 個欄位，包含（可依你的領域調整）：
   - bibliographic: title, year, venue, doi/arxiv_id
   - problem/task
   - method/category
   - dataset(s)
   - metric(s)
   - experimental setting / baselines
   - key findings (受引用約束，不能捏造)
   - limitations reported by authors
   - code/data availability
2) 每個欄位要寫：name, type, description, allowed_values（若是 enum）
3) 若你要做品質/風險評估，也預留欄位：quality_score、quality_notes

回報：schema 的欄位清單（name 列表）。
```

### Prompt 14：對 included studies 做資料抽取（extracted_data.csv）
```text
請對最終 included 的 papers 做資料抽取，輸出：

- TOPIC_WS/extraction/extracted_data.csv

要求：
1) 欄位符合 extraction_schema.json
2) 任何你無法從 paper 取得的資訊請留空，不可猜
3) 每列要保留 paper_id，用於追溯
4) 建議同時輸出 extracted_data.json（可選）以保留巢狀欄位（多資料集/多指標）

同時更新 PAPER_DIR/build_log.md（新增一節「Data Extraction」）：
- 抽取方法（人工/半自動/LLM）
- 缺失率統計（每個欄位空值比例）

回報：included 篇數、抽取完成篇數、缺失最嚴重的 3 個欄位。
```

### Prompt 15：品質/風險評估（quality_assessment.csv）
```text
請建立並填寫 TOPIC_WS/extraction/quality_assessment.csv。

要求：
1) 先判斷 included studies 的研究型態（大致分類即可）：
   - RCT/介入研究、觀察研究、定性研究、工程/系統論文、benchmark 實驗、使用者研究等
2) 選擇評估工具並在 build_log.md 說明理由：
   - 醫學介入：RoB2（RCT）/ ROBINS-I（非隨機）
   - CS/SE：使用 quality checklist（例如：研究問題清楚、資料/程式可得、baseline 足夠、評估設計合理、威脅有效性討論等）
3) quality_assessment.csv 至少包含：
   paper_id, domain_type, criterion_id, judgement, notes
   judgement 建議：low/medium/high 或 yes/partial/no（自行定義但要一致）
4) 若採用 RoB2/ROBINS-I，請至少做到「結果/主要 outcome」層級的判斷（不要只做 study-level 一句話）

回報：你使用的工具/清單、總體品質分佈（高/中/低）。
```

### Prompt 16：制定綜整（synthesis）計畫（taxonomy + evidence tables）
```text
請建立 TOPIC_WS/synthesis/synthesis_plan.md，說明你會如何把 extracted_data 綜整成 paper 內容。

要求：
1) taxonomy 設計：至少 2 層（例如：方法類別 -> 子類）
2) 每個 taxonomy 類別要對應：哪些 papers（用 paper_id 列表，不要亂寫引用格式）
3) 證據表（evidence tables）規格：至少 2 張表
   - 表 1：Paper × Task/Method/Dataset/Metric（矩陣式）
   - 表 2：方法類別 × 優缺點/適用情境/限制（每格要能追溯到 paper_id）
4) 若要做 meta-analysis：只有在 outcomes 可比且資料充分時才做，否則採 narrative synthesis；要在此處寫明判定標準。

回報：taxonomy 的頂層類別列表 + 你預計的兩張表欄位。
```

### Prompt 17：生成 evidence tables（輸出到 synthesis/evidence_tables/）
```text
請根據 extracted_data.csv 生成 evidence tables：

- TOPIC_WS/synthesis/evidence_tables/table1_matrix.csv
- TOPIC_WS/synthesis/evidence_tables/table2_methods_vs_notes.csv
- （可選）TOPIC_WS/synthesis/evidence_tables/summary_stats.csv（年份分佈、venue 分佈、dataset 出現次數等）

要求：
1) 不得捏造數據；統計只能來自 extracted_data.csv 的實際欄位。
2) 每個表格要有 README（table*_README.md）說明：資料來源、欄位意義、限制。
3) 在 build_log.md 記錄生成命令與腳本位置（建議放 PAPER_DIR/scripts/ 內）。

回報：表格檔案路徑 + summary_stats 的 3 個最重要觀察（必須可追溯）。
```

### Prompt 18：生成 taxonomy 圖（figures/taxonomy.*）
```text
請把 taxonomy 轉成一張論文可用的圖：

- 輸出：PAPER_DIR/figures/taxonomy.pdf（優先）或 taxonomy.png
- 產圖程式：PAPER_DIR/scripts/make_taxonomy_figure.py

要求：
1) taxonomy 的文字與結構必須來自 synthesis_plan.md，不可臨時改掉不記錄。
2) 圖要 readable（字不能太小），並有 caption。
3) 在 paper.md 中要能引用這張圖（稍後會做）。

回報：圖檔路徑 + taxonomy 的層級示意（文字版）。
```

### Prompt 19：生成趨勢/統計圖（figures/trends.*）
```text
請從 extracted_data.csv 或 summary_stats.csv 生成一張趨勢圖（年份 vs 篇數 或 dataset 使用頻率等）：

- 輸出：PAPER_DIR/figures/trends.pdf（或 .png）
- 產圖程式：PAPER_DIR/scripts/make_trends_figure.py

要求：
1) 不得補值或猜測缺失年份；缺失就排除並註明。
2) 圖中要標註資料口徑（例如：n = included studies）。
3) 在 build_log.md 記錄命令。

回報：你畫的是哪一種趨勢圖、以及你用到哪些欄位。
```

### Prompt 20：建立 paper_outline.md（對齊 PRISMA 結構）
```text
請建立 PAPER_DIR/paper_outline.md，內容要對齊 PRISMA 2020 的報告結構（Title/Abstract/Intro/Methods/Results/Discussion/Other）。

要求：
1) 每個章節列出 3-6 個「必答問題」（bullet）。
2) 在 Methods 與 Results 章節標註：對應的中間產物檔案（例如 search_strategy.md、screening_fulltext.csv、quality_assessment.csv、prisma_flow.pdf）。
3) 在 Literature Review / Synthesis 章節標註：taxonomy 與 evidence tables 會如何被引用。
4) 最後加一段「寫作風格規範」：
   - 禁止捏造引用
   - 避免誇大
   - 每個重要主張要可追溯 paper_id

回報：outline 的章節清單。
```

### Prompt 21：寫 Title + Abstract（遵循 PRISMA for Abstracts）
```text
請在 PAPER_DIR/paper.md 先建立前兩段：Title + Abstract（其他章節先留空標題）。

要求：
1) Title 必須包含「systematic review」字樣（符合 PRISMA 標題建議）。
2) Abstract 用結構化格式（建議分段）：Background, Objectives, Data sources, Eligibility criteria, Methods, Results, Limitations, Conclusions, Registration（若無註冊就寫 N/A）。
3) Abstract 中的數字（包含納入篇數）只能引用 prisma_counts.json 或 included 最終統計，不可猜。
4) 如果目前還沒跑完篩選，abstract 可以先用佔位：「[TODO: update after screening]」，但要在 todo_missing_sources.md 記錄。

回報：paper.md 目前內容（只需貼 Title + Abstract）。
```

### Prompt 22：寫 Introduction（Rationale + Objectives）
```text
請在 PAPER_DIR/paper.md 填寫 Introduction（至少 4-8 段）。

要求：
1) 內容包含：研究背景、為何需要 systematic review、與既有 review 的差異/缺口（若找不到既有 review，寫明你如何檢查的）。
2) 明確寫出 Primary RQ + Sub RQs（引用 protocol.md）。
3) 盡量使用已納入的 key papers 或方法論文做背景引用；若尚未確定引用，就用 [TODO:CITATION_NEEDED] 並記錄到 todo_missing_sources.md。

回報：Introduction 的段落大綱（每段一句話摘要）。
```

### Prompt 23：寫 Methods - Protocol & Registration
```text
請在 paper.md 的 Methods 章節新增子節：Protocol and registration。

要求：
1) 描述 protocol 是否有註冊（例如 PROSPERO/OSF）。若沒有註冊，寫明原因（例如 CS 領域無通用註冊平台）與你如何仍保持透明（公開 protocol.md）。
2) 指向本 repo/workspace 的 protocol 檔案（以可公開的方式描述；若 repo 私有就寫「available upon request」或類似）。
3) 對齊 PRISMA 的透明性要求：說明你在寫作早期就對照 PRISMA 項目。

回報：這個子節的文字。
```

### Prompt 24：寫 Methods - Eligibility criteria
```text
請在 paper.md 的 Methods 章節新增子節：Eligibility criteria。

要求：
1) 直接對應 protocol.md 的 inclusion/exclusion。
2) 補充：研究類型、語言限制、年份限制、出版型態（preprint vs peer-reviewed）的處理原則。
3) 提到你如何處理重複版本（arXiv vs conference/journal extended）。

回報：這個子節的文字。
```

### Prompt 25：寫 Methods - Information sources & Search strategy
```text
請在 paper.md 的 Methods 章節新增子節：Information sources / Search strategy。

要求：
1) 列出所有資料庫/來源與最後檢索日期（從 search_strategy.md/raw_sources_manifest.json 取得）。
2) 交代你使用的查詢策略概念（關鍵字群組與布林邏輯），並說明完整查詢字串在附錄（search_strategy.md）。
3) 描述去重方法（從 build_log.md Dedup 節取得）。

回報：這個子節的文字。
```

### Prompt 26：寫 Methods - Study selection process（含雙人覆核或一致性策略）
```text
請在 paper.md 的 Methods 章節新增子節：Study selection process。

要求：
1) 說明兩階段篩選：title/abstract -> full-text。
2) 說明誰做篩選（人工/LLM/混合），以及一致性/覆核策略（例如抽樣複查、衝突解決流程）。
3) 提到排除理由如何記錄（excluded_with_reasons.csv）並在 Results 會彙整。

回報：這個子節的文字。
```

### Prompt 27：寫 Methods - Data extraction & Data items
```text
請在 paper.md 的 Methods 章節新增子節：Data extraction / Data items。

要求：
1) 交代抽取欄位的來源（extraction_schema.json）與抽取流程（extracted_data.csv）。
2) 說明如何處理缺失資料、與如何確保不捏造（空值策略）。
3) 至少列出 8-12 個最關鍵的抽取欄位（用項目符號）。

回報：這個子節的文字。
```

### Prompt 28：寫 Methods - Quality / Risk of bias assessment
```text
請在 paper.md 的 Methods 章節新增子節：Quality assessment / Risk of bias。

要求：
1) 說明你採用的工具（RoB2/ROBINS-I 或 quality checklist），以及為何適合本領域。
2) 說明評估層級（study-level 或 outcome-level），與評估流程（是否雙人、如何解決分歧）。
3) 指向 quality_assessment.csv。

回報：這個子節的文字。
```

### Prompt 29：寫 Methods - Synthesis methods（narrative/taxonomy/evidence tables）
```text
請在 paper.md 的 Methods 章節新增子節：Synthesis methods。

要求：
1) 描述你如何建 taxonomy、如何分群、如何從 extracted_data 產生 evidence tables。
2) 若沒有 meta-analysis：清楚說明原因（例如 outcome 異質、報告不一致），並說明你採用 narrative synthesis 的結構化方法。
3) 若有做統計/趨勢圖：說明統計口徑與欄位來源。

回報：這個子節的文字。
```

### Prompt 30：寫 Results - Study selection（含 PRISMA flow）
```text
請在 paper.md 的 Results 章節新增子節：Study selection。

要求：
1) 報告：identification -> screening -> eligibility -> included 的數字（必須來自 prisma_counts.json）。
2) 在文中引用 PRISMA flow 圖（prisma_flow.*）並寫 caption 文字（不需要重畫）。
3) 簡要總結最常見的 full-text 排除理由（從 excluded_with_reasons.csv 統計 top 5）。

回報：這個子節的文字 + 你引用的數字列表。
```

### Prompt 31：寫 Results - Study characteristics（描述研究特徵）
```text
請在 Results 章節新增子節：Study characteristics。

要求：
1) 用 extracted_data.csv 的欄位來描述：年份分佈、venue 類型、研究方法類型、常見 datasets/metrics。
2) 引用 evidence tables 或 summary_stats（若有），並指向表格檔。
3) 不得描述你沒有抽到的資訊（缺失就說明缺失率）。

回報：這個子節的文字。
```

### Prompt 32：寫 Results - Quality / Risk of bias results
```text
請在 Results 章節新增子節：Risk of bias / Quality assessment results。

要求：
1) 彙總 quality_assessment.csv 的結果（高/中/低 或 yes/partial/no 分佈）。
2) 指出最常見的弱點（例如缺 baseline、缺 ablation、缺資料公開...），但必須可追溯到評估準則。
3) 不要對單一 paper 做過度指控；用審慎語氣描述。

回報：這個子節的文字。
```

### Prompt 33：寫 Results - Synthesis of findings（taxonomy + evidence tables）
```text
請在 Results 章節新增子節：Synthesis of findings。

要求：
1) 依 taxonomy 的頂層類別分小節（至少 4 個小節）。
2) 每個小節都要：
   - 先用 2-3 句定義該類別
   - 引用 evidence tables（表格中的 paper_id）
   - 用引用支撐你的描述（不要捏造性能結論）
3) 若你沒有足夠可量化結果，就把重點放在：方法假設、設計選擇、評估方式、適用場景與限制。

回報：taxonomy 小節標題列表 + 每節 1 句摘要。
```

### Prompt 34：寫 Discussion - Summary, Implications, Limitations
```text
請在 paper.md 的 Discussion 章節撰寫三個小節：

A) Summary of evidence（總結主要發現，不誇大）
B) Implications for researchers/practitioners（研究與實務建議）
C) Limitations（至少包含：檢索限制、篩選可能偏差、資訊缺失、品質評估主觀性/自動化限制）

要求：
- Limitations 必須誠實對應 build_log.md 與 todo_missing_sources.md 中記錄的限制。
- 若你有做任何自動化（LLM 篩選/抽取），需特別說明可能偏差與緩解措施。

回報：Discussion 的三段摘要（每段 3-5 bullet）。
```

### Prompt 35：寫 Conclusion + Future work
```text
請在 paper.md 完成 Conclusion 與 Future work。

要求：
1) Conclusion 用 1 段總結 + 3-5 點條列（不誇大）。
2) Future work 至少 5 點，並且每點要能對應你在 review 中發現的缺口（例如：缺 benchmark、缺標準化評估、缺公開資料）。

回報：Conclusion/Future work 的條列清單。
```

### Prompt 36：建立 claim_to_citation_table.md（主張-證據對照）
```text
請建立 PAPER_DIR/claim_to_citation_table.md，用表格列出 paper.md 中的重要主張與其引用證據。

格式：
Claim | Evidence (citation keys 或 paper_id) | Location in paper.md | Status (OK/TODO) | Notes

要求：
1) 至少列 20 條主張（越重要越先列）。
2) Status 只要 Evidence 不足就標 TODO，並把缺口寫入 todo_missing_sources.md。
3) 不要把「常識句」也列進來，聚焦在可被質疑的主張（比較、因果、效果、趨勢、結論）。

回報：表格前 5 條（示例）。
```

### Prompt 37：生成 references.bib 並做引用一致性檢查
```text
請生成 PAPER_DIR/references.bib（或更新），資料來源僅能來自：

- merged_dedup.csv / extracted_data.csv 中的 bibliographic 欄位
- 或你能從 paper 的 DOI/URL 解析得到的 bibtex（若能查到）

要求：
1) 不得編造 bib 條目；缺資訊就留到 todo_missing_sources.md。
2) 在 build_log.md 記錄你生成 bib 的方法（例如：用 DOI 查 CrossRef；或從 arXiv 解析）。
3) 做一致性檢查：
   - paper.md 中的 citation keys 是否全都存在 references.bib
   - references.bib 是否有未被引用的條目（列出統計即可）

回報：bib 條目數、缺失 DOI 的篇數、以及引用不一致（若有）。
```

### Prompt 38：填 PRISMA checklist（自動對照 paper 章節）
```text
請建立 PAPER_DIR/prisma_checklist_filled.md（或 .csv），把 PRISMA 2020 的主要項目逐條對照你 paper.md 的位置。

要求：
1) 不要照抄 checklist 原文；用你自己的話描述「本 paper 如何滿足」。
2) 每一項要填：Status(OK/TODO) + Location(章節/段落) + Notes。
3) 若 TODO，要指向你要補的中間產物或文字，並同步寫入 todo_missing_sources.md。

回報：TODO 的項目列表（至少列出 item 類別 + 欠缺原因）。
```

### Prompt 39：產生 paper.pdf（若環境允許）
```text
若 pandoc + xelatex 可用，請產生 PAPER_DIR/paper.pdf。

要求：
1) 在 PAPER_DIR/scripts/build_pdf.sh（或 .py）寫下完整建置命令。
2) paper.pdf 要包含：圖、表、References（bib）。
3) 若 PDF 無法生成（缺依賴或錯誤），請：
   - 把錯誤訊息摘要寫入 build_log.md
   - 保留 paper.md 為最終輸出
   - 在 todo_missing_sources.md 註記「PDF build failed」與原因

回報：paper.pdf 是否成功與檔案大小。
```

### Prompt 40：最終 QA（禁止捏造、可重現、可投稿）
```text
請做最終 QA，並把結果寫成 PAPER_DIR/final_qa_report.md：

檢查清單：
1) paper.md 中是否還有 [TODO:*] 或 [TODO:CITATION_NEEDED]
2) excluded_with_reasons.csv 是否完整（至少包含 full-text 排除）
3) PRISMA flow 圖數字是否與 prisma_counts.json 一致
4) claim_to_citation_table.md 是否涵蓋主要結論
5) references.bib 是否有缺少必填欄位（作者/年份/標題）
6) 產物是否都在 TOPIC_WS 下（避免散落）
7) build_log.md 是否能重現主要步驟（搜尋/去重/篩選/抽取/產圖/建 PDF）

最後請在 final_qa_report.md 給我：
- 產出的檔案清單（用樹狀）
- 如何一鍵重現（最少命令集合）
- 最大的 5 個風險/缺口與建議補救方案
```

## 主要方法學資源（連結）
- PRISMA 2020 官方入口：https://www.prisma-statement.org/prisma-2020
- PRISMA 2020 checklist：https://www.prisma-statement.org/prisma-2020-checklist
- PRISMA 2020 flow diagram：https://www.prisma-statement.org/prisma-2020-flow-diagram
- PRISMA 2020 Explanation & Elaboration（BMJ 2021;372:n160）：https://www.bmj.com/content/372/bmj.n160
- Cochrane RoB 2：https://methods.cochrane.org/risk-bias-2
- Cochrane ROBINS-I：https://methods.cochrane.org/methods-cochrane/robins-i-tool
- Kitchenham & Charters SLR(SE) v2.3 (2007) PDF（示例鏡像）：https://www.uofsa.edu/cc/wp-content/uploads/2023/03/guidelines-for-se-literature-reviews-full.pdf
