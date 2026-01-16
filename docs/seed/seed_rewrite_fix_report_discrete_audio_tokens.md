# AUTOSR-SDSE Seed Rewrite 失敗復現與修復方案報告（Discrete Audio Tokens Case）

> 產出格式：Markdown（.md）  
> 報告日期：2026-01-15  
> 對應專案：`Sologa/AUTOSR-SDSE`  
> 對應案例：`docs/seed/seed_rewrite_failure_repro_discrete_audio_tokens.md`  
> 目標：針對 Seed Rewrite / Seed Retrieval 在「Discrete Audio Tokens: More Than a Survey!」主題的失敗，做**深度解析**並提出**可落地的修復方案**；同時依照你的要求修正 **prompt 設計**、補上 **iteration 必須帶完整歷史** 的設計，並整理 `Sologa/codex-pipeline` 的 skills 在此階段可如何派上用場。

---

## 0. 結論摘要（先給可執行的方向）

### 0.1 這次失敗的最核心原因（以「系統層面」表述）

1. **Seed rewrite loop 是「無狀態」的**：每次迭代給 LLM 的訊息幾乎相同（只含 topic），因此 10 次迭代本質上接近 10 次重抽樣；在 deterministic / 低溫設定下甚至等價於重跑同一次。  
2. **Seed selection 的「cutoff」把唯一命中的候選直接清空**：原始查詢與 rewrite 查詢都只命中 1 筆（那就是目標 paper 本身），然後 cutoff 規則又把它移除，導致 `records_after_filter=0` 進入 rewrite；rewrite 仍回到同一筆 → 無限循環直到 `max_attempts`。  
3. **查詢策略過度依賴 title-like phrase + survey_terms**：對於「新 / 少人用同一種詞彙描述」的主題，title-based recall 會非常脆弱；同時把 `survey|review|overview|tutorial` 當成硬性 AND 條件，會把大量相關但不在 title/abstract 放這些字的候選排除，導致 recall 更差。  
4. **沒有把「上一輪得到的失敗訊號」回饋給 LLM**（例如：查詢只命中 1 筆、被過濾清空、需要更廣義詞/別名/相關子領域詞），因此 LLM 無法「策略性探索」而只能在 topic 附近做微小改寫。

### 0.2 最有效的一組修復（建議優先級）

> 下面 4 點合起來，才能把系統從「一再撞牆」改成「有方向地探索」。

**(A) 讓 rewrite 迭代變成 stateful：把完整歷史（至少摘要）帶進 prompt**  
- 每次 iteration 提供：  
  - 之前輸出過的 phrases / queries  
  - 每個 query 的 `records_total`、`records_after_filter`、下載成功數  
  - （可選）top-k 命中 paper 的 title（若 prompt 規範允許；若不允許就只給 count 與「過窄」類型的抽象訊號）  
- 要求 LLM「下一次必須與先前輸出有明顯差異」，並以「提高命中候選數」為目標。

**(B) rewrite 不要只產生 1 組 phrases：每輪產生多組候選，做 “dry-run retrieval scoring” 再選最好**  
- 例如每輪生成 8–20 個 query candidates（每個 candidate 1–3 phrases），先只做 metadata 搜索（不下載 PDF），計算一個 score，選出最可能帶來 >0 seeds 的候選，再進入 seed selection + download。  
- 這不是 “rule-based fallback”，而是**基於 retrieval feedback 的自動選擇**；真正擴寫仍由 LLM 產生。

**(C) 把 survey_terms 從「硬 AND」改成「soft filter / rerank」或二段式**  
- Stage 1：先用更廣義 query 抓候選（不加 survey_terms 或把它放到 OR/boost）  
- Stage 2：再用分類器/LLM 判斷哪些是 survey / overview / benchmark / taxonomy，再挑 seed。  
- 這會顯著改善 recall。

**(D) cutoff 不要把唯一候選直接清空（至少要有 “min survivors” 保護）**  
- 如果 cutoff 會造成 candidates = 0：  
  - 方案 1：改成「降權」而不是刪除（例如記分扣分）  
  - 方案 2：允許保留 1–k 個候選（包含 self-match）但打標記 `self_related=true`，由下游決定要不要用  
  - 方案 3：當只剩 self-match 時，直接觸發「更廣義 rewrite」而不是把它刪光

