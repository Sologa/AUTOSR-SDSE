# LatteReview Latte Inputs Implementation Notes

The keyword extractor no longer emits `latte_inputs` rows. This file is retained for historical context only and will be removed once all downstream consumers finish migrating. Refer to `docs/keyword_extractor/關鍵詞抽取流程與提示詞.md` and `docs/keyword_extractor/module.md` for the up-to-date schema (`papers` + `reviewer_profile`).

Legacy design details (prompt placeholders, fallback rebuilding helpers, and validation rules) were documented in earlier revisions of this file. If you need that context, inspect the Git history prior to the removal of `latte_inputs` support.
