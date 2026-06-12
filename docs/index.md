# araclean

Arabic text normalization and cleaning — **pure-Python, composable, reproducible, offset-preserving**.

araclean fixes mojibake and inconsistent encoding, optionally folds the spelling and vocalization
variants that fragment a vocabulary, and does it through one small, serializable interface. Its core
install pulls only [pydantic](https://docs.pydantic.dev/) — no compiler, Java, or model download.

It is **non-destructive by default**: the default profile only repairs encoding and never discards
linguistic signal. Anything lossy (removing tashkeel, folding alef/hamza, mapping digits) is
**opt-in** through a named profile, and every profile tells you exactly which steps it applies and
whether each is lossless or lossy — see [Profiles](profiles/index.md) and
[the safety contract](concepts/safety.md).

## Install

```bash
pip install araclean
```

Optional extras: `araclean[cli]`, `araclean[pandas]`, `araclean[polars]`, `araclean[emoji]`, or
`araclean[all]` — see [Getting started](getting-started.md).

## Quickstart

```pycon
>>> from araclean import normalize
>>> normalize("العـــربية")  # default LIGHT profile: lossless encoding repair (here, drops tatweel)
'العربية'
>>> normalize("اَلسّلامُ عليكم", profile="search")  # SEARCH: lossy folds that maximize recall
'السلام عليكم'

```

That's the whole surface for batch use. For span-level work — RAG citation, NER projection —
`apply_aligned` returns the normalized text *and* a map back to every original position:

```pycon
>>> from araclean import Pipeline, RemoveTatweel, FoldAlef
>>> pipe = Pipeline([RemoveTatweel(), FoldAlef()])
>>> normalized, omap = pipe.apply_aligned("أحمـد")
>>> normalized
'احمد'
>>> omap.to_original((0, 4))   # where does the whole normalized word sit in the original?
(0, 5)

```

No other Arabic NLP library exposes this. See **[Offset-preserving normalization](guides/offset-preserving.md)**.

The default `LIGHT` profile is safe to run on any corpus; reach for `SEARCH`, `ML`, `SOCIAL`, or
`CLASSICAL` when you want their specific folding. Every Python example in these docs is executed
by the test suite, so what you read is what runs.

## Where to next

**New to araclean?**

- **[Getting started](getting-started.md)** — install, the first call, and how to pick a profile.
- **[Profiles](profiles/index.md)** — what each profile does, step by step, lossless vs lossy.

**Using it day to day**

- **[Offset-preserving normalization](guides/offset-preserving.md)** — project normalized spans
  back to original text, for RAG citation and NER/QA span grounding.
- **[Command line](guides/cli.md)** — stream files, stdin/stdout, and JSONL corpora from the shell.
- **[pandas & polars](guides/dataframes.md)** — normalize a text column in one call.
- **[Tuning profiles](guides/tuning-profiles.md)** — per-knob overrides (`map_digits=True`,
  `emoji="strip"`, …) with loud validation.
- **[Composing pipelines](guides/composing-pipelines.md)** — build, filter, and reorder your own
  `Pipeline`.
- **[Writing custom steps](guides/custom-steps.md)** — drop your own transform into a pipeline.
- **[Reproducible preprocessing](guides/reproducibility.md)** — serialize the exact pipeline a
  paper or teammate can rerun.
- **[Stopword removal](guides/stopwords.md)** — the bundled, negation-safe Arabic stopword list.

**Understanding it**

- **[Why araclean](concepts/why-araclean.md)** — the rationale, and what sets it apart.
- **[The safety contract](concepts/safety.md)** — lossless vs lossy, and how to audit a pipeline.
- **[Architecture & performance](concepts/architecture.md)** — the three-layer design and the fused
  execution engine.

**Looking something up**

- **[Python API reference](reference.md)** — `normalize`, the `Pipeline`, and every `Step`.
- **[CLI reference](reference/cli.md)** — every flag of `araclean normalize`, generated from the
  CLI itself.
- **[Glossary](glossary.md)** — the Arabic terminology, glossed to English (and shown on hover).
- **[FAQ](faq.md)** — limitations, edge cases, and project policy.