---

## 1. 失敗案例完整復現與觀察（Discrete Audio Tokens）

### 1.1 你 repo 中的復現方式（摘要）

- 使用 `--seed-rewrite` 開啟 rewrite 模式  
- `--seed-rewrite-max-attempts 10`  
- 最終錯誤：**Seed rewrite exhausted without PDFs**（意味著 10 次 rewrite 都沒有任何可下載到的 seed PDF）

### 1.2 產物（artifacts）層面的關鍵證據（你 repo 中已整理）

#### (a) `seed_selection.json` 的行為

- `records_total = 1`：查詢只命中 1 筆  
- `records_after_filter = 0`：過濾後 0 筆  
- `cutoff_reason = cutoff_removed_all_candidates`：表示那 1 筆被 cutoff 規則移除了  
- 等價於：**查到的唯一候選就是「自己」，而 cutoff 把它刪掉** → rewrite 觸發

#### (b) `download_results.json` 的行為

- `downloads.arxiv = []`：沒有任何下載到的 arXiv PDF  
- `rewrite_attempts = 10`：達到最大嘗試次數仍 0

#### (c) `seed_rewrite.json` 的行為

- 每次 `raw_output` 產生的 phrases 都非常貼近 topic（例如 `discrete audio tokenization` / `audio token sequences` / `audio token representations` 等）  
- 10 次之間缺乏結構性的探索（沒有明顯跳到更上位概念、方法名、典型系統、benchmark、關鍵詞群）

### 1.3 本質上發生什麼事（用一句話）

> 你的 pipeline 在「只有 1 篇 paper 命中」且「cutoff 會把它清掉」的情況下，**rewrite agent 無法在缺乏歷史回饋的情況下產生足夠廣義的替代查詢**，因此永遠回到同一篇 paper → 直到 attempts 耗盡。

---

## 2. 為什麼 “iteration 一定要讓模型看到前面 iter 的完整歷史”

你提出的第 3 點非常關鍵：**為什麼之前大家沒提？**  
在這個系統裡，這其實是「最致命」的設計缺口之一。

### 2.1 形式化地看：你現在的迭代 = 無狀態重抽樣

若 iteration 的 prompt ≈ `f(topic)`，那第 t 次輸出：

\[
y_t \sim p(y \mid \text{topic})
\]

如果 prompt 不含任何 `y_{<t}` 或任何來自 retrieval 的 feedback，則：

- `y_1, y_2, ..., y_T` **近似獨立同分佈**  
- 在低溫或 deterministic 設定下，甚至會高度重複（或完全一樣）

也就是說，你的迭代不是「逐步逼近解」，而是「同樣的抽樣再做 10 次」。

### 2.2 在工程上：iteration 要成立必須至少滿足一個條件

要讓 iteration 能真的探索，至少要做到其中之一（最好是多個）：

1. **把歷史（前面產生過的候選）塞回去**：讓模型知道哪些方向已失敗  
2. **把 reward / feedback 塞回去**：讓模型知道“什麼方向有更高的命中率”  
3. **施加顯式多樣性約束**：例如禁止重複 n-gram、要求覆蓋不同概念類型  
4. **外部機制做探索**：例如 multi-armed bandit / beam search / MCTS 之類的控制（但你現在不是）

你現在 1–4 幾乎都沒有，所以 retries 不會帶來系統性改善。

---

## 3. Prompt 的問題與修正（符合你的第 2 點要求）

你要求：

> prompt 不能攜帶「某個特定領域的關鍵字」  
> 例如不能出現「speech/acoustic/music instead of audio」這種提示式領域引導

### 3.1 為什麼這個要求合理

如果 prompt 中包含「把 audio 改成 speech / acoustic / music」之類的例子，會產生兩個副作用：

- **把 rewrite 空間硬綁到特定領域**：你想要的是 domain-agnostic 的 query expansion，而不是把某些同義詞硬寫死  
- **造成非預期偏置**：模型會覺得“這題答案就該往那些詞靠”，導致探索變窄

