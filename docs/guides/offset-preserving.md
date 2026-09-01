# Offset-preserving normalization

`apply_aligned` normalizes text while keeping a map between the normalized and original strings.

## The problem

Search and ML profiles change the text: tatweel is stripped, alef variants fold, and tashkeel may
disappear. If you then need to

- **cite a span** in the original document (RAG answer grounding)
- **project a model prediction** back to raw text (NER / span annotation)

the character positions need to remain traceable through those changes.

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
original = "قال أحمـد: على قدر أهل العزم"
normalized, omap = pipe.apply_aligned(original)

# Retrieval-time: a search hit in the normalized index gives a span
# Suppose a fuzzy search found "احمد" somewhere in the normalized text
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

original_doc = "وَقَفَ الشاعرُ محمـدٌ أمامَ الجمهورِ"
normalized, omap = pipe.apply_aligned(original_doc)

# A NER model running on normalized text predicts a PERSON span
ner_start = normalized.index("محمد")
ner_end = ner_start + len("محمد")

# Project to original text
orig_start, orig_end = omap.to_original((ner_start, ner_end))
original_span = original_doc[orig_start:orig_end]
print(original_span)   # "محمـد" — the original spelling, tatweel intact (the deleted
                       # trailing tanween sits past the span: it produced no normalized char)
```

## What the map tracks

Every normalization step is one of a few operation kinds, each tracked by the map:

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
from araclean import OffsetMap, SafetyClass

class MyStep:
    safety = SafetyClass.ENCODING_REPAIR

    def __call__(self, s: str, /) -> str:
        return s.replace("x", "y")  # 1→1 replace

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        # 1→1 replacement: length is unchanged, each char maps to itself
        return self(s), OffsetMap.identity(len(s))
```

For deletions or multi-char substitutions, use `OffsetMap.from_translate` or
`OffsetMap.from_regex_sub` — see the [`OffsetMap` API reference](../reference.md#offset-maps).
