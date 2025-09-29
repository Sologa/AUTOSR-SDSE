# LatteReview Paper Review Data Guide

## Purpose
This note captures every data artifact LatteReview needs so we can stage paper-review workflows without guesswork. It distills the expectations that are scattered across the LatteReview agents and workflow implementation inside `resources/LatteReview`.

## Reviewer Configuration Payload
Each reviewer agent is a Pydantic model that inherits the shared prompt template. Populate these fields up front so `BasicReviewer.setup()` can render the prompt without runtime errors (`resources/LatteReview/lattereview/agents/basic_reviewer.py:55`).
- `generic_prompt` or `prompt_path`: provide one prompt source; the template uses `${item}$`, `${inclusion_criteria}$`, `${exclusion_criteria}$`, `${reasoning}$`, `${additional_context}$`, and `${examples}$` tokens (`resources/LatteReview/lattereview/agents/title_abstract_reviewer.py:8`).
- Inclusion / exclusion criteria strings: required so the prompt can be formatted and saved on the agent identity (`resources/LatteReview/lattereview/agents/title_abstract_reviewer.py:48`).
- `provider`: inject a provider instance (LiteLLM/OpenAI/Ollama) before the workflow runs; otherwise `BasicReviewer` raises `AgentError` during setup (`resources/LatteReview/lattereview/agents/basic_reviewer.py:82`).
- `response_format`: map of keys to Python types, e.g. `{ "reasoning": str, "evaluation": int }`, which drives column generation later (`resources/LatteReview/lattereview/agents/title_abstract_reviewer.py:51`).
- Optional enrichments (all substituted into the prompt when present): `reasoning` (`"brief"` vs `"cot"`), `examples`, `additional_context` callable or string, and `model_args` for provider-specific parameters (`resources/LatteReview/docs/quickstart.md:61`).

## Review Workflow Schema
Create a list of round descriptors that mirrors `ReviewWorkflow.workflow_schema` (`resources/LatteReview/lattereview/workflows/review_workflow.py:17`). Each round dictionary should include:
- `round`: label used to prefix output columns (recommended: single letter or integer).
- `reviewers`: single reviewer or list. Every reviewer must inherit `ScoringReviewer`; the initializer enforces this (`resources/LatteReview/lattereview/workflows/review_workflow.py:27`).
- `text_inputs`: column names to concatenate for the user prompt. The workflow validates that each name exists on the DataFrame or corresponds to a prior reviewer output fragment such as `round-A_Alice_evaluation` (`resources/LatteReview/lattereview/workflows/review_workflow.py:38`).
- Optional `image_inputs`: columns that contain filesystem paths to images; each entry must exist before the round runs (`resources/LatteReview/lattereview/workflows/review_workflow.py:55`).
- Optional `filter`: callable that receives a row and returns `True` for rows that should go to the reviewers (`resources/LatteReview/lattereview/workflows/review_workflow.py:158`).

The workflow automatically appends `round-{ROUND}_{ReviewerName}_output` plus one column per response-format key so later rounds can reference earlier feedback (`resources/LatteReview/lattereview/workflows/review_workflow.py:189`).

## Submission Table Structure
LatteReview accepts multiple entry points: a `pandas.DataFrame`, a dict coercible to DataFrame, or a path to `.csv`, `.xlsx`, `.xls`, or `.ris` resources (`resources/LatteReview/lattereview/workflows/review_workflow.py:64`). We recommend keeping the ingestion table in tidy form:

| Column | Type | Notes |
| --- | --- | --- |
| `title` | string | Example text input used by the title/abstract reviewer tutorials (`resources/LatteReview/docs/quickstart.md:117`). |
| `abstract` | string | Paired with `title` in most examples (`resources/LatteReview/tutorials/title_abstract_review/data.csv:1`). |
| Additional metadata | string / numeric | Optional columns (e.g. DOI, modality). Leave them in place if you need them for downstream filtering; reviewers ignore them unless you pass the names via `text_inputs` or custom prompts. |
| `image_path` | string | Only required when a review round consumes images via `image_inputs` (`resources/LatteReview/lattereview/workflows/review_workflow.py:181`). |

When a round finishes, LatteReview will extend the table with structured output columns such as `round-A_Alice_output`, `round-A_Alice_evaluation`, and `round-A_Alice_reasoning` (`resources/LatteReview/lattereview/workflows/review_workflow.py:189`). Make sure downstream processes tolerate these additions.

## Integration with Keyword Extractor
- `extract_search_terms_from_surveys` hydrates paper metadata from arXiv before prompting and returns a consolidated JSON payload containing `papers` plus a reviewer configuration block (`reviewer_profile`).
- The helper validates that titles/abstracts match the canonical metadata and ensures reviewer fields are populated, so you can pair `result["papers"]` with the shared `reviewer_profile` when constructing LatteReview ingestion tables.
- Previous `latte_inputs` rows have been removed; downstream code should populate reviewer columns directly from the shared profile when building DataFrames.
- Output remains ordered; keep the `papers` list aligned with any derived table if ordering is significant for multi-round workflows.

## Example Payload
```python
from lattereview.providers import LiteLLMProvider
from lattereview.agents import TitleAbstractReviewer
from lattereview.workflows import ReviewWorkflow

reviewer = TitleAbstractReviewer(
    provider=LiteLLMProvider(model="gpt-4o-mini"),
    name="Alice",
    inclusion_criteria="AI applied to medical imaging",
    exclusion_criteria="Exclude non peer-reviewed work",
    reasoning="brief",
    response_format={"reasoning": str, "evaluation": int},
)

workflow = ReviewWorkflow(
    workflow_schema=[
        {
            "round": "A",
            "reviewers": [reviewer],
            "text_inputs": ["title", "abstract"],
        }
    ]
)
```
This follows the quickstart pattern and ensures every placeholder is satisfied (`resources/LatteReview/docs/quickstart.md:139`).

## Testing Checklist
- Load demo CSV or RIS data and confirm the workflow adds `round-*` columns for each reviewer (`resources/LatteReview/lattereview/workflows/review_workflow.py:189`).
- Run a dry test with the LiteLLM provider to verify JSON parsing stays consistent with your `response_format` contract.
- If you rely on image inputs, stub a row with a known local path and assert reviewers receive the encoded image list (`resources/LatteReview/lattereview/workflows/review_workflow.py:181`).

## Known Limitations
- The default response schema only returns reasoning and evaluation. Extend `response_format` if you need certainty scores or other metrics before a run starts (`resources/LatteReview/lattereview/agents/title_abstract_reviewer.py:51`).
- Cost tracking depends on the `tokencost` package; missing model definitions can skew totals and may require manual overrides (`resources/LatteReview/lattereview/providers/base_provider.py:32`).
- RIS ingestion funnels through `ris_to_dataframe`; malformed RIS files surface as workflow errors rather than partial results (`resources/LatteReview/lattereview/workflows/review_workflow.py:79`).
- Keyword extractor workflow requires PDFs named with arXiv identifiers so metadata enrichment can succeed; otherwise ingestion will raise before any LLM calls.
