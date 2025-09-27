# Keyword Extractor Module

Purpose
- Extract anchor terms, categorized search terms, synonyms, excluded terms, and boolean queries from one or more survey PDFs using the LLM provider layer.

Interface
- Python: `src/utils/keyword_extractor.py`
  - `extract_search_terms_from_surveys(pdf_paths, provider='openai', model='gpt-5-nano', params=ExtractParams(), service=None)` → dict
  - `ExtractParams(topic=None, max_queries=50, include_ethics=True, language='en', custom_categories=None, seed_anchors=None, anchor_variants=None, exclude_terms=None, mode='combined')`
  - `build_generate_instructions(params)` and `build_aggregate_instructions(partials, max_queries)` helpers.

Usage Example
```python
from pathlib import Path
from src.utils.keyword_extractor import ExtractParams, extract_search_terms_from_surveys

pdfs = [
    Path('resources/datasets/arxiv_papers/Systematic_Review(系統性綜述__SR)/sample1.pdf'),
    Path('resources/datasets/arxiv_papers/Systematic_Review(系統性綜述__SR)/sample2.pdf'),
]
params = ExtractParams(topic='dialogue summarization', max_queries=20, include_ethics=False, mode='combined')
result = extract_search_terms_from_surveys(pdfs, provider='openai', model='gpt-5-nano', params=params)
print(result['anchor_terms'])
```

- Provide at least one PDF path; the helper raises `ValueError` on empty input so upstream callers can short-circuit before touching the provider.

Prompt Behaviour
- `build_generate_instructions` renders a runtime overrides block (topic, language, category set, seeds, exclusions) and dynamically adjusts the category list when `custom_categories` or `include_ethics` are toggled.
- Providing `anchor_variants` locks the anchors to those exact variants; the prompt explicitly warns the model not to introduce additional anchor terms.
- When only `topic` is supplied, the helper auto-derives anchor variants (topic, singular/plural swaps, speech↔spoken forms, acronym) and instructs the model to stick to them.
- JSON scaffolding in the prompt remains neutral (`<category>` placeholders) so custom taxonomies can be inferred without further string replacements.
- The parser strips ``` fences irrespective of casing (e.g. ```JSON) before decoding, reducing fragility when models change their formatting hints.

Testing
- Live tests: `pytest -q -k keyword_extractor_live` (requires `OPENAI_API_KEY`) and uses `gpt-5-nano` to keep costs low.
- Unit tests: `pytest -q test/unit/test_keyword_extractor_prompts.py` exercises instruction rendering, input validation, fence stripping, and usage logging safeguards.

Usage Logging
- If omitted, logs default to `test_artifacts/llm/keyword_extractor_usage_<timestamp>.json`; override `usage_log_path` to control location.
- Logs now write even when parsing fails, so you can inspect token usage for malformed model outputs; the helper ensures the parent directory exists.

Known Limits
- Combined mode depends on provider support for multiple file attachments (OpenAI Responses API supported). If failing due to size limits, switch to `two_step` mode.
- Output is model‑generated JSON; the helper raises `ValueError` if decoding fails so callers can retry or fall back. Anchor terms are normalised to the derived topic variants to keep them consistent. Always validate keys before downstream use.

Prompt Storage
- Primary prompts in this repo: `resources/LLM/prompts/keyword_extractor/`.
- Mirrored for SurveyX: `SurveyX/resources/LLM/prompts/keyword_extractor/` (external path).
