#!/usr/bin/env python
"""Topic CLI pipeline runner.

This CLI stitches together the repository's building blocks into a single,
repeatable workflow driven by a topic string.

Usage (run all major stages):
    source sdse-uv/.venv/bin/activate
    python scripts/topic_pipeline.py run --topic "speech language model"

You can also run stages individually:
    python scripts/topic_pipeline.py seed --topic "..."
    python scripts/topic_pipeline.py filter-seed --topic "..."
    python scripts/topic_pipeline.py keywords --topic "..."
    python scripts/topic_pipeline.py harvest --topic "..."
    python scripts/topic_pipeline.py criteria --topic "..." --mode pdf+web
    python scripts/topic_pipeline.py review --topic "..."
    python scripts/topic_pipeline.py snowball --topic "..."
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.pipelines.topic_pipeline import (
    extract_keywords_from_seed_pdfs,
    filter_seed_papers_with_llm,
    generate_structured_criteria,
    harvest_arxiv_metadata,
    harvest_other_sources,
    resolve_workspace,
    run_latte_review,
    run_snowball_asreview,
    seed_surveys_from_arxiv,
)


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--topic",
        help="主題字串（會被用來建立 workspace）",
        default=argparse.SUPPRESS,
    )
    common.add_argument(
        "--workspace-root",
        type=Path,
        default=argparse.SUPPRESS,
        help="workspace 根目錄（預設 workspaces/）",
    )

    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_subparser(name: str, **kwargs: object) -> argparse.ArgumentParser:
        return subparsers.add_parser(name, parents=[common], **kwargs)

    seed = add_subparser("seed", help="搜尋並下載 seed surveys (arXiv)")
    seed.add_argument("--max-results", type=_positive_int, default=25)
    seed.add_argument("--download-top-k", type=int, default=5)
    seed.add_argument("--scope", default="all", choices=["all", "ti", "abs"])
    seed.add_argument("--boolean-operator", default="AND", choices=["AND", "OR"])
    seed.add_argument("--no-cache", action="store_true", help="忽略已存在的 seed query cache")
    seed.add_argument("--anchor", action="append", default=None, help="額外 anchor term（可重複）")
    seed.add_argument("--survey-term", action="append", default=None, help="自訂 survey modifier（可重複）")
    seed.add_argument(
        "--anchor-mode",
        default="phrase",
        choices=["phrase", "token_and"],
        help="anchor 組合方式：phrase=完整片語；token_and=同一 anchor 內 token 以 AND 結合",
    )
    seed.add_argument(
        "--arxiv-raw-query",
        default=None,
        help="直接指定 arXiv search_query（會忽略 anchors/survey_terms/scope/boolean_operator）",
    )
    seed.add_argument(
        "--cutoff-by-similar-title",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="若偵測到與 topic 標題高度相似的 survey，則排除該篇並只使用更早的 surveys",
    )
    seed.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.8,
        help="判定「標題高度相似」的相似度門檻（0~1）",
    )

    keywords = add_subparser("keywords", help="從 seed PDFs 抽取 anchor/search terms")
    keywords.add_argument("--pdf-dir", type=Path, default=None, help="PDF 來源目錄（預設 seed downloads/arxiv）")
    keywords.add_argument("--max-pdfs", type=_positive_int, default=3)
    keywords.add_argument("--provider", default="openai")
    keywords.add_argument("--model", default="gpt-5")
    keywords.add_argument("--temperature", type=float, default=0.2)
    keywords.add_argument("--max-queries", type=_positive_int, default=50)
    keywords.add_argument("--include-ethics", action="store_true", help="允許 ethics 類術語")
    keywords.add_argument("--seed-anchor", action="append", default=None, help="傳入 ExtractParams.seed_anchors")
    keywords.add_argument("--reasoning-effort", default="medium")
    keywords.add_argument("--max-output-tokens", type=int, default=128000)
    keywords.add_argument("--force", action="store_true", help="覆寫 keywords.json")

    harvest = add_subparser("harvest", help="用 keywords 做 arXiv metadata harvest")
    harvest.add_argument("--keywords-path", type=Path, default=None, help="keywords.json 路徑（預設 workspace/keywords/keywords.json）")
    harvest.add_argument("--max-terms-per-category", type=_positive_int, default=3)
    harvest.add_argument("--top-k-per-query", type=_positive_int, default=100)
    harvest.add_argument("--scope", default="all", choices=["all", "ti", "abs"])
    harvest.add_argument("--boolean-operator", default="OR", choices=["AND", "OR"])
    harvest.add_argument("--no-require-accessible-pdf", action="store_true", help="不檢查 PDF HEAD 可用性")
    harvest.add_argument("--start-date", default=None, help="YYYY 或 YYYY-MM-DD")
    harvest.add_argument("--end-date", default=None, help="YYYY 或 YYYY-MM-DD")
    harvest.add_argument("--force", action="store_true", help="覆寫 arxiv_metadata.json")

    other = add_subparser("harvest-other", help="（選用）抓 Semantic Scholar / DBLP records")
    other.add_argument("--keywords-path", type=Path, default=None)
    other.add_argument("--max-terms-per-category", type=_positive_int, default=3)
    other.add_argument("--semantic-limit", type=_positive_int, default=100)
    other.add_argument("--dblp-per-term-limit", type=_positive_int, default=50)
    other.add_argument("--request-pause", type=float, default=0.3)
    other.add_argument("--no-semantic-scholar", action="store_true")
    other.add_argument("--no-dblp", action="store_true")
    other.add_argument("--force", action="store_true")

    criteria = add_subparser("criteria", help="（選用）產生 structured criteria JSON")
    criteria.add_argument("--recency-hint", default="過去3年")
    criteria.add_argument("--mode", default="web", choices=["web", "pdf+web"])
    criteria.add_argument("--pdf-dir", type=Path, default=None)
    criteria.add_argument("--max-pdfs", type=_positive_int, default=5)
    criteria.add_argument("--search-model", default="gpt-4.1")
    criteria.add_argument("--formatter-model", default="gpt-5")
    criteria.add_argument("--pdf-model", default="gpt-4.1")
    criteria.add_argument("--force", action="store_true")

    review = add_subparser("review", help="（選用）跑 LatteReview Title/Abstract 初篩")
    review.add_argument("--metadata", type=Path, default=None, help="arXiv metadata JSON（預設 workspace/harvest/arxiv_metadata.json）")
    review.add_argument("--criteria", type=Path, default=None, help="criteria.json（預設 workspace/criteria/criteria.json）")
    review.add_argument("--output", type=Path, default=None, help="輸出檔案（預設 workspace/review/latte_review_results.json）")
    review.add_argument("--top-k", type=int, default=None)
    review.add_argument("--skip-titles-containing", default="survey")
    review.add_argument("--junior-nano-model", default="gpt-5-nano")
    review.add_argument("--junior-mini-model", default="gpt-4.1-mini")
    review.add_argument("--senior-model", default="gpt-5-mini")
    review.add_argument("--senior-reasoning-effort", default="medium")

    snowball = add_subparser("snowball", help="（選用）LatteReview → ASReview + snowballing")
    snowball.add_argument("--review-results", type=Path, default=None)
    snowball.add_argument("--metadata", type=Path, default=None)
    snowball.add_argument("--output-dir", type=Path, default=None)
    snowball.add_argument("--email", default=None, help="OpenAlex 查詢用 email")
    snowball.add_argument("--keep-label", action="append", default=["include"])
    snowball.add_argument("--min-date", default=None)
    snowball.add_argument("--max-date", default=None)
    snowball.add_argument("--skip-forward", action="store_true")
    snowball.add_argument("--skip-backward", action="store_true")

    run = add_subparser("run", help="一鍵串接：seed → keywords → harvest（可加上 criteria/review/snowball）")
    run.add_argument("--with-criteria", action="store_true")
    run.add_argument("--criteria-mode", default="web", choices=["web", "pdf+web"])
    run.add_argument("--with-review", action="store_true")
    run.add_argument("--with-snowball", action="store_true")

    run.add_argument("--seed-max-results", type=_positive_int, default=25)
    run.add_argument("--seed-download-top-k", type=int, default=5)
    run.add_argument("--seed-scope", default="all", choices=["all", "ti", "abs"])
    run.add_argument("--seed-boolean-operator", default="AND", choices=["AND", "OR"])
    run.add_argument("--seed-anchor-mode", default="phrase", choices=["phrase", "token_and"])
    run.add_argument("--seed-arxiv-raw-query", default=None)
    run.add_argument(
        "--seed-cutoff-by-similar-title",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="seed 階段：若偵測到與 topic 標題高度相似的 survey，則排除該篇並只使用更早的 surveys",
    )
    run.add_argument(
        "--seed-similarity-threshold",
        type=float,
        default=0.8,
        help="seed 階段：相似度門檻（0~1）",
    )

    run.add_argument("--max-pdfs", type=_positive_int, default=3)
    run.add_argument("--extract-model", default="gpt-5")

    run.add_argument("--max-terms-per-category", type=_positive_int, default=3)
    run.add_argument("--top-k-per-query", type=_positive_int, default=100)
    run.add_argument("--harvest-scope", default="all", choices=["all", "ti", "abs"])
    run.add_argument("--harvest-boolean-operator", default="OR", choices=["AND", "OR"])
    run.add_argument("--start-date", default=None)
    run.add_argument("--end-date", default=None)
    run.add_argument("--no-require-accessible-pdf", action="store_true")

    run.add_argument("--recency-hint", default="過去3年")
    run.add_argument("--force", action="store_true", help="覆寫主要輸出（keywords/arxiv/criteria）")

    filter_seed = add_subparser("filter-seed", help="（可選）LLM 審核 seed papers（title+abstract yes/no）")
    filter_seed.add_argument("--provider", default="openai")
    filter_seed.add_argument("--model", default="gpt-5-mini")
    filter_seed.add_argument("--temperature", type=float, default=0.2)
    filter_seed.add_argument("--max-output-tokens", type=_positive_int, default=400)
    filter_seed.add_argument("--reasoning-effort", default="low")
    filter_seed.add_argument("--include-keyword", action="append", default=None)
    filter_seed.add_argument("--force", action="store_true", help="覆寫 LLM 篩選輸出")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "topic"):
        parser.error("--topic 為必填參數（可放在 subcommand 前或後）")
    workspace_root = getattr(args, "workspace_root", Path("workspaces"))
    ws = resolve_workspace(topic=args.topic, workspace_root=workspace_root)

    if args.command == "seed":
        result = seed_surveys_from_arxiv(
            ws,
            anchor_terms=args.anchor,
            survey_terms=args.survey_term,
            max_results=args.max_results,
            download_top_k=args.download_top_k,
            scope=args.scope,
            boolean_operator=args.boolean_operator,
            reuse_cached_queries=not args.no_cache,
            cutoff_by_similar_title=args.cutoff_by_similar_title,
            similarity_threshold=args.similarity_threshold,
            anchor_mode=args.anchor_mode,
            arxiv_raw_query=args.arxiv_raw_query,
        )
        print(result)
        return 0

    if args.command == "keywords":
        result = extract_keywords_from_seed_pdfs(
            ws,
            pdf_dir=args.pdf_dir,
            max_pdfs=args.max_pdfs,
            provider=args.provider,
            model=args.model,
            temperature=args.temperature,
            max_queries=args.max_queries,
            include_ethics=args.include_ethics,
            seed_anchors=args.seed_anchor,
            reasoning_effort=args.reasoning_effort,
            max_output_tokens=args.max_output_tokens,
            force=args.force,
        )
        print(result)
        return 0

    if args.command == "filter-seed":
        result = filter_seed_papers_with_llm(
            ws,
            provider=args.provider,
            model=args.model,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            reasoning_effort=args.reasoning_effort,
            include_keywords=args.include_keyword,
            force=args.force,
        )
        print(result)
        return 0

    if args.command == "harvest":
        result = harvest_arxiv_metadata(
            ws,
            keywords_path=args.keywords_path,
            max_terms_per_category=args.max_terms_per_category,
            top_k_per_query=args.top_k_per_query,
            scope=args.scope,
            boolean_operator=args.boolean_operator,
            require_accessible_pdf=not args.no_require_accessible_pdf,
            start_date=args.start_date,
            end_date=args.end_date,
            force=args.force,
        )
        print(result)
        return 0

    if args.command == "harvest-other":
        result = harvest_other_sources(
            ws,
            keywords_path=args.keywords_path,
            max_terms_per_category=args.max_terms_per_category,
            semantic_limit=args.semantic_limit,
            dblp_per_term_limit=args.dblp_per_term_limit,
            request_pause=args.request_pause,
            include_semantic_scholar=not args.no_semantic_scholar,
            include_dblp=not args.no_dblp,
            force=args.force,
        )
        print(result)
        return 0

    if args.command == "criteria":
        result = generate_structured_criteria(
            ws,
            recency_hint=args.recency_hint,
            mode=args.mode,
            pdf_dir=args.pdf_dir,
            max_pdfs=args.max_pdfs,
            search_model=args.search_model,
            formatter_model=args.formatter_model,
            pdf_model=args.pdf_model,
            force=args.force,
        )
        print(result)
        return 0

    if args.command == "review":
        result = run_latte_review(
            ws,
            arxiv_metadata_path=args.metadata,
            criteria_path=args.criteria,
            output_path=args.output,
            top_k=args.top_k,
            skip_titles_containing=args.skip_titles_containing,
            junior_nano_model=args.junior_nano_model,
            junior_mini_model=args.junior_mini_model,
            senior_model=args.senior_model,
            senior_reasoning_effort=args.senior_reasoning_effort,
        )
        print(result)
        return 0

    if args.command == "snowball":
        result = run_snowball_asreview(
            ws,
            review_results_path=args.review_results,
            metadata_path=args.metadata,
            output_dir=args.output_dir,
            email=args.email,
            keep_label=args.keep_label,
            min_date=args.min_date,
            max_date=args.max_date,
            skip_forward=args.skip_forward,
            skip_backward=args.skip_backward,
        )
        print(result)
        return 0

    if args.command == "run":
        seed_surveys_from_arxiv(
            ws,
            max_results=args.seed_max_results,
            download_top_k=args.seed_download_top_k,
            scope=args.seed_scope,
            boolean_operator=args.seed_boolean_operator,
            reuse_cached_queries=True,
            cutoff_by_similar_title=args.seed_cutoff_by_similar_title,
            similarity_threshold=args.seed_similarity_threshold,
            anchor_mode=args.seed_anchor_mode,
            arxiv_raw_query=args.seed_arxiv_raw_query,
        )
        extract_keywords_from_seed_pdfs(
            ws,
            max_pdfs=args.max_pdfs,
            model=args.extract_model,
            force=args.force,
        )
        harvest_arxiv_metadata(
            ws,
            max_terms_per_category=args.max_terms_per_category,
            top_k_per_query=args.top_k_per_query,
            scope=args.harvest_scope,
            boolean_operator=args.harvest_boolean_operator,
            require_accessible_pdf=not args.no_require_accessible_pdf,
            start_date=args.start_date,
            end_date=args.end_date,
            force=args.force,
        )
        if args.with_criteria:
            generate_structured_criteria(
                ws,
                recency_hint=args.recency_hint,
                mode=args.criteria_mode,
                force=args.force,
            )
        if args.with_review:
            run_latte_review(ws)
        if args.with_snowball:
            run_snowball_asreview(ws)
        print({"workspace": str(ws.root)})
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
