# Build a new MIT library rather than fork or contribute upstream

We will build a new, MIT-licensed library from a clean slate rather than forking Maha or
contributing to CAMeL Tools / pyarabic.

Why: the hard-to-replicate value in the incumbents is small — the Arabic character maps are
short and fully documented (we have the Unicode taxonomy) — while the real value (clean API
design, full typing with `py.typed`, tests, docs, fused-`str.translate` performance,
reproducible versioned profiles, offset/alignment tracking) must be built fresh regardless.
Forking Maha means adopting an abandoned 2022 codebase (Python ≤3.10, no `py.typed`, no living
upstream); pyarabic is GPL-3.0 (incompatible with an MIT goal); CAMeL's heavy install and
maintainer constraints can't be fixed without a rewrite they may not accept.

## Consequences

- We owe nothing to upstream APIs and can design clean from line one.
- We will use Maha (BSD-3, readable) and CAMeL as design references and as differential-test
  correctness oracles — not as a code base.
