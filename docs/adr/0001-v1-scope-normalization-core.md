# v1 scope: normalization/cleaning core, morphology deferred

v1 is scoped to the **normalization/cleaning core** — character- and Unicode-level reshaping
and noise removal, pure-Python — and deliberately excludes morphology-dependent features
(stemming, clitic tokenization, lemmatization, dialect/Arabizi handling, trained
spaCy/HuggingFace pipelines).

Why: the survey of incumbents (pyarabic, CAMeL Tools, Farasa, Maha, tashaphyne, arabicstopwords)
showed the clear, winnable gap is an install-trivial, fully typed, well-documented,
*non-destructive* normalizer. Morphology is where quality depends on data/models and where
CAMeL/Farasa already compete hard. A focused v1 can be shipped to excellence and stay pure-Python.

## Consequences

- The architecture must keep morphology-dependent features addable later as optional extras
  without breaking the core API.
- The reference repos do more than v1 does (e.g. tashaphyne stemming, arabicstopwords). This
  "no" is deliberate, not an oversight.
