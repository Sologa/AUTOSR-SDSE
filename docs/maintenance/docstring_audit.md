# Docstring Coverage Update

## 目的
- 補齊專案內可編輯模組與腳本的缺漏 docstring，提升可讀性與 AI/人類協作可解析度。
- 保留既有行為不變，僅新增說明文字。

## 介面 / 參數
本次補齊 docstring 的範圍：
- `src/pipelines/topic_pipeline.py`
- `scripts/topic_pipeline.py`
- `scripts/snowball_iterate.py`
- `scripts/update_snowball_registry.py`
- `src/utils/llm.py`
- `src/utils/paper_downloaders.py`
- `src/utils/paper_workflows.py`
- `src/utils/keyword_extractor.py`
- `src/utils/openai_web_search.py`
- `src/utils/structured_web_search_pipeline.py`
- `unified_research_pipeline.py`
- `test/tools/download_speechlm_pdfs.py`
- `test/tools/parse_snowball_screening_results.py`

## 使用範例
以下範例可用來重新檢查缺漏 docstring 的項目（僅示意，可依需求調整掃描範圍）：

```bash
python - <<'PY'
import ast
from pathlib import Path

root = Path('.')
paths = list((root / 'src').rglob('*.py')) + list((root / 'scripts').rglob('*.py'))
paths += [root / 'unified_research_pipeline.py']

missing = []
for path in paths:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    if not ast.get_docstring(tree):
        missing.append((path, 'module'))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node) is None:
            missing.append((path, f'function:{node.name}'))
        if isinstance(node, ast.ClassDef):
            if ast.get_docstring(node) is None:
                missing.append((path, f'class:{node.name}'))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(child) is None:
                    missing.append((path, f'method:{node.name}.{child.name}'))

for item in missing:
    print(item)
PY
```

## 測試要點
- 本次為 docstring 補齊，未新增或修改邏輯；可視需求執行 `ruff check .` 或相關 unit tests 作驗證。

## 未涵蓋/尚待處理
- `resources/` 與 `target_papers/` 下的腳本尚未補齊。
- `test/` 下的測試腳本尚未補齊。

## 已知限制
- 目前僅針對核心管線與工具程式補齊，完整覆蓋需另行擴展掃描範圍。
