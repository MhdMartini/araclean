"""Internal seam: precomputed Unicode tables for the character-level steps.

The single source of truth for the code points each `Step` maps, built once at import. This is
**not** a public interface -- every step is tested through its `str -> str` behavior, so a table
here can later be fused into the single-pass engine (0018) without touching a test.
"""

from __future__ import annotations

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
# WHY PER-CODE-POINT TRANSLATE, NOT WHOLE-STRING NFKC: NFKC also applies Canonical Ordering, which
# **reorders combining marks** by Canonical_Combining_Class (UAX #15). Run over a whole string it
# would silently reshuffle tashkeel on vocalized/Qur'anic text. Reading each form's decomposition
# into a `str.translate` map and substituting in place applies the identical folds while leaving
# every surrounding combining mark exactly where it was -- which is what keeps this step safe for
# the CLASSICAL profile (0015, vocalized/Qur'anic text). The behavior is pinned by
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
