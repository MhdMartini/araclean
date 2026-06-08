# Pure-Python normalization engine using fused str.translate tables

The normalization engine is pure-Python for v1. Single-character maps (alef/hamza/yeh/teh-marbuta
folding, tashkeel/tatweel removal, digit folding) are applied with **fused `str.translate` tables**
built once at construction — one C-level pass over the string, and combinable so a whole profile's
char-level work collapses into a single pass. Multi-character/contextual rules use module-level
precompiled `re` patterns; Unicode form via `unicodedata.normalize`. No Rust/native extension in v1.

Why: `str.translate` with a `maketrans` table is the fastest pure-Python option for 1-char→1-char
(or →deletion) mapping — a single C pass — and beats CAMeL Tools' char-by-char `dict.get` loop, our
nearest performance comparison. Most Arabic normalization is exactly this shape, so the Python path
is already C-fast without the install/build complexity of a native extension. A Rust/PyO3 (maturin)
core remains a possible later escalation if profiling on real corpora shows a bottleneck — but only
behind a pure-Python fallback, so `pip install` never requires a toolchain.

## Consequences

- Steps precompute their translate table / compiled regex at construction; the per-string
  `__call__` does no setup and no validation.
- Compatible single-char steps in a profile should be **fused into one translate pass** where
  possible (the biggest single optimization) — design steps so this fusion is achievable.
- Benchmark with `pytest-benchmark` (micro) + `asv` (regression-over-time) against a realistic
  mixed MSA/dialect/diacritized corpus, reporting throughput vs CAMeL/pyarabic.
