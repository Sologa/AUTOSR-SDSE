# Codex CLI Review Pipeline

## 目的

在 review/snowball 階段提供 `codex-cli` provider：以 `codex exec`（JuniorNano/SeniorLead）搭配 Gemini CLI（JuniorMini）完成 Title/Abstract 初篩，輸出維持 `latte_review_results.json` 格式。

## 介面 / 參數

入口：
- `scripts/topic_pipeline.py review --provider codex-cli`
- `scripts/snowball_iterate.py --review-provider codex-cli`

關鍵參數：
- `--junior-nano-model` / `--junior-mini-model` / `--senior-model`
- `--junior-nano-reasoning-effort` / `--junior-mini-reasoning-effort` / `--senior-reasoning-effort`
- `--codex-bin` / `--codex-home` / `--codex-extra-arg` / `--codex-allow-web-search`
- `--codex-schema`（預設 `resources/schemas/review_response.schema.json`）
- `--gemini-allow-web-search`

預設模型（與 `docs/codex/test-review` 對齊）：
- JuniorNano: `gpt-5.1-codex-mini`
- JuniorMini: `gemini-2.5-pro`
- SeniorLead: `gpt-5.2`

## 使用範例

```bash
export CODEX_HOME=$PWD/.codex
export CODEX_BIN=/opt/homebrew/bin/codex

python scripts/topic_pipeline.py review \
  --topic "Discrete Audio Tokens: More Than a Survey!" \
  --provider codex-cli \
  --junior-nano-model gpt-5.1-codex-mini \
  --junior-mini-model gemini-2.5-pro \
  --senior-model gpt-5.2 \
  --junior-nano-reasoning-effort medium \
  --junior-mini-reasoning-effort medium \
  --senior-reasoning-effort medium \
  --codex-home "$CODEX_HOME"
```

Snowball review（單回合）：
```bash
python scripts/snowball_iterate.py \
  --topic "Discrete Audio Tokens: More Than a Survey!" \
  --mode loop \
  --start-round 1 \
  --max-rounds 1 \
  --review-provider codex-cli \
  --junior-nano-model gpt-5.1-codex-mini \
  --junior-mini-model gemini-2.5-pro \
  --senior-model gpt-5.2 \
  --junior-nano-reasoning-effort medium \
  --junior-mini-reasoning-effort medium \
  --senior-reasoning-effort medium \
  --codex-home "$CODEX_HOME"
```

## 輸出

- `workspaces/<topic_slug>/review/latte_review_results.json`
- `workspaces/<topic_slug>/snowball_rounds/round_XX/latte_review_results.json`

## 測試要點

- `latte_review_results.json` 具備 `final_verdict`，且格式可被 snowball 讀取。
- `codex exec` 預設不啟用 web search（除非 `--codex-allow-web-search`）。
- Gemini runner 會暫時調整 `.gemini/settings.json`，結束後應還原。

## 已知限制

- Gemini CLI 不支援 reasoning effort；此參數僅記錄，不會生效。
- Codex reasoning effort 透過 `CODEX_HOME/config.toml` 控制，需確保該目錄已登入。
