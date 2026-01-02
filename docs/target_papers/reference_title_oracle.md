# Reference Title Oracle

## Purpose
Extract reference titles from a BibTeX file, optionally enrich them with arXiv metadata, and compute title-only Precision/Recall/F1 against a retrieved paper pool.

## Interfaces
### Extract titles + arXiv metadata
```
python target_papers/scripts/extract_reference_metadata.py \
  --paper-dir target_papers/discrete_audio_tokens_more_than_a_survey \
  --out-jsonl target_papers/discrete_audio_tokens_more_than_a_survey/reference_oracle.jsonl \
  --use-arxiv false
```

### Extract titles from .bbl (special-case)
```
python target_papers/scripts/extract_reference_titles_bbl.py \
  --bbl-path target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/tmlr_main_arxiv.bbl \
  --out-jsonl target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/reference_oracle.jsonl
```

Key parameters:
- `--bib-path`: explicit BibTeX path (overrides auto-discovery)
- `--entry-types`: BibTeX types to include (default: all non-string entries)
- `--min-score`: title similarity threshold
- `--cache-dir`: cache for arXiv responses

### Compute title-only F1
```
python target_papers/scripts/compute_title_f1.py \
  --oracle-jsonl target_papers/discrete_audio_tokens_more_than_a_survey/reference_oracle.jsonl \
  --retrieved-json workspaces/discrete_audio_tokens_more_than_a_survey/snowball_rounds/final_included.json \
  --out-report workspaces/discrete_audio_tokens_more_than_a_survey/snowball_rounds/title_f1_report.json
```

## Usage Notes
- Title normalization removes braces, TeX commands, punctuation, and normalizes case.
- arXiv matching is title-only; works not indexed by arXiv will remain unmatched.
- If any arXiv queries fail, the script exits non-zero and reports errors.

## Testing Checklist
- Verify BibTeX discovery finds the intended `.bib`.
- Spot-check normalized titles for edge cases (TeX commands, braces, symbols).
- Confirm F1 report counts match expectations (TP, precision, recall).

## Known Limitations
- Title-only matching can miss paraphrased or heavily formatted titles.
- arXiv-only enrichment cannot cover non-arXiv references.

### Print per-round F1 tables (two fixed topics)
```
python scripts/print_oracle_f1_tables.py
```

Optional: write to a markdown file
```
python scripts/print_oracle_f1_tables.py --out docs/presentation/snowball_title_f1_results.md
```

Optional: write to a directory (uses default filename)
```
python scripts/print_oracle_f1_tables.py --out-dir workspaces/discrete_audio_tokens_more_than_a_survey
```
