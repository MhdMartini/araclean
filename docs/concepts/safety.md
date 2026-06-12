# The safety contract

Every araclean step declares what kind of information it may discard — its **safety class** — and a
pipeline can be audited against that declaration. This is the library's core contract: nothing is
lost unless you opted in, and what you opted into is machine-checkable.

## The three classes

| Safety class | Lossless? | What it touches |
|--------------|-----------|-----------------|
| `encoding_repair` | ✓ lossless | Repairs the *encoding*: Unicode form (NFC), presentation forms, tatweel, bidi/zero-width controls, look-alike letters, whitespace runs. No linguistic signal is discarded. |
| `linguistic_folding` | ✗ lossy | Discards a distinction *within* the Arabic text: tashkeel removal, alef/hamza/teh-marbuta/alef-maqsura folds, digit and punctuation mapping, elongation reduction, stopword removal. |
| `cleaning` | ✗ lossy | Removes *non-linguistic noise* around the text: URLs, mentions, hashtags, HTML, emoji handling, foreign-script spans. |

Linguistic folding and cleaning are siblings, not synonyms — stripping a URL is not a statement
about Arabic, and folding an alef is not noise removal. Keeping them separate lets the audit say
precisely what a pipeline does: *"this pipeline folds 3 distinctions and removes 2 kinds of
noise"*, not just "it's lossy".

A pipeline is **lossless** exactly when every step is `encoding_repair`. The default LIGHT profile
(and CLASSICAL) is all-`encoding_repair` by construction; the other profiles are lossy and
therefore opt-in — the [profile pages](../profiles/index.md) label every step.

## Auditing a pipeline

The contract is queryable. `audit()` reads each step's declared class and buckets the names, in
pipeline order:

```pycon
>>> from araclean import Pipeline
>>> Pipeline.from_profile("light").audit().lossless
True
>>> report = Pipeline.from_profile("social").audit()
>>> report.lossless
False
>>> report.cleaning
('CleanURLs', 'CleanMentions', 'CleanHashtags', 'CleanHTML')
>>> report.linguistic_folding
('RemoveTashkeel', 'ReduceElongation')

```

This works for adapted pipelines and [custom steps](../guides/custom-steps.md) too — whatever you
assembled, the report reflects the steps actually in it. Note that some steps' class depends on
their configuration: `HandleEmoji(mode="keep")` is a lossless no-op (`encoding_repair`), while
`strip`/`demojize` are `cleaning` — the declared class always describes the configured behavior.

## What "lossless" means precisely

Lossless is defined over *Arabic-language text content*, with three deliberate edges:

1. **Canonical equivalence, not byte identity.** araclean treats canonically-equivalent Unicode
   sequences as the same text. Output is always NFC, so a non-canonically-ordered input comes back
   with its marks in canonical order — every mark preserved, the bytes possibly different. This is
   also what makes every profile idempotent: normalizing twice equals normalizing once.
2. **The Arabic-language assumption.** Look-alike unification (ک→ك, ی→ي, the heh family) is
   lossless *for Arabic text*, where those code points are typing/encoding artifacts. For Persian
   or Urdu content they are real letters — araclean is Arabic-only by contract, and one residual
   follows from it (the word-final Farsi yeh, see the [FAQ](../faq.md)).
3. **Line structure is content.** Whitespace runs collapse, but a run containing a line break
   collapses to a newline, not a space — flattening lines loses document structure, so it is
   opt-in (`collapse_lines=True`; only SEARCH does it by default, where bag-of-words matching wants
   it).

## Loud failure over silent drift

The same philosophy governs configuration. Overrides are validated against a closed model: an
unknown profile, a typo'd knob, or a knob that does not apply to the chosen profile raises
immediately —

```pycon
>>> from araclean import normalize
>>> try:
...     normalize("نص", profile="light", emoji="strip")
... except ValueError as error:
...     print(error)
override(s) ['emoji'] do not apply to profile 'light': it has no matching step to configure.

```

— because a preprocessing option that silently no-ops is a description of your data that lies.
The same applies across the API: `drop()` on an absent step name raises, deserializing against a
mismatched stopword-list version raises, and `map_digits=True` is rejected on any profile whose
contract it would silently change.

The safety classes, the non-destructive default, and the loud-validation rule are recorded as
architecture decisions in the repository (ADR-0004, ADR-0009, ADR-0010, ADR-0011) if you want the
full reasoning trail.
