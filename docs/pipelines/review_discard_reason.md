# Review Discard Reason

## 目的
- 讓 review 結果可追溯排除原因，避免 `discard_reason` 全空。

## 行為
- `final_verdict` 為 `exclude ...` 時：
  - `discard_reason` 會填入該 `final_verdict` 字串。
- `final_verdict` 為 `maybe ...` 時：
  - `discard_reason` 會標記為 `review_needs_followup`。
- `final_verdict` 為 `include ...` 時：
  - `discard_reason` 為 `null`。
- 既有的 cutoff/discard 條目仍使用原本的 `discard_reason`。

## 產出
- `workspaces/<topic>/review/latte_review_results.json`

## 測試要點
- 檢查 review 結果中至少部分 `discard_reason` 非空。
- `discard` 條目仍保留原 discard 規則字串。