### 3.2 你真正需要的 prompt 不是「同義詞提示」，而是「探索策略提示」

你要的是：  
- 讓模型「自己」找出文獻常用的別名、上位概念、常見系統名、benchmark 名稱、方法族群  
- 但你不能把這些詞塞進 prompt 當範例

因此 prompt 應該寫成「策略層」約束，而不是「詞彙層」提示。

---

## 4. 建議的新 Seed Rewrite Prompt（不含特定領域替換提示）

> 下列 prompt 片段刻意不包含任何「把 X 改成 Y」的領域例子；只給**抽象策略**。  
> 可作為 `resources/LLM/prompts/seed/seed_query_rewrite.md` 的 v2 候選。

### 4.1 Prompt v2（單輪產生多候選 + 明確多樣性 + 利用歷史）

**System / Instruction（概念草案）**

```
你是一個「學術檢索查詢改寫器」。目標：為給定主題生成可用於學術資料庫（例如 arXiv）檢索的 query phrases，以最大化找到“綜述/回顧/概覽/教學/基準/分類/趨勢”等類型的相關文獻。

你會拿到：
- topic：使用者提供的主題
- history：先前迭代已嘗試過的 phrases 與其檢索結果摘要（命中數量）
- constraints：輸出限制與避免重複的規則

要求：
1) 每次輸出 8–12 組候選（每組 1–3 個 query phrase），以增加探索覆蓋面。
2) 你必須避免與 history 中的 phrases 重複或高相似；至少 70% 的候選需引入「不同於 topic 的關鍵概念」。
3) 候選必須覆蓋不同“概念型別”，至少包含：
   - 上位/更一般概念（更廣義的研究方向）
   - 方法/模型/表徵層面的概念
   - 評測/基準/系統化比較/分類等概念
4) 候選 phrases 要像學術檢索關鍵字：短、可組合、可出現在標題或摘要。
5) 不要輸出解釋、不要輸出編號、不要輸出任何多餘文字，只輸出候選，每行一組。每組中的多個 phrase 用 " | " 分隔。
```

**User variables（輸入）**

```
topic: <<TOPIC>>

history (last attempts):
<<HISTORY_SUMMARY>>

constraints:
- each line: 1–3 phrases separated by " | "
- no numbering
- avoid repeating any phrase from history
- prefer phrases likely to appear in paper title/abstract
```

**Output example（格式示意；不放具體詞）**

```
<phrase A>
<phrase B 1> | <phrase B 2>
<phrase C>
...
```

### 4.2 為什麼這個 prompt 能解你現在的問題

- **history 直接讓模型知道哪些方向已失敗**（你第 3 點）  
- 一輪多候選 + scoring 能避免「一次只押注 1 個 phrase」造成的脆弱性  
- “概念型別覆蓋”是讓模型探索更大的語義空間，但不需要塞任何特定領域詞進 prompt

---

## 5. 讓 rewrite 真的有效：加入「檢索回饋」與「選擇策略」

### 5.1 新的迭代主迴圈（建議）

把現在的：

> 迭代：LLM → 產生 1–3 phrases → 立刻組 query → 搜索 → 若失敗再 LLM …

改成：

> 迭代：LLM → 產生 N 組候選 →（對每組做 metadata 搜索）→ scoring → 選最好的 query → 正式 download → 若仍失敗，再把結果摘要塞回 history，進下一輪

### 5.2 建議 scoring 指標（可先簡單）

對每個 candidate query，做一次 metadata search（不下載 PDF），得到：

- `records_total`
- `records_after_filter`
- `records_after_dedupe`（若有）
- `survey_like_count`（可選：用 title/abstract 是否含 survey_terms 做粗估）

然後 score：

\[
\text{score} = \log(1+\text{records\_after\_filter}) 
              - \lambda \cdot \text{similarity\_to\_history}
\]

- 最初版本你甚至可以只用 `records_after_filter` 最大化  
- `similarity_to_history` 用簡單 Jaccard / cosine（TF-IDF）即可

