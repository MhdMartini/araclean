## v0.2.0 (2026-06-12)

### BREAKING CHANGE

- remove the exclude_sukun option from RemoveTashkeel and
remove_tashkeel and drop it from the serialized config. Sukun is the
absence of a vowel (not a haraka) but always rides with HARAKAT —
stripping the vowels while leaving a bare sukun was never a use case, so
the flag added API surface for no real need. Sukun is still removed only
alongside HARAKAT, never on its own.

### Feat

- implement offset-preserving normalization (Phase 2 Bet 1, ADR-0012)
- add the polars .araclean Series namespace
- add the pandas .araclean Series accessor
- add the araclean CLI — a thin Typer adapter over the facade
- add RemoveStopwords — a curated, versioned, negation-safe stopword list
- add the config trust boundary — NormalizeConfig, JSON Schema, safety audit
- add SOCIAL — the noisy-user-text profile that keeps the signal
- add CLASSICAL — the vocalization-preserving lossless profile
- add HandleEmoji — keep / strip / demojize
- add cleaning steps — CleanURLs, CleanMentions, CleanHTML
- add Pipeline ergonomics — batch, repr, select
- add ML, the conservative-on-letters profile
- add SEARCH, the maximal recall profile
- add ReduceElongation, the repeated-letter elongation cap
- add MapDigits + MapPunctuation, the digit/punctuation folds
- add the four opt-in letter folds
- add RemoveTashkeel, the first lossy step
- preserve line structure in CollapseWhitespace by default
- complete LIGHT with the four char-map steps
- fold Arabic presentation forms into LIGHT
- thread NormalizeUnicode through all three layers

### Fix

- harden apply_aligned (ADR-0012 review) and repair the CI gate
- make `asv run` build araclean via pip instead of a missing wheel
- flatten line breaks in the SEARCH profile per ADR-0010 (0025)
- give every lossy profile the shared CollapseWhitespace+NFC closing tail
- **steps**: complete the alef/hamza letter-fold repertoire
- cover the full tashkeel repertoire; drop exclude_sukun
- guarantee canonical NFC output so normalize is idempotent

### Refactor

- consolidate the duplicated _build_pipeline helper into one

### Perf

- fuse a pipeline's consecutive str.translate steps into one pass
