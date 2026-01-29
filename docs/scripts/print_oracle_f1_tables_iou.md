# print_oracle_f1_tables IoU Metric

## Purpose
Add IoU (Jaccard) overlap reporting for title-only matching in `scripts/print_oracle_f1_tables.py`.

## Interface
- Function: `compute_iou(oracle: Set[str], retrieved: Set[str]) -> float`
- Inputs: normalized title sets from `load_oracle_titles` and `load_retrieved_titles`.
- Output: `|A ∩ B| / |A ∪ B|`, with `0.0` when the union is empty.

## Usage Example
Run the script and read the IoU column in the markdown table output:

```bash
python scripts/print_oracle_f1_tables.py --out snowball_title_f1_tables.md
```

## Test Points
- IoU is `0.0` when both sets are empty.
- IoU is `1.0` when the sets are identical.
- IoU is `0.0` when the sets are disjoint.
- The table includes the IoU column for each round.

## Known Limitations
- Metrics are set-based, so duplicate titles are ignored.
- Exact match only after title normalization; no fuzzy matching.
- Does not reflect ranking or confidence scores from retrieval.
