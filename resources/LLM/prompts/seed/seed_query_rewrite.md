# seed query rewrite (cutoff-first)

You are given a single research topic string.
Rewrite it into an English-only list of short search phrases that preserve the same core research meaning.

Output format (strict)
- Return JSON only.
- Schema: {"phrases": ["...", "..."]}
- The array must contain 1 to <<n_phrases>> items.
- Each phrase must be a concise noun-phrase (2 to 8 words).
- No explanations, no extra keys, no markdown.

Constraints (strict)
- English-only: ASCII printable characters only.
- Do not include any survey/review/overview terms or their variants.
- Do not introduce new concepts outside the topic.
- Avoid duplicates.

topic
<<topic>>
