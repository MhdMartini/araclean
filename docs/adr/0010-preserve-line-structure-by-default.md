# Whitespace collapse preserves line structure by default; flattening is opt-in

`CollapseWhitespace` collapses each whitespace run to a **single character**: a purely horizontal
run becomes one ASCII space, and a run containing any line break becomes a single `"\n"`. Line
structure is therefore **preserved by default**. Flattening every run to a space — turning a
multi-line document into one line — is the opt-in behavior, `collapse_lines=True`, which the
recall-oriented `SEARCH` profile sets.

This reverses the intuitive "collapse everything to a space," and the reversal is deliberate:

- **It keeps the default honest about being lossless.** `LIGHT` is sold as lossless **encoding
  repair** (ADR-0004). Collapsing redundant horizontal spacing is lossless — space count/kind is not
  signal. Collapsing newlines into spaces is *not*: it destroys recoverable document structure
  (paragraph, list, and — for vocalized/Qur'anic text — verse/hemistich boundaries). A library whose
  entire identity is "we don't silently destroy signal" must not silently flatten documents by
  default.
- **It matches the user story's actual wording.** The user story asks for "NBSP and other Unicode
  *spaces* collapsed to a single space, so that spacing differences don't create duplicate tokens" —
  about horizontal spacing and tokenization, not line structure. The earlier `\s+ → " "`
  implementation over-reached by also eating newlines.
- **It is the right reading of the project's guiding paper.** Gorman & Pinter, *Don't Touch My
  Diacritics* (arXiv:2410.24140), is specifically about not stripping linguistic signal and about
  *consistent* encoding; it says nothing about whitespace. Its principle — normalize true noise,
  preserve information — extends to: collapse redundant spacing (noise), keep line structure
  (information). It does not license flattening documents.

Use cases line up with the profiles, which is why the split lives on a flag rather than in the
default: search / IR / bag-of-words matching want flattening (`collapse_lines=True`); sequence
labeling, segmentation, text generation, classical/Qur'anic, and human-readable cleaning want the
structure-preserving default.

The rule is symmetric and idempotent: horizontal run → one space, line-break run → one `"\n"`. A run
of blank lines collapses to a single newline (consistent with horizontal runs collapsing to one
space); preserving the *exact* number of blank lines is intentionally out of scope. "Line break" is
exactly the boundary set `str.splitlines()` recognizes (LF, CR, VT, FF, FS/GS/RS, NEL, U+2028,
U+2029); see `chars.LINE_BREAKS`.

## Consequences

- `LIGHT` (and any lossless profile) preserves line breaks; `normalize(text)` no longer flattens a
  multi-line document. The behavior is pinned end-to-end in `tests/test_api.py` and by the golden
  snapshot.
- `SEARCH` (when built) constructs `CollapseWhitespace(collapse_lines=True)` to
  flatten for maximum recall. The flag is serialized in `to_dict`, so a flattening pipeline can be
  pinned and shared like any other.
- A future need for paragraph-exact preservation (collapse runs but keep blank-line boundaries)
  would be a further option, not a change to this default.
