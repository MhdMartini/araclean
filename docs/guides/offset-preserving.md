# Offset-preserving normalization

araclean's flagship differentiator: normalize text *and* keep a map from every position in the
normalized string back to the original.  No other Arabic NLP library exposes this.

## The problem

When you normalize Arabic for search or ML, you change the text.  Tatweel is stripped, alef
variants fold, tashkeel disappears.  That is fine for indexing — but the moment you need to:

- **cite a span** in the original document (RAG answer grounding)
- **project a model prediction** back to raw text (NER / span annotation)

you need to know *where* the normalized span came from.  Without an offset map, you have two bad
choices: skip normalization (losing recall) or lose provenance.

## The solution: `apply_aligned`

Every built-in step and every `Pipeline` exposes `apply_aligned`:

```python
normalized, omap = pipe.apply_aligned(text)
```

`omap` is an `OffsetMap`.  Its public surface is two methods:

| Method | Direction | Use |
|--------|-----------|-----|
| `omap.to_original((start, end))` | normalized → original | Project a model span back to raw text |
| `omap.to_normalized((start, end))` | original → normalized | Find where an original span ended up |

Spans are half-open `[start, end)` intervals over Unicode code points, matching Python's
`str[start:end]` slice convention.

## RAG: cite in original, search in normalized

```python
from araclean import Pipeline, RemoveTatweel, FoldAlef, RemoveTashkeel

pipe = Pipeline([RemoveTatweel(), FoldAlef(), RemoveTashkeel()])

# Index-time: normalize, store the original
original = "كتاب أحمـد الكبير"
normalized, omap = pipe.apply_aligned(original)

# Retrieval-time: a search hit in the normalized index gives a span
# Suppose a fuzzy search found "احمد" at position 6 in the normalized text
found_start = normalized.index("احمد")
found_end = found_start + len("احمد")

# Project back to the original for citation
orig_start, orig_end = omap.to_original((found_start, found_end))
citation = original[orig_start:orig_end]
print(citation)   # "أحمـد" — the original spelling, with tatweel and hamza intact
```

## NER: project model output to original text

```python
from araclean import Pipeline, FoldAlef, RemoveTashkeel, RemoveTatweel

pipe = Pipeline([RemoveTatweel(), RemoveTashkeel(), FoldAlef()])

original_doc = "قال الرئيسُ محمـدٌ في المؤتمرِ"
normalized, omap = pipe.apply_aligned(original_doc)

# A NER model running on normalized text predicts a PERSON span
ner_start, ner_end = 12, 16  # "محمد" in normalized

# Project to original text
orig_start, orig_end = omap.to_original((ner_start, ner_end))
original_span = original_doc[orig_start:orig_end]
print(original_span)   # "محمـدٌ" — the original spelling in the source document
```

## What the map tracks

Every normalization step is one of three operation kinds, all of which araclean tracks exactly:

| Kind | Examples | Alignment |
|------|---------|-----------|
| `str.translate` 1→0 (delete) | `RemoveTatweel`, `RemoveTashkeel` | Deleted char leaves no normalized char; the next normalized char points past it |
| `str.translate` 1→1 (replace) | `FoldAlef`, `MapDigits` | One-to-one; position is preserved |
| `str.translate` 1→N (expand) | `FoldPresentationForms` (lam-alef ligature → two chars) | Both result chars point back to the one source char |
| Regex substitution N→M | `CollapseWhitespace`, `CleanURLs`, `ReduceElongation` | Each replacement char points to the whole matched span |

Pipeline composition chains the per-step maps automatically.

## Composing across profiles

`apply_aligned` works with any pipeline, including named profiles:

```python
from araclean import Pipeline, SEARCH

pipe = Pipeline.from_profile(SEARCH)
normalized, omap = pipe.apply_aligned("وَقَالَ الرَّئيسُ")
```

The output of `pipe(text)` is always identical to the `normalized` from `apply_aligned` — the
method only adds the map, never changes the normalization.

## Custom steps

A custom step that does not implement `apply_aligned` raises `AlignmentNotSupportedError` when
`Pipeline.apply_aligned` reaches it.  Add the hook to opt in:

```python
from araclean.offsets import OffsetMap
from araclean.safety import SafetyClass

class MyStep:
    safety = SafetyClass.ENCODING_REPAIR

    def __call__(self, s: str, /) -> str:
        return s.replace("x", "y")  # 1→1 replace

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        # 1→1 replacement: length is unchanged, each char maps to itself
        return self(s), OffsetMap.identity(len(s))
```

For deletions or multi-char substitutions, use `OffsetMap.from_translate` or
`OffsetMap.from_regex_sub` — see the [`OffsetMap` API reference](../reference.md#offsetmap).
