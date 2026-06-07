# araclean — Arabic Text Normalization & Cleaning

**araclean** — non-destructive Arabic text normalization & cleaning for NLP: pure-Python, fully
typed, with reproducible profiles. The bare call does only lossless encoding repair, so it never
silently strips tashkeel or folds letters — aggressive normalization is one keyword away.
MIT-licensed. v1 scope is the **normalization/cleaning core** (character- and Unicode-level
reshaping and noise removal); morphology-dependent features (stemming, clitic tokenization,
lemmatization, dialect/Arabizi) are deliberately out of v1 and designed to bolt on later as
optional extras.

## Language

**Normalization**:
Reshaping Arabic text at the character/Unicode level so that equivalent forms become
identical (folding presentation-form ligatures, unifying alef variants, etc.). The project's
core remit. Composed of independently toggleable, ordered steps.
_Avoid_: "preprocessing" (too broad — includes the morphology we exclude).

**Cleaning**:
Removal of non-linguistic noise (URLs, mentions, HTML, emoji, control/zero-width characters,
excess whitespace). A sibling concern to Normalization, not a synonym.
_Avoid_: using "cleaning" and "normalization" interchangeably.

**Encoding repair** (lossless, always-on):
The subset of normalization that is information-preserving for Arabic-language text: Unicode
form (NFC), lam-alef & presentation-form folding, tatweel removal, bidi/zero-width
stripping, look-alike kaf/yeh/heh unification, whitespace collapse. (Lam-alef & presentation-form
folding are true Unicode identities — lossless for any language; look-alike unification is correct
**under the Arabic-language assumption** — araclean is Arabic-only, so non-Arabic Arabic-script
input is the caller's responsibility.) Safe defaults — on.
_Avoid_: "fixing".

**Linguistic folding** (lossy, gated):
The subset that discards information: dediacritization, alef/hamza unification,
teh-marbuta→heh, alef-maqsura→yeh. Off or task-gated by default; opt-in per use case.
_Avoid_: lumping it with "encoding repair" — the lossless/lossy split is the core safety contract.

**Step**:
A single, pure `str -> str` transform (e.g. `RemoveTashkeel`, `NormalizeAlef`). The atom of
the library; usable standalone or inside a Pipeline.

**Profile**:
A named, versioned preset that assembles Steps into a Pipeline for a use case
(e.g. `LIGHT`, `SEARCH`, `ML`). The reproducibility unit users pin and share.

## Terminology convention (Arabic ↔ English) — binding for all contributors and agents

Arabic NLP has two audiences with non-overlapping vocabularies: native speakers know the **script**
but not the English jargon (*diacritic*, *nunation*); practitioners know the **jargon** but not the
Arabic terms. araclean serves both, so terminology is fixed once and used consistently:

- **Arabic-script-specific entities use their established transliteration as the canonical term** —
  `tashkeel`, `harakat`, `tanween`, `shadda`, `tatweel`, `hamza`, `alef`, `teh marbuta`,
  `alef maqsura`, `lam-alef`, `waw`, `yeh`, `kaf`, `heh`. This is what the Arabic-NLP ecosystem
  already uses (CAMeL Tools, PyArabic, Farasa), so it is familiar to both audiences and more precise
  than the English approximations.
- **General Unicode/NLP concepts stay in English** — Unicode form, presentation forms, bidi, zero-width,
  whitespace, normalization, folding. (Transliterating these helps no one.)
- **Every Arabic term is glossed to its English equivalent** in [`GLOSSARY.md`](./GLOSSARY.md) (the
  single source of truth), surfaced as mkdocs-material hover tooltips in docs, and named
  Arabic-primary in the API with the English equivalent in the docstring + search index.
- **One canonical name per concept, no English aliases** — enforced by a project cSpell dictionary
  (`cspell.json`) so spelling can't drift in code, docs, or agent output.
- _Avoid_: a second romanization of a term we already spell one way (`tashkeel`, never `tashkil`); <!-- cspell:disable-line -->
  English-only names for Arabic-script entities (`RemoveDiacritics` as the *only* name).

When you add a new Arabic term, add a row to `GLOSSARY.md` and a docs abbreviation, and use the
canonical spelling there. See [`GLOSSARY.md`](./GLOSSARY.md) for the full mapping and
[ADR-0007](./docs/adr/0007-arabic-primary-terminology.md) for the rationale.

## Boundaries (v1)

- **In scope:** character/Unicode normalization; cleaning; social-media handling (elongation,
  emoji, URLs/mentions); digit & punctuation mapping; reproducible profiles; a curated versioned
  stopword list + a `RemoveStopwords` step; a Typer CLI (`[cli]` extra); a pandas/polars accessor
  (`[pandas]`/`[polars]` extras). **No tokenizer** (a naive one adds little; a real one needs the
  deferred morphology).
- **Out of scope (deferred):** morphological clitic segmentation, stemming, lemmatization,
  dialect modeling, Arabizi transliteration, spaCy/HuggingFace trained pipelines. The
  architecture must allow these later as optional extras without breaking the core.

## Flagged ambiguities

- "preprocessing" / "cleaning" / "normalization" are used interchangeably across the Arabic-NLP
  community. Resolved here: **Normalization** = char/Unicode reshaping; **Cleaning** = noise
  removal; "preprocessing" = the umbrella term (includes deferred morphology) and is avoided
  as a precise term.

## Example dialogue

> **Maintainer:** "A user pastes text where لا shows up as a single presentation-form glyph
> (U+FEFB). Is fixing that Normalization the user opts into, or always-on?"
> **Domain expert:** "Always-on — it's **Encoding repair**, lossless. But unifying أ/إ/آ into
> bare ا is **Linguistic folding**: lossy, so it's off unless the user picks a SEARCH-style
> **Profile**."
