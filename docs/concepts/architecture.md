# Architecture & performance

araclean is a small library with a deliberate shape: validate once at the edge, run a precompiled
plan in the middle, and keep every behavior in one deep core that several thin adapters share.

## Three layers, one validation boundary

| Layer | Surface | Validates? |
|-------|---------|------------|
| 3 — facade | `normalize(text, profile=…, **overrides)` | **yes** — the trust boundary |
| 2 — composition | `Pipeline`, `Profile`, named presets | at construction only |
| 1 — primitives | `Step` objects and their bare functions (`remove_tatweel(s)`, …) | no — the hot path |

All untrusted input — profile names, override knobs, serialized configs — is validated at the
facade through one pydantic model (`NormalizeConfig`, a closed set of enums and bounded scalars),
so a bad option fails there with a clear error. Below the boundary, nothing validates per string:
steps precompute their tables and regexes at construction, and `Pipeline.__call__` just runs them.
That split is why the facade can be friendly *and* the per-string path fast.

The CLI, the pandas accessor, and the polars namespace are **adapters at the same seam**: each
parses its own input format, passes through the same boundary once, then streams or maps the
resulting pipeline. None of them contains normalization logic, which is why behavior is identical
across all four entry points.

## The fused execution engine

Most repair and fold steps are, in implementation terms, a single `str.translate` over a static
table — a context-free, per-character map that never re-scans its own output. Composing two such
maps is itself such a map, so when a pipeline contains a *run* of consecutive translate steps,
araclean fuses the run into **one combined table applied in a single C-level pass** at pipeline
construction. SEARCH, for example, composes 18 steps but executes 11 passes; LIGHT's 7 steps run
as 5.

The fusion is exact — output is identical to running the steps one by one — and invisible:
`pipe.steps`, `repr`, `select`/`drop`, `audit()` and serialization all speak in terms of the steps
you composed. Contextual steps (regex-based cleaning, `ReduceElongation`, `NormalizeUnicode`)
cannot be expressed as a per-character map, so each stays its own pass, in order, and fusion
happens within the stretches between them.

In the repo's benchmark suite this is worth roughly a 1.7× throughput advantage over the
incumbent multi-pass approach on character-level normalization, measured continuously in CI;
an [asv](https://asv.readthedocs.io/) suite additionally tracks araclean against itself across
commits so regressions are caught. [Custom steps](../guides/custom-steps.md) whose behavior is one
translate table can opt into fusion by exposing `translate_table`.

## Invariants the pipelines maintain

Every built-in profile guarantees, by construction:

- **Output is NFC and whitespace-collapsed.** Profiles open *and* close with a Unicode NFC pass
  (folds in the middle can re-expose non-canonical mark order), and close with a whitespace
  collapse (deletions leave gaps). The closing pair makes the postcondition unconditional.
- **Idempotence.** Normalizing an already-normalized text is a no-op:

```pycon
>>> from araclean import normalize
>>> out = normalize("اَلسّلامُ عليكم", profile="search")
>>> normalize(out, profile="search") == out
True
>>> normalize(out) == out  # lossy output is already LIGHT-stable too
True

```

- **Profile containment.** SEARCH, ML, and SOCIAL all begin with LIGHT's exact steps, so "every
  profile does everything LIGHT does" holds by construction, and ML sits strictly between LIGHT
  and SEARCH in what it removes.

These are pinned by property-based tests (Hypothesis) and snapshot tests in the repository, not
just asserted in prose.

## Correctness machinery behind the scenes

Worth knowing even if you never touch it:

- **Whole-category character tables are derived from the live Unicode Character Database** and
  enforced by invariant tests, so e.g. the tashkeel repertoire tracks Unicode releases instead of
  a hand-typed list going stale.
- **Differential oracles**: araclean's folds are cross-checked against an independent
  implementation (pyarabic, as a dev-only test oracle — it never ships as a dependency) on
  generated inputs.
- **Generated docs with drift guards**: the per-profile pages, the glossary tooltips, and the
  [CLI reference](../reference/cli.md) are generated from the code and re-checked by tests, and
  every Python example in these docs runs as a doctest in CI.

## Reserved seams

`apply_aligned()` — offset/alignment tracking that maps normalized spans back to the original
text — is reserved on every step and on `Pipeline`, and currently raises a clear
`AlignmentNotSupportedError`. It is the designed next major feature (the architecture's
per-code-point tables and anchored regexes were chosen to make it tractable); until then the
contract is honest: it fails loudly rather than approximating.
