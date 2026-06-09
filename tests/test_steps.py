"""Behavior of individual normalization steps (the `Step` family)."""

import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import (
    CollapseWhitespace,
    FoldPresentationForms,
    MarkClass,
    NormalizeUnicode,
    RemoveTashkeel,
    RemoveTatweel,
    SafetyClass,
    StripBidi,
    UnifyLookalikes,
    collapse_whitespace,
    fold_presentation_forms,
    normalize_unicode,
    registry,
    remove_tashkeel,
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


def test_collapse_whitespace_keeps_line_breaks_by_default() -> None:
    # A run that crosses a line boundary collapses to a single newline, NOT a space: line structure
    # is preserved by default (ADR-0010). Horizontal whitespace in the run is absorbed into it.
    assert CollapseWhitespace()("a \t\n b") == "a\nb"
    assert CollapseWhitespace()("a\n\n\nb") == "a\nb"  # a run of newlines -> one newline
    assert CollapseWhitespace()("a" + chr(0x2028) + "b") == "a\nb"  # Unicode LINE SEPARATOR
    # purely horizontal runs are unaffected -- they still become a single space
    assert CollapseWhitespace()("a \t b") == "a b"


def test_collapse_whitespace_collapse_lines_flattens_to_spaces() -> None:
    # The opt-in aggressive mode (what SEARCH uses): every run, line breaks included, -> one space.
    assert CollapseWhitespace(collapse_lines=True)("a \t\n b") == "a b"
    assert CollapseWhitespace(collapse_lines=True)("a\n\nb") == "a b"


def test_collapse_whitespace_serializes_collapse_lines() -> None:
    # The flag round-trips so a flattening (SEARCH-style) pipeline can be pinned and shared.
    step = CollapseWhitespace(collapse_lines=True)
    assert step.to_dict() == {"name": "CollapseWhitespace", "config": {"collapse_lines": True}}
    assert CollapseWhitespace.from_dict(step.to_dict()["config"])("a\nb") == "a b"


def test_collapse_whitespace_safety_is_encoding_repair() -> None:
    # Both modes are lossless encoding repair: the flag changes aggressiveness, not safety class.
    assert CollapseWhitespace().safety is SafetyClass.ENCODING_REPAIR
    assert CollapseWhitespace(collapse_lines=True).safety is SafetyClass.ENCODING_REPAIR


def test_collapse_whitespace_free_function_agrees_with_step() -> None:
    for text in ("a  b\tc", "a\n\nb", "line1 \n\t line2"):
        assert collapse_whitespace(text) == CollapseWhitespace()(text)
        assert collapse_whitespace(text, collapse_lines=True) == CollapseWhitespace(
            collapse_lines=True
        )(text)


@given(st.text())
def test_collapse_whitespace_is_total_and_idempotent(text: str) -> None:
    once = CollapseWhitespace()(text)
    assert CollapseWhitespace()(once) == once


@given(st.text())
def test_collapse_whitespace_collapse_lines_is_total_and_idempotent(text: str) -> None:
    once = CollapseWhitespace(collapse_lines=True)(text)
    assert CollapseWhitespace(collapse_lines=True)(once) == once


# --- RemoveTashkeel (issue 0006, stories 25 & 26) — the first LOSSY step ---

# Code points so the vocalization is pinned regardless of how this file is saved.
FATHA, DAMMA, KASRA, SUKUN = chr(0x064E), chr(0x064F), chr(0x0650), chr(0x0652)
SHADDA, MADDA, DAGGER_ALEF = chr(0x0651), chr(0x0653), chr(0x0670)
FATHATAN = chr(0x064B)  # tanween fath
SMALL_FATHA, OPEN_FATHATAN, SUKUN_BELOW = chr(0x0618), chr(0x08F0), chr(0x08D0)
MADDA_WAAJIB = chr(0x089C)  # an extended Qur'anic recitation mark (Arabic Extended-B)


def test_remove_tashkeel_default_strips_every_class() -> None:
    # The default removes a mark from EVERY class at once; only the bare carriers remain. This pins
    # one representative per class, including the small / open / extended marks the original
    # range-based table silently missed (harakat, tanween, shadda, madda, dagger alef, sukun, then
    # small fatha, open fathatan, and an extended Qur'anic mark).
    carriers = (0x0643, 0x062A, 0x0628, 0x0648, 0x0647, 0x0646, 0x0633, 0x0635, 0x0642)
    marks = (
        FATHA,
        FATHATAN,
        SHADDA,
        MADDA,
        DAGGER_ALEF,
        SUKUN,
        SMALL_FATHA,
        OPEN_FATHATAN,
        MADDA_WAAJIB,
    )
    vocalized = "".join(chr(c) + m for c, m in zip(carriers, marks, strict=True))
    assert RemoveTashkeel()(vocalized) == "".join(chr(c) for c in carriers)


def test_remove_tashkeel_selective_harakat_keeps_shadda() -> None:
    # دَرَّس with *remove harakat, keep shadda* -> درّس (the doubling survives), NOT درس (story 26).
    word = chr(0x062F) + FATHA + chr(0x0631) + SHADDA + FATHA + chr(0x0633)
    out = RemoveTashkeel(classes={MarkClass.HARAKAT})(word)
    assert out == chr(0x062F) + chr(0x0631) + SHADDA + chr(0x0633)
    assert out != chr(0x062F) + chr(0x0631) + chr(0x0633)  # shadda was NOT dropped


def test_remove_tashkeel_tanween_keeps_its_alef() -> None:
    # كتابًا (...beh + tanween fath + alef) with *remove tanween* -> كتابا: the U+064B mark is
    # deleted, the alef LETTER stays (removal never touches a carrier).
    word = "كتاب" + FATHATAN + chr(0x0627)
    assert RemoveTashkeel(classes={MarkClass.TANWEEN})(word) == "كتاب" + chr(0x0627)


def test_remove_tashkeel_dagger_alef_yields_standard_spelling() -> None:
    # هٰذا (heh + dagger alef + ذ + alef) with *remove dagger alef* -> the standard هذا spelling.
    word = chr(0x0647) + DAGGER_ALEF + chr(0x0630) + chr(0x0627)
    assert RemoveTashkeel(classes={MarkClass.DAGGER_ALEF})(word) == "هذا"


def test_remove_tashkeel_covers_small_open_and_extended_marks() -> None:
    # The widened classes catch the marks a numeric range missed — in the RIGHT class (the
    # partition stays pure by function): small fatha and sukun-below ride with HARAKAT; open
    # tanween is nunation (TANWEEN, NOT harakat); extended recitation marks ride in QURANIC.
    noon = chr(0x0646)
    assert RemoveTashkeel(classes={MarkClass.HARAKAT})(noon + SMALL_FATHA) == noon
    assert RemoveTashkeel(classes={MarkClass.HARAKAT})(noon + SUKUN_BELOW) == noon
    assert RemoveTashkeel(classes={MarkClass.HARAKAT})(noon + OPEN_FATHATAN) == noon + OPEN_FATHATAN
    assert RemoveTashkeel(classes={MarkClass.TANWEEN})(noon + OPEN_FATHATAN) == noon
    assert RemoveTashkeel(classes={MarkClass.QURANIC})(noon + MADDA_WAAJIB) == noon
    assert (
        RemoveTashkeel(classes={MarkClass.QURANIC})(chr(0x06DD)) == ""
    )  # a non-Mn structural sign


# مِنْ ("from"): م + kasra + ن + sukun. Sukun always rides with the harakat (never separable).
MIN = chr(0x0645) + KASRA + chr(0x0646) + SUKUN


def test_remove_tashkeel_removes_sukun_with_harakat() -> None:
    # Sukun is not a haraka, but it rides with HARAKAT for convenience -> bare من.
    assert RemoveTashkeel(classes={MarkClass.HARAKAT})(MIN) == chr(0x0645) + chr(0x0646)


def test_remove_tashkeel_sukun_rides_only_with_harakat() -> None:
    # Sukun goes ONLY when HARAKAT is selected: a class that does not own it leaves it untouched.
    assert RemoveTashkeel(classes={MarkClass.SHADDA})(MIN) == MIN


def test_remove_tashkeel_madda_removes_combining_mark_not_the_letter() -> None:
    # The COMBINING madda U+0653 is removed with MADDA; the alef-with-madda LETTER آ U+0622 is a
    # real alef variant (letter folding, issue 0007) and must be left untouched here.
    waw_with_madda = chr(0x0648) + MADDA  # waw carrying a combining madda
    assert RemoveTashkeel(classes={MarkClass.MADDA})(waw_with_madda) == chr(0x0648)
    alef_madda = chr(0x0622)  # the standalone letter آ
    assert RemoveTashkeel()(alef_madda) == alef_madda  # even full removal leaves the letter


def test_remove_tashkeel_safety_is_linguistic_folding() -> None:
    # Dediacritization discards information, so it is the LOSSY class (story 41 / ADR-0004); the
    # selection does not change the safety class.
    assert RemoveTashkeel().safety is SafetyClass.LINGUISTIC_FOLDING
    assert RemoveTashkeel(classes={MarkClass.SHADDA}).safety is SafetyClass.LINGUISTIC_FOLDING


def test_remove_tashkeel_free_function_agrees_with_step() -> None:
    fully_vocalized = chr(0x0643) + FATHA + chr(0x062A) + SHADDA + chr(0x0628) + FATHATAN
    assert remove_tashkeel(fully_vocalized) == RemoveTashkeel()(fully_vocalized)
    # ... and the selection passes through identically.
    assert remove_tashkeel(MIN, classes={MarkClass.HARAKAT}) == RemoveTashkeel(
        classes={MarkClass.HARAKAT}
    )(MIN)


def test_remove_tashkeel_serializes_its_selection() -> None:
    # The selection round-trips so a dediacritization pipeline can be pinned and reproduced (0016).
    step = RemoveTashkeel(classes={MarkClass.HARAKAT, MarkClass.SHADDA})
    spec = step.to_dict()
    assert spec == {
        "name": "RemoveTashkeel",
        "config": {"classes": ["harakat", "shadda"]},
    }
    rebuilt = RemoveTashkeel.from_dict(spec["config"])
    assert rebuilt == step  # value-equal (the precomputed table is excluded from equality)
    assert rebuilt(MIN) == step(MIN)


def test_remove_tashkeel_default_round_trips_through_registry() -> None:
    # Building from an empty config (what the registry does for a bare step) yields the all-classes
    # default, and its serialized form rehydrates to an equal step.
    built = registry.build("RemoveTashkeel", {})
    assert isinstance(built, RemoveTashkeel)
    assert RemoveTashkeel.from_dict(built.to_dict()["config"]) == built


@given(st.text())
def test_remove_tashkeel_is_total_and_idempotent(text: str) -> None:
    once = RemoveTashkeel()(text)  # never raises on arbitrary text
    assert RemoveTashkeel()(once) == once


# --- The mark-class partition invariant (chars.py: ONE STATED PRINCIPLE) ---
#
# The classes must TILE araclean's tashkeel repertoire: full removal deletes every Arabic-script
# combining mark, and only marks. These two tests re-derive the repertoire from the LIVE Unicode
# database, so a future Unicode version that adds an Arabic mark fails CI until the mark is triaged
# into a class in chars.py — membership is verified against the principle, never left to a guessed
# numeric range (the U+06BE lesson). The two NFC-composing hamza marks are the documented exception:
# under NFC they (re)compose into a distinct letter (أ ؤ ئ إ), so they are letter content owned by
# letter folding (issue 0007), not tashkeel.
_NFC_COMPOSING_HAMZA = frozenset((0x0654, 0x0655))
_ARABIC_BLOCKS = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x0870, 0x089F),  # Arabic Extended-B
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
    (0x10EC0, 0x10EFF),  # Arabic Extended-C
)


