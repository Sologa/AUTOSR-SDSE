# Data Model: Codex CLI Keywords Provider Switch

**Date**: 2026-01-13  
**Spec**: `docs/specs/001-codex-cli-keywords/spec.md`

## Entities

### ProviderSelection

- provider: string (`openai` | `codex-cli`)
- model: string
- created_at: string (ISO 8601)

### KeywordInput

- topic: string
- pdf_paths: string[]
- metadata_block: string

### PdfTextArtifact

- pdf_path: string
- text_path: string
- extracted_at: string (ISO 8601)

### KeywordOutput

- topic: string
- anchor_terms: string[]
- search_terms: object (category → string[])
- papers: PaperKeyword[]

### PaperKeyword

- source_id: string
- title: string
- abstract: string
- year: string
- source_url: string
- detected_keywords: DetectedKeyword[]

### DetectedKeyword

- term: string
- category: string
- evidence: object
- confidence: number

### KeywordRunRecord

- provider: string
- model: string
- command: string[] (e.g., `["/opt/homebrew/bin/codex", "exec", "-", "--model", "gpt-5.1-codex-mini"]`)
- codex_home: string | null
- input_pdfs: string[]
- text_paths: string[]
- output_path: string
- raw_output_path: string | null
- errors: string[]
- created_at: string (ISO 8601)
- reasoning_effort: string | null
