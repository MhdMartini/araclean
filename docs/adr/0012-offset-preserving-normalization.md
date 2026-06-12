# Implement offset-preserving normalization via `OffsetMap`

**Status:** Accepted — supersedes ADR-0005 (defer offset tracking)

---

## Context

ADR-0005 reserved `apply_aligned()` on the `Step` and `Pipeline` seams but deferred the
implementation.  The ROADMAP identified this as **Phase 2 Bet 1**: the flagship differentiator
of araclean v1.0, because *no Arabic NLP library* — not CAMeL, PyArabic, or Maha — can tell
you where a normalized span sits in the original text.

Two growth use-cases require it:

- **RAG**: index and search the normalized text, but cite and highlight in the *original*
  document.  Without provenance, every RAG stack over Arabic either skips normalization (losing
  recall) or loses grounding.
- **NER / span annotation**: models run on normalized text; gold spans and downstream consumers
  live on raw text.  Offset projection is the standard fix (HuggingFace `tokenizers` does it for
  their own normalizers) and nobody offers it for Arabic-specific folds.

## Decision

Implement `apply_aligned(text) -> (str, OffsetMap)` on every built-in `Step` and on `Pipeline`,
composing per-step maps into one final map that links any normalized span back to the original.

### `OffsetMap` (`src/araclean/offsets.py`)

A compact flat list: for normalized character *i*, entries `[2i, 2i+1]` store
`(orig_start, orig_end)` in the original string.  Public surface:

```python
omap.to_original((start, end)) -> (orig_start, orig_end)
omap.to_normalized((start, end)) -> (norm_start, norm_end)   # best-effort for lossy ops
```

Factory helpers for the three normalization operation kinds:

| Kind | Factory | Examples |
|------|---------|---------|
| No-op | `OffsetMap.identity(n)` | — |
| `str.translate` (1→0, 1→1, 1→N) | `OffsetMap.from_translate(s, table)` | `RemoveTatweel`, `FoldAlef`, `FoldPresentationForms` |
| Regex substitution | `OffsetMap.from_regex_sub(s, spans, rep_lens)` | `CollapseWhitespace`, `CleanURLs`, … |

`OffsetMap.compose(other)` chains two maps (`self`: norm1→orig, `other`: norm2→norm1) to
produce norm2→orig.

### `apply_aligned` on steps

Every built-in step implements `apply_aligned(s) -> (str, OffsetMap)`:

- **Translate steps** (`FoldPresentationForms`, `RemoveTatweel`, `UnifyLookalikes`,
  `FoldAlef`, `FoldAlefMaqsura`, `FoldHamza`, `FoldTehMarbuta`, `MapDigits`,
  `RemoveTashkeel(position="all")`, `RemovePunctuation`, `MapQuotes`): one call to
  `OffsetMap.from_translate(s, self.translate_table)`.
- **Regex steps** (`CollapseWhitespace`, `ReduceElongation`, `MapPunctuation`,
  `FoldTanweenAlef`, `RemoveTashkeel(position="final")`, `CleanURLs`, `CleanMentions`,
  `CleanHashtags`, `HandleEmoji(STRIP)`, `RemoveForeign`, `RemoveStopwords`): collect match
  spans via `_collect_regex_sub`, then `OffsetMap.from_regex_sub`.
- **Multi-pass steps** (`StripBidi`: regex + translate; `CleanHTML`: tags + html.unescape;
  `MapDigits(map_separators=True)`: translate + regex): chain sub-step maps with `.compose()`.
- **`NormalizeUnicode`**: `unicodedata.normalize` can change the code-point count; alignment
  uses `difflib.SequenceMatcher` for correctness across all forms (in practice, NFC on Arabic
  is identity and the fast-path returns `OffsetMap.identity` immediately).
- **`Trim`**: leading whitespace count gives the offset; each normalized char maps to
  `orig[lead+i : lead+i+1]`.
- **`HandleEmoji(KEEP)`**: identity map.

### `Pipeline.apply_aligned`

Iterates `self._steps` (not `self._plan` — the fused plan merges steps), calls each step's
`apply_aligned`, and accumulates via `running = running.compose(step_map)`.  Raises
`AlignmentNotSupportedError` for any custom step that has not implemented the hook.

### Key invariant (property test)

For any text through a pipeline of lossless (ENCODING_REPAIR) steps:

```python
normalized, omap = pipe.apply_aligned(text)
for start in range(len(normalized) + 1):
    for end in range(start, len(normalized) + 1):
        orig_start, orig_end = omap.to_original((start, end))
        assert 0 <= orig_start <= orig_end <= len(text)
```

Verified by Hypothesis over the `LIGHT` profile.

## Consequences

- `Pipeline.apply_aligned()` is now fully functional for all built-in steps.
- The `AlignmentNotSupportedError` / `SupportsAlignment` protocol machinery is retained:
  custom steps that omit `apply_aligned` still raise a clear, actionable error naming the step.
- The `str -> str` contract of `__call__` is unchanged — `apply_aligned` is additive.
- `OffsetMap` is exported from `araclean.__init__` as part of the public API.
- ADR-0005 is superseded; the "offset tracking deferred" placeholder is gone.
