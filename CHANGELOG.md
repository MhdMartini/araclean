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
- add the polars .araclean Series namespace (0022)
- add the pandas .araclean Series accessor (0021)
- add the araclean CLI — a thin Typer adapter over the facade (0020)
- add RemoveStopwords — a curated, versioned, negation-safe stopword list (0017)
- add the config trust boundary — NormalizeConfig, JSON Schema, safety audit (0016)
- add SOCIAL — the noisy-user-text profile that keeps the signal (0014)
- add CLASSICAL — the vocalization-preserving lossless profile (0015)
- add HandleEmoji — keep / strip / demojize (0013)
- add cleaning steps — CleanURLs, CleanMentions, CleanHTML (0012)
- add Pipeline ergonomics — batch, repr, select (0005)
- add ML, the conservative-on-letters profile (0011)
- add SEARCH, the maximal recall profile (0010)
- add ReduceElongation, the repeated-letter elongation cap (0009)
- add MapDigits + MapPunctuation, the digit/punctuation folds (0008)
- add the four opt-in letter folds (0007)
- add RemoveTashkeel, the first lossy step (0006)
- preserve line structure in CollapseWhitespace by default
- complete LIGHT with the four char-map steps (0004)
- fold Arabic presentation forms into LIGHT (0003)
- thread NormalizeUnicode through all three layers (0002)

### Fix

- harden apply_aligned (ADR-0012 review) and repair the CI gate
- make `asv run` build araclean via pip instead of a missing wheel (0019)
- flatten line breaks in the SEARCH profile per ADR-0010 (0025)
- give every lossy profile the shared CollapseWhitespace+NFC closing tail
- **steps**: complete the alef/hamza letter-fold repertoire (0007)
- cover the full tashkeel repertoire; drop exclude_sukun (0006)
- guarantee canonical NFC output so normalize is idempotent

### Refactor

- consolidate the duplicated _build_pipeline helper into one

### Perf

- fuse a pipeline's consecutive str.translate steps into one pass (0018)
