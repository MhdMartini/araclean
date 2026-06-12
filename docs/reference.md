# API reference

The whole public surface: the one-call `normalize` facade, the `Pipeline` it assembles, the
configuration boundary, and every `Step`. Each Arabic term below is glossed to English on hover
(ADR-0007); searching the English name (e.g. *diacritics*) finds the Arabic-primary step
(`RemoveTashkeel`). For the `araclean` shell command, see the [CLI reference](reference/cli.md).

## The `normalize` facade

::: araclean.normalize

## Pipelines & profiles

::: araclean.Pipeline

::: araclean.Profile

## Configuration

The validated override surface behind `normalize(..., profile=…, **overrides)` — see
[Tuning profiles](guides/tuning-profiles.md) for the task-oriented view.

::: araclean.NormalizeConfig

::: araclean.ProfileName

## Safety classes (the lossless / lossy split)

::: araclean.SafetyClass

::: araclean.SafetyReport

## Steps

Every step is a pure `str -> str` transform that precomputes its table or regex at construction and
declares its safety class. Steps are grouped here by what they do.

Each step class also exists as a bare function with the same options as keyword arguments
(`RemoveTatweel()` ↔ `remove_tatweel(s)`, `FoldTehMarbuta(target="teh")` ↔
`fold_teh_marbuta(s, target="teh")`) for one-off, validation-free use — Layer 1 of the API
(see [Architecture](concepts/architecture.md)).

### Encoding repair (lossless)

::: araclean.NormalizeUnicode

::: araclean.StripBidi

::: araclean.FoldPresentationForms

::: araclean.RemoveTatweel

::: araclean.UnifyLookalikes

::: araclean.CollapseWhitespace

::: araclean.Trim

### Linguistic folding (lossy)

::: araclean.RemoveTashkeel

::: araclean.FoldAlef

::: araclean.FoldAlefMaqsura

::: araclean.FoldHamza

::: araclean.FoldTehMarbuta

::: araclean.FoldTanweenAlef

::: araclean.MapDigits

::: araclean.MapPunctuation

::: araclean.RemovePunctuation

::: araclean.MapQuotes

::: araclean.ReduceElongation

::: araclean.RemoveStopwords

### Cleaning (lossy)

::: araclean.CleanURLs

::: araclean.CleanMentions

::: araclean.CleanHashtags

::: araclean.CleanHTML

::: araclean.HandleEmoji

::: araclean.RemoveForeign

## Step options

The closed option sets the configurable steps accept (as enum members or their string values).

::: araclean.MarkClass

::: araclean.TehMarbutaTarget

::: araclean.DigitTarget

::: araclean.CleanMode

::: araclean.EmojiMode

::: araclean.HashtagMode

## Extension & protocol types

::: araclean.Step

## Stopword data

The curated, versioned list behind `RemoveStopwords` — see the
[stopwords guide](guides/stopwords.md). `STOPWORDS` (the matching set), `STOPWORDS_VERSION`,
`STOPWORDS_LICENSE`, and `NEGATION_PARTICLES` (the polarity particles deliberately excluded) are
importable from the module:

::: araclean.stopwords
    options:
      members: false

## DataFrame accessors

Installed by importing `araclean.pandas` / `araclean.polars` (each needs its extra) — see
[pandas & polars](guides/dataframes.md).

::: araclean.pandas.AracleanAccessor

::: araclean.polars.AracleanNamespace

## Errors

::: araclean.AlignmentNotSupportedError

::: araclean.EmojiSupportNotInstalledError

::: araclean.cli.CLIExtraNotInstalledError

::: araclean.pandas.PandasExtraNotInstalledError

::: araclean.polars.PolarsExtraNotInstalledError
