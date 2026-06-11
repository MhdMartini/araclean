# araclean

Arabic text normalization and cleaning — **pure-Python, composable, reproducible**.

araclean fixes mojibake and inconsistent encoding, optionally folds the spelling and vocalization
variants that fragment a vocabulary, and does it through one small, serializable interface. Its core
install pulls only [pydantic](https://docs.pydantic.dev/) — no compiler, Java, or model download.

It is **non-destructive by default**: the default profile only repairs encoding and never discards
linguistic signal. Anything lossy (removing tashkeel, folding alef/hamza, mapping digits) is
**opt-in** through a named profile, and every profile tells you exactly which steps it applies and
whether each is lossless or lossy — see [Profiles](profiles/index.md).

## Install

```bash
pip install araclean
```

Optional extras: `araclean[cli]`, `araclean[pandas]`, `araclean[polars]`, or `araclean[all]`.

## Quickstart

```pycon
>>> from araclean import normalize
>>> normalize("العـــربية")  # default LIGHT profile: lossless encoding repair (here, drops tatweel)
'العربية'
>>> normalize("اَلسّلامُ عليكم", profile="search")  # SEARCH: lossy folds that maximize recall
'السلام عليكم'

```

That's the whole surface: one `normalize` call, a profile to pick the trade-off. The default
`LIGHT` profile is safe to run on any corpus; reach for `SEARCH`, `ML`, `SOCIAL`, or `CLASSICAL`
when you want their specific folding.

## Where to next

- **[Profiles](profiles/index.md)** — what each profile does, step by step, lossless vs lossy.
- **[Glossary](glossary.md)** — the Arabic terminology, glossed to English (and shown on hover).
- **[API reference](reference.md)** — `normalize`, the `Pipeline`, and every `Step`.
