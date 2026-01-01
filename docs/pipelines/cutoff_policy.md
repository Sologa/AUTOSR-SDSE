# Cutoff Policy (Automatic)

## Purpose
- Automatically derive a cutoff date from the target paper title (topic string).
- Enforce hard exclusions: same-title papers and any paper on/after the cutoff date.
- Avoid user-supplied cutoff inputs.
- Validate `final_included` before writing outputs; violations are surfaced as a hard error.

## Interface / Parameters
- Input: `topic` (string) and seed selection artifacts in `workspaces/<topic>/seed/queries/seed_selection.json`.
- Output artifact: `workspaces/<topic>/cutoff/cutoff.json`.
- Fields in `cutoff.json`:
  - `topic_title`, `topic_title_normalized`
  - `target_paper` (source/id/title/published_date/published_raw)
  - `cutoff_date`
  - `policy` (exclude_same_title, exclude_on_or_after_cutoff_date)

## Usage Example
1) Run `seed` as usual.
2) The pipeline writes `workspaces/<topic>/cutoff/cutoff.json` automatically.
3) Subsequent stages (harvest/review/snowball) read `cutoff.json` and apply the hard filters.
4) Snowball output writing halts if `final_included` violates the cutoff policy.

## Testing Notes
- Verify `cutoff.json` exists after seed.
- Ensure `final_included.json` has no normalized title equal to the topic title.
- Ensure no record with `published_date >= cutoff_date` is included.
- If violations occur, confirm `cutoff_violations.json` is written alongside the output.

## Known Limitations
- If the target paper title is not found in seed candidates, no cutoff is applied.
- If the target paper is found but has no resolvable publication date, the pipeline raises an error.
