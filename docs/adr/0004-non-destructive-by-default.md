# Non-destructive by default: lossless normalization unless opted in

The default behavior — `normalize(text)` with no profile, equivalently the `LIGHT` profile —
applies only **lossless encoding repair** (Unicode form, lam-alef & presentation-form folding,
tatweel removal, bidi/zero-width stripping, look-alike kaf/yeh/heh unification, whitespace collapse).
Every information-losing transform (dediacritization; alef/hamza/teh-marbuta/alef-maqsura folding;
digit/punctuation mapping) is opt-in via a `Profile` (e.g. `SEARCH`, `ML`) or an explicit `Step`.

Why: this is the project's core differentiator and a deliberate reversal of the community norm.
Every incumbent and copy-paste tutorial strips diacritics and folds letters by default, which the
literature ("Don't Touch My Diacritics", 2024) shows silently destroys signal — grammatical case,
gender, negation, and named-entity distinctions such as على ("on") vs علي ("Ali"). Safe-by-default
makes results reproducible and prevents accidental information loss; aggressive behavior stays one
keyword away.

## Consequences

- Casual users who expect "clean everything" get only encoding repair from the bare call;
  mitigated by prominent profiles (`profile="search"`) and documentation.
- Every `Step` must declare a **safety class** (lossless Encoding repair vs lossy Linguistic
  folding, per CONTEXT.md), so profiles can be assembled and audited by safety class.