> 重點：**你需要 reward signal**，否則 iteration 沒意義。

### 5.3 仍符合 “不做 rule-based fallback” 的原則嗎？

是的，原因：

- “擴寫/探索”仍由 LLM 產生  
- scoring 只是選擇哪個 LLM 候選先嘗試  
- 你不是用 hard-coded domain synonyms 或寫死替換規則來救場

---

## 6. cutoff 規則該怎麼修（避免永遠清空）

你現在的 failure 由這個模式造成：

1. query 命中 1 篇（而且就是 topic 本身）
2. cutoff 把它刪掉 → 0
3. rewrite 仍產生近似 query → 還是命中同一篇 → 重複

### 6.1 建議的 “min survivors” 設計

在 cutoff 階段加入保護：

- 若 cutoff 後 candidates 會變成 0，則：
  - **保留 1 篇**（即使與 topic 高相似），但加上 `self_match=true`  
  - 同時觸發 “needs_broader_search=true” 讓 rewrite 走更廣義路線  
  - 下游可決定「不把 self_match 當 seed」，但至少 pipeline 不會直接崩潰

這樣你有兩種選擇：

- 想讓 pipeline 一定能產出 seed：就允許下載 self_match  
- 想維持不下載 self_match：那也能繼續跑 rewrite（因為你至少知道系統卡在 self-match）

### 6.2 更好的方式：把 cutoff 從「硬刪」改成「打分扣分」

如果你的 seed selection 本來就是 ranking-based：  
- cutoff 可以改成 penalty  
- 讓 self-match 永遠不是 top-1，除非真的沒有其他任何候選

---

## 7. 查詢構造（arXiv API 層）與你現在策略的缺陷

### 7.1 你現在的 query 形式容易過窄

你 repo 的 query 是「topic 變形 + survey_terms」：

- topic variants（title-like）提供的 recall 太弱  
- survey_terms 當 AND 條件，會把很多 benchmark / taxonomy / analysis 但沒寫 “survey/review” 的 paper 排除

### 7.2 arXiv API 查詢構造要點（你可在系統裡引用的依據）

- arXiv Search API 支援 `ti:`（title）、`abs:`（abstract）、`all:`（全域）等 field 前綴，也支援 `AND/OR/ANDNOT` 組合。  
- 多詞 phrase 常見寫法是 `abs:"deep learning"`，通常是 “all-words matching”，不一定是 strict phrase。  
- 使用 query wrapper（如 `arxiv.py` / `arxivpy` / `aRxiv`）可以更安全地產生 query、處理分頁與 rate limit。

參考（可在你的 repo README/notes 放入這些連結）：
```text
OpenAI Codex skills (skills 定義與格式): https://developers.openai.com/codex/skills
arxiv.py (Python wrapper): https://github.com/lukasschwab/arxiv.py
aRxiv tutorial (R, query 組合示例): https://docs.ropensci.org/aRxiv/articles/aRxiv.html
arxivpy (Python wrapper, query examples): https://github.com/titipata/arxivpy
```

### 7.3 建議的 query builder v2（語義更寬但仍可控）

**做法 1：二段式（強烈建議）**

- Stage 1（廣義抓候選）：  
  - 用 LLM 產生多個 “core concept” phrases  
  - 用 `abs:` 與 `ti:` 混合（title 不能命中就靠 abstract）  
  - 不強制加 survey_terms
- Stage 2（判斷 survey/overview/benchmark）：  
  - 用 LLM 或簡單 classifier 對 title/abstract 做分類  
  - 只在這一階段才用 survey_terms 當特徵

**做法 2：survey_terms soft condition（次佳）**

把：

- `(... topic variants ...) AND (survey_terms)`

改成：

- `(... topic variants ...) AND (survey_terms OR benchmark_terms OR taxonomy_terms OR "in-depth analysis" ...)`

其中 benchmark_terms / taxonomy_terms 是**抽象型別字**，不是特定領域名詞。

---

## 8. 依照 seed 流程，我能 retrieve 到哪些 paper（以“可當 seeds”角度整理）

