# Glossary — araclean

Arabic NLP forces a vocabulary problem: the people who know the **script** (native Arabic speakers)
often do *not* know the English jargon (*diacritic*, *nunation*, *gemination*), and the people who know
the **jargon** (NLP practitioners) often do *not* know the Arabic terms. araclean serves both, so it
fixes the vocabulary in one place here and uses it consistently everywhere.

## The terminology convention (the rule)

1. **Arabic-script-specific entities use their established transliteration as the canonical term**
   — `tashkeel`, `harakat`, `tanween`, `shadda`, `tatweel`, `hamza`, `alef`, `teh marbuta`,
   `alef maqsura`, `lam-alef`, `waw`, `yeh`, `kaf`, `heh`. These are what the **Arabic-NLP literature
   and tools already use** (CAMeL Tools, PyArabic, Farasa all say `tashkeel`/`hamza`/`alef`), so they
   are familiar to both audiences and more precise than the English approximations.
2. **General Unicode / NLP concepts stay in English** — *Unicode normalization form*, *presentation
   forms*, *bidi control characters*, *zero-width characters*, *whitespace*, *normalization*, *folding*.
   Transliterating these would help no one.
3. **Every Arabic term is glossed to its English/technical equivalent on first use**, and the mapping
   lives in this file (the single source of truth).
4. **Docs render the gloss automatically.** mkdocs-material abbreviations show the English meaning on
   hover wherever an Arabic term appears (`*[Tashkeel]: Diacritics — short-vowel & related marks`), so
   neither audience is stranded and prose stays uncluttered.
5. **One canonical name, no aliases.** Public step names are Arabic-primary (e.g. `RemoveTashkeel`),
   with the English equivalent in the docstring summary line, this glossary, and the docs search index,
   so a user searching "diacritics" still finds `RemoveTashkeel`. We deliberately ship **no English
   aliases** (no `RemoveDiacritics = RemoveTashkeel`) — a single name keeps the API maintainable for the
   community. Canonical spelling is enforced by a project **cSpell dictionary** (`cspell.json`), so a
   variant spelling fails CI and contributors/agents can't drift.

> **For contributors and AI agents:** this convention is binding. It is also recorded in
> [`CONTEXT.md`](./CONTEXT.md) (the ubiquitous-language spine every contributing agent reads). When you
> introduce a new Arabic term, add a row here and an `*[Term]: gloss` abbreviation to the docs, and use
> the canonical spelling below — do not invent a second romanization (`tashkeel`, never `tashkil`; `maqsura`, never `maksura` — root ق-ص-ر "to shorten", not ك-س-ر "to break"). <!-- cspell:disable-line -->

## Mapping

Canonical spelling is the first column. "Also seen" lists romanizations to avoid in our prose (but to
index for search). Code points are the primary Unicode characters involved.