def test_remove_tashkeel_deletes_every_arabic_combining_mark() -> None:
    # Completeness: full removal deletes every Arabic-script nonspacing mark (Mn) save the excluded
    # hamza pair. A lone mark translates to "" — it has no carrier to leave behind.
    marks = [
        cp
        for lo, hi in _ARABIC_BLOCKS
        for cp in range(lo, hi + 1)
        if unicodedata.category(chr(cp)) == "Mn"
    ]
    survived = [
        hex(cp) for cp in marks if cp not in _NFC_COMPOSING_HAMZA and remove_tashkeel(chr(cp)) != ""
    ]
    assert survived == [], f"Arabic marks not covered by any MarkClass: {survived}"
    # the excluded pair is deliberately preserved here (NFC composes it; 0007 folds the seat).
    assert all(remove_tashkeel(chr(cp)) == chr(cp) for cp in _NFC_COMPOSING_HAMZA)


def test_remove_tashkeel_never_strips_a_carrier() -> None:
    # Carrier safety: removal touches marks only — base letters (incl. the hamza-seat and alef
    # variants that letter folding 0007 owns) and digits pass through untouched.
    carriers = (
        "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"  # the basic letters
        + "".join(
            map(chr, (0x0621, 0x0623, 0x0625, 0x0622, 0x0624, 0x0626, 0x0649, 0x0671))
        )  # hamza / alef family
        + "".join(map(chr, range(0x0660, 0x066A)))  # Arabic-Indic digits (U+0660-0669)
        + "".join(map(chr, range(0x06F0, 0x06FA)))  # extended Arabic-Indic digits (U+06F0-06F9)
        + "ABCabc123"
    )
    assert remove_tashkeel(carriers) == carriers


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
