# Citation Styles Reference（重述版本）

本文件提供常見文獻回顧引用格式的詳細規則。

## APA Style（7th Edition）

### Journal Articles

**格式**：Author, A. A., Author, B. B., & Author, C. C. (Year). Title of article. *Title of Periodical*, *volume*(issue), page range. https://doi.org/xx.xxx/yyyy

**例**：Smith, J. D., Johnson, M. L., & Williams, K. R. (2023). Machine learning approaches in drug discovery. *Nature Reviews Drug Discovery*, *22*(4), 301-318. https://doi.org/10.1038/nrd.2023.001

### Books

**格式**：Author, A. A. (Year). *Title of work: Capital letter also for subtitle*. Publisher Name. https://doi.org/xxxx

**例**：Kumar, V., Abbas, A. K., & Aster, J. C. (2021). *Robbins and Cotran pathologic basis of disease* (10th ed.). Elsevier.

### Book Chapters

**格式**：Author, A. A., & Author, B. B. (Year). Title of chapter. In E. E. Editor & F. F. Editor (Eds.), *Title of book* (pp. xx-xx). Publisher.

**例**：Brown, P. O., & Botstein, D. (2020). Exploring the new world of the genome with DNA microarrays. In M. B. Eisen & P. O. Brown (Eds.), *DNA microarrays: A molecular cloning manual* (pp. 1-45). Cold Spring Harbor Laboratory Press.

### Preprints

**格式**：Author, A. A., & Author, B. B. (Year). Title of preprint. *Repository Name*. https://doi.org/xxxx

**例**：Zhang, Y., Chen, L., & Wang, H. (2024). Novel therapeutic targets in Alzheimer's disease. *bioRxiv*. https://doi.org/10.1101/2024.01.001

### Conference Papers

**格式**：Author, A. A. (Year, Month day-day). Title of paper. In E. E. Editor (Ed.), *Title of conference proceedings* (pp. xx-xx). Publisher. https://doi.org/xxxx

---

## Nature Style

### Journal Articles

**格式**：Author, A. A., Author, B. B. & Author, C. C. Title of article. *J. Name* **volume**, page range (year).

**例**：Smith, J. D., Johnson, M. L. & Williams, K. R. Machine learning approaches in drug discovery. *Nat. Rev. Drug Discov.* **22**, 301-318 (2023).

### Books

**格式**：Author, A. A. & Author, B. B. *Book Title* (Publisher, Year).

**例**：Kumar, V., Abbas, A. K. & Aster, J. C. *Robbins and Cotran Pathologic Basis of Disease* 10th edn (Elsevier, 2021).

### Multiple Authors

- 1–2 authors：列出全部
- 3+ authors：只列第一作者並加「et al.」

**例**：Zhang, Y. et al. Novel therapeutic targets in Alzheimer's disease. *bioRxiv* https://doi.org/10.1101/2024.01.001 (2024).

---

## Chicago Style（Author-Date）

### Journal Articles

**格式**：Author, First Name Middle Initial. Year. "Article Title." *Journal Title* volume, no. issue (Month): page range. https://doi.org/xxxx.

**例**：Smith, John D., Mary L. Johnson, and Karen R. Williams. 2023. "Machine Learning Approaches in Drug Discovery." *Nature Reviews Drug Discovery* 22, no. 4 (April): 301-318. https://doi.org/10.1038/nrd.2023.001.

### Books

**格式**：Author, First Name Middle Initial. Year. *Book Title: Subtitle*. Edition. Place: Publisher.

**例**：Kumar, Vinay, Abul K. Abbas, and Jon C. Aster. 2021. *Robbins and Cotran Pathologic Basis of Disease*. 10th ed. Philadelphia: Elsevier.

---

## Vancouver Style（Numbered）

### Journal Articles

**格式**：Author AA, Author BB, Author CC. Title of article. Abbreviated Journal Name. Year;volume(issue):page range.

**例**：Smith JD, Johnson ML, Williams KR. Machine learning approaches in drug discovery. Nat Rev Drug Discov. 2023;22(4):301-18.

### Books

**格式**：Author AA, Author BB. Title of book. Edition. Place: Publisher; Year.

**例**：Kumar V, Abbas AK, Aster JC. Robbins and Cotran pathologic basis of disease. 10th ed. Philadelphia: Elsevier; 2021.

### Citation in Text

使用上標數字："Recent studies^1,2^ have shown..."

---

## IEEE Style

### Journal Articles

**格式**：[#] A. A. Author, B. B. Author, and C. C. Author, "Title of article," *Abbreviated Journal Name*, vol. x, no. x, pp. xxx-xxx, Month Year.

**例**：[1] J. D. Smith, M. L. Johnson, and K. R. Williams, "Machine learning approaches in drug discovery," *Nat. Rev. Drug Discov.*, vol. 22, no. 4, pp. 301-318, Apr. 2023.

### Books

**格式**：[#] A. A. Author, *Title of Book*, xth ed. City, State: Publisher, Year.

**例**：[2] V. Kumar, A. K. Abbas, and J. C. Aster, *Robbins and Cotran Pathologic Basis of Disease*, 10th ed. Philadelphia, PA: Elsevier, 2021.

---

## 常見期刊縮寫

- Nature: Nat.
- Science: Science
- Cell: Cell
- Nature Reviews Drug Discovery: Nat. Rev. Drug Discov.
- Journal of the American Chemical Society: J. Am. Chem. Soc.
- Proceedings of the National Academy of Sciences: Proc. Natl. Acad. Sci. U.S.A.
- PLOS ONE: PLoS ONE
- Bioinformatics: Bioinformatics
- Nucleic Acids Research: Nucleic Acids Res.

---

## DOI 最佳實務

1. **一律驗證 DOI**：使用 verify_citations.py
2. **使用 DOI URL 格式**：https://doi.org/10.xxxx/yyyy
3. **DOI 後不要加句點**：DOI 為最後元素
4. **確認導向正確**：需指向正確論文

---

## 文內引用規則

### APA
- (Smith et al., 2023)
- Smith et al. (2023) demonstrated...
- 多重引用：(Brown, 2022; Smith et al., 2023; Zhang, 2024)

### Nature
- 上標數字：Recent studies^1,2^ have shown...
- 或：Recent studies (refs 1,2) have shown...

### Chicago
- (Smith, Johnson, and Williams 2023)
- Smith, Johnson, and Williams (2023) found...

---

## Reference List 排序

### 依引用風格
- **APA, Chicago**：按作者姓氏字母排序
- **Nature, Vancouver, IEEE**：依文內出現順序編號

### Hanging Indents
多數格式使用懸掛縮排（首行不縮排，其餘行縮排）。

### 一致性
全文件維持一致格式：
- 大小寫規則
- 期刊縮寫
- DOI 表示方式
- 作者名格式
