# Arabic-primary terminology with a bidirectional glossary

araclean fixes its public vocabulary: **Arabic-script-specific entities are named with their
established transliteration** (`tashkeel`, `harakat`, `tanween`, `shadda`, `tatweel`, `hamza`, `alef`,
`teh marbuta`, `alef maqsura`, `lam-alef`, `waw`, `yeh`, `kaf`, `heh`); **general Unicode/NLP concepts
stay in English** (`NormalizeUnicode`, `CollapseWhitespace`, `StripBidi`). Each term is mapped to its
English equivalent in [`GLOSSARY.md`](../../GLOSSARY.md) (the single source of truth), surfaced as
mkdocs-material hover tooltips, and recorded in [`CONTEXT.md`](../../CONTEXT.md). There is **one
canonical name per concept and no English aliases**.

Why: Arabic NLP has two audiences with disjoint vocabularies — native speakers know the script but not
the English jargon (*diacritic*, *nunation*); practitioners know the jargon but not the Arabic terms.
(a) The established Arabic-NLP ecosystem already names these entities by transliteration — pyarabic
(`strip_tashkeel`, `normalize_hamza`, `normalize_alef`), CAMeL Tools (`dediac`, `normalize_alef_ar`,
`normalize_teh_marbuta_ar`), Maha, tashaphyne — so transliteration-primary *is* "follow the existing
patterns," and it serves the Arabic-speaking main users. (b) Most of these terms have no clean English
anyway (`alef`, `hamza`, `teh marbuta`), and the few that do map only to obscure jargon (tatweel →
"kashida", tanween → "nunation", shadda → "gemination"); an English-only API would be a *mix* that is
neither simpler nor standard and would re-create the very accessibility problem this decision solves.
(c) Aliases (`RemoveDiacritics = RemoveTashkeel`) were rejected — a single canonical name keeps the API
maintainable for a community project. See [`docs/competitive-landscape.md`](../competitive-landscape.md)
for the ecosystem-naming evidence.

## Consequences

- `GLOSSARY.md` is the source of truth; every new Arabic term needs a glossary row plus a docs
  abbreviation. Canonical spelling is enforced by a project **cSpell dictionary** (`cspell.json`) — e.g.
  `tashkil`/`alif`/`diactric` fail CI — so terminology cannot drift in code, docs, or agent output. <!-- cspell:disable-line -->
- General concepts keep English names; do not transliterate "whitespace" or "presentation forms".
- Contributing agents read `CONTEXT.md`, so the rule is applied automatically and consistently.
