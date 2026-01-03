# Docker MCP Toolkit 在 VS Code Codex Extension 中的使用報告

## 1. 研究範圍與結論摘要
- 目標：釐清 Docker MCP Toolkit 如何在 VS Code 的 Codex Extension 中使用，並給出可操作的設定流程。
- 核心結論：Docker MCP Toolkit 透過「MCP Gateway」提供 MCP 入口；Codex Extension 依 OpenAI 官方文件使用 `~/.codex/config.toml` 管理 MCP 伺服器。將 Docker MCP Gateway 以 `command = "docker"`、`args = ["mcp", "gateway", "run"]` 的方式加入 Codex 的 MCP 設定，即可讓 Codex Extension 以 stdio 方式連到 Docker MCP Toolkit。（推論，依據 Docker 提供的 stdio 範例與 Codex 支援 stdio MCP 的事實）
- 重要區分：VS Code 自身的 MCP（通常搭配 GitHub Copilot Agent Mode）使用 `.vscode/mcp.json`；Codex Extension 使用 `~/.codex/config.toml`。兩者是不同設定來源，不能互相取代。

## 2. 事實檢查流程與外部來源
- 使用者提供內容：需求為「研究 Docker MCP Toolkit 在 VS Code Codex Extension 中的使用方式，並輸出報告到 `docs/mcp/`」。
- 外部查核渠道（官方/一手資料）：Docker Docs、OpenAI Codex 官方文件、VS Code 官方文件、Microsoft Learn、ModelContextProtocol.io。
- Context7：查得 MCP 規格文件（Model Context Protocol 2025-11-25 版）內容用於交叉驗證。
- Kit MCP：嘗試搜尋 `mcp` 套件後未定位到與 Docker MCP Toolkit 直接相關的套件文件（未找到可用庫）。

## 3. MCP 與傳輸方式（背景）
- MCP（Model Context Protocol）是一個開放協定，用於讓 LLM 應用以一致方式連結外部資料與工具。
- Codex 官方文件指出 MCP 可在 Codex CLI 與 IDE Extension 中使用，並支援 stdio 與 streamable HTTP 兩種伺服器型態；設定集中在 `~/.codex/config.toml`。

## 4. Docker MCP Toolkit 重點
### 4.1 啟用與 Gateway
- Docker Desktop 的「Settings > Beta features」提供 **Docker MCP Toolkit** 啟用開關。
- Docker MCP Toolkit 透過 `docker mcp gateway run` 啟動 MCP Gateway；也可使用 `docker mcp client connect <client>` 連接部分已整合的客戶端。
- 對於未被列出的客戶端，Docker 文件提供 stdio 設定範例，執行命令同樣是 `docker mcp gateway run`。

### 4.2 VS Code（Copilot Agent Mode）範例
- Docker 文件提供 VS Code 範例：在 `.vscode/mcp.json` 設定 stdio，或以 `docker mcp client connect vscode` 自動建立設定。
- Microsoft Learn 與 VS Code 文件顯示：VS Code 可在 `.vscode/mcp.json` 中配置 MCP 伺服器，並透過 Command Palette 使用 `MCP: List Servers` 等指令管理。

## 5. Codex Extension 的 MCP 設定方式
- OpenAI 文件明確指出：Codex CLI 與 IDE Extension 共用同一份 `~/.codex/config.toml`。
- VS Code 版 Codex Extension 可從設定齒輪進入 **MCP settings**，直接開啟 `config.toml`。
- MCP 設定以 `[mcp_servers.<name>]` 區塊定義，包含 `command`、`args`、`env`、`cwd` 等欄位。

## 6. 建議操作流程（Docker MCP Toolkit + VS Code Codex Extension）
1. 在 Docker Desktop 啟用 **Docker MCP Toolkit**。
2. 確認 Docker MCP Gateway 可用：
   - 可在終端機執行 `docker mcp gateway run`（手動啟動），或由 Codex 以 stdio 方式啟動。
3. 在 `~/.codex/config.toml` 新增 MCP 設定（推論：將 Docker 的 stdio Gateway 直接交給 Codex 管理）：
   ```toml
   [mcp_servers.docker_mcp]
   command = "docker"
   args = ["mcp", "gateway", "run"]
   ```
4. 重新載入 Codex Extension（或重新開啟 VS Code）。
5. 驗證方式：
   - Docker 文件提供 Codex CLI 驗證方式：`codex mcp list` 應列出 MCP_DOCKER（此命令顯示 command 也是 `docker mcp gateway run`）。
   - 依 OpenAI 文件「CLI 與 IDE 共用設定」可推論：CLI 成功通常代表 Extension 亦讀到相同 MCP 設定。（推論）

## 7. 常見誤區與限制
- **誤區**：把 `.vscode/mcp.json` 當作 Codex Extension 的設定。Codex Extension 依 OpenAI 文件只讀 `~/.codex/config.toml`。
- **限制**：Docker MCP Toolkit 位於 Docker Desktop Beta features，行為可能變動。
- **缺口**：目前未找到「Docker MCP Toolkit + Codex Extension」的官方一對一範例；以上流程為由 Docker Gateway 標準輸出與 Codex MCP 設定推導出的可行做法（已標註推論）。

## 8. 資料來源（官方）
- Docker Docs: MCP Toolkit / Get started / VS Code client example
  - https://docs.docker.com/ai/mcp/get-started/
  - https://docs.docker.com/ai/mcp/toolkit/
- OpenAI Codex Docs: MCP 設定與 IDE Extension
  - https://developers.openai.com/codex/mcp
- VS Code Docs: MCP servers（Copilot Chat）
  - https://code.visualstudio.com/docs/copilot/chat/mcp-servers
- Microsoft Learn: 在 VS Code 連線 MCP（mcp.json / MCP: List Servers）
  - https://learn.microsoft.com/en-us/azure/app-service/configure-authentication-mcp-server-vscode#connect-from-visual-studio-code
- Model Context Protocol 官方網站
  - https://modelcontextprotocol.io/