> 你 repo 中指出：原始查詢只命中 1 篇（`arXiv:2506.10274`），rewrite 後仍只有這 1 篇，因此被 cutoff 清空。  
> 這裡我用「同一研究主題的種子文獻集合」角度，列出更合理應該被取回的 survey/overview/benchmark 類型 paper（你可以把它們當作 seed retrieval 的 target set）。

### 8.1 已知必然相關（且在你 repo case 中出現/被提及）

1. **arXiv:2506.10274 — _Discrete Audio Tokens: More Than a Survey!_**  
   - 類型：survey + benchmark + taxonomy（paper 自述）  
   - 問題：若 cutoff 規則把它視為 self-match 並移除，必須確保仍能找到其他 seeds

2. **arXiv:2502.06490 — _Recent Advances in Discrete Speech Tokens: A Review_**  
   - 類型：review / survey  
   - 在你的 repo 裡，API workspace 曾能 retrieve 到它（而 codex workspace 沒有）

### 8.2 應該被納入 seeds 的「同族」綜述/系統化比較（可提升成功率）

3. **arXiv:2402.13236 — _Towards audio language modeling -- an overview_**  
   - 類型：overview（非常符合你硬性 survey_terms 之一：overview）  
   - 內容：提供 neural audio codecs 與 codec-based audio language models 的系統化整理  
   - 這篇的存在意味著：只要 rewrite 能跳到更上位概念（例如 audio language modeling / neural audio codec），就不會卡死在 2506.10274

4. **arXiv:2402.13071 — _Codec-SUPERB: An In-Depth Analysis of Sound Codec Models_**  
   - 類型：benchmark + in-depth analysis（雖未必含 “survey” 字樣，但本質是系統化比較）  
   - 這篇對於「離散 tokenizer」這個子題非常關鍵：它給 codec 作為 tokenizer 的普適評測框架

> 上面 3–4 的存在直接支持：**你的 query builder 不該把 survey_terms 當 hard AND**；至少要把 “benchmark / in-depth analysis / taxonomy” 視為同一類 “survey-like seed”。

### 8.3 “seed rewrite” 若做對了，查詢應該能自然命中這些類型

以 seed rewrite 的目標來看（不是寫死某些領域詞），合理應該探索：

- “audio language modeling” / “codec language model” / “neural audio codec”
- “sound codec benchmark” / “tokenizer benchmark” / “in-depth analysis”
- “discrete tokens” + “review/overview”

---

## 9. 把 `Sologa/codex-pipeline` skills 用在這個問題上（你的第 4 點）

你提到想用例如 `scientific-brainstorming` 這類 skill。  
你的 pipeline 現在卡住的點其實就是「缺乏系統性探索 + 缺乏可重複的研究流程」。skills 正好可以補上：

> 註：此處的 skill 行為與流程設計依照你 repo 內 skill 文件的描述做整理；重點是把它轉成可落地的 pipeline 子流程。

### 9.1 建議把問題拆成 4 個可用 skill 封裝的子任務

#### 任務 A：診斷與假設（用 hypothesis-generation / critical-thinking）
輸入：失敗 artifact（seed_selection.json / seed_rewrite.json / download_results.json）  
輸出：可檢驗的 failure hypotheses + 對應修復手段

你目前的 hypotheses 至少包括：
- query recall 太低
- survey_terms 太硬
- cutoff 清空
- rewrite 無歷史無回饋

#### 任務 B：候選 query 產生（用 scientific-brainstorming）
輸入：topic + 已嘗試 history + 失敗訊號（命中數）  
輸出：大量多樣化候選 query phrases（多概念型別覆蓋）

這個 skill 的價值在於：它通常會要求「先發散再收斂」，非常適合做 query expansion。

#### 任務 C：文獻檢索與整理（用 literature-review）
輸入：candidate queries  
輸出：候選 papers 清單（含 metadata）、去重、分類（survey / benchmark / tutorial / taxonomy）

#### 任務 D：產出可追溯報告（用 scientific-writing + citation-management）
輸入：選中的 seeds + 分類結果  
輸出：給 OrionVault / Obsidian 可長期維護的 md 報告（含引用與摘要）

### 9.2 把 skills 融合進 seed 模組：一個可實作的流程範本

