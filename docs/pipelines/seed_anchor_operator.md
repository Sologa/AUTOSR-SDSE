# Seed Anchor Operator

## Purpose
Control how anchor terms are combined when building the arXiv seed query.

## Interface/Parameters
- CLI: `python scripts/topic_pipeline.py seed --anchor-operator {AND|OR}`
- CLI: `python scripts/topic_pipeline.py run --seed-anchor-operator {AND|OR}`
- Function: `seed_surveys_from_arxiv(..., anchor_operator="OR")`

Notes:
- Default is `OR` to maximize recall.
- Applies only to how multiple anchor terms are joined.

## Usage Example
```bash
python scripts/topic_pipeline.py seed \
  --topic "discrete audio tokens" \
  --anchor-operator OR \
  --anchor-mode token_or \
  --scope all
```

## Testing Notes
- Run a seed query with both `--anchor-operator OR` and `--anchor-operator AND` and compare `seed/queries/seed_selection.json`.
- Use `--no-cache` to ensure the search is re-run.

## Known Limitations
- `anchor_operator` only affects how anchor terms are joined; `token_and` still uses AND within each anchor term.
- 若使用 `core_phrase` / `core_token_or`（僅核心片語），通常只有一個 anchor，`anchor_operator` 影響有限。
- `AND` can be too strict and may return zero results for broad topics.
