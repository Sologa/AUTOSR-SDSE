# seed query rewrite

you are given a single research topic string.
rewrite it into 1 to 3 short search phrases that slightly broaden retrieval while preserving the same core research meaning.

goals
- improve recall when the original topic string is too narrow for search.
- preserve the exact core technical concept; do not introduce new concepts or adjacent subtopics.
- keep each phrase specific enough to avoid drifting into overly broad, generic umbrella terms.

how to rewrite
1) extract anchors
- identify the smallest set of distinctive technical terms from the topic that uniquely identify the concept.
- anchors must be domain-specific; avoid choosing only generic methodological words if more distinctive terms exist.
- treat the anchors as mandatory: do not drop them.

2) generate 1 to 3 phrases
- each phrase must include all anchors, or a very close synonym / standard abbreviation / standard expansion of an anchor.
- do not output phrases that are strict subsets of another output phrase.
- if you output multiple phrases, keep them at similar specificity (no “broad fallback” phrase).
- prefer 2 to 6 words per phrase; keep phrases short and noun-phrase-like.
- do not add document-type words (e.g., survey/review) unless they are part of the core concept.

3) final self-check before responding
- output is 1 to 3 lines only.
- one phrase per line.
- lowercase only.
- letters/numbers/spaces only.
- no quotes, no punctuation, no bullets, no numbering, no explanations, no extra whitespace lines.

topic
<<topic>>
