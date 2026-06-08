# Defer offset tracking; keep the Step contract minimal and alignment-ready

v1 does not implement offset/alignment tracking (mapping normalized text back to original spans).
The `Step` contract is the minimal pure `str -> str` callable, with alignment reserved as a
future, *optional* capability `Protocol` (e.g. `apply_aligned(s) -> (str, OffsetMap)`) that the
`Pipeline` can detect and use when present.

Why: usage research shows the overwhelming majority of Arabic preprocessing is corpus/training-data
prep (`df["text"].apply(clean)` → vectorizer/model), where the normalized text *is* the output and
no back-mapping is needed. Offset mapping matters only for the minority inference-time span workflow
(NER/QA over raw text), which HuggingFace tokenizers already partly cover via their own offset
mapping. A bare `str -> str` contract serves the 95% fast/simple path and avoids over-building a
focused v1 — while the reserved optional Protocol means alignment can be added later **additively**
(custom steps that don't implement it simply don't support offsets), with no breaking change.

## Consequences

- The flagged "offset tracking" differentiator is intentionally postponed, not foreclosed.
- Requesting offsets through a step that doesn't implement `apply_aligned` must raise a clear,
  actionable error.
