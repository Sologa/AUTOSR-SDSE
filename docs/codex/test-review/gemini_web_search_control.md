# Gemini CLI 單次指令的 Web Search 開關方式（文件查核）

> 規範：禁止使用任何 API key；禁止將 CLI 測試納入 CI/CD；僅允許手動執行。

> 本文件依 Gemini CLI 官方文件與官方 repo 查核整理，僅涵蓋「單次指令（headless）如何控制 Web Search」。

## 結論（先看這裡）

- Gemini CLI 的 Web Search 以內建工具 `google_web_search` 提供，工具名稱在官方文件與官方 repo 中一致。  
  來源：
  - https://google-gemini.github.io/gemini-cli/docs/tools/web-search.html
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/tools/tool-names.ts
- Headless 單次指令（`gemini -p/--prompt`）的官方參數表未提供「開/關 Web Search」旗標。  
  來源：https://google-gemini.github.io/gemini-cli/docs/cli/headless.html
- Gemini CLI 支援專案層設定檔 `./.gemini/settings.json`，會覆蓋使用者層設定，適合用於 repo 內固定政策。  
  來源：https://google-gemini.github.io/gemini-cli/docs/get-started/configuration.html
- Web Search 的「可用性」由工具清單控制：
  - `tools.core`：以 allowlist 方式限制可用工具
  - `tools.exclude`：以 blocklist 方式排除工具
  來源：https://google-gemini.github.io/gemini-cli/docs/get-started/configuration.html
- 工具是否被實際呼叫由模型決定；使用者只能透過工具可用性限制範圍。  
  來源：https://google-gemini.github.io/gemini-cli/docs/tools/

> 文件未揭露單次指令層級的「強制開/關 Web Search」旗標；若另有未記載旗標，官方文件未提供依據，無法確定。

---

## 單次指令（headless）基本用法

- 官方 headless 入口：`gemini --prompt` / `gemini -p`

```bash
gemini -p "請整理這份說明文件"
```

來源：https://google-gemini.github.io/gemini-cli/docs/cli/headless.html

---

## 控制 Web Search 的方式（設定檔）

Gemini CLI 的工具可用性由設定檔中的 `tools.core` 與 `tools.exclude` 控制。

### 1) 禁用 Web Search（blocklist）

在專案 `.gemini/settings.json` 加入：

```json
{
  "tools": {
    "exclude": ["google_web_search"]
  }
}
```

- `tools.exclude` 會排除 `google_web_search`。  
  來源：https://google-gemini.github.io/gemini-cli/docs/get-started/configuration.html
- 官方 repo 顯示排除名單會被套用到工具可用清單。  
  來源：https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/tools/tool-registry.ts

### 2) 僅允許 Web Search（allowlist）

在專案 `.gemini/settings.json` 加入：

```json
{
  "tools": {
    "core": ["google_web_search"]
  }
}
```

- `tools.core` 為 allowlist；未列入的內建工具不會註冊。  
  來源：https://google-gemini.github.io/gemini-cli/docs/get-started/configuration.html
- 官方 repo 顯示註冊工具時會檢查 `tools.core` 清單。  
  來源：https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/config/config.ts

> 若需要其他工具（例如 `read_file`、`web_fetch`），必須一併列入 `tools.core`。

---

## 本 repo 的使用規則（docs/codex/test-review）

- 預設政策：runner 會在執行時套用 `./.gemini/settings.json`，排除 `google_web_search`，避免 Gemini CLI 出網。
- 允許 Web Search：使用 `--gemini-allow-web-search` 讓 runner 放行，並在結束後回復原本設定。
- 若要長期固定 policy，可自行維護 `./.gemini/settings.json`；runner 仍會依旗標在執行期間覆寫並於結束後回復。

---

## 如何確認 Web Search 是否可用

- 在 CLI 中使用 `/tools` 查看可用工具清單。  
  來源：https://google-gemini.github.io/gemini-cli/docs/cli/commands.html

---

## 注意事項（工具被呼叫的條件）

- 工具是否被實際呼叫由模型判斷；使用者只能透過 allowlist/blocklist 影響可用工具集合。  
  來源：https://google-gemini.github.io/gemini-cli/docs/tools/

---

## API 層對照（Gemini API）

- Gemini API 的 Web Search 工具名稱為 `google_search`（API 的工具名稱與 CLI 的 `google_web_search` 不同）。  
  來源：https://ai.google.dev/gemini-api/docs/google-search

---

## 來源清單（完整）

- Gemini CLI Headless： https://google-gemini.github.io/gemini-cli/docs/cli/headless.html
- Gemini CLI Tools： https://google-gemini.github.io/gemini-cli/docs/tools/
- Web Search Tool： https://google-gemini.github.io/gemini-cli/docs/tools/web-search.html
- Gemini CLI 設定檔： https://google-gemini.github.io/gemini-cli/docs/get-started/configuration.html
- CLI 指令列表： https://google-gemini.github.io/gemini-cli/docs/cli/commands.html
- Gemini API Google Search： https://ai.google.dev/gemini-api/docs/google-search
- 官方 repo：
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/tools/tool-names.ts
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/config/config.ts
  - https://raw.githubusercontent.com/google-gemini/gemini-cli/main/packages/core/src/tools/tool-registry.ts
