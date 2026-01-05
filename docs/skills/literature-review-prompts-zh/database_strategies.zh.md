# Literature Database Search Strategies（重述版本）

本文件提供多資料庫系統性搜尋的完整指引。

## 可用資料庫與技能

### Biomedical & Life Sciences

#### PubMed / PubMed Central
- **Access**：使用 `gget` 或 WebFetch
- **Coverage**：35M+ biomedical citations
- **Best for**：臨床研究、生醫研究、基因與分子生物學
- **Search tips**：MeSH、布林運算（AND/OR/NOT）、欄位標籤 [Title], [Author]
- **範例**："CRISPR"[Title] AND "gene editing"[Title/Abstract] AND 2020:2024[Publication Date]

#### bioRxiv / medRxiv
- **Access**：使用 `gget` 或 API
- **Coverage**：生醫 preprints
- **Best for**：最新未出版研究
- **Note**：未 peer-reviewed；需謹慎確認
- **Search tips**：依分類搜尋（bioinformatics, genomics 等）

### General Scientific Literature

#### arXiv
- **Access**：直接 API
- **Coverage**：physics, math, CS, quantitative biology
- **Best for**：演算法、計算方法
- **Categories**：q-bio, cs.LG, stat.ML
- **Search format**：cat:q-bio.QM AND title:"single cell"

#### Semantic Scholar
- **Access**：API（需金鑰）
- **Coverage**：200M+ papers
- **Best for**：跨領域搜尋、citation graph
- **Features**：influential citations、recommendations
- **Rate limits**：100 requests / 5 minutes（有 API key）

#### Google Scholar
- **Access**：手動或謹慎爬取
- **Coverage**：最完整
- **Best for**：高引用文獻、會議論文、論文
- **Limitations**：無官方 API
- **Export**：可用 Cite 功能

### Specialized Databases

#### ChEMBL / PubChem
- **Access**：`gget` 或 `bioservices`
- **Coverage**：化合物、生物活性
- **Best for**：drug discovery
- **ChEMBL**：2M+ compounds
- **PubChem**：110M+ compounds

#### UniProt
- **Access**：`gget` 或 `bioservices`
- **Coverage**：蛋白序列與功能
- **Best for**：蛋白研究、功能註釋

#### KEGG
- **Access**：`bioservices`
- **Coverage**：pathways, diseases, drugs, genes
- **Best for**：pathway analysis

#### COSMIC
- **Access**：`gget` 或下載
- **Coverage**：癌症基因變異
- **Best for**：癌症研究

#### AlphaFold Database
- **Access**：`gget alphafold`
- **Coverage**：蛋白結構預測
- **Best for**：結構生物學

#### PDB
- **Access**：`gget` 或 API
- **Coverage**：實驗 3D 結構
- **Best for**：結構生物學、drug design

### Citation & Reference Management

#### OpenAlex
- **Access**：API（免費）
- **Coverage**：250M+ works
- **Best for**：bibliometrics
- **Features**：open access

#### Dimensions
- **Access**：free tier
- **Coverage**：publications、grants、patents、clinical trials
- **Best for**：research impact

---

## Search Strategy Framework

### 1. 定義研究問題（PICO）

臨床/生醫回顧使用 PICO：
- **P**opulation
- **I**ntervention
- **C**omparison
- **O**utcome

範例：
「CRISPR-Cas9 gene therapy（I）治療 sickle cell disease（P）相較標準照護（C）對 outcomes（O）的效益？」

### 2. 建立搜尋詞

#### Primary Concepts
- 從研究問題抽取 2–4 個概念。

#### Synonyms & Related Terms
- 列出同義詞、縮寫、相關詞。
- 工具：MeSH browser

#### Boolean Operators
- AND：縮小
- OR：放大
- NOT：排除

範例：
`(CRISPR OR Cas9 OR "gene editing") AND ("sickle cell" OR SCD) AND therapy`

#### Wildcards & Truncation
- `*` or `%`：任意字元
- `?`：單一字元

範例：`genom*`

### 3. 納排條件

#### Inclusion Criteria
- Date range（2015–2024）
- Language（English）
- Publication type（peer-reviewed、preprint）
- Study design（RCTs、cohort）
- Population（human、animal）

#### Exclusion Criteria
- Case reports（n<5）
- 無全文 conference abstracts
- Editorials / commentaries
- Duplicate publications
- Retracted articles

### 4. Database Selection Strategy

#### Multi-Database
- 至少 3 個互補資料庫
- 例：PubMed + bioRxiv + Semantic Scholar

#### Database-Specific Syntax

| Database | Field Tags | Example |
|----------|-----------|---------|
| PubMed | [Title], [Author], [MeSH] | "CRISPR"[Title] AND 2020:2024[DP] |
| arXiv | ti:, au:, cat: | ti:"machine learning" AND cat:q-bio.QM |
| Semantic Scholar | title:, author:, year: | title:"deep learning" year:2020-2024 |

---

## Search Execution Workflow

