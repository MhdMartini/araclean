# Cleaning is a third safety class, a sibling of linguistic folding

The cleaning steps (`CleanURLs`, `CleanMentions`, `CleanHTML`, and later `HandleEmoji`) declare a
**third** `SafetyClass`, `CLEANING`, rather than reusing `LINGUISTIC_FOLDING`. The enum is now:

- `ENCODING_REPAIR` — lossless, default-on (the `LIGHT` profile).
- `LINGUISTIC_FOLDING` — lossy; discards a linguistic distinction *within* the Arabic text
  (dediacritization, alef/hamza/teh-marbuta/maqsura folding, digit/punctuation mapping).
- `CLEANING` — lossy; removes *non-linguistic noise* around the text (URLs, mentions, HTML, emoji).

## Why a third class and not a second lossy value

The safety contract's gate is unchanged and stays binary in effect: a pipeline is **lossless iff
every step is `ENCODING_REPAIR`**, so cleaning steps — which delete or rewrite content — must not be
`ENCODING_REPAIR`, and never run under `LIGHT`/`CLASSICAL`. That much only requires "not lossless".

The reason to name the loss `CLEANING` rather than fold it into `LINGUISTIC_FOLDING` is
[`CONTEXT.md`](../../CONTEXT.md), the binding domain language:

- **Cleaning** is defined there as *"removal of non-linguistic noise … a sibling concern to
  Normalization, not a synonym"*, with an explicit *"avoid: using 'cleaning' and 'normalization'
  interchangeably."*
- **Linguistic folding** is defined as *"the subset \[of normalization] that discards information:
  dediacritization, alef/hamza unification, teh-marbuta→heh, alef-maqsura→yeh."*

So `LINGUISTIC_FOLDING` is, by definition, a subset of **Normalization**; stripping a URL is
**Cleaning**, a sibling concern. Labeling a URL strip `LINGUISTIC_FOLDING` would contradict the
project's own vocabulary. The distinction is also load-bearing for the story-41 audit
([`0016`](../../issues/0016-config-reproducibility.md)): a researcher reproducing a paper asks two
different questions — *"did this touch my Arabic letters?"* (`LINGUISTIC_FOLDING`) and *"did this
remove surrounding noise?"* (`CLEANING`) — and a precise audit must answer them separately, not
collapse both into "lossy".

This follows the project's "correct over conventional" preference: the more faithful model is worth
one extra enum value (ADR-0007 applies the same principle to terminology).

## Consequences

- A `LIGHT`/`CLASSICAL` pipeline is lossless under exactly the same rule as before — *"all steps are
  `ENCODING_REPAIR`"* — so adding `CLEANING` changes no lossless assertion. The registry-driven invariant
  (`test_lossless_step_is_identity_on_clean_arabic`) excludes `CLEANING` steps automatically.
- The safety audit (story 41 / issue 0016) reports a pipeline as lossless, or enumerates its lossy
  steps split by **kind** — `LINGUISTIC_FOLDING` vs `CLEANING` — which is strictly more useful than a
  single lossy bucket.
- `SafetyClass` is now a three-value `StrEnum`. Any code that exhaustively matched two values must
  handle the third; none did at introduction (only `is ENCODING_REPAIR` gate checks existed).
