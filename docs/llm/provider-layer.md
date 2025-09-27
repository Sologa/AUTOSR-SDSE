# LLM Provider Layer

## 目的
- 抽象化多家 LLM 服務，統一同步（sync）、批次（batch）、非同步（async）與 PDF 解析流程。
- 追蹤每次呼叫的 token 使用量與費用，支援自訂價目表。
- 在模組載入時自動讀取倉庫根目錄的 `.env`，避免遺漏 API key。

## 介面
- `BaseLLMProvider`：封裝重試、費用計算、使用量紀錄。所有 provider 需繼承此類別。
- `OpenAIProvider`：實作 Responses API、PDF 上傳流程，支援最新 GPT-5 系列。
  - 針對 OpenAI 官方標記的推理模型（`gpt-5*`、`o1*`、`o3*`、`o4*`）會自動忽略 `temperature` 參數，以避免呼叫 API 時收到 400。
  - 若沿用舊有 `max_tokens` 參數，會自動轉成 Responses API 的 `max_output_tokens`。
- `AnthropicProvider` / `GeminiProvider`：原型骨架，未配置客戶端時會拋出 `ProviderNotConfiguredError`。
- `LLMService`：入口 façade，負責路由至指定 provider，並提供統一的 usage summary。
- `LLMUsageTracker` / `ModelPriceRegistry`：分別負責使用量累積與價目表管理。
  - 內建 `DEFAULT_PRICING` 會跟隨官方文件同步更新，預設涵蓋：`gpt-5` / `gpt-5-mini` / `gpt-5-nano`、`gpt-4o` / `gpt-4o-mini`、`gpt-4.1` / `gpt-4.1-mini` / `gpt-4.1-nano`、`o1` / `o1-mini` / `o1-pro`、`o3` / `o3-mini` / `o3-pro` / `o3-deep-research`、`o4-mini`（OpenAI），`claude-opus-4-1` / `claude-sonnet-4` / `claude-3-5-haiku`（Anthropic），`gemini-2.5-pro` / `gemini-2.5-flash` / `gemini-2.5-flash-lite`（Google Gemini）。價格來源分別為 [`openai.com/api/pricing`](https://openai.com/api/pricing) 與 [OpenAI Model 細節頁](https://platform.openai.com/docs/models)、[Anthropic Docs](https://docs.anthropic.com/claude/docs/models-overview)、[Gemini Pricing](https://ai.google.dev/pricing) 2025-09 版面。
  - `ModelPricing` 的定價單位為「每百萬 tokens (USD/1M tok)」，成本會以六位小數四捨五入。
- `read_pdf_batch`：讓多份 PDF 以批次方式處理並套用 `batch_discount`，節省費用。

## 使用範例
```python
from pathlib import Path

from src.utils.llm import LLMService

service = LLMService()

# 同步訊息
prompt = "請濃縮段落成三點 bullet"
sync_result = service.chat("openai", "gpt-5-nano", prompt)
print(sync_result.content)
print(sync_result.usage.cost)  # 已四捨五入到 6 位小數

# 批次訊息（自動套用 0.5 discount）
batch_prompts = [[{"role": "user", "content": f"說明研究領域 {i} 的三項挑戰"}] for i in range(10)]
batch_results = service.chat_batch("openai", "gpt-5-nano", batch_prompts)

# 非同步訊息
async def run_async_batch() -> list[str]:
    async_results = await service.chat_async("openai", "gpt-5-nano", batch_prompts, concurrency=3)
    return [item.content for item in async_results]

# PDF 單筆與批次（PDF 需存在且小於 10MB）
pdf_single = service.read_pdf(
    "openai",
    "gpt-5-nano",
    Path("resources/datasets/arxiv_papers/sample.pdf"),
    instructions="請整理重點摘要",
)

pdf_batch = service.read_pdf_batch(
    "openai",
    "gpt-5-nano",
    [
        Path("resources/datasets/arxiv_papers/doc1.pdf"),
        Path("resources/datasets/arxiv_papers/doc2.pdf"),
    ],
    instructions="請給我一句話摘要",
)
```

## 測試要點
- 單元測試：`python -m pytest test/unit/test_llm_usage.py`（需先 `source sdse-uv/.venv/bin/activate`）。
- 直播整合測試：`python -m pytest test/integration_live/test_openai_llm_provider_live.py`
  - Coverage：同步、批次、非同步 chat 各 10 筆，以及使用 `resources/datasets/arxiv_papers` 中真實 PDF 的 10 筆閱讀流程。
  - 測試將載入 `.env`，並需要 `OPENAI_API_KEY`；若缺少將標示為 skipped。
  - 成功執行後會在 `test_artifacts/llm/` 產生包含實際回應、token 統計與費用的 JSON 檔，可供驗證與後續分析。
- 所有測試預設在 OpenAI 上跑 10 筆資料（chat 與 PDF 皆然），並驗證 token 資訊與費用計算。

## 已知限制
- Anthropic / Gemini provider 尚未接上實際 API client，會主動提醒未完成配置。
- 批次折扣預設為 0.5（費用減半），若各家策略不同需在子類別覆寫。
- 測試流程假定 `sdse-uv` 虛擬環境可用；請勿在未啟用環境的情況下執行指令。

## 開發 / 擴充建議
- 模組匯入時會自動呼叫 `load_env_file()`，如需自訂路徑可直接使用 `src/utils/env.load_env_file()`。
- 若需新增模型，請透過 `ModelPriceRegistry.register()` 註冊「每百萬 tokens」的 input/output 費率。
- `LLMUsageTracker.summarize()` 適合在流程尾端統計跨 provider 的成本、token 使用量與呼叫次數。
- 要支援其他供應商時，繼承 `BaseLLMProvider` 並實作 `_chat_request/_chat_request_async/_pdf_request/_extract_usage/_extract_content`，再注入 `LLMService`。
