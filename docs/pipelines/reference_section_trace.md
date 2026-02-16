# Reference Section Trace

## Purpose
Map citation keys from a target paper's LaTeX sources back to the sections where they appear, using `reference_oracle.jsonl` and/or `arxiv_metadata.json` as the key list.

## Interface / Parameters
- Script: `src/pipelines/reference_section_trace.py`
- Required:
  - `--paper-dir`: target paper directory (contains `tmlr_main_arxiv.tex`)
- Optional:
  - `--main-tex`: override main LaTeX entrypoint (default: `<paper-dir>/tmlr_main_arxiv.tex`)
  - `--oracle-jsonl`: override oracle JSONL (default: `<paper-dir>/reference_oracle.jsonl` if present)
  - `--arxiv-metadata`: path to `arxiv_metadata.json` (optional)
  - `--out-json`: output JSON path (default: `<paper-dir>/reference_section_map.json`)
  - `--out-csv`: optional CSV output for flat `key, section, count`
  - `--level`: section granularity (`file`, `section`, `subsection`, `subsubsection`; default: `section`)

## Usage Examples
```bash
source sdse-uv/.venv/bin/activate
python src/pipelines/reference_section_trace.py \
  --paper-dir target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey \
  --arxiv-metadata workspaces/titlepaper_criteria_review/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/harvest/arxiv_metadata.json \
  --out-json workspaces/titlepaper_criteria_review/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/reference_section_map.json
```

```bash
source sdse-uv/.venv/bin/activate
python src/pipelines/reference_section_trace.py \
  --paper-dir target_papers/on_the_landscape_of_spoken_language_models_a_comprehensive_survey \
  --level subsection \
  --out-csv workspaces/titlepaper_criteria_review/on_the_landscape_of_spoken_language_models_a_comprehensive_survey/reference_section_map.csv
```

## Testing Notes
- Confirm `reference_section_map.json` includes `records[*].sections` and `records[*].section_hits`.
- Check `missing_keys` (input keys with no citations) and `unmatched_citations` (citations not in input list).

## Known Limitations
- Only `\\cite*`-style commands are parsed; custom citation macros are ignored.
- Section labels are derived from LaTeX `\\section` / `\\subsection` / `\\subsubsection` commands.
