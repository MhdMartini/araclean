# API reference

The whole public surface: the one-call `normalize` facade, the `Pipeline` it assembles, and every
`Step`. Each Arabic term below is glossed to English on hover (ADR-0007); searching the English name
(e.g. *diacritics*) finds the Arabic-primary step (`RemoveTashkeel`).

## The `normalize` facade

::: araclean.normalize

## Pipelines & profiles

::: araclean.Pipeline

::: araclean.Profile

## Safety classes (the lossless / lossy split)

::: araclean.SafetyClass

::: araclean.SafetyReport

## Steps

Every step is a pure `str -> str` transform that precomputes its table or regex at construction and
declares its safety class. Steps are grouped here by what they do.

### Encoding repair (lossless)

::: araclean.NormalizeUnicode

::: araclean.StripBidi

::: araclean.FoldPresentationForms

::: araclean.RemoveTatweel

::: araclean.UnifyLookalikes

::: araclean.CollapseWhitespace

### Linguistic folding (lossy)

::: araclean.RemoveTashkeel

::: araclean.FoldAlef

::: araclean.FoldAlefMaqsura

::: araclean.FoldHamza

::: araclean.FoldTehMarbuta

::: araclean.MapDigits

::: araclean.MapPunctuation

::: araclean.ReduceElongation

::: araclean.RemoveStopwords

### Cleaning (lossy)

::: araclean.CleanURLs

::: araclean.CleanMentions

::: araclean.CleanHTML

::: araclean.HandleEmoji
