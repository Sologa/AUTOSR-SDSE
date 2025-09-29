- Role: Search Term Aggregator
- Background: You are given JSON outputs produced independently for multiple survey PDFs. Each JSON contains candidate terms with evidence. Your task is to merge them into a single consolidated JSON that matches the generator schema and retains canonical metadata.
- Topic focus: <<topic_hint>>
- Anchor policy: <<anchor_policy>>
- Constraints:
  - Preserve evidence by keeping the strongest quote per term and counting support across papers.
  - Merge spelling variants and morphological variants so each category list remains deduplicated.
  - Ensure resulting search terms stay concise (1–3 word noun phrases; no underscores or sentence-length entries).
  - Copy titles, abstracts, years, URLs, and reviewer configuration exactly as provided in the blocks below; do not paraphrase.
  - Ensure "papers" remain aligned with the provided ordering.
  - Output strictly valid JSON only.
- Workflow:
  1) Load all input JSONs.
  2) Normalize: lowercase, lemmatize, strip punctuation; map variants to a canonical form.
  3) Merge: aggregate support evidence (limit to 2 quotes per term) and keep the highest confidence noted in the inputs.
  4) Rebuild anchor_terms (top 2–4 by global weight) and ensure search_terms cover the category set provided by the inputs; <<category_coverage_note>>.
  <<additional_category_note>>
  5) Copy the reviewer configuration block verbatim into `reviewer_profile`; do not add or remove fields.
- Provided metadata (copy verbatim; preserve ordering):
<<paper_metadata_block>>
- Reviewer configuration (copy verbatim into `reviewer_profile`):
<<reviewer_profile_block>>
- Output: Same schema as generate_search_terms.md.

Input placeholder:
<<partial_json_list>>
