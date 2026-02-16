# Evidence Base Tagging for CADS Dialogue Summarization SR

## Purpose
Annotate metadata entries for the CADS dialogue summarization systematic review with a boolean evidence label based on papers referenced in the LitRev-DialogueSum repository.

## Interface / Parameters
Input:
- `workspaces/titlepaper_criteria_review/cads_a_systematic_literature_review_on_the_challenges_of_abstractive_dialogue_summarization/harvest/title_abstracts_metadata.jsonl`
- LitRev-DialogueSum repo (cloned to `/tmp/LitRev-DialogueSum` for analysis)

Output:
- `workspaces/titlepaper_criteria_review/cads_a_systematic_literature_review_on_the_challenges_of_abstractive_dialogue_summarization/harvest/title_abstracts_metadata_evidence_annotated.jsonl`
- `workspaces/titlepaper_criteria_review/cads_a_systematic_literature_review_on_the_challenges_of_abstractive_dialogue_summarization/harvest/evidence_base_match_report.json`

Annotation fields:
- `evidence_base`: `true` for confident matches, `false` for non-matches, `null` for unresolved ambiguous candidates.
- `evidence_match_source`: list of match reasons (`title_exact`, `title_fuzzy`, `author_year_unique`, `author_year_context`, or `ambiguous_citation`).

## Usage Example
1) Clone the repo to a temp location.
2) Run a matching script that:
   - Extracts paper titles from tables.
   - Extracts author-year citations from text.
   - Matches to metadata titles and citation keys.
   - Emits annotated JSONL plus a match report.

## Testing Notes
- Verify the counts of `evidence_base` values in the annotated JSONL.
- Review `evidence_base_match_report.json` for unresolved ambiguous citations and missing references.

## Known Limitations
- Some citations are ambiguous (common surnames and years) and require manual adjudication.
- Some repo references do not exist in the metadata file and cannot be tagged.
- Non-ASCII author names may reduce citation extraction recall.
