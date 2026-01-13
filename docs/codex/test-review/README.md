# Codex/Gemini CLI Review Smoke Test

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

本資料夾只用於手動測試，不修改正式 pipeline。

## 先決條件
- 已啟用 `sdse-uv` 虛擬環境
- `.env` 已設定必要金鑰（腳本會在啟動時讀取 `.env`）
- 本機可執行 `codex` 與 `gemini` CLI
- 已用 ChatGPT 訂閱帳號登入 Codex CLI（使用 `codex login`，或 `codex login --device-auth`）
- `CODEX_HOME` 已指向 repo 下的 `./.codex`：（`export CODEX_HOME=$PWD/.codex`）
- Codex CLI 中的 web search 工具預設也已在 repo 內 `./.codex/config.toml` 關閉（`features.web_search_request=false`）；如需特別允許某次 run 可搭配 `--allow-web-search` 參數來覆寫。
- Gemini CLI 的 Web Search 由專案層 `./.gemini/settings.json` 控制，headless 模式沒有單次指令旗標；runner 會在執行時自動套用/回復該檔（預設排除 `google_web_search`），如需允許請加 `--gemini-allow-web-search`，細節見 `docs/codex/test-review/gemini_web_search_control.md`。
- 若需一次性調整 sandbox/network/approval 設定，請參考 `docs/codex/test-review/config.md`，裡面示範 `./.codex/config.toml` 的範例與建議做法。

## 建議執行順序
1) 單 reviewer（Codex）
2) 單 reviewer（Gemini）
3) 完整 workflow（JuniorNano + JuniorMini → SeniorLead）

### 1) Codex 單 reviewer
```bash
source sdse-uv/.venv/bin/activate
codex login
# Export CODEX_HOME before running so CLI stores credentials locally:
export CODEX_HOME=$PWD/.codex
# 若 venv 內的 codex 不是 OpenAI CLI，可指定：
# python docs/codex/test-review/run_codex_single.py --run-id 20260110_090000 --codex-bin /opt/homebrew/bin/codex
python docs/codex/test-review/run_codex_single.py --run-id 20260110_090000
```

你可以用 `--codex-extra-arg` 來直接把 flag 接到 `codex exec`，例如 `--codex-extra-arg --full-auto`（也可重複多次）會在 `codex exec` 與 prompt 之間插入指定 flag，用以控制 approval、sandbox、network 等行為。

### 2) Gemini 單 reviewer
```bash
source sdse-uv/.venv/bin/activate
python docs/codex/test-review/run_gemini_single.py --run-id 20260110_090000 --model gemini-2.5-pro
```

允許 Gemini Web Search：
```bash
python docs/codex/test-review/run_gemini_single.py --run-id 20260110_090000 --model gemini-2.5-pro --gemini-allow-web-search
```

### 3) 完整 workflow
```bash
source sdse-uv/.venv/bin/activate
python docs/codex/test-review/run_full_workflow.py --run-id 20260110_090000
```

允許 Gemini Web Search（僅 Gemini）：
```bash
python docs/codex/test-review/run_full_workflow.py --run-id 20260110_090000 --gemini-allow-web-search
```

## 輸出檔案
所有輸出會寫入：`docs/codex/test-review/outputs/<run_id>/`
- `codex_single.json`
- `gemini_single.json`
- `full_workflow.json`
- `run_manifest.json`
- `example_output.json` 為示意用範例

## 驗證輸出
```bash
python docs/codex/test-review/validate_review_output.py docs/codex/test-review/outputs/<run_id>/codex_single.json
python docs/codex/test-review/validate_review_output.py docs/codex/test-review/outputs/<run_id>/gemini_single.json
python docs/codex/test-review/validate_review_output.py docs/codex/test-review/outputs/<run_id>/full_workflow.json
python docs/codex/test-review/validate_run_manifest.py docs/codex/test-review/outputs/<run_id>/run_manifest.json
```

## 來源與 criteria 規則
- 來源固定：`workspaces/discrete_audio_tokens_more_than_a_survey/harvest/arxiv_metadata.json`（取前 5 筆）
- criteria 讀取順序：workspace 內 `criteria/criteria.json` → 預設文案
