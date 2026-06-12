# Tuning profiles

A named profile is a preset, not a straitjacket. `normalize` (and the CLI, and the dataframe
accessors) accept per-knob **overrides** that adjust exactly one behavior of the chosen profile:

```pycon
>>> from araclean import normalize
>>> normalize("٢٠٢٤", profile="ml")                    # ML keeps digits by default
'٢٠٢٤'
>>> normalize("٢٠٢٤", profile="ml", map_digits=True)   # opt in to the ASCII digit fold
'2024'
>>> normalize("جميييييل", profile="ml", elongation_cap=2)  # keep a doubled letter as emphasis
'جمييل'

```

Every override is validated up front against `NormalizeConfig` — a pydantic model with
`extra="forbid"` — so a typo'd knob or a bad value fails loudly at the call, and an override that
names a step the profile does not carry is rejected rather than silently doing nothing:

```pycon
>>> try:
...     normalize("نص", profile="light", emoji="strip")  # LIGHT has no HandleEmoji step
... except ValueError as error:
...     print(error)
override(s) ['emoji'] do not apply to profile 'light': it has no matching step to configure.

```

This is a reproducibility guarantee, not pedantry: a knob that silently no-ops is a preprocessing
description that lies. See [Reproducible preprocessing](reproducibility.md).

## The knobs

| Knob | Applies to | What it does |
|------|------------|--------------|
| `map_digits` | `ml` only | `True` **appends** a `MapDigits` fold to ASCII. ML-only because SEARCH already folds digits and the lossless profiles must stay lossless. |
| `remove_stopwords` | `search` only | `True` **inserts** `RemoveStopwords` (plus a closing `Trim`) after the letter folds — see [Stopword removal](stopwords.md). |
| `emoji` | `social` | `keep` (default) / `strip` / `demojize` (needs the `[emoji]` extra). |
| `elongation_cap` | `search`, `ml`, `social` | Max repeated letters kept by `ReduceElongation` (SEARCH/ML default 1, SOCIAL 2). |
| `url_mode`, `url_token` | `social` | Delete URLs or replace with a placeholder token (SOCIAL default: `[رابط]`). |
| `mention_mode`, `mention_token` | `social` | Same for @mentions (SOCIAL default: `[مستخدم]`). |
| `hashtag_mode`, `hashtag_token` | `social` | `segment` (default: `#اليوم_الوطني` → `اليوم الوطني`) / `delete` / `placeholder` / `keep`. |
| `teh_marbuta` | `search` | Fold ة to `heh` (default) or `teh`, or `keep` it. |
| `tashkeel_classes` | `search`, `ml`, `social` | Which mark classes `RemoveTashkeel` removes: any subset of `harakat`, `tanween`, `shadda`, `madda`, `dagger_alef`, `quranic`. |
| `collapse_lines` | every profile | Flatten line breaks to spaces (`True`) or keep line structure (`False`). Only SEARCH flattens by default. |

Some examples:

```pycon
>>> normalize("مَدْرَسَةٌ", profile="search")                       # default: ة → ه
'مدرسه'
>>> normalize("مَدْرَسَةٌ", profile="search", teh_marbuta="keep")   # keep ة, still fold the rest
'مدرسة'
>>> normalize("كِتَابٌ", profile="ml", tashkeel_classes={"tanween"})  # remove only tanween
'كِتَاب'
>>> normalize("سطر١\nسطر٢", profile="search", collapse_lines=False)  # SEARCH, but keep lines
'سطر1\nسطر2'

```

The same knobs exist as CLI flags (`--map-digits`, `--emoji strip`, `--teh-marbuta keep`, …) and as
keyword arguments on the dataframe accessors — one override surface, three entry points.

## When a knob is not enough

Overrides patch the steps a profile already carries (plus the two documented append/insert cases).
If you want a different step *sequence* — drop a fold, add `MapQuotes`, reorder — compose a
pipeline explicitly instead: see [Composing pipelines](composing-pipelines.md).

For programmatic use, the same configuration exists as a frozen pydantic model you can build,
serialize, and pass around:

```pycon
>>> from araclean import NormalizeConfig, normalize
>>> config = NormalizeConfig(profile="ml", map_digits=True)
>>> normalize("٢٠٢٤", config=config)
'2024'

```