### Phase 1: Pilot Search
1. 初步廣泛搜尋
2. 檢查前 50 筆結果
3. 記錄關鍵詞與 MeSH
4. 調整策略

### Phase 2: Comprehensive Search
1. 依修正策略搜尋所有資料庫
2. 匯出結果（RIS/BibTeX/JSON）
3. 記錄搜尋字串與日期
4. 記錄各資料庫結果數

### Phase 3: Deduplication
1. 合併為單一檔案
2. 使用 `search_databases.py --deduplicate`
3. 依 DOI / title 去重
4. 保留 metadata 最完整版本

### Phase 4: Screening
1. Title screening
2. Abstract screening
3. Full-text screening
4. 記錄排除原因

### Phase 5: Quality Assessment
1. RCTs：Cochrane RoB
2. Observational：Newcastle-Ottawa
3. Systematic reviews：AMSTAR 2
4. 分級：high / moderate / low / very low

---

## Search Documentation Template

```markdown
## 搜尋策略

### Database: PubMed
- **搜尋日期**：2024-10-25
- **日期範圍**：2015-01-01 to 2024-10-25
- **搜尋字串**：
  ```
  ("CRISPR"[Title] OR "Cas9"[Title] OR "gene editing"[Title/Abstract])
  AND ("sickle cell disease"[MeSH] OR "SCD"[Title/Abstract])
  AND ("gene therapy"[MeSH] OR "therapeutic editing"[Title/Abstract])
  AND 2015:2024[Publication Date]
  AND English[Language]
  ```
- **結果數**：247
- **去重後**：189

### Database: bioRxiv
- **搜尋日期**：2024-10-25
- **日期範圍**：2015-01-01 to 2024-10-25
- **搜尋字串**："CRISPR" AND "sickle cell"（title/abstract）
- **結果數**：34
- **去重後**：28

### Total Unique Articles
- **合併後**：217
- **標題篩選後**：156
- **摘要篩選後**：89
- **全文篩選後**：52
```

---

## Advanced Search Techniques

### Citation Chaining

#### Forward Citation Search
- 使用 Google Scholar "Cited by"
- 使用 OpenAlex 或 Semantic Scholar API
- 用於找後續研究

#### Backward Citation Search
- 從核心文獻的 reference 追溯
- 找高引用基礎研究

### Snowball Sampling
1. 先選 3–5 篇高度相關研究
2. 抽取 references
3. 找多篇共同引用文獻
4. 審查高重疊文獻
5. 重複迭代

### Author Search
- 追蹤領域作者
- 查看 ORCID / Google Scholar
- 研究最近發表

### Related Article Features
- PubMed "Similar articles"
- Semantic Scholar "Recommended papers"

---

## Quality Control Checklist

### Before Searching
- [ ] 研究問題已定義
- [ ] PICO 已建立（若適用）
- [ ] 搜尋詞與同義詞已列出
- [ ] 納排條件已記錄
- [ ] 目標資料庫已選（至少 3）
- [ ] 日期範圍已決定

### During Searching
- [ ] 搜尋字串已測試
- [ ] 結果含完整 metadata
- [ ] 搜尋參數已記錄
- [ ] 各資料庫結果數已記錄
- [ ] 搜尋日期已記錄

### After Searching
- [ ] 已去重
- [ ] 已依流程篩選
- [ ] 排除原因已記錄
- [ ] 品質評估完成
- [ ] DOI 已驗證
- [ ] 搜尋方法已寫入回顧

---

## Common Pitfalls to Avoid

1. 搜尋過窄 → 遺漏文獻
2. 搜尋過寬 → 雜訊過高
3. 單一資料庫 → 覆蓋不足
4. 忽略 preprints → 錯過最新結果
5. 無搜尋紀錄 → 無法重現
6. 手動去重 → 低效且易錯
7. 未驗證 DOI → 引文錯誤
8. 發表偏誤 → 忽略未發表研究

---

## Example Multi-Database Search Workflow

```python
# Example workflow using available skills

# 1. Search PubMed via gget
search_term = "CRISPR AND sickle cell disease"
# Use gget search pubmed search_term

# 2. Search bioRxiv
# Use gget search biorxiv search_term

# 3. Search arXiv for computational papers
# Search arXiv with: cat:q-bio AND "CRISPR" AND "sickle cell"

# 4. Search Semantic Scholar via API
# Use semantic scholar API with search query

# 5. Aggregate and deduplicate results
# python search_databases.py combined_results.json --deduplicate --format markdown --output review_papers.md

# 6. Verify all citations
# python verify_citations.py review_papers.md

# 7. Generate final PDF
# python generate_pdf.py review_papers.md --citation-style nature
```

---

## Resources

### MeSH Browser
https://meshb.nlm.nih.gov/search

### Boolean Search Tutorial
https://www.ncbi.nlm.nih.gov/books/NBK3827/

### Citation Style Guides
見 references/citation_styles.md

### PRISMA Guidelines
http://www.prisma-statement.org/
