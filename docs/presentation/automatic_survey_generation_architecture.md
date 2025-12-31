# Automatic Survey Generation 架構流程圖（概念版）

> 本文件為概念性流程圖，避免程式與函式細節；聚焦整體架構與資料流。

## A) 全貌流程圖（Automatic Survey Generation）

```mermaid
flowchart TD
  classDef stage fill:#F3F6FF,stroke:#3949AB,stroke-width:1px,color:#111;
  classDef artifact fill:#E8F5E9,stroke:#2E7D32,stroke-width:1px,color:#111;

  P1[1. Paper Pool Construction and Retrieval]:::stage
  P2[2. Paper Structuring - attribute and evidence extraction]:::stage
  P3[3. Taxonomy and Outline]:::stage
  P4[4. Survey Drafting - citation-aware synthesis]:::stage
  P5[5. Verification and Refinement]:::stage
  P6[6. LaTeX Build and Debug to PDF]:::stage
  P7[7. PDF]:::artifact

  P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7
  P2 -.-> P4
  P2 -.-> P5
```

說明：
- 實線為主流程，虛線表示「Paper Structuring」的輸出同時支援撰寫與 refinement。

## B) Paper Pool Construction / Retrieval（現行 pipeline 細節）

```mermaid
flowchart TD
  classDef stage fill:#F3F6FF,stroke:#3949AB,stroke-width:1px,color:#111;
  classDef artifact fill:#E8F5E9,stroke:#2E7D32,stroke-width:1px,color:#111;
  classDef agent fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px,color:#111;
  classDef online fill:#E1F5FE,stroke:#0277BD,stroke-width:1px,color:#111;
  classDef db fill:#F1F8E9,stroke:#558B2F,stroke-width:1px,color:#111;
  classDef snowball fill:#FCE4EC,stroke:#C2185B,stroke-width:1px,color:#111;

  A[輸入 topic]:::stage
  B{{改寫 topic 為 query term<br/>以下載相關survey/review}}:::agent
  C[(在 Arxiv 進行 seed paper<br/>檢索/下載)]:::db
  D[Seed Papers]:::artifact
  E{{抽取 anchor/search terms}}:::agent
  F[(在 Arxiv 依組合後的 query<br/>檢索/下載)]:::db
  G[初步 Retrieved Paper]:::artifact
  H[/網路/]:::online
  I{{產生 Criteria}}:::agent
  J{{Title/Abstract 初篩}}:::agent
  J1[入選 paper]:::artifact
  K[[Snowball 擴展]]:::snowball
  L[Paper Pool（供後續 structuring）]:::artifact

  A --> B --> C --> D --> E --> F --> G
  D --> I
  H --> I
  I --> J
  G --> J
  J --> J1 --> K --> L
```

形狀圖例：
- `正方形`：實際存在的 artifact（含入選 paper）
- `{{ }}`：Agent 參與
- `/ /`：網路
- `[( )]`：paper 資料庫（如 Arxiv）
- `[[ ]]`：Snowball 擴展流程

## C) 補充說明（與全貌對齊）

1. **Paper Pool Construction / Retrieval**：以 topic 觸發檢索與篩選，建立可用於綜述的候選 paper pool。
2. **Paper Structuring（attribute & evidence extraction）**：對候選論文做屬性與證據抽取，形成可被引用的結構化資訊。
3. **Taxonomy & Outline**：在結構化資訊基礎上產出分類與章節結構。
4. **Survey Drafting（citation-aware synthesis）**：結合結構化證據撰寫內容，保留可追溯的引用關係。
5. **Verification & Refinement**：根據證據與引用關係進行一致性檢核與修訂。
6. **LaTeX Build & Debug → PDF**：完成排版、除錯並輸出 PDF。
7. **PDF**：最終成果輸出。
