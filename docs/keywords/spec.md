# Keywords Stage 規格（spec）

本文件定義「Keywords」階段的行為與介面：讀取 seed PDFs，透過 LLM 產生 **anchor_terms** 與 **search_terms**（分類化），並輸出 `keywords.json` 供後續 harvest 使用。

---

## 1) 目的

- 由 seed PDFs 產生主題的 **anchor_terms**（穩定錨點）
- 由 seed PDFs 產生分類化的 **search_terms**
- 輸出結構化 JSON，供後續 harvest 使用

---

## 2) 介面 / 參數

### CLI
```
python scripts/topic_pipeline.py keywords --topic "<topic>"
```

### 主要參數
- `--topic`：主題字串（寫入輸出）
- `--pdf-dir`：指定 PDF 來源目錄（預設 `seed/downloads/ta_filtered/`）
- `--max-pdfs`：最多讀取幾篇 PDF（預設 3）
- `--provider` / `--model`：LLM 供應商與模型（**固定使用 gpt-5.2**）
- `--temperature`：抽詞溫度（**固定 1.0**）
- `--max-queries`：search terms 總量上限（預設 50）
- `--include-ethics`：允許 ethics 類術語
- `--seed-anchor`：可重複指定（補充或覆寫錨點指引）
- `--reasoning-effort` / `--max-output-tokens`：LLM 輸出控制（預設 **medium**；支援 low/medium/high/xhigh）
- `--force`：覆寫既有 `keywords.json`

---

## 3) 核心行為

### 3.1 讀取資料
- 從 `--pdf-dir` 收集 PDFs
- 依 PDF 檔名推斷 arXiv id
- 透過 arXiv metadata 補齊 title/abstract/year/url

### 3.2 LLM 抽詞
- 每篇 PDF 各自抽取（per‑paper）
- 產出 `anchor_terms` + `search_terms` + `papers[*].detected_keywords`
- 再由聚合步驟合併與去重
> 注意：為配合 reasoning LLM，模型固定為 **gpt-5.2**，temperature 固定為 **1.0**。

### 3.3 Anchor 與 Search Terms
- **本階段會同時產生 `anchor_terms` 與 `search_terms`**（同一份輸出）
- 不需要使用者額外提供 anchor（除非想提供 `--seed-anchor` 作為提示）
> 補充：anchor/search terms 將被用來組合布林查詢（例如 `(anchor OR ...) AND (term OR ...)`），因此必須是可搜尋、可泛化的短片語。
> 本階段 **不使用 topic 變體作為 anchor**；anchor 會從 PDF/metadata 與 search_terms 中抽取並清理（去除與 topic 相同或不合規的錨點）。

---

## 4) 輸出

### 主要產物
```
workspaces/<topic_slug>/keywords/keywords.json
workspaces/<topic_slug>/keywords/keyword_extractor_usage_<timestamp>.json
```

### keywords.json 結構（摘要）
```json
{
  "topic": "...",
  "anchor_terms": ["..."],
  "search_terms": {
    "<category>": ["..."]
  },
  "papers": [
    {
      "id": "...",
      "source_id": "arXiv:....",
      "title": "...",
      "abstract": "...",
      "year": "YYYY",
      "source_url": "...",
      "detected_keywords": [
        {"term": "...", "category": "...", "evidence": {"quote": "...", "page": "n/a"}, "confidence": 0.0}
      ]
    }
  ]
}
```

---

## 5) LLM Prompt（完整模板）

> 下列為 **實際使用的完整模板**（含 placeholder），來源為
> `resources/LLM/prompts/keyword_extractor/generate_search_terms.md`

