# Spec: extract_reference_metadata (title-only + arXiv)

## Purpose
Build an oracle reference pool by extracting titles from a BibTeX file, then query arXiv by title to enrich metadata. Output a JSONL file for downstream evaluation.

## Scope
- Input: BibTeX file for a paper's references.
- Output: JSONL with local titles plus optional arXiv match metadata and provenance.
- Optional: title-only Precision/Recall/F1 against a retrieved paper pool.

## CLI
```
python target_papers/scripts/extract_reference_metadata.py \
  --paper-dir <path> \
  --bib-path <path> \
  --out-jsonl <path> \
  --cache-dir <path> \
  --use-arxiv <true|false> \
  --min-score <float> \
  --max-rps <float> \
  --timeout <seconds> \
  --entry-types <comma_separated|all>
```

## Inputs
- --paper-dir: directory containing a paper's source (used to locate .bib if --bib-path is not set).
- --bib-path: explicit path to the BibTeX file; takes precedence over discovery.
- --entry-types: types to include (default: all non-string entries).
- --use-arxiv: when true, query arXiv to fill missing metadata (default: false).
- --min-score: minimum similarity score to accept a match.
- --max-rps: client-side rate limit.
- --timeout: HTTP timeout seconds.

## Discovery Rules
1. If --bib-path is provided, use it.
2. Else, scan --paper-dir for *.bib.
3. If exactly one .bib is found, use it; otherwise fail with an explicit error.

## Title Extraction
- Only include entries whose type is in --entry-types. Default is all non-string entries.
- Extract the raw `title` field and keep it verbatim in output for traceability.

## Title Normalization
- Remove outer braces and surrounding quotes.
- Strip TeX commands and leftover braces.
- Normalize whitespace and punctuation.
- Lowercase for matching.
- Example: `Codec-{SUPERB}@ {SLT} 2024: A lightweight benchmark for neural audio codec models` should normalize to a stable, comparable string.

## arXiv Query (when --use-arxiv=true)
- Use the arXiv API title search (`ti:`) with a quoted query.
- Request a small candidate set.
- Normalize candidate titles using the same rules.
- Compute a similarity score between query title and candidate title.
- Select the best match; if no candidate meets --min-score, mark as unmatched.

## Matching & Merge Policy
- Match priority: title similarity only (no DOI/author fallback).
- Local fields override online fields unless empty.
- Record per-field provenance in `sources`.

## Output Format (JSONL)
One record per BibTeX entry. Example shape:
```
{
  "key": "citation_key",
  "entry_type": "article",
  "query_title": "...",
  "normalized_title": "...",
  "matched": true,
  "match_score": 0.93,
  "arxiv": {
    "id": "...",
    "title": "...",
    "authors": ["..."],
    "published": "...",
    "doi": "...",
    "url": "...",
    "primary_category": "..."
  },
  "sources": {
    "query_title": "local",
    "arxiv": "arxiv"
  },
  "raw": {
    "local": {"...": "..."},
    "arxiv": {"...": "..."}
  }
}
```

## Caching
- Cache raw arXiv API responses keyed by normalized title.
- Cache hit skips network and records provenance as `cache`.

## Errors & Retries
- Retry on HTTP 429/5xx with exponential backoff.
- On repeated failure, continue and mark entry with `errors` list.
- At the end, if any errors occurred, exit non-zero and report the failures.

## Logging
- Log start/end, input paths, number of entries, online query counts, and failures.

## Evaluation (optional)
### CLI
```
python target_papers/scripts/compute_title_f1.py \
  --oracle-jsonl <path> \
  --retrieved-json <path> \
  --out-report <path>
```

### Inputs
- --oracle-jsonl: output from extract_reference_metadata.py.
- --retrieved-json: pipeline output containing titles (e.g., final_included.json).

### Algorithm
- Normalize titles from both sources using the same normalization rules.
- Build sets O (oracle) and R (retrieved).
- Compute TP, Precision, Recall, and F1.
- Output counts, metrics, and matched/unmatched title lists.

## Tests (future)
- Unit: BibTeX parsing, title normalization, similarity scoring.
- Integration: real arXiv API calls only; no mock/stub/recording or offline snapshots.

## Non-Goals
- Filling metadata for non-arXiv works.
- De-duplicating references across multiple papers.
