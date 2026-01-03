# Seed Topic Variants (Title-Safe)

## 目的
- 生成 seed 搜尋用的 topic 變體，但避免對「論文標題」做縮寫。

## 行為
- 一般情況：保留原字串、全小寫、Title Case、必要的單複數變化。
- **若 topic 看起來是論文標題**（含 `:`/`!`/`?` 或詞數較多，或包含 survey/review/overview 等字樣）：
  - **不產生 acronym**（避免 DATMTAS 類縮寫）。
  - 仍可產生去除標點的乾淨版本與「冒號前主詞片語」作為替代查詢。

## 使用範例
- `Discrete Audio Tokens: More Than a Survey!`
  - 會保留 `Discrete Audio Tokens`（冒號前主詞）
  - 不會生成 `DATMTAS`

## 測試要點
- seed 產出的 `download_results.json` 中 `anchors` 不應含 acronym。