```
- Role: Academic Search Strategy Designer and Systematic Review Analyst
- Background: The user uploads one or more survey papers (PDFs). Your goal is to extract high-quality search terms and prepare a metadata-aligned JSON summary for downstream systematic-review tooling.
- Profile: You design evidence-grounded, reproducible search strategies for literature reviews. You prioritize deduplication, clarity, and coverage.
- Skills: Systematic review methodology, taxonomy-driven term extraction, boolean query synthesis, deduplication and synonym consolidation, concise rationale writing.
- Goals: Produce a JSON-only output containing anchor terms, categorized search terms, and per-paper metadata entries (including detected keywords with evidence). Ground every field in the PDFs and the provided metadata.
 - Constraints:
  - Use only information present in the uploaded PDFs or in the metadata block appended below.
  - Copy each paper title and abstract exactly as provided; do not paraphrase or truncate them.
  - Prefer multi-paper-supported terms; mark single-paper terms with lower confidence.
  - Keep each rationale under 20 words; cite page numbers if available; otherwise use "page": "n/a".
  - Keep total recommended search terms <= <<max_queries>> (default 50).
  - Keep each search term as a concise noun phrase (ideally 1–2 words, maximum 3); never output full sentences or tokens with underscores.
  - Output strictly valid JSON, no extra text.
- Downstream usage (important):
  - The output anchor_terms and search_terms will be used to construct boolean search queries for arXiv-style engines.
  - anchor_terms are treated as stable topic anchors; search_terms are category-specific query terms.
  - Queries are built by combining anchor_terms with search_terms (e.g., (anchor OR anchor OR ...) AND (term OR term OR ...)).
  - Matching is mostly literal, so anchor_terms and search_terms must be searchable, generalizable phrases (not full titles, not overly specific wording).
  - Avoid punctuation-heavy strings, quotes, dataset IDs, or long phrases; prefer 1–3 word noun phrases likely to appear in titles/abstracts.
  - Do not add meta terms like "survey/review" unless the topic itself explicitly centers on surveys/reviews.
- Topic interpretation (important):
  - The provided topic_hint may be either (1) a broad research area or (2) a specific paper title (possibly exact).
  - Silently decide which type topic_hint is; do not output the decision.
  - Never output topic_hint itself as anchor_terms.
  - If topic_hint is type (2), you must NOT copy the title, subtitle, punctuation, or create abbreviations from it. Derive anchors only from the PDFs/metadata.
  - If topic_hint is type (1), you may use common field abbreviations only when they appear in the PDFs/metadata and are widely used in the field.
  - Anchor_terms must appear verbatim (case-insensitive) in the titles/abstracts; use 1–3 word noun phrases without punctuation.
  - Abbreviations are allowed only if they appear in the PDFs/metadata and are widely used in the field; never invent acronyms.
  - When an abbreviation is used, include its long-form anchor term alongside it (do not output acronym-only anchors).
  - Do not inject external domain assumptions; derive anchor_terms from the PDFs/metadata only.
- Workflow:
  1) Review the provided paper metadata (see block below) to capture canonical identifiers, titles, abstracts, publication years, and URLs.
  2) Read the PDFs and identify the central task/topic; propose 2–4 anchor_terms aligned with the metadata guidance.
  3) For each paper, extract candidate terms grouped by categories: <<category_list>>.
     <<category_coverage_note>>
<<additional_category_note>>
  4) Normalize and merge across papers: lemmatize, deduplicate, and consolidate related phrasing for each category.
  5) Identify supporting evidence for detected keywords (quotes + page numbers when available) so each term can be traced back to the PDFs.
  6) Keep each `papers[*]` entry aligned with the metadata block; copy titles/abstracts verbatim and supply detected keywords with evidence.
- Runtime overrides (current request):
  - topic_hint: <<topic_hint>>
  - language: <<language>>
  - include_ethics: <<include_ethics>>
  - max_queries: <<max_queries>>
  - seed_anchors: <<seed_anchors_info>>
  - custom_categories: <<custom_categories_info>>
  - exclude_terms: <<exclude_terms_info>>
  - anchor_terms: <<anchor_guidance>>
  - category_coverage_note: <<category_coverage_note>>
- Provided paper metadata (copy titles/abstracts exactly; keep ordering):
<<paper_metadata_block>>
- OutputFormat (strict JSON):
{
  "topic": "<<topic_or_inferred>>",
  "anchor_terms": ["…", "…"],
  "search_terms": {
    "<category>": ["…"],
    "<category>": ["…"]
  },
  "papers": [
    {
      "id": "<stable short id>",
      "source_id": "arXiv:<identifier>",
      "title": "<copy title exactly>",
      "abstract": "<copy abstract exactly>",
      "year": "<YYYY or unknown>",
      "source_url": "<https://arxiv.org/abs/...>",
      "detected_keywords": [
        {
          "term": "…",
          "category": "<category label>",
          "evidence": {"quote": "…", "page": "n/a|<number>"},
          "confidence": 0.0
        }
      ]
    }
  ]
}
```

---

## 6) 測試要點

- `keywords.json` 是否存在且 JSON 合法
- `anchor_terms` 與 `search_terms` 是否同時出現
- `papers[*].detected_keywords` 是否包含 evidence
- 若 `--force` 未啟用，重跑應該回傳 `skipped: true`

---

## 7) 已知限制

- 結果品質高度取決於 seed PDFs
- 若 seed PDF 過少，分類與術語容易偏窄
- LLM 可能生成雜訊 anchor_terms（可用 `--seed-anchor` 引導）
