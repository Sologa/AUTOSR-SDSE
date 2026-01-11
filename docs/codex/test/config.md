# Codex CLI Configuration for Smoke Tests

為了讓 `codex exec` 只能在 repo 內環境運行、並保持 network 連線受控，請在每次啟動前：

1. 進入 repo root（含 `.codex/config.toml`）。
2. 設定 `CODEX_HOME`：

```bash
export CODEX_HOME=$PWD/.codex
```

3. `.codex/config.toml` 範例如下，會鎖定 sandbox 只允許 workspace 內寫入、關閉 shell 命令網路，並關閉 `web_search_request`（Codex web search tool 會因為 feature 關閉而不可用）：

```toml
model = "gpt-5.1-codex-mini"
model_reasoning_effort = "medium"
preferred_auth_method = 'chatgpt'

[features]
rmcp_client = true
web_search_request = false

[sandbox_workspace_write]
network_access = false

[projects]
[projects.'/Users/xjp/Desktop/Survey-with-LLMs/Survey-for-survey-review-with-LLMs/AUTOSR-SDSE']
trust_level = 'trusted'
```

4. 需要調整 approval/automation (例如 `--full-auto`) 時，請透過 `docs/codex/test/run_*` 的 `--codex-extra-arg` 參數在 codex exec 之前插入 flag，執行後結果與 manifest 會記錄實際命令。`web_search` 工具預設被關閉；若某次要允許，可加上 `--allow-web-search`。

5. 維持此配置可避免改動個人 `~/.codex/config.toml`，也讓測試過程可重現。
