# Keyword Extractor Pipeline Notes

_Last updated: 2025-09-29_

This file captures the context, code changes, and open questions around the
`src/utils/keyword_extractor.py` pipeline, so future work can pick up without
re-reading the entire git history.

## 1. Background

- The pipeline powers survey-paper keyword extraction via two LLM calls:
  1. Per-PDF extraction (`LLMService.read_pdf`).
  2. Aggregation over the partial JSONs (`LLMService.chat`).
- Artifacts (LLM usage + final JSON) live under `test_artifacts/` so we can
  inspect responses after live runs.

## 2. Key Changes to Date

### Earlier updates (other sessions, before 2025-09-29)

- Introduced `allow_additional_categories` to `ExtractParams` and threaded it
  across prompt builders and aggregation so the model can invent new buckets.
- Replaced the topic-specific Latte reviewer profile with a neutral default
  JSON and refreshed the example prompts/documentation (both English & Chinese).
- Integration tests were updated to point at
  `test_artifacts/live_downloads/spoken_language_model_assets/` and to exercise
  custom `max_output_tokens`/`reasoning_effort` settings.

### Recent work (2025-09-29 session)

- Made category guidance fully dynamic when callers do not supply
  `custom_categories`:
  - `_resolved_categories` now returns an empty list and the prompt tells the
    model to “infer 4–6 descriptive snake_case categories (benchmarks,
    training_methods, datasets, evaluation_metrics, …)”.
  - Added `_DEFAULT_DYNAMIC_CATEGORY_COUNT` (6) as the heuristic budget and
    recalculated per-category targets via `_default_category_terms_target`.
- Added richer instructions:
  - Generation prompt warns that buckets with fewer than three terms should be
    merged into another category.
  - Aggregation prompt echoes the same rule and reminds the model to keep the
    overall term count ≤ `max_queries`.
  - Chinese documentation and the English module doc were updated so both
    teammates and future prompts stay aligned with the new behaviour.
- Post-processing enhancements in `_enrich_search_terms_from_papers`:
  - Collect detected keywords and per-PDF `search_terms` to repopulate any
    missing items before reviewer seeds are merged.
  - New `_merge_duplicate_categories` helper canonicalises labels (e.g.
    “architecture” vs “architectures”) to prevent one-off buckets.
- Added `_sanitize_search_term_buckets` to convert underscores to spaces, drop
  sentence-length phrases, enforce 1–3 word noun phrases, and deduplicate search
  terms case-insensitively. Prompt templates and docs now instruct the LLM to
  avoid underscores and overly long phrases.
- Raised the live test budget (`max_queries=40`) to ensure the integration test
  no longer throttles the model to three terms per category.
- Adjusted unit tests (`test/unit/test_keyword_extractor_prompts.py`) to assert
  for the new category instructions, including the “< 3 terms ⇒ merge” rule.
- Removed the LatteReview dependency from keyword extraction: prompts no longer
  request `reviewer_profile`, the pipeline drops Latte-specific post-processing,
  and `latte_review_configs.py` plus the reviewer JSON have been deleted in
  favour of caller-supplied reviewer metadata.
- Usage logs now default to `test_artifacts/keyword_extractor_live/` instead of
  the shared `test_artifacts/llm/` directory so live artifacts stay grouped with
  the extractor outputs.

## 3. Outstanding / Follow-Up Tasks

- **Run tests locally**: `pytest` was not available in the shell environment, so
  the updated unit test suite (`test/unit/test_keyword_extractor_prompts.py`) and
  live tests should be re-run via the project’s preferred command (e.g.
  `uv run pytest ...`).
- **Regenerate live artifacts**: Existing JSONs under
  `test_artifacts/keyword_extractor_live/` were produced with the old
  `max_queries=3` budget. Re-run the integration test (or invoke the pipeline
  manually) to validate the richer category behaviour.
- **Monitor category outputs**: After regenerating, confirm the model is
  emitting multiple items per inferred category and folding redundant buckets as
  instructed. Adjust `_DEFAULT_DYNAMIC_CATEGORY_COUNT` or messaging if further
  tuning is needed.

## 4. Usage Tips

- Pass `custom_categories` when you need a fixed taxonomy; otherwise let the LLM
  infer categories—it now has ample prompt guidance to do so.
- Increase `max_queries` (or `ExtractParams.max_queries`) for topics that require
  broader vocabularies; the per-category minimum scales with this budget.
- Inspect `test_artifacts/keyword_extractor_live/keyword_extractor_usage_*.json` to understand token
  consumption after each run.

## 5. Quick Reference (Updated Files)

- `src/utils/keyword_extractor.py`: dynamic category logic, post-processing,
  prompt builders, aggregation safeguards.
- `resources/LLM/prompts/keyword_extractor/generate_search_terms.md` and
  `aggregate_terms.md`: new instructions for category inference and quotas.
- `docs/keyword_extractor/關鍵詞抽取流程與提示詞.md`: Chinese translation of the new
  prompts and workflow.
- `docs/keyword_extractor/module.md`: English module overview refreshed with the
  current behaviour.
- `test/unit/test_keyword_extractor_prompts.py`: guard rails for prompt content.
- `test/integration_live/test_keyword_extractor_live.py`: higher `max_queries`
  for live validation.

Keep this document updated whenever substantial behavioural changes land, so the
next debugging session can pick up instantly.
