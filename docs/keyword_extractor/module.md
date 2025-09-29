# Keyword Extractor Module

Purpose
- Extract anchor terms, categorized search terms, and metadata-aligned reviewer context from one or more survey PDFs using the LLM provider layer.

Interface
- Python: `src/utils/keyword_extractor.py`
  - `extract_search_terms_from_surveys(pdf_paths, provider='openai', model='gpt-5-nano', params=ExtractParams(), service=None)` → dict
  - `ExtractParams(topic=None, max_queries=50, include_ethics=True, language='en', custom_categories=None, seed_anchors=None, anchor_variants=None, exclude_terms=None, prompt_path=None, aggregate_prompt_path=None, max_output_tokens=None, reasoning_effort=None, allow_additional_categories=True, min_terms_per_category=None)`
  - `build_generate_instructions(params, resolved_anchor_variants=None, metadata_block=None, reviewer_profile_block=None)` and `build_aggregate_instructions(partials, max_queries=50, topic=None, anchor_variants=None, metadata_block=None, reviewer_profile_block=None, allow_additional_categories=True, category_target=None)` helpers.
  - Output validation raises `ValueError` when returned titles/abstracts diverge from the canonical metadata (prevents drift before LatteReview ingestion).

Usage Example
```python
from pathlib import Path
from src.utils.keyword_extractor import ExtractParams, extract_search_terms_from_surveys

pdfs = [
    Path('resources/datasets/arxiv_papers/Systematic_Review(系統性綜述__SR)/sample1.pdf'),
    Path('resources/datasets/arxiv_papers/Systematic_Review(系統性綜述__SR)/sample2.pdf'),
]
params = ExtractParams(topic='dialogue summarization', max_queries=20, include_ethics=False)
result = extract_search_terms_from_surveys(pdfs, provider='openai', model='gpt-5-nano', params=params)
print(result['anchor_terms'])
```

- Provide at least one PDF path; the helper raises `ValueError` on empty input so upstream callers can short-circuit before touching the provider.
- PDF filenames must encode the arXiv identifier (e.g. `2504.08528_something.pdf`) so that the extractor can recover metadata. Missing IDs now raise immediately instead of deferring to the LLM.
- Set `max_output_tokens` or the function argument of the same name when working with large PDFs so the Responses API has enough budget; `reasoning_effort` can be passed (low/medium/high) for models that support OpenAI’s reasoning payload.

Metadata Integration
- `_collect_paper_metadata` infers the arXiv ID from each file name and calls `fetch_arxiv_metadata`, reusing a single requests session and caching results in-process.
- The prompt includes a `<<paper_metadata_block>>` section containing canonical `source_id`, `title`, `abstract`, `year`, `url`, and the file path. The LLM is instructed (and enforced via validation) to copy titles/abstracts verbatim.
- Final JSON includes:
  - `papers`: ordered list containing the canonical metadata plus `detected_keywords`.
  - `reviewer_profile`: the reviewer configuration surfaced once for convenience when instantiating TitleAbstract reviewers.
- `_validate_output_against_metadata` ensures `papers` align with the metadata, titles/abstracts remain exact copies, and every reviewer field is present and non-empty.
- Reviewer payloads resolve via `src/utils/latte_review_configs.py`, which loads `data/latte_review/title_abstract_reviewer_profiles.json` (aliases supported for topic matching with a default fallback).
- A deterministic fallback merges the per-PDF payloads when the aggregation LLM returns malformed or non-compliant JSON, so LatteReview rows remain available even under provider hiccups.

Prompt Behaviour
- `build_generate_instructions` renders a runtime overrides block (topic, language, category set, seeds, exclusions). When no custom taxonomy is supplied it now asks the model to infer 4–6 descriptive snake_case categories (datasets, benchmarks, training_methods, evaluation_metrics, …) and reminds it—via the coverage note—to keep at least `min_terms_per_category` (or a derived default) terms in each inferred bucket, folding singleton categories back into the closest existing group.
- Additional prompt guidance nudges the LLM to emit concise (1–3 word) noun phrases and to avoid underscores/sentence-length outputs; `_sanitize_search_term_buckets` enforces these constraints during post-processing.
- Providing `anchor_variants` locks the anchors to those exact variants; the prompt explicitly warns the model not to introduce additional anchor terms.
- When only `topic` is supplied, the helper auto-derives anchor variants (topic, singular/plural swaps, speech↔spoken forms, acronym) and instructs the model to stick to them.
- JSON scaffolding in the prompt remains neutral (`<category>` placeholders) so custom taxonomies can be inferred without further string replacements. The schema now exposes `papers[*].source_id/title/abstract/year/url` alongside a single `reviewer_profile` block for downstream use.
- Aggregation instructions echo the same coverage goal and honour `allow_additional_categories`, preserving any new categories surfaced during the per-PDF step while still capping the total term budget.
- The parser strips ``` fences irrespective of casing (e.g. ```JSON) before decoding, reducing fragility when models change their formatting hints.

Testing
- Live tests: `pytest -q -k keyword_extractor_live` (requires `OPENAI_API_KEY`) and uses `gpt-5-nano` to keep costs low.
- Live tests now assert that returned metadata aligns exactly (titles/abstracts copied verbatim) and that no deprecated `latte_inputs` block is present.
- Unit tests: `pytest -q test/unit/test_keyword_extractor_prompts.py` exercises instruction rendering, input validation, fence stripping, and usage logging safeguards.

Usage Logging
- If omitted, logs default to `test_artifacts/llm/keyword_extractor_usage_<timestamp>.json`; override `usage_log_path` to control location.
- Logs now write even when parsing fails, so you can inspect token usage for malformed model outputs; the helper ensures the parent directory exists.

Known Limits
- Output remains model‑generated JSON, but a fallback aggregator now guarantees metadata-aligned results even when the consolidation response is malformed. Validation still raises `ValueError` if the final payload cannot be realigned with the canonical metadata. Anchor terms are normalised to the derived topic variants to keep them consistent. Always validate keys before downstream use.
- Requires outbound HTTPS to `https://export.arxiv.org/api/query` for metadata enrichment; transient failures surface as `ValueError` so callers can retry or queue offline.

Prompt Storage
- Primary prompts in this repo: `resources/LLM/prompts/keyword_extractor/`.
- Mirrored for SurveyX: `SurveyX/resources/LLM/prompts/keyword_extractor/` (external path).
