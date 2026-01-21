# Cutoff Policy (Conditional)

## Purpose
- Derive a cutoff date from the target paper title (topic string) only when an exact-title match exists.
- Enforce hard exclusions: same-title papers and any paper on/after the cutoff date (when cutoff exists).
- Support explicit cutoff overrides (`--cutoff-arxiv-id`, `--cutoff-title-override`).
- Validate `final_included` before writing outputs; violations are surfaced as a hard error when cutoff is present.

## Interface / Parameters
- Input: `topic` (string); exact-title match in arXiv results or explicit override flags.
- Output artifact (optional): `workspaces/<topic>/cutoff/cutoff.json` (only when cutoff exists).
- Fields in `cutoff.json`:
  - `topic_title`, `topic_title_normalized`
  - `target_paper` (source/id/title/published_date/published_raw)
  - `cutoff_date`
  - `policy` (exclude_same_title, exclude_on_or_after_cutoff_date)

## Usage Example
1) Run `seed` as usual.
2) If an exact-title match (or override) exists, the pipeline writes `workspaces/<topic>/cutoff/cutoff.json`.
3) Subsequent stages (harvest/review/snowball) read `cutoff.json` and apply the hard filters.
4) If no cutoff exists, downstream stages skip cutoff filters.
5) Snowball output writing halts if `final_included` violates the cutoff policy.

## Testing Notes
- Verify `cutoff.json` exists only when cutoff is found or explicitly provided.
- Ensure `final_included.json` has no normalized title equal to the topic title.
- Ensure no record with `published_date >= cutoff_date` is included (when cutoff exists).
- If violations occur, confirm `cutoff_violations.json` is written alongside the output.

## Known Limitations
- If the target paper title is not found in seed candidates, no cutoff is applied and `cutoff.json` is not created.
- If the target paper is found but has no resolvable publication date, the pipeline raises an error.
