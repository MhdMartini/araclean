"""Internal seam: precomputed Unicode tables for the character-level steps.

The single source of truth for the code points each `Step` maps, built once at import. This is
**not** a public interface -- every step is tested through its `str -> str` behavior, so a table
here can later be fused into the single-pass engine (0018) without touching a test.
"""

from __future__ import annotations

import re
import unicodedata

# --- FoldPresentationForms table (issue 0003) -------------------------------------------------
#
# The two Arabic *presentation-form* blocks of the Unicode Standard:
#   - Arabic Presentation Forms-A  U+FB50-U+FDFF
#   - Arabic Presentation Forms-B  U+FE70-U+FEFF
# These hold the contextual glyph shapes (isolated / initial / medial / final) and the ligatures
# that OCR, legacy 8-bit code pages and copy-paste leave behind in otherwise-normal Arabic text.
#
# THE RULE: fold a code point back to its base letters *iff* the Unicode Character Database (UCD)
# gives it a **compatibility decomposition** -- Decomposition_Type in {Isolated, Initial, Medial,
# Final} for the letter shapes, plus the ligature mappings (lam-alef U+FEF5-U+FEFC -> lam + the
# matching alef variant, e.g. ﻷ -> لأ). See Unicode Standard Annex #15, "Unicode Normalization
# Forms". `unicodedata.normalize("NFKC", ch)` returns exactly that mapping, so we read the fold
# straight from the UCD instead of hand-maintaining ~700 rows -- and it tracks new code points
# across Unicode releases for free. Every contextual *letter* form has such a mapping, so the
# OCR/legacy/copy-paste case is fully covered.
#
# WHY PER-CODE-POINT TRANSLATE, NOT WHOLE-STRING NFKC: two reasons, both about *scope*.
#   1. SCOPE OF FOLDING. Whole-string NFKC applies *every* compatibility decomposition in the text,
#      not just the presentation forms -- it would also expand the atomic symbols / honorific
#      ligatures we deliberately keep (see "INTENTIONALLY NOT FOLDED" below) and any other
#      compatibility character the caller had elsewhere. Restricting a `str.translate` map to the
#      two presentation-form ranges folds *only* the contextual glyphs and leaves the rest alone.
#   2. SCOPE OF REORDERING. NFKC also applies Canonical Ordering, reordering combining marks by
#      Canonical_Combining_Class (UAX #15). Keeping that out of the fold makes this step a pure
#      per-glyph substitution that never itself reshuffles a caller's tashkeel. Canonical ordering
#      is applied exactly once, by the pipeline's *closing* NormalizeUnicode, so the final output
#      is still NFC -- the fold simply isn't where it happens (ADR-0009).
# Net effect for vocalized/Qur'anic text (CLASSICAL, 0015): marks are folded in place here and put
# into canonical order once at the end; no mark is dropped and no compatibility character is
# silently expanded. This step's own no-reorder behavior is pinned by
# tests/test_steps.py::test_fold_presentation_forms_preserves_combining_mark_order.
#
# INTENTIONALLY NOT FOLDED (the `if folded != char` filter below drops them, because the UCD gives
# them no compatibility mapping and NFKC returns them unchanged):
#   - unassigned code points, and the 32 Unicode *noncharacters* U+FDD0-U+FDEF;
#   - the BOM / ZERO WIDTH NO-BREAK SPACE U+FEFF -- a format char, not a letter glyph (stripping
#     invisibles is StripBidi's job, issue 0004);
#   - atomic Arabic *symbols* and honorific/phrase ligatures the UCD treats as standalone glyphs
#     rather than letter sequences (general category Sk / So / Lo): the modifier marks
#     U+FBB2-U+FBC2, the ornate parentheses U+FD3E/U+FD3F, and the phrase ligatures U+FD40-U+FD4F,
#     U+FDCF and U+FDFD-U+FDFF. Unicode deliberately assigns these no decomposition, so neither do
#     we: expanding them would mean araclean inventing a canonical spelling for each, out of scope
#     for lossless encoding repair.
_PRESENTATION_FORM_RANGES: tuple[tuple[int, int], ...] = ((0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def _build_presentation_forms() -> dict[int, str]:
    table: dict[int, str] = {}
    for start, end in _PRESENTATION_FORM_RANGES:
        for code_point in range(start, end + 1):
            char = chr(code_point)
            folded = unicodedata.normalize("NFKC", char)
            # Keep only genuine presentation forms: a code point with no compatibility mapping
            # (unassigned, noncharacter, BOM, or an atomic symbol/ligature) decomposes to itself
            # under NFKC and is therefore left untouched by the fold.
            if folded != char:
                table[code_point] = folded
    return table


PRESENTATION_FORMS: dict[int, str] = _build_presentation_forms()


# --- RemoveTatweel table (issue 0004, story 21) -----------------------------------------------
#
# Tatweel / kashida U+0640 stretches a word horizontally for justification and carries no meaning
# (GLOSSARY: Tatweel). FoldPresentationForms (0003) can itself emit a tatweel -- the *medial*-form
# tashkeel glyphs (e.g. U+FE77 FATHA MEDIAL FORM) decompose under NFKC to tatweel + the mark -- so
# this step runs after the fold in LIGHT to clean up those carriers too.
TATWEEL = 0x0640
REMOVE_TATWEEL: dict[int, None] = {TATWEEL: None}


# --- StripBidi table (issue 0004, story 22) ---------------------------------------------------
#
# Delete the invisible format characters that carry no Arabic letter content but silently break
# string equality and tokenization: the Unicode bidi controls plus the zero-width / BOM formatters.
#
#   Bidi controls -- every code point with the Unicode `Bidi_Control=Yes` property (UAX #9 §2):
#     U+061C ARABIC LETTER MARK, U+200E/U+200F (LEFT-/RIGHT-TO-LEFT MARK),
#     U+202A-U+202E (the LRE/RLE/PDF/LRO/RLO explicit-formatting set),
#     U+2066-U+2069 (the LRI/RLI/FSI/PDI directional-isolate set).
#   Zero-width / BOM -- invisible formatters that are NOT whitespace, so CollapseWhitespace's `\s`
#   run-collapse cannot reach them; they must be deleted here instead:
#     U+200B ZERO WIDTH SPACE, U+200C ZERO WIDTH NON-JOINER (ZWNJ),
#     U+200D ZERO WIDTH JOINER (ZWJ), U+2060 WORD JOINER, U+FEFF ZERO WIDTH NO-BREAK SPACE (BOM).
#
# ZWNJ (U+200C) is stripped by default; a keep/space option for Persian-mixed text is deferred to
# the config boundary (issue 0016). U+FEFF is handled HERE, not by the presentation-form fold
# (0003): it is a format char, not a letter glyph, so 0003 deliberately leaves it for this step.
_BIDI_CONTROLS: tuple[int, ...] = (
    0x061C,
    0x200E,
    0x200F,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
)
_ZERO_WIDTH: tuple[int, ...] = (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)
STRIP_BIDI: dict[int, None] = {cp: None for cp in (*_BIDI_CONTROLS, *_ZERO_WIDTH)}


# --- UnifyLookalikes table (issue 0004, story 23) ---------------------------------------------
#
# araclean assumes its input is Arabic (the Arabic-language assumption). Letters borrowed by other
# Arabic-script orthographies (Persian, Urdu, Kurdish, ...) are visually identical to an Arabic
# letter; when they turn up in Arabic text -- from a foreign keyboard layout, a localized font, or
# copy-paste -- they are an *encoding* artifact, so folding them back to the Arabic letter is
# lossless repair, not letter folding.
#
#   - Persian/Urdu keheh  ک U+06A9 -> kaf  ك U+0643   (GLOSSARY: Kaf)
#   - Farsi yeh           ی U+06CC -> yeh  ي U+064A   (GLOSSARY: Yeh)
#
# THE HEH FAMILY -- every unmarked, heh-shaped letter that other Arabic-script orthographies use,
# all folding to Arabic heh ه U+0647 (GLOSSARY: Heh). The principle is purely visual: an unmarked
# heh-shaped foreign letter in Arabic text is a mis-encoded heh, regardless of its phonetic job in
# the source language.
#   - heh goal        ہ U+06C1 -> heh  (Urdu/Sindhi gol-he, the /h/ consonant)
#   - ae              ە U+06D5 -> heh  (Kurdish/Uyghur vowel; dotless, a final-heh shape)
#   - heh doachashmee ھ U+06BE -> heh  (Urdu/Sindhi "two-eyed he", an aspiration marker. Its
#     isolated/final forms render as a plain heh loop -- only the joined forms show the two eyes --
#     and it never occurs in Arabic, so under the Arabic-only assumption it is a mis-encoded heh.)
#
# THE ONE ACCEPTED RESIDUAL (GLOSSARY: Yeh): U+06CC is dotless word-finally, so an alef-maqsura
# word typed on a Persian keyboard (علی = …ل + U+06CC) merges على -> علي. This is the only
# look-alike fold that is not strictly lossless; it is accepted under the Arabic-only assumption.
#
# DELIBERATELY EXCLUDED -- these have a real principle behind them, unlike the heh family above:
#   - U+06C0 ۀ / U+06C2 ۂ (heh carrying a yeh/hamza above) -- folding to bare heh would DROP the
#     combining mark, so it is not lossless; left untouched (U+06C0 is also governed by NFC).
#   - teh marbuta ة U+0629 (and its goal form ۃ U+06C3) -> heh -- a real Arabic letter; that fold
#     is *lossy* and belongs to the opt-in FoldTehMarbuta (issue 0007), not to encoding repair.
UNIFY_LOOKALIKES: dict[int, str] = {
    0x06A9: chr(0x0643),  # keheh -> kaf
    0x06CC: chr(0x064A),  # farsi yeh -> yeh
    0x06C1: chr(0x0647),  # heh goal -> heh
    0x06D5: chr(0x0647),  # ae -> heh
    0x06BE: chr(0x0647),  # heh doachashmee -> heh
}


# --- CollapseWhitespace pattern + line-break set (issue 0004, story 24) ------------------------
#
# A *contextual* rule (a whitespace run -> one character), so a precompiled regex rather than a
# str.translate table (ADR-0006). `\s` already covers ASCII whitespace plus every Unicode space
# separator -- NBSP U+00A0, the U+2000-U+200A set, U+202F, U+205F, U+3000 -- AND the line/paragraph
# breaks, so the pattern never needs hand-maintaining. The zero-width characters are NOT `\s` (they
# are deleted by StripBidi instead).
#
# CollapseWhitespace then asks, per run, whether the run crossed a line boundary: a purely
# horizontal run becomes one ASCII space; a run containing any LINE_BREAK becomes a single "\n".
# Preserving line structure keeps the *default* lossless -- flattening lines to spaces is lossy (it
# destroys document structure), so it is opt-in via `collapse_lines=True` (ADR-0010). A lone run at
# the start or end collapses in place (collapse, not trim), so the step stays a fixed point.
#
# LINE_BREAKS is exactly the boundary set Python's str.splitlines() recognizes: LF, CR, vertical
# tab, form feed, the C1 FS/GS/RS separators, NEL (U+0085), and LINE / PARAGRAPH SEPARATOR (U+2028
# / U+2029). All are matched by `\s`, so they fall inside the runs the pattern finds; U+001F UNIT
# SEPARATOR is `\s` but NOT a line break (splitlines agrees too), so it is correctly excluded.
WHITESPACE_RUN: re.Pattern[str] = re.compile(r"\s+")
LINE_BREAKS: frozenset[str] = frozenset("\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029")


# --- RemoveTashkeel mark-class code points (issue 0006, stories 25 & 26) -----------------------
#
# The vocalization-mark taxonomy (GLOSSARY: Tashkeel): one frozenset of code points per removable
# class, so RemoveTashkeel deletes the union of the *selected* classes (story 26). This is the
# internal seam -- a step is tested through its str -> str behavior, so a class can be re-tabulated
# here without touching a test.
#
# ONE STATED PRINCIPLE (verified, not guessed). The classes PARTITION araclean's tashkeel
# repertoire: pairwise disjoint, together covering EVERY Arabic-script nonspacing combining mark
# (Unicode category Mn) across the Arabic, Supplement and Extended-A/-B/-C blocks, PLUS a short
# enumerated set of non-Mn Qur'anic signs (end-of-ayah, rub-el-hizb, sajda, the small waw/yeh
# letters), MINUS exactly the two NFC-composing hamza marks. Full removal therefore deletes the
# whole repertoire; tests/test_steps.py re-derives that repertoire from the live Unicode database
# and asserts the partition matches it -- so a future Unicode version that adds an Arabic mark fails
# CI until the mark is triaged into a class here. Each member is verified against this principle,
# never left to a guessed numeric range (the U+06BE lesson).
#
# Boundaries that are deliberate and load-bearing:
#   - SUKUN (U+0652, plus U+08D0 sukun-below) is NOT a haraka: it marks the *absence* of a vowel
#     (GLOSSARY: Harakat), so it is its own constant, kept OUT of HARAKAT. RemoveTashkeel deletes it
#     together with HARAKAT purely for convenience (stripping the vowels but leaving a bare sukun is
#     not a use case); by design, neither is removable without the other.
#   - The named classes are pure BY FUNCTION, not by name. HARAKAT / TANWEEN gather every
#     TYPOGRAPHIC variant of the short vowels / nunation (small, curly, open, dotted), but not the
#     generic "vowel sign" marks coined for non-Arabic languages. MADDA is the orthographic
#     combining madda U+0653 alone (the LETTER alef-madda U+0622 is letter folding, issue 0007);
#     DAGGER_ALEF is the standard superscript alef U+0670 alone. Their Qur'anic-recitation
#     namesakes -- small high madda, madda waajib, superscript alef mokhassas, subscript alef, the
#     tajweed signs -- are recitation annotation, not orthographic vocalization, ride in QURANIC.
#   - Two hamza marks are EXCLUDED outright: U+0654 HAMZA ABOVE and U+0655 HAMZA BELOW. Under NFC
#     they (re)compose with their carrier into a distinct letter (alef-hamza, waw-hamza, ...), i.e.
#     letter content owned by letter folding (issue 0007), not free-standing vocalization. This is
#     the NFC-composing pair specifically; non-composing hamza marks (e.g. U+065F wavy hamza below)
#     are ordinary annotation and ride in QURANIC. A stray U+0654 on a non-composing carrier is left
#     for 0007 to fold, not stripped here.
#   - QURANIC is intentionally HETEROGENEOUS -- Qur'anic recitation/annotation signs (small high
#     letters, pause/sajda/end-of-verse marks, tajweed signs), extended non-Arabic vocalization
#     marks, and a few non-Mn structural signs. It is the umbrella SEARCH removes as one block and
#     CLASSICAL preserves, not a single linguistic category.
HARAKAT: frozenset[int] = frozenset(
    (
        0x064E,  # fatha
        0x064F,  # damma
        0x0650,  # kasra
        0x0618,  # small fatha (Qur'anic rawm / ishmaam)
        0x0619,  # small damma
        0x061A,  # small kasra
        0x0657,  # inverted damma
        0x065D,  # reversed damma
        0x065E,  # fatha with two dots
        0x08E3,  # turned damma below
        0x08E4,  # curly fatha
        0x08E5,  # curly damma
        0x08E6,  # curly kasra
        0x08F4,  # fatha with ring
        0x08F5,  # fatha with dot above
        0x08F6,  # kasra with dot below
        0x08FE,  # damma with dot
    )
)
# Vowelless mark -- the *absence* of a haraka, not a haraka. Its own constant; deleted together with
# HARAKAT for convenience (see the module note), never on its own and never separable.
SUKUN: frozenset[int] = frozenset((0x0652, 0x08D0))  # sukun, sukun below
TANWEEN: frozenset[int] = frozenset(
    (
        0x064B,  # fathatan
        0x064C,  # dammatan
        0x064D,  # kasratan
        0x08E7,  # curly fathatan
        0x08E8,  # curly dammatan
        0x08E9,  # curly kasratan
        0x08F0,  # open fathatan
        0x08F1,  # open dammatan
        0x08F2,  # open kasratan
    )
)
SHADDA: int = 0x0651  # gemination / consonant-doubling mark
MADDA: int = 0x0653  # orthographic combining madda above (not the letter alef-madda U+0622)
DAGGER_ALEF: int = 0x0670  # standard superscript alef marking an omitted long alef
# Qur'anic annotation marks + extended/other combining marks (GLOSSARY) -- the heterogeneous
# catch-all (see the module note). Preserved by CLASSICAL; removable as a class under SEARCH.
QURANIC: frozenset[int] = frozenset(
    (
        *range(0x0610, 0x0618),  # honorific signs + small high tah / ligature / zain
        0x0656,  # subscript alef
        0x0658,  # mark noon ghunna
        *range(0x0659, 0x065D),  # extended vowel signs (non-Arabic orthographies)
        0x065F,  # wavy hamza below (a non-composing hamza mark)
        *range(0x06D6, 0x06EE),  # small high ligatures, pause/sajda/end-of-ayah, small waw/yeh
        *range(0x0898, 0x08A0),  # small high/low recitation words + extended madda & alef signs
        *range(0x08CA, 0x08D0),  # small high farsi-yeh/yeh-barree/word-sah/zah, large round dots
        *range(0x08D1, 0x08E3),  # small high/low words, footnote & safha, disputed end-of-ayah
        *range(0x08EA, 0x08F0),  # tone marks
        0x08F3,  # small high waw
        *range(0x08F7, 0x08FE),  # recitation arrowheads
        0x08FF,  # mark sideways noon ghunna
        *range(0x10EFD, 0x10F00),  # small low words: sakta, qasr, madda (Arabic Extended-C)
    )
)


# --- Letter-fold tables (issue 0007, stories 27-30) -------------------------------------------
#
# The opt-in LINGUISTIC_FOLDING letter folds: lossy collapses of letter *spelling* distinctions
# that boost search recall (SEARCH, 0010) but destroy a real contrast, so none run under LIGHT.
# Each is a single-character str.translate map (internal seam) -- fusion candidates for 0018.
#
# These steps operate on the PRECOMPOSED (NFC) letters. In any profile NFC runs first, so a
# combining hamza/madda on an alef is already composed into the precomposed letter (alef + hamza
# above -> أ, alef + combining madda -> آ) before a fold runs; the fold only sees those letters.
#
# FoldAlef -- the alef-variant LETTERS of contemporary Arabic -> bare alef ا U+0627 (GLOSSARY: Alef
# variants). The hamza-/madda-bearing alef letters (أ إ آ), alef-wasla ٱ, and the wavy-hamza alefs
# (ٲ ٳ, a Qur'anic/old-orthography hamza shape) all collapse to the plain alef. The combining marks
# they carry are not seen here: NFC has already folded them into these letters.
#
# ONE STATED PRINCIPLE (verified, not a guessed range -- the U+06BE lesson). The candidate set is
# every Arabic-script alef LETTER (Unicode name "...ALEF..." other than alef maqsura ى, or an NFKD
# that begins with the bare alef U+0627); tests/test_steps.py re-derives it from the LIVE Unicode
# database and asserts each candidate is either folded here or in the DELIBERATELY-EXCLUDED set
# below, so a future Unicode alef fails CI until it is triaged.
# DELIBERATELY EXCLUDED -- not contemporary Arabic, so folding them would invent a spelling:
#   - high-hamza alef U+0675 (bare alef + the high hamza U+0674; Kazakh/Jawi orthographies);
#   - the digit-annotated alefs U+0773/U+0774 (Qur'anic/African superscript-digit marks);
#   - the Arabic Extended-B manuscript alefs U+0870-U+0882 (attached fatha/kasra, strokes, dots and
#     rings -- scholarly annotation glyphs) and the low alef U+08AD (African Arabic).
BARE_ALEF: int = 0x0627
FOLD_ALEF: dict[int, str] = {
    0x0623: chr(BARE_ALEF),  # أ alef with hamza above
    0x0625: chr(BARE_ALEF),  # إ alef with hamza below
    0x0622: chr(BARE_ALEF),  # آ alef with madda
    0x0671: chr(BARE_ALEF),  # ٱ alef wasla
    0x0672: chr(BARE_ALEF),  # ٲ alef with wavy hamza above
    0x0673: chr(BARE_ALEF),  # ٳ alef with wavy hamza below
}

# FoldAlefMaqsura -- alef maqsura ى U+0649 -> yeh ي U+064A (GLOSSARY: Alef maqsura). The two are a
# real contrast (ى is a final long-alef sound), so merging them collides على/علي -- which is
# exactly why the fold is opt-in (SEARCH) and not encoding repair. ى is the ONLY Arabic alef-maqsura
# letter (a live-UCD test pins this); the Urdu yeh-barree ے/ۓ U+06D2/U+06D3 is a different,
# non-Arabic letter, deliberately left untouched (it is not a look-alike typo for yeh either).
YEH: int = 0x064A
FOLD_ALEF_MAQSURA: dict[int, str] = {0x0649: chr(YEH)}

# FoldHamza -- a SEPARATE, configurably-aggressive fold of the hamza (GLOSSARY: Hamza), kept apart
# from FoldAlef so a caller can neutralize hamza on the waw/yeh carriers without folding alef.
# Three pieces, by what hamza they touch:
#   - CARRIERS: the precomposed waw-/yeh-hamza letters ؤ/ئ -> bare waw/yeh. Always folded (light).
#   - COMBINING marks U+0654/U+0655: hamza seated ON a carrier as a standalone combining mark. NFC
#     composes these into a precomposed letter (ا+ٔ→أ, و+ٔ→ؤ, ي+ٔ→ئ, ا+ٕ→إ), so in normalized text
#     they are gone; a *stray* one on a non-composing carrier is letter content that issue 0006
#     routes here (it is NOT tashkeel, so RemoveTashkeel leaves it). Deleting the mark folds
#     carrier+hamza to the bare carrier -- the same neutralization as folding ؤ/ئ -- so it is part
#     of the always-on carrier fold, in BOTH modes. The precomposed alef-hamza LETTERS أ/إ are NOT
#     here: they are alef variants owned by FoldAlef.
#   - the STANDALONE hamza LETTERS -- ء U+0621 (no carrier) and the HIGH HAMZA ٴ U+0674 (its high
#     spacing variant): dropped only in the HEAVY mode (drop_standalone_hamza=True). Light keeps
#     them -- they have no seat to fold onto.
#
# ONE STATED PRINCIPLE (verified). The hamza-bearing letters are partitioned across the two letter
# folds: the alef carriers أ/إ/ٲ/ٳ belong to FoldAlef, the waw/yeh carriers ؤ/ئ and the standalone
# ء/ٴ belong here. A live-UCD test re-derives every non-alef Arabic-script hamza LETTER and asserts
# it is folded here or DELIBERATELY EXCLUDED as non-Arabic: the high-hamza waw/u/yeh U+0676-U+0678,
# the foreign hamza carriers hah U+0681, heh-goal U+06C2, yeh-barree U+06D3, reh U+076C, beh U+08A1
# and yeh-with-two-dots U+08A8, and the tatweel-hamza element U+0883. (The combining hamza marks
# U+0654/U+0655 are letter content guarded by the 0006 mark-partition test, not here.)
WAW: int = 0x0648
FOLD_HAMZA_CARRIERS: dict[int, str] = {
    0x0624: chr(WAW),  # ؤ waw with hamza above -> waw
    0x0626: chr(YEH),  # ئ yeh with hamza above -> yeh
}
COMBINING_HAMZA: frozenset[int] = frozenset((0x0654, 0x0655))  # hamza above / hamza below
STANDALONE_HAMZA: int = 0x0621  # ء the hamza letter (no carrier)
HIGH_HAMZA: int = 0x0674  # ٴ the high hamza spacing letter (heavy-mode standalone, parallel to ء)

# FoldTehMarbuta -- the word-final "tied taa" ة U+0629 (GLOSSARY: Teh marbuta) folded to a
# configurable target. ة marks a real grammatical ending, so the fold is lossy and opt-in. Its
# goal-form variant ۃ U+06C3 folds with it (issue 0004 routed it here, not to look-alike repair).
# The two standard search/morphology targets are heh (default, the common search fold) and teh
# (its underlying value); `keep` is the no-op target a profile can pin to leave ة in place.
TEH_MARBUTA: frozenset[int] = frozenset((0x0629, 0x06C3))  # teh marbuta + its goal form
HEH: int = 0x0647  # ه target
TEH: int = 0x062A  # ت target
