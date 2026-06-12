# pandas & polars

araclean registers an `.araclean` accessor on pandas and polars Series, so normalizing a text
column is one idiomatic call. Both adapters validate their arguments through the same trust
boundary as `normalize`, build the pipeline **once**, and map it over the column — they hold no
normalization logic of their own.

Each lives behind its extra:

```bash
pip install 'araclean[pandas]'   # or 'araclean[polars]', or 'araclean[all]'
```

## pandas

Importing `araclean.pandas` registers the accessor (importing it without pandas installed raises a
clear error naming the extra):

```pycon
>>> import pandas as pd
>>> import araclean.pandas
>>> s = pd.Series(["العـــربية", "اَلسّلامُ عليكم"])
>>> s.araclean.normalize(profile="search").tolist()
['العربيه', 'السلام عليكم']

```

In a dataframe workflow:

```pycon
>>> df = pd.DataFrame({"text": ["جميييييل 😍 https://t.co/xyz"]})
>>> df["text"].araclean.normalize(profile="social", emoji="strip").tolist()
['جمييل [رابط]']

```

Missing values (`NaN`/`None`) pass through unchanged (`na_action="ignore"`); empty strings
normalize to empty strings.

## polars

Importing `araclean.polars` registers the namespace, mirroring the pandas accessor:

```pycon
>>> import polars as pl
>>> import araclean.polars
>>> s = pl.Series(["العـــربية", "اَلسّلامُ عليكم"])
>>> s.araclean.normalize(profile="search").to_list()
['العربيه', 'السلام عليكم']

```

Use it inside an expression pipeline via `map_batches` on the column, or normalize the Series and
reattach it:

```pycon
>>> df = pl.DataFrame({"text": ["العـــربية"]})
>>> df.with_columns(df["text"].araclean.normalize(profile="search").alias("text")).to_dicts()
[{'text': 'العربيه'}]

```

Null values pass through unchanged; the result is a String Series, value-for-value identical to
what the pandas accessor produces.

## Overrides and errors

Both accessors take the same `profile` plus per-knob `**overrides` as
[`normalize`](../reference.md) — `map_digits=True`, `emoji="strip"`, `teh_marbuta="keep"`, … An
unknown profile, knob, or value raises the same clear error as the facade, before any row is
touched. See [Tuning profiles](tuning-profiles.md).

## Performance notes

The pipeline is assembled and validated once per call, not once per row — the per-row work is the
optimized core (see [Architecture & performance](../concepts/architecture.md)). For very large
datasets prefer the [CLI](cli.md) on JSONL, which streams without materializing the corpus, or
`Pipeline.batch` over an iterator in Python.
