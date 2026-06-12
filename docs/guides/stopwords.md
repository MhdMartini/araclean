# Stopword removal

araclean bundles a curated, versioned Arabic stopword list — Modern Standard Arabic function words
(prepositions, pronouns, demonstratives, relative pronouns, neutral conjunctions and particles) —
behind the `RemoveStopwords` step. It is freshly authored for araclean and dedicated to the public
domain (CC0-1.0), so it carries no copyleft into your project.

## Turning it on

Stopword removal is an opt-in knob of the SEARCH profile:

```pycon
>>> from araclean import normalize
>>> normalize("ذهبنا في الصباح الى المدرسة", profile="search", remove_stopwords=True)
'ذهبنا الصباح المدرسه'

```

(or `--remove-stopwords` on the [CLI](cli.md)). It is SEARCH-only by design: the list ships in
**folded** spelling, so it requires exactly the letter folds SEARCH runs before it — see the
ordering contract below.

## Negation-safe by default

The headline design decision: the polarity-bearing particles — `لا`, `ما`, `لم`, `لن`, `ليس` — are
**deliberately excluded** from the list. A naive stopword list deletes them as "frequent function
words", silently flipping the meaning of a sentence (`لا أحب` *I don't like* → `أحب` *I like*) —
a real hazard in shipped Arabic stopword lists. With araclean, removal can never invert polarity:

```pycon
>>> normalize("لا أحب الانتظار", profile="search", remove_stopwords=True)
'لا احب الانتظار'

```

The exclusion is exported as `NEGATION_PARTICLES` and enforced by an import-time integrity check —
a list edit that violates it cannot ship.

## Whole tokens only — no clitic stripping

The list is flat, not morphology-aware. Only a *standalone* token is removed; a function word
fused into a longer token as a proclitic or suffix is kept:

```pycon
>>> normalize("والكتاب فيها", profile="search", remove_stopwords=True)  # و+الكتاب, في+ها: kept
'والكتاب فيها'

```

This is a deliberate boundary: clitic segmentation is morphology, which araclean's core excludes
by design. If you need clitic-aware removal, run a segmenter first and compose.

## Why the list ships folded

Real typed Arabic routinely omits hamza (`الى` for `إلى`), and vocalized text never matches a bare
list. Instead of enumerating every spelling variant, araclean stores each entry once, in the
spelling that exists *after* `RemoveTashkeel` + `FoldAlef` + `FoldAlefMaqsura` + `FoldHamza` — and
lets the pipeline itself be the variant generator: the canonical `إلى`, the hamza-less `الى`, and
the vocalized `إلَى` all fold to the one entry.

That makes ordering a hard contract, not a convention: `RemoveStopwords` declares it
`requires_before` those folds, and `Pipeline` rejects at construction any pipeline where they do
not precede it (see [Composing pipelines](composing-pipelines.md)). SEARCH with
`remove_stopwords=True` inserts the step in the right place for you.

## Using the list directly

The data is public API, importable without running any step:

```pycon
>>> from araclean.stopwords import NEGATION_PARTICLES, STOPWORDS, STOPWORDS_VERSION
>>> "في" in STOPWORDS
True
>>> STOPWORDS.isdisjoint(NEGATION_PARTICLES)
True

```

`STOPWORDS_VERSION` identifies the exact list revision; serialized pipelines pin it, and
rehydrating against a release with a different list fails loudly instead of removing different
words — see [Reproducible preprocessing](reproducibility.md).

Want a *different* list? Compose a [custom step](custom-steps.md) — `RemoveStopwords` deliberately
takes no word-list parameter, so that "the bundled list, version X" is the whole story a serialized
pipeline has to tell.
