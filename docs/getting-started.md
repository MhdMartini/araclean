# Getting started

araclean needs Python 3.12+ and installs in seconds: the core depends only on
[pydantic](https://docs.pydantic.dev/) — no compiler, no Java, no model download.

## Install

```bash
pip install araclean
```

Everything beyond the Python API lives behind optional extras, so the core stays lean:

| Extra | Installs | Gives you |
|-------|----------|-----------|
| `araclean[cli]` | [Typer](https://typer.tiangolo.com/) | the `araclean` shell command — see the [CLI guide](guides/cli.md) |
| `araclean[pandas]` | pandas | the `.araclean` Series accessor — see [pandas & polars](guides/dataframes.md) |
| `araclean[polars]` | polars | the `.araclean` Series namespace — see [pandas & polars](guides/dataframes.md) |
| `araclean[emoji]` | [emoji](https://pypi.org/project/emoji/) | `HandleEmoji`'s `demojize` mode (`keep`/`strip` need nothing) |
| `araclean[all]` | all of the above | everything |

Using a feature without its extra never crashes with a bare `ImportError`: you get a clear error
naming the exact `pip install` command to run.

## Your first normalization

The whole quick-use surface is one function:

```pycon
>>> from araclean import normalize
>>> normalize("ﻣﺮﺣﺒﺎ")  # OCR/copy-paste presentation forms fold back to real letters
'مرحبا'
>>> normalize("العـــربية")  # tatweel (visual elongation) is dropped
'العربية'

```

With no `profile`, `normalize` applies the **LIGHT** profile: *lossless encoding repair*. It fixes
the Unicode form, strips invisible bidi/zero-width characters, folds presentation-form glyphs back
to letters, removes tatweel, unifies look-alike letters (Persian keheh ک → Arabic kaf ك), and
collapses whitespace. It never removes tashkeel, never folds alef variants, never touches digits —
it discards no linguistic signal, so it is safe to run on any Arabic corpus, including vocalized or
Qur'anic text.

## Choosing a profile

Anything lossy is opt-in through a named profile. Pass the name to `normalize`:

```pycon
>>> normalize("عَلَى")                    # LIGHT: vocalization and spelling preserved
'عَلَى'
>>> normalize("عَلَى", profile="search")  # SEARCH: tashkeel removed, alef maqsura folded
'علي'
>>> normalize("جميييييل", profile="ml")   # ML: dediacritize + collapse emphatic elongation
'جميل'
>>> normalize("رااااائع 😍 https://t.co/xyz", profile="social")  # SOCIAL: clean noise, keep emoji
'راائع 😍 [رابط]'

```

Pick by task:

| You are doing | Use | Why |
|---------------|-----|-----|
| anything — you just want clean, consistent text | [`LIGHT`](profiles/light.md) (default) | lossless; repairs encoding only |
| search / retrieval / matching | [`SEARCH`](profiles/search.md) | folds spelling & vocalization variants so على matches علي |
| training or feeding a model | [`ML`](profiles/ml.md) | dediacritizes and caps elongation, but keeps letter distinctions that carry signal |
| social-media text | [`SOCIAL`](profiles/social.md) | cleans URLs/mentions/HTML, segments hashtags, keeps emoji |
| vocalized / classical / Qur'anic text | [`CLASSICAL`](profiles/classical.md) | lossless repair with an explicit every-mark-preserved guarantee |

Each profile page lists the exact steps it runs, in order, each labelled lossless or lossy — the
pages are generated from the assembled pipelines themselves, so they cannot drift from the code.

## Beyond one call

- Process files from the shell: `pip install 'araclean[cli]'`, then
  `araclean normalize corpus.txt --profile search` — see the [CLI guide](guides/cli.md).
- Normalize a dataframe column: `df["text"].araclean.normalize(profile="search")` — see
  [pandas & polars](guides/dataframes.md).
- Adjust one knob of a profile (`map_digits=True`, `emoji="strip"`, …) — see
  [Tuning profiles](guides/tuning-profiles.md).
- Assemble your own step sequence — see [Composing pipelines](guides/composing-pipelines.md).
- Understand exactly what you might be discarding — see [the safety contract](concepts/safety.md).
