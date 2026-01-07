# gh-address-comments

- 位置：`/Users/xjp/.codex/skills/gh-address-comments`

## 手把手步驟

1. 在 Codex 輸入 `/skills` 或輸入 `$`，確認本 skill 名稱出現。
2. 在對話中輸入 `$gh-address-comments`，並附上你的任務描述。
3. 依下方 `SKILL.md` 內容執行，若內含「When to Use / Core Capabilities / Examples」，請照該章節逐步操作。
4. 若 `SKILL.md` 要求額外資源（scripts / references / assets），依指示提供或執行。
5. 完成後核對輸出是否符合 `SKILL.md` 的限制與格式。

## SKILL.md（原文）

```markdown
---
name: gh-address-comments
description: Help address review/issue comments on the open GitHub PR for the current branch using gh CLI; verify gh auth first and prompt the user to authenticate if not logged in.
metadata:
  short-description: Address comments in a GitHub PR review
---

# PR Comment Handler

Guide to find the open PR for the current branch and address its comments with gh CLI. Run all `gh` commands with elevated network access.

Prereq: ensure `gh` is authenticated (for example, run `gh auth login` once), then run `gh auth status` with escalated permissions (include workflow/repo scopes) so `gh` commands succeed. If sandboxing blocks `gh auth status`, rerun it with `sandbox_permissions=require_escalated`.

## 1) Inspect comments needing attention
- Run scripts/fetch_comments.py which will print out all the comments and review threads on the PR

## 2) Ask the user for clarification
- Number all the review threads and comments and provide a short summary of what would be required to apply a fix for it
- Ask the user which numbered comments should be addressed

## 3) If user chooses comments
- Apply fixes for the selected comments

Notes:
- If gh hits auth/rate issues mid-run, prompt the user to re-authenticate with `gh auth login`, then retry.
```
