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
    backfill_arxiv_metadata_from_dblp_titles,
    extract_keywords_from_seed_pdfs,
    filter_seed_papers_with_llm,
    generate_structured_criteria,
    harvest_arxiv_metadata,
    harvest_other_sources,
    resolve_workspace,
    run_cli_review,
    run_latte_review,
    run_snowball_asreview,
    run_snowball_iterative,
    seed_surveys_from_arxiv,
    seed_surveys_from_arxiv_cutoff_first,
)


def _positive_int(value: str) -> int:
    """Argparse helper that enforces a positive integer."""
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser with all subcommands and shared flags."""
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

    seed = add_subparser("seed", help="搜尋 seed surveys metadata (arXiv)")
    seed.add_argument(
        "--seed-mode",
        default="legacy",
        choices=["legacy", "cutoff-first"],
        help="seed 流程模式（legacy=舊版；cutoff-first=one-pass）",
    )
    seed.add_argument("--max-results", type=_positive_int, default=25, help="legacy 模式：arXiv 查詢上限")
    seed.add_argument(
        "--download-top-k",
        type=int,
        default=5,
        help="legacy 模式：seed 選取上限（不下載）",
    )
    seed.add_argument("--cutoff-arxiv-id", default=None, help="cutoff-first：指定 cutoff arXiv id")
    seed.add_argument("--cutoff-title-override", default=None, help="cutoff-first：指定 cutoff title")
    seed.add_argument(
        "--cutoff-date-field",
        default="published",
        choices=["published", "updated", "submitted"],
        help="cutoff-first：cutoff 日期欄位（submitted 會映射到 published）",
    )
    seed.add_argument("--scope", default="all", choices=["all", "ti", "abs"], help="legacy 模式：查詢欄位")
    seed.add_argument(
        "--boolean-operator",
        default="AND",
        choices=["AND", "OR"],
        help="legacy 模式：anchor 與 survey modifiers 的布林運算子",
    )
    seed.add_argument(
        "--anchor-operator",
        default="OR",
        choices=["AND", "OR"],
        help="legacy 模式：anchor terms 彼此的布林運算子（預設 OR；僅影響 anchors 組合）",
    )
    seed.add_argument("--no-cache", action="store_true", help="legacy 模式：忽略已存在的 seed query cache")
    seed.add_argument(
        "--anchor-mode",
        default="phrase",
        choices=["phrase", "token_and", "token_or", "core_phrase", "core_token_or"],
        help=(
            "legacy 模式：anchor 組合方式：phrase=完整片語；token_and=同一 anchor 內 token 以 AND 結合；"
            "token_or=同一 anchor 內 token 以 OR 結合；"
            "core_phrase/core_token_or=僅使用主題核心片語"
        ),
    )
    seed.add_argument(
        "--cutoff-by-similar-title",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="legacy 模式：若偵測到與 topic 標題高度相似的 survey，則排除該篇並只使用更早的 surveys",
    )
    seed.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.8,
        help="legacy 模式：判定「標題高度相似」的相似度門檻（0~1）",
    )
    seed.add_argument(
        "--seed-rewrite",
        action="store_true",
        help="legacy 模式：seed 無有效候選或 cutoff 全移除時改寫 query 後重試",
    )
    seed.add_argument("--seed-rewrite-max-attempts", type=_positive_int, default=2)
    seed.add_argument("--seed-rewrite-provider", default="openai", choices=["openai", "codex-cli"])
    seed.add_argument("--seed-rewrite-model", default="gpt-5.2")
    seed.add_argument("--seed-rewrite-reasoning-effort", default="low")
    seed.add_argument("--seed-rewrite-codex-bin", default=None, help="Codex CLI 執行檔路徑")
    seed.add_argument("--seed-rewrite-codex-home", type=Path, default=None, help="CODEX_HOME（repo-local .codex 建議）")
    seed.add_argument(
        "--seed-rewrite-codex-extra-arg",
        action="append",
        default=None,
        help="附加在 `codex exec` 之前的旗標（可重複）。",
    )
    seed.add_argument(
        "--seed-rewrite-codex-allow-web-search",
        action="store_true",
        help="允許 Codex web search（預設關閉）",
    )
    seed.add_argument("--seed-rewrite-preview", action="store_true", help="只輸出改寫結果，不重跑 seed")
    seed.add_argument("--seed-rewrite-n", type=_positive_int, default=5, help="cutoff-first：改寫片語數量上限")
    seed.add_argument(
        "--seed-blacklist-mode",
        default="clean",
        choices=["clean", "fail"],
        help="cutoff-first：黑名單處理模式（clean=清理；fail=直接失敗）",
    )
    seed.add_argument(
        "--seed-arxiv-max-results-per-query",
        type=_positive_int,
        default=50,
        help="cutoff-first：每個 phrase 查詢的 arXiv 最大回傳數",
    )
    seed.add_argument(
        "--seed-max-merged-results",
        type=_positive_int,
        default=200,
        help="cutoff-first：合併後最大保留筆數",
    )

    keywords = add_subparser("keywords", help="從 seed PDFs 抽取 anchor/search terms")
    keywords.add_argument("--pdf-dir", type=Path, default=None, help="PDF 來源目錄（預設 seed downloads/arxiv）")
    keywords.add_argument("--max-pdfs", type=_positive_int, default=3)
    keywords.add_argument("--provider", default="openai", choices=["openai", "codex-cli"])
    keywords.add_argument(
        "--model",
        default="gpt-5.2",
        help="openai 路徑固定 gpt-5.2；codex-cli 會使用此參數",
    )
    keywords.add_argument("--temperature", type=float, default=1.0, help="openai 路徑固定 1.0（忽略此參數）")
    keywords.add_argument("--max-queries", type=_positive_int, default=50)
    keywords.add_argument("--include-ethics", action="store_true", help="允許 ethics 類術語")
    keywords.add_argument("--seed-anchor", action="append", default=None, help="傳入 ExtractParams.seed_anchors")
    keywords.add_argument("--reasoning-effort", default="medium")
    keywords.add_argument("--max-output-tokens", type=int, default=128000)
    keywords.add_argument("--codex-bin", default=None, help="Codex CLI 執行檔路徑")
    keywords.add_argument("--codex-home", type=Path, default=None, help="CODEX_HOME（repo-local .codex 建議）")
    keywords.add_argument(
        "--codex-extra-arg",
        action="append",
        default=None,
        help="附加在 `codex exec` 之前的旗標（可重複）。",
    )
    keywords.add_argument(
        "--codex-allow-web-search",
        action="store_true",
        help="允許 Codex web search（預設關閉）",
    )
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
    other.add_argument(
        "--dblp-title-arxiv",
        action="store_true",
        help="用 DBLP title 回查 arXiv 並合併到 arxiv_metadata.json",
    )
    other.add_argument("--dblp-title-arxiv-max-results", type=_positive_int, default=10)
    other.add_argument("--force", action="store_true")

    criteria = add_subparser("criteria", help="（選用）產生 structured criteria JSON")
    criteria.add_argument("--recency-hint", default="過去3年")
    criteria.add_argument("--mode", default="web", choices=["web", "pdf+web"])
    criteria.add_argument("--provider", default="openai", choices=["openai", "codex-cli"])
    criteria.add_argument("--pdf-dir", type=Path, default=None)
    criteria.add_argument("--max-pdfs", type=_positive_int, default=5)
    criteria.add_argument("--search-model", default="gpt-5.2-chat-latest")
    criteria.add_argument("--formatter-model", default="gpt-5.2")
    criteria.add_argument("--pdf-model", default="gpt-4.1")
    criteria.add_argument("--search-reasoning-effort", default=None)
    criteria.add_argument("--formatter-reasoning-effort", default=None)
    criteria.add_argument("--pdf-reasoning-effort", default=None)
    criteria.add_argument("--codex-bin", default=None, help="Codex CLI 執行檔路徑")
    criteria.add_argument("--codex-home", type=Path, default=None, help="CODEX_HOME（repo-local .codex 建議）")
    criteria.add_argument(
        "--codex-extra-arg",
        action="append",
        default=None,
        help="附加在 `codex exec` 之前的旗標（可重複）。",
    )
    criteria.add_argument(
        "--codex-allow-web-search",
        action="store_true",
        help="允許 Codex web search（預設關閉）",
    )
    criteria.add_argument("--force", action="store_true")

    review = add_subparser("review", help="（選用）跑 Title/Abstract 初篩")
    review.add_argument("--metadata", type=Path, default=None, help="arXiv metadata JSON（預設 workspace/harvest/arxiv_metadata.json）")
    review.add_argument("--criteria", type=Path, default=None, help="criteria.json（預設 workspace/criteria/criteria.json）")
    review.add_argument("--output", type=Path, default=None, help="輸出檔案（預設 workspace/review/latte_review_results.json）")
    review.add_argument("--top-k", type=int, default=None)
    review.add_argument("--skip-titles-containing", default="***")
    review.add_argument("--provider", default="openai", choices=["openai", "codex-cli"])
    review.add_argument("--junior-nano-model", default=None)
    review.add_argument("--junior-mini-model", default=None)
    review.add_argument("--senior-model", default=None)
    review.add_argument("--junior-nano-reasoning-effort", default=None)
    review.add_argument("--junior-mini-reasoning-effort", default=None)
    review.add_argument("--senior-reasoning-effort", default="medium")
    review.add_argument("--codex-bin", default=None, help="Codex CLI 執行檔路徑")
    review.add_argument("--codex-home", type=Path, default=None, help="CODEX_HOME（repo-local .codex 建議）")
    review.add_argument(
        "--codex-extra-arg",
        action="append",
        default=None,
        help="附加在 `codex exec` 之前的旗標（可重複）。",
    )
    review.add_argument(
        "--codex-allow-web-search",
        action="store_true",
        help="允許 Codex web search（預設關閉）",
    )
    review.add_argument(
        "--gemini-allow-web-search",
        action="store_true",
        help="允許 Gemini web search（預設關閉）",
    )
    review.add_argument(
        "--codex-schema",
        type=Path,
        default=None,
        help="Codex review schema path（預設 resources/schemas/review_response.schema.json）",
    )

    snowball = add_subparser("snowball", help="（選用）LatteReview → ASReview + snowballing")
    snowball.add_argument("--review-results", type=Path, default=None)
    snowball.add_argument("--metadata", type=Path, default=None)
    snowball.add_argument("--output-dir", type=Path, default=None)
    snowball.add_argument("--round", type=int, default=1, help="snowball round index（從 1 開始）")
    snowball.add_argument("--registry", type=Path, default=None, help="review registry JSON 路徑")
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
    run.add_argument("--snowball-mode", default="loop", choices=["loop", "while"])
    run.add_argument("--snowball-max-rounds", type=_positive_int, default=1)
    run.add_argument("--snowball-start-round", type=_positive_int, default=1)
    run.add_argument("--snowball-stop-raw-threshold", type=int, default=None)
    run.add_argument("--snowball-stop-included-threshold", type=int, default=None)
    run.add_argument("--snowball-min-date", default=None)
    run.add_argument("--snowball-max-date", default=None)
    run.add_argument("--snowball-email", default=None)
    run.add_argument("--snowball-keep-label", action="append", default=["include"])
    run.add_argument("--snowball-skip-forward", action="store_true")
    run.add_argument("--snowball-skip-backward", action="store_true")
    run.add_argument("--snowball-review-top-k", type=int, default=None)
    run.add_argument("--snowball-skip-titles-containing", default="***")
    run.add_argument("--snowball-registry", type=Path, default=None)
    run.add_argument("--snowball-retain-registry", action="store_true")
    run.add_argument("--snowball-bootstrap-review", type=Path, default=None)
    run.add_argument("--snowball-force", action="store_true")

    run.add_argument(
        "--seed-mode",
        default="legacy",
        choices=["legacy", "cutoff-first"],
        help="seed 流程模式（legacy=舊版；cutoff-first=one-pass）",
    )
    run.add_argument("--seed-max-results", type=_positive_int, default=25, help="legacy 模式：arXiv 查詢上限")
    run.add_argument("--seed-download-top-k", type=int, default=5, help="legacy 模式：seed 選取上限（不下載）")
    run.add_argument("--seed-scope", default="all", choices=["all", "ti", "abs"], help="legacy 模式：查詢欄位")
    run.add_argument(
        "--seed-boolean-operator",
        default="AND",
        choices=["AND", "OR"],
        help="legacy 模式：anchor 與 survey modifiers 的布林運算子",
    )
    run.add_argument("--seed-anchor-operator", default="OR", choices=["AND", "OR"], help="legacy 模式")
    run.add_argument(
        "--seed-anchor-mode",
        default="phrase",
        choices=["phrase", "token_and", "token_or", "core_phrase", "core_token_or"],
        help="legacy 模式",
    )
    run.add_argument(
        "--seed-cutoff-by-similar-title",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="legacy 模式：若偵測到與 topic 標題高度相似的 survey，則排除該篇並只使用更早的 surveys",
    )
    run.add_argument(
        "--seed-similarity-threshold",
        type=float,
        default=0.8,
        help="legacy 模式：相似度門檻（0~1）",
    )
    run.add_argument("--seed-rewrite", action="store_true", help="legacy 模式：seed 無 PDF 時改寫 query 後重試")
    run.add_argument("--seed-rewrite-max-attempts", type=_positive_int, default=2)
    run.add_argument("--seed-rewrite-provider", default="openai", choices=["openai", "codex-cli"])
    run.add_argument("--seed-rewrite-model", default="gpt-5.2")
    run.add_argument("--seed-rewrite-reasoning-effort", default="low")
    run.add_argument("--seed-rewrite-codex-bin", default=None)
    run.add_argument("--seed-rewrite-codex-home", type=Path, default=None)
    run.add_argument("--seed-rewrite-codex-extra-arg", action="append", default=None)
    run.add_argument("--seed-rewrite-codex-allow-web-search", action="store_true")
    run.add_argument("--seed-rewrite-preview", action="store_true", help="只輸出改寫結果，不重跑 seed")
    run.add_argument("--seed-cutoff-arxiv-id", default=None, help="cutoff-first：指定 cutoff arXiv id")
    run.add_argument("--seed-cutoff-title-override", default=None, help="cutoff-first：指定 cutoff title")
    run.add_argument(
        "--seed-cutoff-date-field",
        default="published",
        choices=["published", "updated", "submitted"],
        help="cutoff-first：cutoff 日期欄位（submitted 會映射到 published）",
    )
    run.add_argument("--seed-rewrite-n", type=_positive_int, default=5, help="cutoff-first：改寫片語數量上限")
    run.add_argument(
        "--seed-blacklist-mode",
        default="clean",
        choices=["clean", "fail"],
        help="cutoff-first：黑名單處理模式（clean=清理；fail=直接失敗）",
    )
    run.add_argument(
        "--seed-arxiv-max-results-per-query",
        type=_positive_int,
        default=50,
        help="cutoff-first：每個 phrase 查詢的 arXiv 最大回傳數",
    )
    run.add_argument(
        "--seed-max-merged-results",
        type=_positive_int,
        default=200,
        help="cutoff-first：合併後最大保留筆數",
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
    run.add_argument("--criteria-provider", default="openai", choices=["openai", "codex-cli"])
    run.add_argument("--criteria-codex-bin", default=None)
    run.add_argument("--criteria-codex-home", type=Path, default=None)
    run.add_argument("--criteria-codex-extra-arg", action="append", default=None)
    run.add_argument("--criteria-codex-allow-web-search", action="store_true")
    run.add_argument("--force", action="store_true", help="覆寫主要輸出（keywords/arxiv/criteria）")

    filter_seed = add_subparser("filter-seed", help="（可選）LLM 審核 seed papers（title+abstract yes/no）")
    filter_seed.add_argument("--provider", default="openai")
    filter_seed.add_argument("--model", default="gpt-5-mini")
    filter_seed.add_argument("--temperature", type=float, default=0.2)
    filter_seed.add_argument("--max-output-tokens", type=_positive_int, default=400)
    filter_seed.add_argument("--reasoning-effort", default="low")
    filter_seed.add_argument("--include-keyword", action="append", default=None)
    filter_seed.add_argument("--codex-bin", default=None, help="Codex CLI 執行檔路徑")
    filter_seed.add_argument("--codex-home", type=Path, default=None, help="CODEX_HOME（repo-local .codex 建議）")
    filter_seed.add_argument(
        "--codex-extra-arg",
        action="append",
        default=None,
        help="附加在 `codex exec` 之前的旗標（可重複）。",
    )
    filter_seed.add_argument(
        "--codex-allow-web-search",
        action="store_true",
        help="允許 Codex web search（預設關閉）",
    )
    filter_seed.add_argument("--force", action="store_true", help="覆寫 LLM 篩選輸出")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for the topic pipeline runner."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "topic"):
        parser.error("--topic 為必填參數（可放在 subcommand 前或後）")
    workspace_root = getattr(args, "workspace_root", Path("workspaces"))
    ws = resolve_workspace(topic=args.topic, workspace_root=workspace_root)

    if args.command == "seed":
        if args.seed_mode == "cutoff-first":
            result = seed_surveys_from_arxiv_cutoff_first(
                ws,
                seed_rewrite_n=args.seed_rewrite_n,
                seed_blacklist_mode=args.seed_blacklist_mode,
                seed_arxiv_max_results_per_query=args.seed_arxiv_max_results_per_query,
                seed_max_merged_results=args.seed_max_merged_results,
                cutoff_arxiv_id=args.cutoff_arxiv_id,
                cutoff_title_override=args.cutoff_title_override,
                cutoff_date_field=args.cutoff_date_field,
                seed_rewrite_provider=args.seed_rewrite_provider,
                seed_rewrite_model=args.seed_rewrite_model,
                seed_rewrite_reasoning_effort=args.seed_rewrite_reasoning_effort,
                seed_rewrite_codex_bin=args.seed_rewrite_codex_bin,
                seed_rewrite_codex_extra_args=args.seed_rewrite_codex_extra_arg,
                seed_rewrite_codex_home=args.seed_rewrite_codex_home,
                seed_rewrite_codex_allow_web_search=args.seed_rewrite_codex_allow_web_search,
            )
        else:
            result = seed_surveys_from_arxiv(
                ws,
                max_results=args.max_results,
                download_top_k=args.download_top_k,
                scope=args.scope,
                boolean_operator=args.boolean_operator,
                anchor_operator=args.anchor_operator,
                reuse_cached_queries=not args.no_cache,
                cutoff_by_similar_title=True,
                similarity_threshold=args.similarity_threshold,
                anchor_mode=args.anchor_mode,
                seed_rewrite=args.seed_rewrite,
                seed_rewrite_max_attempts=args.seed_rewrite_max_attempts,
                seed_rewrite_provider=args.seed_rewrite_provider,
                seed_rewrite_model=args.seed_rewrite_model,
                seed_rewrite_reasoning_effort=args.seed_rewrite_reasoning_effort,
                seed_rewrite_codex_bin=args.seed_rewrite_codex_bin,
                seed_rewrite_codex_extra_args=args.seed_rewrite_codex_extra_arg,
                seed_rewrite_codex_home=args.seed_rewrite_codex_home,
                seed_rewrite_codex_allow_web_search=args.seed_rewrite_codex_allow_web_search,
                seed_rewrite_preview=args.seed_rewrite_preview,
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
            codex_bin=args.codex_bin,
            codex_extra_args=args.codex_extra_arg,
            codex_home=args.codex_home,
            codex_allow_web_search=args.codex_allow_web_search,
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
            codex_bin=args.codex_bin,
            codex_extra_args=args.codex_extra_arg,
            codex_home=args.codex_home,
            codex_allow_web_search=args.codex_allow_web_search,
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
        if args.dblp_title_arxiv:
            backfill_result = backfill_arxiv_metadata_from_dblp_titles(
                ws,
                max_results_per_title=args.dblp_title_arxiv_max_results,
                request_pause=args.request_pause,
                force=args.force,
            )
            result.update(backfill_result)
        print(result)
        return 0

    if args.command == "criteria":
        result = generate_structured_criteria(
            ws,
            recency_hint=args.recency_hint,
            mode=args.mode,
            provider=args.provider,
            pdf_dir=args.pdf_dir,
            max_pdfs=args.max_pdfs,
            search_model=args.search_model,
            formatter_model=args.formatter_model,
            pdf_model=args.pdf_model,
            search_reasoning_effort=args.search_reasoning_effort,
            formatter_reasoning_effort=args.formatter_reasoning_effort,
            pdf_reasoning_effort=args.pdf_reasoning_effort,
            codex_bin=args.codex_bin,
            codex_extra_args=args.codex_extra_arg,
            codex_home=args.codex_home,
            codex_allow_web_search=args.codex_allow_web_search,
            force=args.force,
        )
        print(result)
        return 0

    if args.command == "review":
        provider = args.provider.strip().lower()
        if provider == "codex-cli":
            junior_nano_model = args.junior_nano_model or "gpt-5.1-codex-mini"
            junior_mini_model = args.junior_mini_model or "gemini-2.5-pro"
            senior_model = args.senior_model or "gpt-5.2"
            result = run_cli_review(
                ws,
                arxiv_metadata_path=args.metadata,
                criteria_path=args.criteria,
                output_path=args.output,
                top_k=args.top_k,
                skip_titles_containing=args.skip_titles_containing,
                junior_nano_model=junior_nano_model,
                junior_mini_model=junior_mini_model,
                senior_model=senior_model,
                junior_nano_reasoning_effort=args.junior_nano_reasoning_effort,
                junior_mini_reasoning_effort=args.junior_mini_reasoning_effort,
                senior_reasoning_effort=args.senior_reasoning_effort,
                codex_bin=args.codex_bin,
                codex_home=args.codex_home,
                codex_extra_args=args.codex_extra_arg,
                codex_schema_path=args.codex_schema,
                allow_web_search=args.codex_allow_web_search,
                gemini_allow_web_search=args.gemini_allow_web_search,
            )
        else:
            junior_nano_model = args.junior_nano_model or "gpt-5-nano"
            junior_mini_model = args.junior_mini_model or "gpt-4.1-mini"
            senior_model = args.senior_model or "gpt-5-mini"
            result = run_latte_review(
                ws,
                arxiv_metadata_path=args.metadata,
                criteria_path=args.criteria,
                output_path=args.output,
                top_k=args.top_k,
                skip_titles_containing=args.skip_titles_containing,
                junior_nano_model=junior_nano_model,
                junior_mini_model=junior_mini_model,
                senior_model=senior_model,
                junior_nano_reasoning_effort=args.junior_nano_reasoning_effort,
                junior_mini_reasoning_effort=args.junior_mini_reasoning_effort,
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
            round_index=args.round,
            registry_path=args.registry,
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
        if args.seed_mode == "cutoff-first":
            seed_surveys_from_arxiv_cutoff_first(
                ws,
                seed_rewrite_n=args.seed_rewrite_n,
                seed_blacklist_mode=args.seed_blacklist_mode,
                seed_arxiv_max_results_per_query=args.seed_arxiv_max_results_per_query,
                seed_max_merged_results=args.seed_max_merged_results,
                cutoff_arxiv_id=args.seed_cutoff_arxiv_id,
                cutoff_title_override=args.seed_cutoff_title_override,
                cutoff_date_field=args.seed_cutoff_date_field,
                seed_rewrite_provider=args.seed_rewrite_provider,
                seed_rewrite_model=args.seed_rewrite_model,
                seed_rewrite_reasoning_effort=args.seed_rewrite_reasoning_effort,
                seed_rewrite_codex_bin=args.seed_rewrite_codex_bin,
                seed_rewrite_codex_extra_args=args.seed_rewrite_codex_extra_arg,
                seed_rewrite_codex_home=args.seed_rewrite_codex_home,
                seed_rewrite_codex_allow_web_search=args.seed_rewrite_codex_allow_web_search,
            )
        else:
            seed_surveys_from_arxiv(
                ws,
                max_results=args.seed_max_results,
                download_top_k=args.seed_download_top_k,
                scope=args.seed_scope,
                boolean_operator=args.seed_boolean_operator,
                anchor_operator=args.seed_anchor_operator,
                reuse_cached_queries=True,
                cutoff_by_similar_title=True,
                similarity_threshold=args.seed_similarity_threshold,
                anchor_mode=args.seed_anchor_mode,
                seed_rewrite=args.seed_rewrite,
                seed_rewrite_max_attempts=args.seed_rewrite_max_attempts,
                seed_rewrite_provider=args.seed_rewrite_provider,
                seed_rewrite_model=args.seed_rewrite_model,
                seed_rewrite_reasoning_effort=args.seed_rewrite_reasoning_effort,
                seed_rewrite_codex_bin=args.seed_rewrite_codex_bin,
                seed_rewrite_codex_extra_args=args.seed_rewrite_codex_extra_arg,
                seed_rewrite_codex_home=args.seed_rewrite_codex_home,
                seed_rewrite_codex_allow_web_search=args.seed_rewrite_codex_allow_web_search,
                seed_rewrite_preview=args.seed_rewrite_preview,
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
                provider=args.criteria_provider,
                codex_bin=args.criteria_codex_bin,
                codex_extra_args=args.criteria_codex_extra_arg,
                codex_home=args.criteria_codex_home,
                codex_allow_web_search=args.criteria_codex_allow_web_search,
                force=args.force,
            )
        if args.with_review:
            run_latte_review(ws)
        if args.with_snowball:
            if (
                not args.with_review
                and not ws.review_results_path.exists()
                and args.snowball_bootstrap_review is None
            ):
                raise FileNotFoundError(
                    "找不到 base review 結果，請先執行 --with-review 或提供 --snowball-bootstrap-review"
                )
            run_snowball_iterative(
                ws,
                mode=args.snowball_mode,
                max_rounds=args.snowball_max_rounds,
                start_round=args.snowball_start_round,
                stop_raw_threshold=args.snowball_stop_raw_threshold,
                stop_included_threshold=args.snowball_stop_included_threshold,
                min_date=args.snowball_min_date,
                max_date=args.snowball_max_date,
                email=args.snowball_email,
                keep_label=args.snowball_keep_label,
                skip_forward=args.snowball_skip_forward,
                skip_backward=args.snowball_skip_backward,
                review_top_k=args.snowball_review_top_k,
                skip_titles_containing=args.snowball_skip_titles_containing,
                registry_path=args.snowball_registry,
                retain_registry=args.snowball_retain_registry,
                bootstrap_review=args.snowball_bootstrap_review,
                force=args.snowball_force,
            )
        print({"workspace": str(ws.root)})
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
