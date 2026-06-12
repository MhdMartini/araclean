# FAQ

## Is the default really lossless?

Yes, with a precise definition: the default LIGHT profile is *encoding repair* — it discards no
linguistic signal from Arabic-language text. Two edges are part of the contract:

- **Output is canonically equivalent, not byte-identical.** araclean emits NFC, so a
  non-canonically-encoded input comes back with the same marks in canonical order.
- **The Arabic-language assumption.** Look-alike unification (ک→ك, ی→ي, the heh family) is correct
  for Arabic text, where those code points are keyboard/encoding artifacts. The one residual: a
  Farsi yeh ی typed *word-finally* is visually identical to alef maqsura ى, so such input can merge
  على→علي even under LIGHT. If that edge matters to your corpus, drop the step:
  `Pipeline.from_profile("light").drop("UnifyLookalikes")`.

See [the safety contract](concepts/safety.md) for the full reasoning.

## Why did my tashkeel / alef hamza / ة disappear?

You ran a lossy profile. Only `SEARCH`, `ML`, and `SOCIAL` fold or remove anything, and each
[profile page](profiles/index.md) lists exactly which steps do it. The default (`LIGHT`) and
`CLASSICAL` never remove a mark. If you want most of a lossy profile but not one fold, use a
[knob](guides/tuning-profiles.md) (`teh_marbuta="keep"`, `tashkeel_classes={...}`) or
[`drop`](guides/composing-pipelines.md) the step.

## Can I use it on Persian, Urdu, or other Arabic-script languages?

Not as-is. araclean is Arabic-only by contract: several LIGHT repairs (look-alike unification
above all) treat Persian/Urdu letters as encoding artifacts to fold into Arabic ones, which is
wrong for those languages. For mixed corpora, separate by language first, or compose an explicit
pipeline without the Arabic-assuming steps.

## Does araclean stem, lemmatize, segment clitics, or tokenize?

No, deliberately. Morphology needs lexicons or models, which would end the pip-install-and-go core
(and most options drag in GPL code, Java, or torch). Compose downstream instead — e.g.
`snowballstemmer`'s Arabic algorithm (BSD, zero deps) after an araclean profile. The same goes for
dialect ID, Arabizi transliteration, and diacritization restoration. See
[Why araclean](concepts/why-araclean.md#what-araclean-is-not).

## Is normalization idempotent?

Yes. Every profile satisfies `normalize(normalize(x)) == normalize(x)`, and lossy-profile output is
LIGHT-stable (running LIGHT on SEARCH output changes nothing). Both are pinned by property-based
tests.

## How do I process a corpus that doesn't fit in memory?

Everything streams. The [CLI](guides/cli.md) processes line by line (plain text or JSONL); in
Python, `Pipeline.batch(texts)` is a lazy generator over any iterable. Build the pipeline once,
outside the loop.

## Can I find out where a normalized span sits in the original text?

Not yet. Offset/alignment tracking (`apply_aligned`) is reserved on every seam and raises a clear
`AlignmentNotSupportedError` today; it is the planned flagship of a future release, designed for
since v1. If you need provenance now, keep the raw text alongside and index by record, not offset.

## What does `demojize` need? Why an extra?

`HandleEmoji(mode="demojize")` rewrites each emoji to a text alias and needs the `emoji` library —
installed via `pip install 'araclean[emoji]'`. `keep` and `strip` are pure-Python and need nothing.
The core stays at one dependency (pydantic); everything else is opt-in extras with actionable
errors when missing.

## Is it really MIT? I've heard Arabic NLP libraries have license traps.

The distributed package is MIT with a single MIT-compatible dependency (pydantic), and the bundled
stopword list is freshly authored, CC0-1.0. GPL software (pyarabic) is used only as a *test oracle*
in the repository's dev environment — it is never imported by, distributed with, or required by
`pip install araclean` or any extra.

## How are versions and breaking changes handled?

Versions are derived from Conventional Commits (semver; the project is pre-1.0, so breaking
changes bump the minor). Profiles' behavior changes only with a version bump and a changelog entry.
The docs are versioned per release — use the version selector to match your installed package, and
pin `araclean==X.Y.Z` together with your serialized pipeline for full reproducibility (see
[Reproducible preprocessing](guides/reproducibility.md)).

## Something looks wrong — where do I report it?

[GitHub issues](https://github.com/MhdMartini/araclean/issues). Bug reports with a minimal input
string are gold: every fold is table-driven and tested against the live Unicode database, so a
counterexample usually localizes the fix to one table entry.
