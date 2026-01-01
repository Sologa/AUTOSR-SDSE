# Criteria Prompt 對齊與預設模型（web）

## 目的
- 統一 criteria 產生流程中「OR 條件」的表達方式，避免 prompt 自相矛盾。
- 更新 web search 的預設模型為 `gpt-5-search-api`，formatter 預設為 `gpt-5.2`。

## 介面 / 參數
- 入口：`python scripts/topic_pipeline.py criteria --topic "<topic>" --mode web`
- 主要參數：
  - `--search-model`：web search 模型（預設 `gpt-5.2-chat-latest`）
  - `--formatter-model`：格式化模型（預設 `gpt-5.2`）
- `--recency-hint`：時間範圍提示（預設 `過去3年`，僅供背景參考，不會轉成 criteria 條款）
  - `web_search` 工具：當 `--search-model=gpt-5-search-api` 時，會使用 `web_search_2025_08_26` 版本工具。
  - formatter prompt 不再包含時間範圍描述，避免 LLM 產出時間條款。

## 使用範例
```bash
source sdse-uv/.venv/bin/activate
python scripts/topic_pipeline.py criteria --topic "Discrete Audio Tokens: More Than a Survey!" --mode web --force
```

## 測試要點
- 產生 `workspaces/<topic_slug>/criteria/criteria.json` 與 `web_search_notes.txt`。
- 檢查 `structured_payload.inclusion_criteria` 是否維持 `required + any_of` 結構。
- 確認 any_of 群組語意為 OR（任一群組任一選項即可）。
- 若規則屬於系統設定（例如 exclude_title），允許 source 為 `internal` 或空白，且不應出現在 sources 清單。
- criteria 內不應包含時間/日期條款；時間範圍由程式以 metadata `published` 進行 discard。
- 確認 sources 是否為 https 且數量符合需求（若不符合需人工檢查與重跑）。
- 確認來源頁面具備明確年月日（YYYY-MM-DD）；僅有年份或年月者視為不合格來源。
- 檢查每條 criteria 的 source 是否與該條件一致；若無法找到一致來源，應使用 internal。
- 若設定了 cutoff 日期，會自動驗證來源頁面的日期（無法抽取日期或晚於 cutoff 會觸發重跑；超過嘗試次數會報錯）。

## 已知限制
- 仍仰賴 web search 回傳來源的穩定性與可存取性，可能出現來源不足或日期不符的情況。
- prompt 可降低錯誤，但不做硬性驗證；如需強制規則，需額外加入後處理檢查。
- criteria 的時間條款會在後處理中自動移除，以避免 LLM 以時間作為判斷依據。
