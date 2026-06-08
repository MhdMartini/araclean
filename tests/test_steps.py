"""Behavior of individual normalization steps (the `Step` family)."""

import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import (
    CollapseWhitespace,
    FoldPresentationForms,
    NormalizeUnicode,
    RemoveTatweel,
    SafetyClass,
    StripBidi,
    UnifyLookalikes,
    collapse_whitespace,
    fold_presentation_forms,
    normalize_unicode,
    registry,
    remove_tatweel,
    strip_bidi,
    unify_lookalikes,
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


# --- RemoveTatweel (issue 0004, story 21) ---

TATWEEL = chr(0x0640)  # ـ ARABIC TATWEEL / kashida


def test_remove_tatweel_strips_the_elongation_character() -> None:
    # محـــمد (with three tatweel marks) -> محمد ("Muhammad")
    word = chr(0x0645) + chr(0x062D) + TATWEEL * 3 + chr(0x0645) + chr(0x062F)
    assert RemoveTatweel()(word) == chr(0x0645) + chr(0x062D) + chr(0x0645) + chr(0x062F)


def test_remove_tatweel_leaves_letters_untouched() -> None:
    plain = "محمد لا إله"
    assert RemoveTatweel()(plain) == plain


def test_remove_tatweel_safety_is_encoding_repair() -> None:
    assert RemoveTatweel().safety is SafetyClass.ENCODING_REPAIR


def test_remove_tatweel_free_function_agrees_with_step() -> None:
    text = "مح" + TATWEEL + "مد"
    assert remove_tatweel(text) == RemoveTatweel()(text)


@given(st.text())
def test_remove_tatweel_is_total_and_idempotent(text: str) -> None:
    once = RemoveTatweel()(text)
    assert RemoveTatweel()(once) == once


# --- StripBidi (issue 0004, story 22) ---

# Invisible code points that carry no letter content: bidi controls, zero-width formatters, BOM.
INVISIBLES = [
    chr(0x200F),  # RIGHT-TO-LEFT MARK (RLM) — bidi control
    chr(0x200E),  # LEFT-TO-RIGHT MARK (LRM) — bidi control
    chr(0x061C),  # ARABIC LETTER MARK (ALM) — bidi control
    chr(0x202B),  # RIGHT-TO-LEFT EMBEDDING — bidi control
    chr(0x2069),  # POP DIRECTIONAL ISOLATE — bidi control
    chr(0x200C),  # ZERO WIDTH NON-JOINER (ZWNJ)
    chr(0x200D),  # ZERO WIDTH JOINER (ZWJ)
    chr(0x200B),  # ZERO WIDTH SPACE
    chr(0x2060),  # WORD JOINER
    chr(0xFEFF),  # ZERO WIDTH NO-BREAK SPACE (the BOM)
]


@pytest.mark.parametrize("invisible", INVISIBLES)
def test_strip_bidi_removes_invisibles_keeping_visible_letters(invisible: str) -> None:
    # The invisible sits between two visible letters; only it is removed.
    text = "ا" + invisible + "ب"
    assert StripBidi()(text) == "اب"


def test_strip_bidi_removes_a_leading_bom() -> None:
    assert StripBidi()(chr(0xFEFF) + "نص") == "نص"


def test_strip_bidi_removes_a_mixed_run_in_one_string() -> None:
    # RLM + ZWJ/ZWNJ + leading BOM all gone; the visible letters survive in order.
    text = chr(0xFEFF) + "ا" + chr(0x200F) + "ب" + chr(0x200D) + chr(0x200C) + "ت"
    assert StripBidi()(text) == "ابت"


def test_strip_bidi_leaves_ordinary_text_untouched() -> None:
    plain = "محمد لا إله"
    assert StripBidi()(plain) == plain


def test_strip_bidi_safety_is_encoding_repair() -> None:
    assert StripBidi().safety is SafetyClass.ENCODING_REPAIR


def test_strip_bidi_free_function_agrees_with_step() -> None:
    text = chr(0xFEFF) + "ا" + chr(0x200F) + "ب"
    assert strip_bidi(text) == StripBidi()(text)


@given(st.text())
def test_strip_bidi_is_total_and_idempotent(text: str) -> None:
    once = StripBidi()(text)
    assert StripBidi()(once) == once


# --- UnifyLookalikes (issue 0004, story 23) ---

# Letters from other Arabic-script orthographies that are visually identical to an Arabic letter;
# under the Arabic-language assumption they fold to the Arabic form. Built from code points.
LOOKALIKE_FOLDS = [
    (chr(0x06A9), chr(0x0643)),  # Persian/Urdu keheh ک -> kaf ك
    (chr(0x06CC), chr(0x064A)),  # Farsi yeh ی -> yeh ي
    (chr(0x06C1), chr(0x0647)),  # heh goal ہ -> heh ه
    (chr(0x06D5), chr(0x0647)),  # ae (Kurdish heh) ە -> heh ه
    (chr(0x06BE), chr(0x0647)),  # heh doachashmee ھ -> heh ه
]


@pytest.mark.parametrize(("lookalike", "arabic"), LOOKALIKE_FOLDS)
def test_unify_lookalikes_folds_to_arabic_letter(lookalike: str, arabic: str) -> None:
    assert UnifyLookalikes()(lookalike) == arabic


def test_unify_lookalikes_accepted_residual_merges_maqsura_word() -> None:
    # The one fold that is not strictly lossless: a Persian-keyboard yeh (U+06CC) is
    # indistinguishable from alef maqsura word-finally, so علی merges to علي (accepted).
    persian_keyboard = chr(0x0639) + chr(0x0644) + chr(0x06CC)  # ain + lam + Farsi yeh
    assert UnifyLookalikes()(persian_keyboard) == chr(0x0639) + chr(0x0644) + chr(0x064A)  # علي


def test_unify_lookalikes_leaves_arabic_letters_untouched() -> None:
    # Already-Arabic kaf/yeh/heh and an alef maqsura are NOT touched (maqsura folding is opt-in).
    plain = chr(0x0643) + chr(0x064A) + chr(0x0647) + chr(0x0649)  # ك ي ه ى
    assert UnifyLookalikes()(plain) == plain


def test_unify_lookalikes_safety_is_encoding_repair() -> None:
    assert UnifyLookalikes().safety is SafetyClass.ENCODING_REPAIR


def test_unify_lookalikes_free_function_agrees_with_step() -> None:
    text = chr(0x06A9) + chr(0x06CC) + chr(0x06C1)
    assert unify_lookalikes(text) == UnifyLookalikes()(text)


@given(st.text())
def test_unify_lookalikes_is_total_and_idempotent(text: str) -> None:
    once = UnifyLookalikes()(text)
    assert UnifyLookalikes()(once) == once


# --- CollapseWhitespace (issue 0004, story 24) ---


def test_collapse_whitespace_collapses_a_run_to_a_single_space() -> None:
    assert CollapseWhitespace()("a  b") == "a b"


def test_collapse_whitespace_maps_unicode_spaces_to_ascii_space() -> None:
    # NBSP, a thin space and an ideographic space each become a single ASCII space.
    assert CollapseWhitespace()("a" + chr(0x00A0) + "b") == "a b"  # NBSP
    assert CollapseWhitespace()("a" + chr(0x2009) + "b") == "a b"  # THIN SPACE
    assert CollapseWhitespace()("a" + chr(0x3000) + "b") == "a b"  # IDEOGRAPHIC SPACE


def test_collapse_whitespace_collapses_leading_and_trailing_runs() -> None:
    # Runs collapse to a single space (collapse, not trim) — leaving a fixed point.
    assert CollapseWhitespace()("  a  ") == " a "


def test_collapse_whitespace_collapses_mixed_whitespace_kinds() -> None:
    # Tabs/newlines are whitespace too: a mixed run collapses to one ASCII space.
    assert CollapseWhitespace()("a \t\n b") == "a b"


def test_collapse_whitespace_safety_is_encoding_repair() -> None:
    assert CollapseWhitespace().safety is SafetyClass.ENCODING_REPAIR


def test_collapse_whitespace_free_function_agrees_with_step() -> None:
    text = "a  b\tc"
    assert collapse_whitespace(text) == CollapseWhitespace()(text)


@given(st.text())
def test_collapse_whitespace_is_total_and_idempotent(text: str) -> None:
    once = CollapseWhitespace()(text)
    assert CollapseWhitespace()(once) == once


# --- Safety-class invariant (story 41 / ADR-0004): lossless steps only touch encoding noise ---
#
# `safety` must be an ENFORCED property, not just a label nobody checks. The check: a lossless
# ENCODING_REPAIR step only ever rewrites encoding noise (presentation forms, tatweel, invisibles,
# look-alike letters, redundant whitespace), so on clean, canonical Arabic it must be the identity.
# A step mislabeled lossless that actually dropped or rewrote a real letter would be caught here.

# Code points that carry genuine Arabic signal. Defined INDEPENDENTLY of the step tables (it is NOT
# "whatever the tables happen to skip"), so a step whose table wrongly maps a real letter is caught
# rather than excused:
#   - U+0621-U+063A and U+0641-U+064A: the standard Arabic letters (hamza, alef, beh ... yeh). The
#     range is split to drop U+0640 TATWEEL (encoding noise RemoveTatweel deletes) and the rarely
#     used extended letters U+063B-U+063F, keeping the set to unambiguous core Arabic.
#   - U+064B-U+0652: tashkeel (harakat / tanween / shadda / sukun). Encoding repair must keep
#     vocalization; removing it is opt-in LINGUISTIC_FOLDING (issue 0006). None of these canonically
#     recompose with a base letter under NFC (only the U+0653-U+0655 madda/hamza marks do), so a
#     canonical run of them survives NFC unchanged.
_PROTECTED_CODE_POINTS = [chr(cp) for cp in (*range(0x0621, 0x063B), *range(0x0641, 0x0653))]

# Built off the registry, so a NEW lossless step is covered automatically -- that is the point of
# the invariant. (Every built-in step builds from an empty config today; a future step that needs
# config would surface here, which is the right place to reckon with its safety class.)
_LOSSLESS_STEPS = [
    step
    for name in sorted(registry.registered_names())
    if (step := registry.build(name, {})).safety is SafetyClass.ENCODING_REPAIR
]


@given(st.text(alphabet=_PROTECTED_CODE_POINTS))
def test_lossless_step_is_identity_on_clean_arabic(text: str) -> None:
    clean = unicodedata.normalize("NFC", text)  # canonical input: nothing legitimate to repair
    for step in _LOSSLESS_STEPS:
        assert step(clean) == clean, f"{type(step).__name__} altered clean Arabic text"