| Term (canonical) | Arabic | English / technical | Key code points | Notes |
|---|---|---|---|---|
| **Tashkeel** | تشكيل | Diacritics / vocalization marks | core U+064B–U+0652, U+0653, U+0670 (full set: every Arabic combining mark) | Umbrella for all vocalization marks. The core MSA marks are tanween/harakat/shadda/sukun (U+064B–U+0652), the combining madda (U+0653) & dagger alef (U+0670); `RemoveTashkeel` covers the **entire** Arabic-script combining-mark repertoire (Unicode category Mn) across the Arabic / Supplement / Extended-A/B/C blocks — the small, curly, open & Qur'anic recitation variants too — **minus** the NFC-composing hamza pair U+0654/U+0655, which is letter content (see Hamza). These are the pronunciation marks (ضبط / شكل) — **not** the letter-distinguishing dots (إعجام), which are part of the base letters. |
| **Harakat** (sing. **haraka**) | حركات | Short vowels | fatha U+064E, damma U+064F, kasra U+0650 | The **three** short vowels (and their small/curly/dotted typographic variants). Sukun (U+0652, plus U+08D0 sukun-below) — the vowelless mark — is formally the *absence* of a haraka, not a haraka; it is grouped with the harakat for convenience and **always** removed with them (stripping the vowels while leaving a bare sukun is never wanted), never on its own. |
| **Fatha / Damma / Kasra / Sukun** | فتحة/ضمة/كسرة/سكون | the short-vowel marks / vowelless mark | U+064E / U+064F / U+0650 / U+0652 | Fatha/damma/kasra are the three harakat; sukun marks the *absence* of a vowel (a letter is متحرك "vocalized" or ساكن "sukun-bearing"). |
| **Tanween** | تنوين | Nunation | U+064B fathatan, U+064C dammatan, U+064D kasratan | A final /n/ sound written as a doubled short vowel; most often marks an indefinite noun, but not always (e.g. تنوين المقابلة on sound feminine plurals مسلماتٌ, تنوين العوض on يومئذٍ). *Also seen:* tanwin. |
| **Shadda** | شدّة | Gemination / consonant-doubling mark | U+0651 | *Also seen:* shaddah. |
| **Madda** | مدّة | Madda sign (hamza + long alef) | U+0653 (combining mark); آ U+0622 (the alef-madda letter) | Two distinct things: the **combining madda U+0653** is a tashkeel mark (the `MADDA` class); the single character **آ U+0622** is the alef-with-madda — an *alef variant* folded under letter folding (آ → ا), not tashkeel removal. Marks an alef carrying hamza + a long alef (آ = hamza + alef). The `MADDA` class is the orthographic U+0653 *alone*; the Qur'anic madd-prolongation signs (small high madda, madda waajib, …) are recitation marks and ride in the Qur'anic class, not here. |
| **Dagger alef** | ألف خنجرية | Superscript alef (marks an unwritten long alef) | U+0670 | Stands in for an omitted long alef. Standard in a fixed set of common words (هٰذا، ذٰلك، لٰكن، الله، الرحمٰن) and pervasive in Qur'anic text; surfaces only when text is vocalized — the bare forms (هذا، لكن) are the normal unvocalized spelling. The `DAGGER_ALEF` class is the standard U+0670 *alone*; the rare Qur'anic-specialized superscript alef and the subscript alef ride in the Qur'anic class. |
| **Qur'anic annotation marks** | علامات قرآنية | Qur'anic recitation/annotation signs (+ extended marks) | U+0610–U+0617, U+0656–U+065F, U+06D6–U+06ED, U+0898–U+089F, U+08CA–U+08FF, U+10EFD–U+10EFF | The `QURANIC` class — a deliberately **heterogeneous catch-all**: small high letters, pause/prostration/end-of-verse signs, tajweed marks, extended (non-Arabic) vowel signs, and a few non-Mn structural signs (end-of-ayah, rub-el-hizb, sajda). It holds everything in the vocalization/annotation repertoire beyond core tashkeel and the named classes — not a single linguistic category. Preserved by `CLASSICAL`, removable as a class by `SEARCH`. |
| **Tatweel** | تطويل | Elongation / justification character (kashida) | U+0640 | Stretches a word visually; carries no meaning. *Also:* kashida. |
| **Hamza** | همزة | Glottal-stop letter/mark | ء U+0621; combining ٔ U+0654 / ٕ U+0655 | Appears standalone or seated on a carrier. The **combining** hamza marks U+0654/U+0655 are *not* tashkeel: under NFC they (re)compose with their carrier into a distinct letter (ا+ٔ→أ, و+ٔ→ؤ, ي+ٔ→ئ, ا+ٕ→إ), i.e. letter content — handled by letter folding, not `RemoveTashkeel`. (Non-composing hamza marks, e.g. wavy hamza below U+065F, are ordinary annotation and ride in the Qur'anic class.) The standalone hamza letters ء U+0621 and the high hamza ٴ U+0674 are dropped only by *heavy* hamza folding (`drop_standalone_hamza`). |
| **Alef** | ألف | The letter alef | ا U+0627 | Variants below fold to bare alef when *Linguistic folding* is opted in. |
| **Alef variants** | — | Alef with hamza above/below, madda, wasla, wavy hamza | أ U+0623, إ U+0625, آ U+0622, ٱ U+0671, ٲ U+0672, ٳ U+0673 | The alef-variant letters of contemporary Arabic; `FoldAlef` collapses all to bare ا. Historical/manuscript alefs — high-hamza alef U+0675, the Extended-B annotation alefs U+0870–U+0882, the low alef U+08AD — are deliberately out of scope (not contemporary Arabic). |
| **Alef maqsura** | ألف مقصورة | Shortened/curtailed alef (dotless yeh form) | ى U+0649 | A final long-alef sound written in the restricted dotless ى form (counterpart of ألف ممدودة, the "extended alef" ا). Distinct from yeh (ي); folding the two merges `على`/`علي`. |
| **Teh marbuta** | تاء مربوطة | "Tied" taa (word-final) | ة U+0629 | Often folded to heh (ه) for search. *Also:* ta marbuta. |
| **Waw** | واو | The letter waw; also the conjunction "and" | و U+0648 | Also a hamza carrier: ؤ (waw + hamza, U+0624) folds to و under hamza-carrier folding. |
| **Yeh** | ياء | The letter yeh/yaa | ي U+064A | Farsi yeh ی (U+06CC) folds to yeh in *Encoding repair* (Arabic-language assumption). Caveat: U+06CC is dotless word-finally, so an alef-maqsura word typed on a Persian keyboard can merge على→علي — an accepted residual, not strictly lossless. *Also:* ya, yaa. |
| **Kaf** | كاف | The letter kaf | ك U+0643 | Persian keheh ک U+06A9 folds to kaf in *Encoding repair*. |
| **Heh** | هاء | The letter heh | ه U+0647 | Several heh look-alike forms unify here. |
| **Lam-alef** | لام ألف | The lam+alef sequence and its ligature | لا; ligatures U+FEF5–U+FEFC (e.g. ﻻ U+FEFB) | Each ligature glyph decomposes in *Encoding repair* to lam + its alef variant: ﻻ→لا, ﻷ→لأ, ﻹ→لإ, ﻵ→لآ (not all to bare لا). |
| **Arabic-Indic digits** | أرقام عربية-هندية | Eastern Arabic numerals | ٠–٩ U+0660–U+0669 | |
| **Extended Arabic-Indic digits** | أرقام فارسية/أردية | Persian/Urdu numerals | ۰–۹ U+06F0–U+06F9 | |
| **Dediacritization** | إزالة التشكيل | Removing tashkeel | — | The operation; *Linguistic folding* (lossy), opt-in. |

## araclean's own coined terms

These are project vocabulary, defined in [`CONTEXT.md`](./CONTEXT.md); included here for completeness.

| Term | Meaning |
|---|---|
| **Encoding repair** | The lossless, always-on subset of normalization (Unicode form, presentation-form/lam-alef folding, tatweel removal, bidi/zero-width stripping, look-alike unification, whitespace collapse). |
| **Linguistic folding** | The lossy, opt-in subset that discards information (dediacritization, alef/hamza/teh-marbuta/alef-maqsura folding, digit/punctuation mapping). |
| **Step** | A single pure `str -> str` transform (e.g. `RemoveTashkeel`). |
| **Profile** | A named, versioned preset that assembles Steps into a Pipeline (`LIGHT`, `SEARCH`, `ML`, …). |
