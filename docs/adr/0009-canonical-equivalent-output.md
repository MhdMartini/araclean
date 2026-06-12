# Canonical-equivalent output: the pipeline guarantees NFC, not byte-exact preservation

araclean's notion of "the same text" is **Unicode canonical equivalence**, and every profile's
output is therefore **NFC**. Two inputs that are canonically equivalent (or that araclean's lossless
folds make equivalent) must produce byte-identical output. To enforce this, a profile both *starts*
and *ends* with `NormalizeUnicode(NFC)`: the opening pass canonicalizes the input for the steps that
follow; the closing pass re-canonicalizes after steps that can disturb combining-mark order.

Why a closing pass is needed at all: `NormalizeUnicode` applies Unicode Canonical Ordering, which
sorts a run of combining marks by `Canonical_Combining_Class`. Two later lossless steps can *create*
a non-canonical run that the opening pass has already gone past and cannot fix:

- **FoldPresentationForms** expands a ligature into `base + combining mark` (e.g. U+FC5B folds to
  U+0630 + U+0670, a dagger alef). A mark that *followed* the ligature in the source now sits
  after the expanded mark, possibly out of canonical order.
- **StripBidi** deletes a format character (e.g. a BOM) that was separating two combining marks;
  removing the separator leaves the two marks adjacent, possibly out of canonical order.

Without the closing pass the consequences are concrete and observable: the output is not NFC,
`normalize` is **not idempotent** (a second call reorders the marks), and — worst — an OCR'd
presentation-form spelling fails to match the hand-typed canonical spelling of the same word, which
defeats the whole purpose of the fold. A targeted Hypothesis strategy (presentation forms × tashkeel)
reproduces all three; plain `st.text()` almost never generates the triggering shape, so the property
is pinned with that strategy plus a concrete fixture.

This also settles a design knot in `FoldPresentationForms`: it folds per code point (a `str.translate`
substitution) **specifically so the step itself introduces no reordering** — it never silently
reshuffles a caller's vocalization the way a whole-string NFKC would. Canonical ordering is then
applied **once, by the pipeline's closing NFC**, not as a side effect scattered through the folds.

The rejected alternative is **byte-exact preservation** (no normalization, keep whatever order the
caller typed). We reject it because Unicode itself defines canonically-equivalent sequences as the
same text: preserving a non-canonical byte order would make visually identical, semantically
identical strings compare unequal — exactly the silent-mismatch failure araclean exists to remove.
Canonical reordering is loss*less* (it changes encoding, never signal), so nothing is given up.

## Consequences

- Every profile's output is NFC; `normalize` is idempotent. "Output is NFC" is a tested postcondition.
- `FoldPresentationForms` stays a pure per-glyph substitution; the single source of canonical ordering
  is the closing `NormalizeUnicode`. Do not remove either NFC pass from a profile — they do different
  jobs (see the comment on `LIGHT` in `profiles.py`).
- **CLASSICAL** preserves *vocalization* (it keeps every tashkeel/Qur'anic mark) but,
  like every profile, emits canonical order — it does **not** promise byte-exact preservation of a
  non-canonical input ordering. If a future use case genuinely needs byte-exact round-tripping, that
  is a new, explicitly-opted-in mode, not the default.
