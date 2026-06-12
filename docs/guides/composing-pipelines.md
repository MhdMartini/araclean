# Composing pipelines

When a profile plus [knobs](tuning-profiles.md) is not enough, drop one layer down: a `Pipeline` is
an ordered sequence of `Step`s, callable like a single `str -> str` function. Profiles are nothing
more than named, serializable recipes for pipelines — everything they do, you can do explicitly.

## From a profile

```pycon
>>> from araclean import Pipeline
>>> pipe = Pipeline.from_profile("light")
>>> pipe
Pipeline([NormalizeUnicode, StripBidi, FoldPresentationForms, RemoveTatweel, UnifyLookalikes, CollapseWhitespace, NormalizeUnicode])
>>> pipe("العـــربية")
'العربية'

```

Building the pipeline once and reusing it is the fast path: all validation and table-building
happens at construction, so the per-string call does no setup. For a stream or a corpus, `batch`
is a lazy generator — nothing is materialized:

```pycon
>>> list(pipe.batch(["العـــربية", "ﻣﺮﺣﺒﺎ"]))
['العربية', 'مرحبا']

```

## Adapting a profile: `drop` and `select`

The common adaptation is subtraction — "SEARCH, but don't touch digits or punctuation":

```pycon
>>> Pipeline.from_profile("search").drop("MapDigits", "MapPunctuation")
Pipeline([NormalizeUnicode, StripBidi, FoldPresentationForms, RemoveTatweel, UnifyLookalikes, CollapseWhitespace, NormalizeUnicode, FoldTanweenAlef, RemoveTashkeel, FoldAlef, FoldHamza, FoldTehMarbuta, FoldAlefMaqsura, ReduceElongation, CollapseWhitespace, NormalizeUnicode])

```

`drop` removes **every** step carrying a name and raises `KeyError` for a name no step carries — a
typo is never a silent no-op. `select` is the additive twin: it builds a new pipeline holding
exactly the named steps, in the order you give, so one primitive covers both filtering and
reordering:

```pycon
>>> Pipeline.from_profile("light").select("StripBidi", "RemoveTatweel")
Pipeline([StripBidi, RemoveTatweel])

```

Both return a **new** pipeline; the original is unchanged. If a name matches several
*differently-configured* copies of a step (SEARCH carries two differently-configured
`CollapseWhitespace` copies), `select` raises rather than guess which one you meant — use `drop`,
or build explicitly.

## Building from explicit steps

Every step is a frozen, reusable object. Construct exactly the sequence you want:

```pycon
>>> from araclean import CollapseWhitespace, NormalizeUnicode, RemoveTashkeel, Trim
>>> pipe = Pipeline([NormalizeUnicode(), RemoveTashkeel(), CollapseWhitespace(), Trim()])
>>> pipe("  مَرْحَبًا  بِكُمْ  ")
'مرحبا بكم'

```

Steps take their configuration at construction — `RemoveTashkeel(classes={"tanween"})`,
`FoldTehMarbuta(target="teh")`, `ReduceElongation(cap=2)`, `CleanURLs(mode="placeholder",
placeholder="[رابط]")` — see the [API reference](../reference.md) for every step and its options.

Two conventions worth copying from the built-in profiles:

- **Open and close with `NormalizeUnicode()` (NFC), and close with `CollapseWhitespace()`.** Folds
  and deletions can re-expose whitespace gaps and non-canonical mark order mid-pipeline; the
  closing pair restores the "whitespace-collapsed NFC output" postcondition every built-in profile
  guarantees.
- **Order is a contract.** For example, `FoldTanweenAlef` must run *before* `RemoveTashkeel` (it
  needs the tanween still present to recognize a carrier alef), and cleaning steps run before
  linguistic folds in SOCIAL. The per-profile pages document the load-bearing orderings.

Some orderings are enforced for you. A step can declare `requires_before`, and `Pipeline` checks it
at construction — not per string:

```pycon
>>> from araclean import RemoveStopwords
>>> Pipeline([RemoveStopwords()])
Traceback (most recent call last):
  ...
ValueError: Step 'RemoveStopwords' requires ['RemoveTashkeel', 'FoldAlef', 'FoldAlefMaqsura', 'FoldHamza'] to run before it in the pipeline ...

```

## One-off calls: the bare functions

Every built-in step also exists as a plain function (Layer 1 of the API), for when you want one
transform without building anything:

```pycon
>>> from araclean import fold_alef, map_digits, remove_tatweel
>>> remove_tatweel("محـــمد")
'محمد'
>>> fold_alef("أحمد إلى آخر")
'احمد الى اخر'
>>> map_digits("٠١٢٣٤٥٦٧٨٩")
'0123456789'

```

The naming is mechanical: step class `RemoveTatweel` ↔ function `remove_tatweel`, with the same
options as keyword arguments. The functions do no validation — they are the hot path the steps
themselves call.

## Auditing what you built

Any pipeline — adapted, explicit, or with [custom steps](custom-steps.md) — can report whether it
is lossless and exactly which steps lose what:

```pycon
>>> report = Pipeline.from_profile("search").audit()
>>> report.lossless
False
>>> report.lossy_steps
('FoldTanweenAlef', 'RemoveTashkeel', 'FoldAlef', 'FoldHamza', 'FoldTehMarbuta', 'FoldAlefMaqsura', 'MapDigits', 'MapPunctuation', 'ReduceElongation')

```

See [the safety contract](../concepts/safety.md) for what the classes mean, and
[Reproducible preprocessing](reproducibility.md) for serializing a pipeline so others can rerun it.
