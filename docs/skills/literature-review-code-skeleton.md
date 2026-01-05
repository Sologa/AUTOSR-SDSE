# literature-review 程式碼骨架與函式簽名（可直接實作）

> 本文件提供可直接落地的程式碼骨架與函式簽名。僅為結構示意，不包含實作細節。

## 1) 新增模組：`src/pipelines/literature_review.py`

```python
"""Literature review stage orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from src.utils.env import load_env_file


@dataclass(frozen=True)
class LiteratureReviewInputs:
    """Resolved input artifacts for the literature review stage."""

    workspace_root: Path
    topic: str
    criteria_path: Optional[Path]
    harvest_path: Path
    review_path: Optional[Path]
    snowball_final_path: Optional[Path]


@dataclass(frozen=True)
class LiteratureReviewOptions:
    """Runtime options for the literature review stage."""

    citation_style: str = "apa"
    require_figures: bool = True
    allow_markdown_only: bool = False
    include_other_sources: bool = True


@dataclass(frozen=True)
class LiteratureReviewResult:
    """Output paths created by the stage."""

    output_dir: Path
    review_md: Path
    prisma_summary: Path
    search_results: Path
    citations_report: Path
    figures_dir: Optional[Path]
    review_pdf: Optional[Path]


class LiteratureReviewError(RuntimeError):
    """Raised when literature review stage fails preconditions."""


def run_literature_review(
    *,
    topic: str,
    workspace_root: Path = Path("workspaces"),
    options: Optional[LiteratureReviewOptions] = None,
) -> LiteratureReviewResult:
    """Run the literature-review stage and return output locations."""
    load_env_file()
    opts = options or LiteratureReviewOptions()
    inputs = resolve_inputs(topic=topic, workspace_root=workspace_root)
    output_dir = prepare_output_dir(inputs)

    base_items = select_base_items(inputs)
    prisma_summary = build_prisma_summary(inputs, output_dir=output_dir)
    search_results = build_search_results(inputs, output_dir=output_dir, include_other_sources=opts.include_other_sources)
    review_md = render_review_document(
        inputs,
        output_dir=output_dir,
        base_items=base_items,
        prisma_summary=prisma_summary,
        search_results=search_results,
    )
    citations_report = verify_citations(review_md, output_dir=output_dir)
    figures_dir = generate_figures(
        inputs,
        output_dir=output_dir,
        prisma_summary=prisma_summary,
        required=opts.require_figures,
    )
    review_pdf = generate_pdf(
        review_md,
        output_dir=output_dir,
        citation_style=opts.citation_style,
        allow_markdown_only=opts.allow_markdown_only,
    )

    return LiteratureReviewResult(
        output_dir=output_dir,
        review_md=review_md,
        prisma_summary=prisma_summary,
        search_results=search_results,
        citations_report=citations_report,
        figures_dir=figures_dir,
        review_pdf=review_pdf,
    )


# ---- helpers (signatures only) ----


def resolve_inputs(*, topic: str, workspace_root: Path) -> LiteratureReviewInputs:
    """Resolve workspace input paths and validate required artifacts."""
    raise NotImplementedError


def prepare_output_dir(inputs: LiteratureReviewInputs) -> Path:
    """Create literature_review output directory under workspace."""
    raise NotImplementedError


def select_base_items(inputs: LiteratureReviewInputs) -> List[Dict[str, Any]]:
    """Select included papers from snowball final or review results."""
    raise NotImplementedError


def build_prisma_summary(inputs: LiteratureReviewInputs, *, output_dir: Path) -> Path:
    """Aggregate pipeline counts and write prisma_summary.json."""
    raise NotImplementedError


def build_search_results(
    inputs: LiteratureReviewInputs,
    *,
    output_dir: Path,
    include_other_sources: bool,
) -> Path:
    """Format harvest outputs into search_results.md."""
    raise NotImplementedError


def render_review_document(
    inputs: LiteratureReviewInputs,
    *,
    output_dir: Path,
    base_items: Sequence[Dict[str, Any]],
    prisma_summary: Path,
    search_results: Path,
) -> Path:
    """Render review.md based on template and resolved metadata."""
    raise NotImplementedError


def verify_citations(review_md: Path, *, output_dir: Path) -> Path:
    """Run DOI verification and output citations_report.json."""
    raise NotImplementedError


def generate_figures(
    inputs: LiteratureReviewInputs,
    *,
    output_dir: Path,
    prisma_summary: Path,
    required: bool,
) -> Optional[Path]:
    """Generate PRISMA/flow figures and return figures directory."""
    raise NotImplementedError


def generate_pdf(
    review_md: Path,
    *,
    output_dir: Path,
    citation_style: str,
    allow_markdown_only: bool,
) -> Optional[Path]:
    """Generate review.pdf if dependencies are available."""
    raise NotImplementedError
```

## 2) 新增 CLI：`scripts/literature_review.py`

```python
#!/usr/bin/env python
"""CLI wrapper for literature-review stage."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.pipelines.literature_review import (
    LiteratureReviewOptions,
    run_literature_review,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path("workspaces"))
    parser.add_argument("--citation-style", default="apa")
    parser.add_argument("--require-figures", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--allow-markdown-only", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--include-other-sources", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    options = LiteratureReviewOptions(
        citation_style=args.citation_style,
        require_figures=args.require_figures,
        allow_markdown_only=args.allow_markdown_only,
        include_other_sources=args.include_other_sources,
    )
    run_literature_review(topic=args.topic, workspace_root=args.workspace_root, options=options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## 3) topic_pipeline 串接（變更示意）

> 以下僅示意，不直接修改檔案。

```python
# scripts/topic_pipeline.py
# ... add subcommand
literature = add_subparser("literature-review", help="（可選）產出文獻回顧報告")
# ... parse options

# in main():
if args.command == "literature-review":
    result = run_literature_review(
        topic=args.topic,
        workspace_root=workspace_root,
        options=LiteratureReviewOptions(
            citation_style=args.citation_style,
            require_figures=args.require_figures,
            allow_markdown_only=args.allow_markdown_only,
            include_other_sources=True,
        ),
    )
    print(result)
    return 0

# in run pipeline path:
if args.with_literature_review:
    run_literature_review(topic=args.topic, workspace_root=workspace_root)
```

## 4) 資源檔案位置（建議）

```
resources/literature_review/
  review_template.md
  citation_styles.md
  database_strategies.md
```

## 5) 測試骨架（最小化）

```python
# test/integration_live/test_literature_review_stage.py

def test_literature_review_outputs(tmp_path):
    # 使用既有 workspace fixture
    # 只驗證輸出檔案存在，不 mock
    ...
```

