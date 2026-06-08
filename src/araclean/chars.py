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
