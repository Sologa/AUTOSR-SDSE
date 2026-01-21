# Seed Rewrite Prompt 背景與架構（cutoff-first）

## 目的
提供 prompt 設計的背景，說明 cutoff-first seed 流程中 **one-shot JSON phrases** 的改寫要求與限制。

## 背景
- cutoff-first 流程會先找 cutoff paper；若未命中同名則視為無 cutoff，仍用 LLM 一次性改寫 topic → phrases。
- 不再存在 iterative scoring / retry / rerun。
- phrases 必須為英文（ASCII-only），且不得含 survey/review/overview 等概念。

## Prompt 要求（摘要）
1) **輸出 JSON**：`{"phrases": ["...", "..."]}`，不可有額外文字。
2) **英文限定**：ASCII printable + 至少 1 個英文字母。
3) **禁止 survey/review/overview 與同義**。
4) **只保留核心領域語意**，不可引入新概念。

## Parser 規則（強制）
- 只接受 JSON object + `phrases` array。
- `phrases_raw` 進行 blacklist 清理 + English-only 檢查。
- `phrases_clean` 為空 → 直接 fail（one-pass）。

## 相關檔案
- Prompt：`resources/LLM/prompts/seed/seed_query_rewrite.md`
- 實作：`src/pipelines/topic_pipeline.py`
- 規格：`docs/seed/AUTOSR_SDSE_seed_cutoff_first_spec.md`
