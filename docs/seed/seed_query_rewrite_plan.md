# Seed Query 改寫機制（cutoff-first）

## 目的
cutoff-first seed 流程中，**必定執行一次** topic → phrases 的改寫，產生 English-only 搜尋片語，作為後續 per-phrase arXiv 查詢的基礎。此流程 **不可迭代、不可重跑**。

## 行為概要（one-pass）
- 直接用 LLM 把 topic 改寫為 N 個 phrases（一次性）。
- phrases 必須是英文（ASCII printable + 至少 1 個英文字母）。
- phrases 中不得包含 survey/review/overview 及同義變體（case-insensitive blacklist 清理或 fail）。
- 若 `phrases_clean` 為空 → **直接 fail**（one-pass，不重跑）。

## 介面 / 參數
- `--seed-rewrite-n`：LLM 產生片語數量上限（default 5）
- `--seed-blacklist-mode {clean,fail}`：黑名單處理策略
- `--seed-rewrite-provider`：`openai` / `codex-cli`
- `--seed-rewrite-model`：LLM model
- `--seed-rewrite-reasoning-effort`：LLM reasoning effort
- `--seed-rewrite-codex-*`：Codex CLI 參數（選用）

## Prompt / 解析規則
- Prompt 檔案：`resources/LLM/prompts/seed/seed_query_rewrite.md`
- LLM 必須輸出 JSON：`{"phrases": ["...", "..."]}`
- Parser 只接受 JSON object + `phrases` array

## 輸出
- `seed/queries/seed_rewrite.json`（v2）
  - `schema_version`
  - `topic_input`
  - `provider` / `model`
  - `n_requested`
  - `phrases_raw`
  - `english_only`（包含 dropped phrases 與 reason）
  - `blacklist`（mode / patterns / hits）
  - `phrases_clean`
  - `errors`

## 已知限制
- 必須有有效的 `OPENAI_API_KEY`（或 Codex CLI 設定）。
- 若 LLM 輸出非 JSON 或 phrases 全被清除 → 直接 fail。
