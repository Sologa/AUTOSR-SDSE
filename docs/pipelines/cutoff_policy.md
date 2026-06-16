# Cutoff Policy (Conditional)

## Purpose

- Derive a cutoff date from the target paper title (topic string) only when an exact-title match exists.
- Enforce hard exclusions: same-title papers and any paper on/after the cutoff date.
- Support explicit cutoff overrides (`--cutoff-arxiv-id`, `--cutoff-title-override`).
- Validate `final_included` before writing outputs; violations are surfaced as a hard error when cutoff is present.
- Stage time windowing is resolved per stage from command args, and only falls back to `cutoff.json` when args are not set.

## Stage time-window policy now in effect

1) `run_topic_cads.sh` resolves one shared window from `workspaces/<topic>/cutoff/cutoff.json`:
   - lower bound: `selection_constraints.published_year_min` only when `published_year_min_hard = true` (converted to `YYYY-01-01`)
   - upper bound: `cutoff_date` (if present)
2) The script passes `--start-date`/`--end-date` to:
   - `seed`
   - `harvest`
   - `review`
   - `snowball_iterate`
3) Each stage entrypoint still resolves dates through `resolve_cutoff_time_window`; if explicit stage args are missing it will fall back to the same `cutoff.json` policy.
4) This means the same cutoff-derived temporal boundary source is used by all downstream stages by default.

## Interface / Parameters

- Input: `topic` (string); exact-title match in arXiv results or explicit override flags.
- Output artifact (optional): `workspaces/<topic>/cutoff/cutoff.json` (only when cutoff exists).
- Fields in `cutoff.json`:
  - `topic_title`, `topic_title_normalized`
  - `target_paper` (source/id/title/published_date/published_raw)
  - `cutoff_date`
  - `policy` (exclude_same_title, exclude_on_or_after_cutoff_date)
  - `selection_constraints.published_year_min`
  - `selection_constraints.published_year_min_hard`

## Usage Example

1) Run `seed` as usual.
2) If an exact-title match (or override) exists, the pipeline writes `workspaces/<topic>/cutoff/cutoff.json`.
3) All later stages apply hard policy:
   - remove entries with `published >= cutoff_date`
   - remove entries with title equal to target title
4) If no cutoff exists, downstream stages do not apply on/after-cutoff filtering.

## Repository mapping (implementation detail)

- Seed, harvest, review, and snowball all use resolver-backed date arguments (`start_date`, `end_date`) and report `start_date_source` / `end_date_source` in key outputs.
- `scripts/topic_pipeline.py` run-path uses `resolve_cutoff_time_window` before invoking each stage.
- `scripts/snowball_iterate.py` also resolves `--start-date/--end-date` and forwards the resolved dates to ASReview + review runs.
- `run_topic_cads.sh` parses `selection_constraints` + `cutoff_date` once and feeds stage-level dates consistently.

## Testing Notes

- Verify `cutoff.json` exists only when cutoff is found or explicitly provided.
- Ensure no paper with `published_date >= cutoff_date` is included (when cutoff exists).
- Confirm `seed/queries/seed_selection.json`, `harvest/query_plan.json`, `review/results`, and `snowball` round metadata all carry matching effective date fields and sources.
- If violations occur, confirm `cutoff_violations.json` is written and run fails.

## Known Limitations

- If the target paper title is not found in seed candidates, no cutoff is applied and `cutoff.json` is not created.
- If the target paper is found but has no resolvable publication date, the pipeline raises an error.