你可以把 seed_rewrite 模組改成：

1. **Brainstorm phase（scientific-brainstorming）**：一次產生 20–50 個短 phrases（不只 3 個）  
2. **Prune/Score phase（script）**：對每個 phrase 做 metadata retrieval，計分  
3. **Select phase（critical-thinking）**：若多個候選分數相近，可用 LLM 做比較選擇  
4. **Retrieve phase（literature-review）**：對 top-k queries 拉回 papers，並做 survey-like 分類  
5. **Commit memory（scientific-writing）**：把這次嘗試的歷史與結果寫入 OrionVault（可供下一次 query rewrite 用）

這樣 “iteration” 的歷史就自然形成可重用的 system memory，而不是每次都從零開始。

---

## 10. 具體改動建議（你可以直接開工的 checklist）

### 10.1 代碼層（必做）

- [ ] 在 seed rewrite agent 的 prompt builder 中加入 `history`（至少包含先前 phrases 與命中數）  
- [ ] 修改 rewrite loop：每輪生成多組候選並 scoring（metadata dry-run）  
- [ ] seed selection cutoff 加入 min survivors 或 penalty 機制，避免清空  
- [ ] 把 survey_terms 由 hard AND 改成二段式或 soft filter

### 10.2 觀測性（必做）

- [ ] `seed_rewrite.json` 增加：  
  - `prompt_used`（至少 hash 或完整內容）  
  - `candidate_queries`（多組）  
  - `per_candidate_stats`（records_total / after_filter / downloads）  
- [ ] 日誌增加：每輪最好的 candidate 為何被選中（分數）

### 10.3 測試（建議）

- [ ] 建一個 regression fixture：  
  - topic = “Discrete Audio Tokens: More Than a Survey!”  
  - 預期：在 `max_attempts<=3` 內能取得至少 1 篇非 self-match 的 seed（例如 2402.13236 / 2402.13071 / 2502.06490 之一）
- [ ] 加一個 unit test：同 topic + history 不同 → LLM output 的重複率降低（可用相似度指標檢測）

---

## 11. 你下一步可以怎麼做（不需要我再讀 repo 的最小閉環）

1. 先做最小 patch：**history injection + 一輪多候選 + dry-run scoring**  
2. 把 `survey_terms` 改成 soft filter（至少別硬 AND）  
3. 再調 cutoff：加 min survivors  
4. 跑 regression：確保這個 case 不再 10 次全掛

---

## 12. 附錄：本報告中提及的外部參考（便於你收進 OrionVault）

### 12.1 Codex skills 概念（OpenAI 官方）
```text
Agent Skills: https://developers.openai.com/codex/skills
OpenAI skills catalog: https://github.com/openai/skills
```

### 12.2 arXiv API / query 組合與 wrapper（便於你寫 query builder）
```text
arxiv.py: https://github.com/lukasschwab/arxiv.py
aRxiv tutorial: https://docs.ropensci.org/aRxiv/articles/aRxiv.html
arxivpy: https://github.com/titipata/arxivpy
```

### 12.3 可作為 seed 的相關綜述/系統化分析（IDs）
```text
arXiv:2506.10274  Discrete Audio Tokens: More Than a Survey!
arXiv:2502.06490  Recent Advances in Discrete Speech Tokens: A Review
arXiv:2402.13236  Towards audio language modeling -- an overview
arXiv:2402.13071  Codec-SUPERB: An In-Depth Analysis of Sound Codec Models
```

---

## 13. 你提出的四點要求逐項對照（確認已覆蓋）

1) **用 md 檔**：本檔即為 Markdown。  
2) **prompt 不攜帶特定領域替換提示**：我提供的 prompt v2 沒有任何 “X instead of Y” 的領域關鍵詞提示；只描述抽象策略。  
3) **解釋 iteration 必須讓模型看到完整歷史**：第 2 節提供形式化與工程層原因，並在第 5 節將其具體化為 history + feedback。  
4) **研究 codex-pipeline skills 並提出可用點**：第 9 節把 skills 映射到可落地的 seed 模組子流程，並給出整合範本。

