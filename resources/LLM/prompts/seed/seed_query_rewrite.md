# seed query rewrite

you are given a single research topic string and a short history of previous attempts.
rewrite it into multiple candidate search phrase groups that broaden retrieval while preserving the same core research meaning.

goals
- improve recall when the original topic string is too narrow for search.
- preserve the exact core technical concept; do not introduce new concepts or adjacent subtopics.
- keep each phrase specific enough to avoid drifting into overly broad, generic umbrella terms.
- avoid repeating phrases already present in the history.

note
- if available, use the scientific-brainstorming skill internally for ideation.
- do not output questions or explanations; the final output must still follow the strict format.

how to rewrite
1) extract anchors
- identify the smallest set of distinctive technical terms from the topic that uniquely identify the concept.
- anchors must be domain-specific; avoid choosing only generic methodological words if more distinctive terms exist.
- treat the anchors as mandatory: do not drop them.

2) generate candidates
- output 8 to 12 candidate lines.
- each line is 1 to 3 short phrases separated by " | ".
- each phrase must include all anchors, or a very close synonym / standard abbreviation / standard expansion of an anchor.
- candidates must be meaningfully different from each other and from history.
- keep phrases concise (2 to 6 words); noun-phrase-like.
- do not add document-type words (e.g., survey/review) unless they are part of the core concept.

3) final self-check before responding
- output is 8 to 12 lines only.
- one candidate per line.
- lowercase only.
- letters/numbers/spaces only, plus the " | " separator.
- no quotes, no punctuation, no bullets, no numbering, no explanations, no extra whitespace lines.

topic
<<topic>>

history (previous attempts)
<<history>>
