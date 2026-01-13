# Codex CLI Keywords Pipeline

## 目的

在 keywords 階段提供 `codex-cli` provider，使用 `codex exec` 產出與既有 `keywords.json` 相容的結果，同時保留 OpenAI path 原本行為。

## 介面 / 參數

入口：`scripts/topic_pipeline.py keywords`

關鍵參數：
- `--provider codex-cli`：啟用 codex CLI 分支
- `--model`：codex CLI 模型（openai 路徑仍固定 `gpt-5.2`）
- `--max-pdfs` / `--max-queries` / `--include-ethics` / `--seed-anchor`
- `--codex-bin`：Codex CLI 執行檔路徑
- `--codex-home`：`CODEX_HOME`（建議指向 repo-local `.codex`）
- `--codex-extra-arg`：附加在 `codex exec` 之前的旗標（可重複）
- `--codex-allow-web-search`：允許 web search（預設關閉）
- `--reasoning-effort`：會寫入 `model_reasoning_effort`（透過 `CODEX_HOME` 暫時覆寫）

## 使用範例

```bash
export CODEX_HOME=$PWD/.codex
export CODEX_BIN=/opt/homebrew/bin/codex

python scripts/topic_pipeline.py keywords \
  --topic "Discrete Audio Tokens: More Than a Survey!" \
  --provider codex-cli \
  --model gpt-5.2 \
  --reasoning-effort medium \
  --codex-home "$CODEX_HOME"
```

## 輸出

- `workspaces/<topic_slug>/keywords/keywords.json`
- `workspaces/<topic_slug>/keywords/keyword_cli_usage_<timestamp>.json`
- `workspaces/<topic_slug>/keywords/codex_text/*.txt`
- `workspaces/<topic_slug>/keywords/codex_raw_<timestamp>.txt`（若有）

## 測試要點

- `keywords.json` 可被 harvest 正常讀取（`anchor_terms`/`search_terms` 皆存在）
- `keyword_cli_usage_*.json` 記錄 `command`、`input_pdfs`、`text_paths`、`errors`
- `codex exec` 預設不使用 web search（除非 `--codex-allow-web-search`）

## 已知限制

- Codex CLI 不支援直接讀 PDF；需先以 `pdfplumber` 轉文字。
- codex-cli 路徑未執行 OpenAI path 的逐篇聚合與多重驗證流程。
- reasoning effort 透過 `CODEX_HOME/config.toml` 控制，需確保該目錄已登入/可用。
