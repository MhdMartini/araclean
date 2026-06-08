"""Behavior of individual normalization steps (the `Step` family)."""

import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import (
    FoldPresentationForms,
    NormalizeUnicode,
    SafetyClass,
    fold_presentation_forms,
    normalize_unicode,
)

# Code points (not glyphs) so the decomposed form is immune to source normalization:
# alef (U+0627) + combining hamza above (U+0654) canonically composes to
# alef-with-hamza-above (U+0623) under NFC. The tail (U+062D/U+0645/U+062F) spells "Ahmad".
_TAIL = chr(0x062D) + chr(0x0645) + chr(0x062F)
DECOMPOSED = chr(0x0627) + chr(0x0654) + _TAIL  # alef + combining hamza + ...
COMPOSED = chr(0x0623) + _TAIL  # alef-with-hamza + ...


def test_normalize_unicode_composes_to_nfc() -> None:
    assert NormalizeUnicode()(DECOMPOSED) == COMPOSED
    # The composed form genuinely differs from the decomposed input (real work happened).
    assert COMPOSED != DECOMPOSED


def test_normalize_unicode_is_idempotent_on_composed_text() -> None:
    step = NormalizeUnicode()
    once = step(COMPOSED)
    assert once == COMPOSED
    assert step(once) == once


def test_free_function_agrees_with_step() -> None:
    # Layer 1 (free str -> str function) == Layer 2 (Step instance) for one step.
    assert normalize_unicode(DECOMPOSED) == NormalizeUnicode()(DECOMPOSED)


def test_step_declares_encoding_repair_safety() -> None:
    # NFC is lossless encoding repair (story 41 / ADR-0004).
    assert NormalizeUnicode().safety is SafetyClass.ENCODING_REPAIR


# --- FoldPresentationForms (issue 0003, stories 19 & 20) ---

# Each lam-alef ligature must decompose to lam + its MATCHING alef variant — not collapse to bare
# لا. Built from code points so the expectation is immune to how this file is saved.
LAM = chr(0x0644)
LAM_ALEF_LIGATURES = [
    (chr(0xFEFB), LAM + chr(0x0627)),  # ﻻ -> ل + alef
    (chr(0xFEF7), LAM + chr(0x0623)),  # ﻷ -> ل + alef-with-hamza-above
    (chr(0xFEF9), LAM + chr(0x0625)),  # ﻹ -> ل + alef-with-hamza-below
    (chr(0xFEF5), LAM + chr(0x0622)),  # ﻵ -> ل + alef-with-madda
]


@pytest.mark.parametrize(("ligature", "expected"), LAM_ALEF_LIGATURES)
def test_fold_presentation_forms_lam_alef_keeps_alef_variant(ligature: str, expected: str) -> None:
    folded = FoldPresentationForms()(ligature)
    assert folded == expected
    # It must NOT collapse every ligature to bare lam-alef.
    assert folded == LAM + expected[1:]


# Representative letter presentation forms from both ranges fold to their base letters. Built from
# code points (not glyphs) so the exact form is pinned regardless of how this file is saved.
# Covers initial / medial / final / isolated glyphs from Forms-B and one Forms-A letter.
LETTER_FORMS = [
    (chr(0xFE91), chr(0x0628)),  # BEH INITIAL FORM   (B) -> beh
    (chr(0xFEEA), chr(0x0647)),  # HEH FINAL FORM     (B) -> heh
    (chr(0xFEDF), chr(0x0644)),  # LAM INITIAL FORM   (B) -> lam
    (chr(0xFECC), chr(0x0639)),  # AIN MEDIAL FORM    (B) -> ain
    (chr(0xFEED), chr(0x0648)),  # WAW ISOLATED FORM  (B) -> waw
    (chr(0xFB58), chr(0x067E)),  # PEH INITIAL FORM   (A) -> peh (base kept, no look-alike fold)
]


@pytest.mark.parametrize(("form", "base"), LETTER_FORMS)
def test_fold_presentation_forms_folds_letters_to_base(form: str, base: str) -> None:
    assert FoldPresentationForms()(form) == base


def test_fold_presentation_forms_preserves_combining_mark_order() -> None:
    # A per-character fold must NOT reorder combining marks the way whole-string NFKC/NFC would —
    # this is what keeps vocalized/Qur'anic text safe for CLASSICAL.
    beh_form = chr(0xFE90)  # BEH FINAL FORM (a presentation glyph)
    marks = chr(0x0651) + chr(0x064E)  # shadda then fatha — deliberately NON-canonical order
    folded = FoldPresentationForms()(beh_form + marks)
    # the glyph became its base letter; the marks stayed in the SAME order they came in
    assert folded == chr(0x0628) + marks
    # contrast: whole-string NFKC reorders them by combining class (proves the hazard is real)
    assert unicodedata.normalize("NFKC", beh_form + marks) != folded


def test_fold_presentation_forms_safety_is_encoding_repair() -> None:
    # Folding a glyph to its base letter is lossless (story 41 / ADR-0004).
    assert FoldPresentationForms().safety is SafetyClass.ENCODING_REPAIR


def test_fold_presentation_forms_free_function_agrees_with_step() -> None:
    # Layer 1 (free str -> str function) == Layer 2 (Step instance).
    text = chr(0xFEF7) + chr(0xFE91) + "نص"
    assert fold_presentation_forms(text) == FoldPresentationForms()(text)


def test_fold_presentation_forms_leaves_base_letters_untouched() -> None:
    # Already-base Arabic text (no presentation forms) passes through unchanged.
    plain = "محمد لا إله"
    assert FoldPresentationForms()(plain) == plain


@given(st.text())
def test_fold_presentation_forms_is_total_and_idempotent(text: str) -> None:
    once = FoldPresentationForms()(text)  # never raises on arbitrary text
    assert FoldPresentationForms()(once) == once
