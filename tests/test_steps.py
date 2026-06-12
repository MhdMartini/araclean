"""Behavior of individual normalization steps (the `Step` family)."""

import sys
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import (
    CleanHashtags,
    CleanHTML,
    CleanMentions,
    CleanMode,
    CleanURLs,
    CollapseWhitespace,
    DigitTarget,
    EmojiMode,
    EmojiSupportNotInstalledError,
    FoldAlef,
    FoldAlefMaqsura,
    FoldHamza,
    FoldPresentationForms,
    FoldTanweenAlef,
    FoldTehMarbuta,
    HandleEmoji,
    HashtagMode,
    MapDigits,
    MapPunctuation,
    MapQuotes,
    MarkClass,
    NormalizeUnicode,
    Pipeline,
    ReduceElongation,
    RemoveForeign,
    RemovePunctuation,
    RemoveStopwords,
    RemoveTashkeel,
    RemoveTatweel,
    SafetyClass,
    StripBidi,
    TehMarbutaTarget,
    Trim,
    UnifyLookalikes,
    clean_hashtags,
    clean_html,
    clean_mentions,
    clean_urls,
    collapse_whitespace,
    fold_alef,
    fold_alef_maqsura,
    fold_hamza,
    fold_presentation_forms,
    fold_tanween_alef,
    fold_teh_marbuta,
    handle_emoji,
    map_digits,
    map_punctuation,
    map_quotes,
    normalize_unicode,
    reduce_elongation,
    registry,
    remove_foreign,
    remove_punctuation,
    remove_stopwords,
    remove_tashkeel,
    remove_tatweel,
    stopwords,
    strip_bidi,
    trim,
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
        "config": {"classes": ["harakat", "shadda"], "position": "all"},
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


# --- FoldAlef (issue 0007, story 27) — the alef-variant letter fold ---

BARE_ALEF = chr(0x0627)
# Every alef-variant LETTER folds to bare alef (built from code points, immune to file encoding):
# alef-with-hamza-above/below, alef-with-madda, alef-wasla, and the wavy-hamza alefs.
ALEF_VARIANTS = [
    (chr(0x0623), BARE_ALEF),  # أ alef with hamza above
    (chr(0x0625), BARE_ALEF),  # إ alef with hamza below
    (chr(0x0622), BARE_ALEF),  # آ alef with madda
    (chr(0x0671), BARE_ALEF),  # ٱ alef wasla
    (chr(0x0672), BARE_ALEF),  # ٲ alef with wavy hamza above
    (chr(0x0673), BARE_ALEF),  # ٳ alef with wavy hamza below
]


@pytest.mark.parametrize(("variant", "expected"), ALEF_VARIANTS)
def test_fold_alef_folds_every_variant_to_bare_alef(variant: str, expected: str) -> None:
    assert FoldAlef()(variant) == expected


def test_fold_alef_in_words() -> None:
    # أحمد / إبراهيم / آمنة / ٱسم -> the bare-alef spellings (the alef variant only; tail intact).
    assert FoldAlef()("أحمد") == BARE_ALEF + "حمد"
    assert FoldAlef()("إبراهيم") == BARE_ALEF + "براهيم"
    assert FoldAlef()("آمنة") == BARE_ALEF + "منة"
    assert FoldAlef()("ٱسم") == BARE_ALEF + "سم"


def test_fold_alef_leaves_bare_alef_and_other_letters_untouched() -> None:
    plain = BARE_ALEF + "محمد لا إله"  # already-bare alef and unrelated letters
    assert FoldAlef()(plain) == BARE_ALEF + "محمد لا " + BARE_ALEF + "له"  # only the إ folds


def test_fold_alef_safety_is_linguistic_folding() -> None:
    # Collapsing the alef variants discards a spelling distinction, so it is the LOSSY class.
    assert FoldAlef().safety is SafetyClass.LINGUISTIC_FOLDING


def test_fold_alef_free_function_agrees_with_step() -> None:
    text = "أحمد وإبراهيم"
    assert fold_alef(text) == FoldAlef()(text)


@given(st.text())
def test_fold_alef_is_total_and_idempotent(text: str) -> None:
    once = FoldAlef()(text)  # never raises on arbitrary text
    assert FoldAlef()(once) == once


# --- FoldAlefMaqsura (issue 0007, story 30) — alef maqsura -> yeh ---

YEH = chr(0x064A)
ALEF_MAQSURA = chr(0x0649)


def test_fold_alef_maqsura_folds_to_yeh() -> None:
    assert FoldAlefMaqsura()(ALEF_MAQSURA) == YEH


def test_fold_alef_maqsura_merges_ala_words() -> None:
    # The documented merge that makes this fold opt-in: على (…+ alef maqsura) -> علي (…+ yeh), so it
    # collides with the genuine علي. This is *why* it never runs under LIGHT.
    ala = chr(0x0639) + chr(0x0644) + ALEF_MAQSURA  # على
    assert FoldAlefMaqsura()(ala) == chr(0x0639) + chr(0x0644) + YEH  # علي


def test_fold_alef_maqsura_leaves_yeh_and_other_letters_untouched() -> None:
    plain = chr(0x0639) + chr(0x0644) + YEH  # already-yeh علي
    assert FoldAlefMaqsura()(plain) == plain


def test_fold_alef_maqsura_safety_is_linguistic_folding() -> None:
    assert FoldAlefMaqsura().safety is SafetyClass.LINGUISTIC_FOLDING


def test_fold_alef_maqsura_free_function_agrees_with_step() -> None:
    text = chr(0x0639) + chr(0x0644) + ALEF_MAQSURA
    assert fold_alef_maqsura(text) == FoldAlefMaqsura()(text)


@given(st.text())
def test_fold_alef_maqsura_is_total_and_idempotent(text: str) -> None:
    once = FoldAlefMaqsura()(text)
    assert FoldAlefMaqsura()(once) == once


# --- FoldHamza (issue 0007, story 28) — the separate, configurably-aggressive hamza fold ---

WAW = chr(0x0648)
WAW_HAMZA = chr(0x0624)  # ؤ
YEH_HAMZA = chr(0x0626)  # ئ
STANDALONE_HAMZA = chr(0x0621)  # ء
HAMZA_ABOVE, HAMZA_BELOW = chr(0x0654), chr(0x0655)  # the combining hamza marks


def test_fold_hamza_light_folds_carriers_keeps_standalone() -> None:
    # Light (default): the waw/yeh hamza carriers fold to bare waw/yeh; مؤمن -> مومن, سئل -> سيل.
    assert FoldHamza()("مؤمن") == "م" + WAW + "من"
    assert FoldHamza()("سئل") == "س" + YEH + "ل"
    # ... but the STANDALONE hamza ء is preserved (that is the "light" contract).
    assert FoldHamza()("جزء") == "جزء"
    assert STANDALONE_HAMZA in FoldHamza()(STANDALONE_HAMZA)


def test_fold_hamza_heavy_also_drops_standalone() -> None:
    # Heavy: the standalone hamza ء is dropped too; carriers still fold.
    heavy = FoldHamza(drop_standalone_hamza=True)
    assert heavy("جزء") == "جز"
    assert heavy("مؤمن") == "م" + WAW + "من"
    # The high hamza ٴ U+0674 is the other standalone hamza letter: dropped in heavy, kept in light
    # (it has no seat to fold onto, exactly like ء).
    high_hamza = chr(0x0674)
    assert heavy(high_hamza) == ""
    assert FoldHamza()(high_hamza) == high_hamza


def test_fold_hamza_owns_the_combining_hamza_marks() -> None:
    # The combining hamza marks U+0654/U+0655 are hamza ON a carrier (GLOSSARY: Hamza).
    # RemoveTashkeel deliberately leaves them (issue 0006 documents them as letter content owned
    # by letter folding); FoldHamza is that owner — it deletes them in BOTH modes, folding
    # carrier+hamza to a bare carrier, parallel to folding ؤ/ئ. (NFC composes them away anyway.)
    beh = chr(0x0628)
    assert FoldHamza()(beh + HAMZA_ABOVE) == beh
    assert FoldHamza()(beh + HAMZA_BELOW) == beh
    assert FoldHamza(drop_standalone_hamza=True)(beh + HAMZA_ABOVE) == beh


def test_fold_hamza_leaves_precomposed_alef_hamza_to_fold_alef() -> None:
    # Division of labor: the precomposed alef-hamza LETTERS أ/إ are alef territory (FoldAlef), so
    # FoldHamza leaves them untouched — it owns the waw/yeh carriers and the combining marks only.
    assert FoldHamza()(chr(0x0623)) == chr(0x0623)  # أ untouched
    assert FoldHamza()(chr(0x0625)) == chr(0x0625)  # إ untouched


def test_fold_hamza_safety_is_linguistic_folding() -> None:
    assert FoldHamza().safety is SafetyClass.LINGUISTIC_FOLDING
    assert FoldHamza(drop_standalone_hamza=True).safety is SafetyClass.LINGUISTIC_FOLDING


def test_fold_hamza_serializes_its_mode() -> None:
    # The light/heavy toggle round-trips so an aggressive-folding pipeline can be pinned (0016).
    light, heavy = FoldHamza(), FoldHamza(drop_standalone_hamza=True)
    assert light.to_dict() == {"name": "FoldHamza", "config": {"drop_standalone_hamza": False}}
    assert heavy.to_dict() == {"name": "FoldHamza", "config": {"drop_standalone_hamza": True}}
    assert FoldHamza.from_dict(heavy.to_dict()["config"]) == heavy
    assert FoldHamza.from_dict(heavy.to_dict()["config"])("جزء") == "جز"


def test_fold_hamza_default_round_trips_through_registry() -> None:
    built = registry.build("FoldHamza", {})  # bare step -> the light default
    assert isinstance(built, FoldHamza)
    assert built("جزء") == "جزء"  # standalone kept
    assert FoldHamza.from_dict(built.to_dict()["config"]) == built


def test_fold_hamza_free_function_agrees_with_step() -> None:
    text = "مؤمن سئل عن جزء"
    assert fold_hamza(text) == FoldHamza()(text)
    assert fold_hamza(text, drop_standalone_hamza=True) == FoldHamza(drop_standalone_hamza=True)(
        text
    )


@given(st.text())
def test_fold_hamza_is_total_and_idempotent(text: str) -> None:
    once = FoldHamza()(text)
    assert FoldHamza()(once) == once
    heavy_once = FoldHamza(drop_standalone_hamza=True)(text)
    assert FoldHamza(drop_standalone_hamza=True)(heavy_once) == heavy_once


# --- FoldTehMarbuta (issue 0007, story 29) — configurable target ---

HEH = chr(0x0647)
TEH = chr(0x062A)
TEH_MARBUTA = chr(0x0629)  # ة
TEH_MARBUTA_GOAL = chr(0x06C3)  # ۃ the goal form
MADRASA = "مدرس"  # the stem of مدرسة minus its final teh marbuta


def test_fold_teh_marbuta_default_target_is_heh() -> None:
    # مدرسة -> مدرسه (the common search fold): teh marbuta ة -> heh ه by default.
    assert FoldTehMarbuta()(MADRASA + TEH_MARBUTA) == MADRASA + HEH


def test_fold_teh_marbuta_target_teh() -> None:
    assert FoldTehMarbuta(target=TehMarbutaTarget.TEH)(MADRASA + TEH_MARBUTA) == MADRASA + TEH


def test_fold_teh_marbuta_target_keep_is_identity() -> None:
    # `keep` leaves the teh marbuta in place (the step is a no-op for that target).
    word = MADRASA + TEH_MARBUTA
    assert FoldTehMarbuta(target=TehMarbutaTarget.KEEP)(word) == word


def test_fold_teh_marbuta_folds_the_goal_form_too() -> None:
    # The goal-form teh marbuta ۃ U+06C3 folds with ة (issue 0004 routed it to this opt-in fold).
    assert FoldTehMarbuta()(MADRASA + TEH_MARBUTA_GOAL) == MADRASA + HEH


def test_fold_teh_marbuta_leaves_plain_heh_and_teh_untouched() -> None:
    plain = MADRASA + HEH + TEH  # already heh / teh — nothing to fold
    assert FoldTehMarbuta()(plain) == plain


def test_fold_teh_marbuta_safety_is_linguistic_folding() -> None:
    assert FoldTehMarbuta().safety is SafetyClass.LINGUISTIC_FOLDING
    assert FoldTehMarbuta(target=TehMarbutaTarget.KEEP).safety is SafetyClass.LINGUISTIC_FOLDING


def test_fold_teh_marbuta_serializes_its_target() -> None:
    # The target round-trips so a folding pipeline can be pinned and reproduced (0016).
    step = FoldTehMarbuta(target=TehMarbutaTarget.TEH)
    assert step.to_dict() == {"name": "FoldTehMarbuta", "config": {"target": "teh"}}
    rebuilt = FoldTehMarbuta.from_dict(step.to_dict()["config"])
    assert rebuilt == step
    assert rebuilt(MADRASA + TEH_MARBUTA) == MADRASA + TEH


def test_fold_teh_marbuta_default_round_trips_through_registry() -> None:
    built = registry.build("FoldTehMarbuta", {})  # bare step -> the heh default
    assert isinstance(built, FoldTehMarbuta)
    assert built(MADRASA + TEH_MARBUTA) == MADRASA + HEH
    assert FoldTehMarbuta.from_dict(built.to_dict()["config"]) == built


def test_fold_teh_marbuta_free_function_agrees_with_step() -> None:
    text = MADRASA + TEH_MARBUTA
    assert fold_teh_marbuta(text) == FoldTehMarbuta()(text)
    assert fold_teh_marbuta(text, target=TehMarbutaTarget.TEH) == FoldTehMarbuta(
        target=TehMarbutaTarget.TEH
    )(text)


@given(st.text())
def test_fold_teh_marbuta_is_total_and_idempotent(text: str) -> None:
    for target in TehMarbutaTarget:
        once = FoldTehMarbuta(target=target)(text)
        assert FoldTehMarbuta(target=target)(once) == once


# --- The letter-fold completeness invariant (chars.py: ONE STATED PRINCIPLE) ---
#
# The sibling of the mark-class partition below, for the opt-in letter folds (issue 0007). Re-derive
# every Arabic-script alef / hamza / maqsura LETTER from the LIVE Unicode database — independent
# of the fold tables (names and decompositions, not "whatever the tables happen to skip") — and
# assert each candidate is either folded by its step or in the explicit, documented EXCLUDED set, so
# a future Unicode letter fails CI until it is triaged, never left to a guessed range (the U+06BE
# lesson). Membership is checked through BEHAVIOR (the step's output), not table internals. The
# combining hamza marks U+0654/U+0655 are letter content guarded by the mark-partition test
# (this is the LETTER repertoire). Presentation forms are excluded from the blocks: those fold to
# base letters via FoldPresentationForms first, and only then do these folds see them.
_LETTER_BLOCKS = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x0870, 0x089F),  # Arabic Extended-B
    (0x08A0, 0x08FF),  # Arabic Extended-A
)
# Alef LETTERS deliberately NOT folded (chars.py FoldAlef note documents why) — not contemporary
# Arabic: high-hamza alef, the digit-annotated alefs, the Extended-B manuscript alefs, the low alef.
_ALEF_EXCLUDED = frozenset((0x0675, 0x0773, 0x0774, *range(0x0870, 0x0883), 0x08AD))
# Non-alef hamza LETTERS deliberately NOT folded (chars.py FoldHamza note) — non-Arabic hamza
# carriers and the high-hamza waw/u/yeh compositions.
_HAMZA_EXCLUDED = frozenset(
    (0x0676, 0x0677, 0x0678, 0x0681, 0x06C2, 0x06D3, 0x076C, 0x0883, 0x08A1, 0x08A8)
)
# The Unicode spelling of the maqsura form, read from its OWN code point so the source never
# hard-codes the project's non-preferred spelling (GLOSSARY: Alef maqsura).
_MAQSURA_TOKEN = unicodedata.name(chr(0x0649)).split()[-1]


def _arabic_letters() -> set[int]:
    return {
        cp
        for lo, hi in _LETTER_BLOCKS
        for cp in range(lo, hi + 1)
        if unicodedata.category(chr(cp)).startswith("L")
    }


def _is_alef_letter(cp: int) -> bool:
    # An alef variant by the UCD: named "...ALEF..." (but not maqsura ى), or an NFKD that begins
    # with the bare alef U+0627 (e.g. the high-hamza alef U+0675 → U+0627 U+0674).
    name = unicodedata.name(chr(cp), "")
    if "ALEF" in name and _MAQSURA_TOKEN not in name:
        return True
    decomposition = unicodedata.normalize("NFKD", chr(cp))
    return bool(decomposition) and ord(decomposition[0]) == 0x0627


def test_fold_alef_covers_every_arabic_alef_letter() -> None:
    fold, bare = FoldAlef(), chr(0x0627)
    candidates = {cp for cp in _arabic_letters() if cp != 0x0627 and _is_alef_letter(cp)}
    uncovered = sorted(
        hex(cp) for cp in candidates if fold(chr(cp)) != bare and cp not in _ALEF_EXCLUDED
    )
    assert uncovered == [], f"alef letters neither folded to bare alef nor excluded: {uncovered}"
    # the EXCLUDED set is real (a subset of the candidates) and genuinely left untouched.
    assert candidates >= _ALEF_EXCLUDED
    assert all(fold(chr(cp)) == chr(cp) for cp in _ALEF_EXCLUDED)


def test_fold_hamza_covers_every_arabic_hamza_letter() -> None:
    # Heavy mode touches every hamza letter the step owns (carriers in both modes; the standalone ء
    # and the high hamza ٴ in heavy), so it is the test for "is this letter handled at all".
    heavy = FoldHamza(drop_standalone_hamza=True)
    candidates = {
        cp
        for cp in _arabic_letters()
        if "HAMZA" in unicodedata.name(chr(cp), "") and not _is_alef_letter(cp)
    }
    uncovered = sorted(
        hex(cp) for cp in candidates if heavy(chr(cp)) == chr(cp) and cp not in _HAMZA_EXCLUDED
    )
    assert uncovered == [], f"hamza letters neither folded nor excluded: {uncovered}"
    assert candidates >= _HAMZA_EXCLUDED
    assert all(heavy(chr(cp)) == chr(cp) for cp in _HAMZA_EXCLUDED)


def test_fold_alef_maqsura_is_the_only_arabic_maqsura_letter() -> None:
    fold, yeh = FoldAlefMaqsura(), chr(0x064A)
    candidates = {cp for cp in _arabic_letters() if _MAQSURA_TOKEN in unicodedata.name(chr(cp), "")}
    assert candidates == {0x0649}  # ى is the sole Arabic alef-maqsura letter
    assert all(fold(chr(cp)) == yeh for cp in candidates)


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


def test_marks_added_after_unicode_15_are_triaged_into_quranic() -> None:
    # Unicode 16.0/17.0 additions, triaged ahead of the interpreter shipping that UCD — the live
    # completeness test above only sees marks the RUNNING Python's database knows. Pepet (Pegon
    # vowel sign, 16.0) and the double vertical bar below (Old Sindhi tanween, 17.0) follow the
    # non-Arabic-orthography rule (like U+0659-U+065C); the alef overlay (16.0) and small low
    # noon (17.0) are Qur'anic annotation.
    for cp in (0x0897, 0x10EFA, 0x10EFB, 0x10EFC):
        assert RemoveTashkeel(classes={MarkClass.QURANIC})(chr(cp)) == "", hex(cp)


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


# --- MapDigits (issue 0008, story 31) — convert among the three digit systems ---

# Built from code points so the expectation is immune to how this file is saved. Each system is a
# contiguous 0-9 run keyed by its zero: ASCII U+0030, Arabic-Indic U+0660, Extended U+06F0.
ARABIC_INDIC_123 = chr(0x0661) + chr(0x0662) + chr(0x0663)  # ١٢٣
EXTENDED_123 = chr(0x06F1) + chr(0x06F2) + chr(0x06F3)  # ۱۲۳ (Persian/Urdu)


def test_map_digits_default_target_is_ascii() -> None:
    # ١٢٣ -> 123: the default folds every digit system to ASCII (numbers parse consistently).
    assert MapDigits()(ARABIC_INDIC_123) == "123"


def test_map_digits_ascii_folds_extended_too() -> None:
    # The Persian/Urdu (Extended) digits ۱۲۳ also fold to ASCII under the default target.
    assert MapDigits()(EXTENDED_123) == "123"


def test_map_digits_target_arabic_indic() -> None:
    # Target Arabic-Indic: 123 -> ١٢٣, and the Extended digits fold to Arabic-Indic too.
    step = MapDigits(target=DigitTarget.ARABIC_INDIC)
    assert step("123") == ARABIC_INDIC_123
    assert step(EXTENDED_123) == ARABIC_INDIC_123


def test_map_digits_target_extended() -> None:
    # Target Extended (Persian/Urdu): ASCII and Arabic-Indic both fold to ۰-۹.
    step = MapDigits(target=DigitTarget.EXTENDED_ARABIC_INDIC)
    assert step("123") == EXTENDED_123
    assert step(ARABIC_INDIC_123) == EXTENDED_123


def test_map_digits_leaves_the_target_system_untouched() -> None:
    # Folding to a target is a no-op on digits already in that system (the step is a fixed point).
    assert MapDigits()("123") == "123"
    assert MapDigits(target=DigitTarget.ARABIC_INDIC)(ARABIC_INDIC_123) == ARABIC_INDIC_123


def test_map_digits_does_not_touch_letters() -> None:
    # Only the three digit systems are in scope: surrounding Arabic letters pass through untouched.
    word = "رقم " + ARABIC_INDIC_123  # "number ١٢٣"
    assert MapDigits()(word) == "رقم 123"


def test_map_digits_safety_is_linguistic_folding() -> None:
    assert MapDigits().safety is SafetyClass.LINGUISTIC_FOLDING
    assert MapDigits(target=DigitTarget.ARABIC_INDIC).safety is SafetyClass.LINGUISTIC_FOLDING


def test_map_digits_serializes_its_target() -> None:
    # The target round-trips so a digit-folding pipeline can be pinned and reproduced (0016).
    step = MapDigits(target=DigitTarget.ARABIC_INDIC)
    assert step.to_dict() == {
        "name": "MapDigits",
        "config": {"target": "arabic_indic", "map_separators": False},
    }
    rebuilt = MapDigits.from_dict(step.to_dict()["config"])
    assert rebuilt == step
    assert rebuilt("123") == ARABIC_INDIC_123


def test_map_digits_default_round_trips_through_registry() -> None:
    built = registry.build("MapDigits", {})  # bare step -> the ASCII default
    assert isinstance(built, MapDigits)
    assert built(ARABIC_INDIC_123) == "123"
    assert MapDigits.from_dict(built.to_dict()["config"]) == built


def test_map_digits_free_function_agrees_with_step() -> None:
    text = "رقم " + ARABIC_INDIC_123 + " و " + EXTENDED_123
    assert map_digits(text) == MapDigits()(text)
    assert map_digits(text, target=DigitTarget.ARABIC_INDIC) == MapDigits(
        target=DigitTarget.ARABIC_INDIC
    )(text)


@given(st.text())
def test_map_digits_is_total_and_idempotent(text: str) -> None:
    for target in DigitTarget:
        once = MapDigits(target=target)(text)
        assert MapDigits(target=target)(once) == once


# --- MapPunctuation (issue 0008, story 32) — Arabic punctuation -> Latin, separator-safe ---

ARABIC_COMMA = chr(0x060C)  # ،
ARABIC_SEMICOLON = chr(0x061B)  # ؛
ARABIC_QUESTION = chr(0x061F)  # ؟


def test_map_punctuation_maps_comma_semicolon_question() -> None:
    # ما رأيك؟ نعم، شكرا؛ -> the three marks become ? , ; at the right positions.
    text = "ما رأيك" + ARABIC_QUESTION + " نعم" + ARABIC_COMMA + " شكرا" + ARABIC_SEMICOLON
    assert MapPunctuation()(text) == "ما رأيك? نعم, شكرا;"


def test_map_punctuation_preserves_a_digit_grouped_separator() -> None:
    # Number-separator safety: an Arabic comma BETWEEN two digits is a numeric separator (e.g. a
    # thousands-grouped number), so it is preserved — not turned into a sentence comma.
    assert MapPunctuation()("1" + ARABIC_COMMA + "234") == "1" + ARABIC_COMMA + "234"
    # The guard holds before MapDigits runs too: ، between Arabic-Indic digits is still a separator.
    grouped = chr(0x0661) + ARABIC_COMMA + chr(0x0662)  # ١،٢
    assert MapPunctuation()(grouped) == grouped


def test_map_punctuation_maps_a_comma_next_to_a_single_digit() -> None:
    # Only a mark flanked by digits on BOTH sides is a separator. A trailing/leading comma touching
    # just one digit is ordinary sentence punctuation and is mapped.
    assert MapPunctuation()("5" + ARABIC_COMMA) == "5,"  # nothing after -> sentence comma
    assert MapPunctuation()(ARABIC_COMMA + "5") == ",5"  # nothing before -> sentence comma


def test_map_punctuation_leaves_dedicated_number_separators_untouched() -> None:
    # The decimal (U+066B), thousands (U+066C) and date (U+060D) separators are out of scope
    # entirely — never mapped — so a decimal number survives unchanged.
    decimal = "3" + chr(0x066B) + "14"  # ٣٫١٤
    assert MapPunctuation()(decimal) == decimal


def test_map_punctuation_safety_is_linguistic_folding() -> None:
    assert MapPunctuation().safety is SafetyClass.LINGUISTIC_FOLDING


def test_map_punctuation_serializes_and_round_trips_through_registry() -> None:
    step = MapPunctuation()
    assert step.to_dict() == {"name": "MapPunctuation", "config": {}}
    built = registry.build("MapPunctuation", {})
    assert isinstance(built, MapPunctuation)
    assert MapPunctuation.from_dict(step.to_dict()["config"]) == step


def test_map_punctuation_free_function_agrees_with_step() -> None:
    text = "ما رأيك" + ARABIC_QUESTION + " 1" + ARABIC_COMMA + "234" + ARABIC_SEMICOLON
    assert map_punctuation(text) == MapPunctuation()(text)


@given(st.text())
def test_map_punctuation_is_total_and_idempotent(text: str) -> None:
    once = MapPunctuation()(text)
    assert MapPunctuation()(once) == once


# --- ReduceElongation (issue 0009, story 33) — collapse repeated-letter word-lengthening ---

# Built from code points so the expectation is immune to how this file is saved.
ELONGATED = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل (4 yeh)
REDUCED = chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644)  # جميل (1 yeh)
REDUCED_CAP2 = chr(0x062C) + chr(0x0645) + chr(0x064A) * 2 + chr(0x0644)  # جميّل-style (2 yeh)
ELONGATED_ALEF = chr(0x0631) + chr(0x0627) * 4 + chr(0x0626) + chr(0x0639)  # راااائع (4 alefs)
REDUCED_ALEF = chr(0x0631) + chr(0x0627) + chr(0x0626) + chr(0x0639)  # رائع (1 alef)


def test_reduce_elongation_cap_one_collapses_to_a_single_letter() -> None:
    # The default cap (1) collapses a lengthened run all the way to one letter.
    assert ReduceElongation()(ELONGATED) == REDUCED
    assert ReduceElongation()(ELONGATED_ALEF) == REDUCED_ALEF


def test_reduce_elongation_cap_two_keeps_a_doubled_letter() -> None:
    # Cap 2 retains emphasis: the run is capped at two copies, not one (جمييييل -> جميّل-style).
    assert ReduceElongation(cap=2)(ELONGATED) == REDUCED_CAP2


def test_reduce_elongation_cap_two_leaves_an_ordinary_double_untouched() -> None:
    # A run no longer than the cap is not elongation past the cap, so it is left as written: a word
    # already spelled with a doubled letter (run of 2) survives cap 2 unchanged. The cap is the
    # contract — it does not try to tell emphasis from a legitimate double.
    assert ReduceElongation(cap=2)(REDUCED_CAP2) == REDUCED_CAP2


def test_reduce_elongation_never_touches_digits() -> None:
    # The load-bearing exclusion: a repeated digit is a NUMBER, not emphasis. Collapsing it would
    # turn 1000 into 1, so no digit system is ever capped — ASCII, Arabic-Indic and Extended alike.
    assert ReduceElongation()("1000") == "1000"
    arabic_indic_1000 = chr(0x0661) + chr(0x0660) * 3  # ١٠٠٠
    assert ReduceElongation()(arabic_indic_1000) == arabic_indic_1000
    extended_run = chr(0x06F5) * 4  # an Extended (Persian/Urdu) digit repeated
    assert ReduceElongation()(extended_run) == extended_run


def test_reduce_elongation_only_caps_letters_never_digits_or_marks() -> None:
    # Soundness invariant (live UCD): scanning every Arabic-script code point, the only runs the
    # step collapses are runs of an Arabic LETTER (Unicode category L*) — never a digit (the
    # 1000->1 hazard) and never a combining mark. Re-derived from the Unicode database, so a code
    # point that slipped into the elongatable class wrongly fails CI. (This guards soundness, not
    # completeness: the step may legitimately leave a rare extended letter uncapped — see chars.py.)
    reduce = ReduceElongation()  # cap 1
    for lo, hi in _LETTER_BLOCKS:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            if reduce(ch * 3) == ch:  # this code point's run was capped
                category = unicodedata.category(ch)
                assert category.startswith("L"), f"{hex(cp)} ({category}) capped, not a letter"


@pytest.mark.parametrize("cap", [0, -1])
def test_reduce_elongation_rejects_a_cap_below_one(cap: int) -> None:
    # cap < 1 would match a lone letter and replace it with nothing — i.e. delete letters — so it is
    # rejected at construction (and in the free function), never silently corrupting text.
    with pytest.raises(ValueError, match="cap"):
        ReduceElongation(cap=cap)
    with pytest.raises(ValueError, match="cap"):
        reduce_elongation("نص", cap=cap)


def test_reduce_elongation_safety_is_linguistic_folding() -> None:
    assert ReduceElongation().safety is SafetyClass.LINGUISTIC_FOLDING
    assert ReduceElongation(cap=2).safety is SafetyClass.LINGUISTIC_FOLDING


def test_reduce_elongation_free_function_agrees_with_step() -> None:
    assert reduce_elongation(ELONGATED) == ReduceElongation()(ELONGATED)
    assert reduce_elongation(ELONGATED, cap=2) == ReduceElongation(cap=2)(ELONGATED)


def test_reduce_elongation_serializes_its_cap() -> None:
    # The cap AND the resolved trigger round-trip so an elongation-reducing pipeline can be pinned
    # and reproduced (0016): min_run=None resolves to max(cap+1, 3) at construction, so the
    # serialized form never carries the placeholder.
    step = ReduceElongation(cap=2)
    assert step.to_dict() == {"name": "ReduceElongation", "config": {"cap": 2, "min_run": 3}}
    rebuilt = ReduceElongation.from_dict(step.to_dict()["config"])
    assert rebuilt == step
    assert rebuilt(ELONGATED) == REDUCED_CAP2


def test_reduce_elongation_default_round_trips_through_registry() -> None:
    built = registry.build("ReduceElongation", {})  # bare step -> the cap-1 default
    assert isinstance(built, ReduceElongation)
    assert built(ELONGATED) == REDUCED
    assert ReduceElongation.from_dict(built.to_dict()["config"]) == built


@given(st.text())
def test_reduce_elongation_is_total_and_idempotent(text: str) -> None:
    for cap in (1, 2):
        once = ReduceElongation(cap=cap)(text)
        assert ReduceElongation(cap=cap)(once) == once


# --- CleanURLs / CleanMentions / CleanHTML (issue 0012, story 34) — noise removal -------------
#
# Cleaning = removal of non-linguistic noise (CONTEXT.md), a sibling of normalization. Each step
# either deletes the matched noise or replaces it with a configurable placeholder token. Entity
# unescaping is always part of CleanHTML. None run under LIGHT (safety is CLEANING, never
# ENCODING_REPAIR).

# Code points, not glyphs, for the bits that surround the noise, so the expectation is immune to
# how this file is saved. "زوروا" (visit) U+0632 U+0648 U+0631 U+0648 U+0627; "الآن" (now).
_VISIT = chr(0x0632) + chr(0x0648) + chr(0x0631) + chr(0x0648) + chr(0x0627)  # زوروا
_NOW = chr(0x0627) + chr(0x0644) + chr(0x0622) + chr(0x0646)  # الآن


def test_clean_urls_delete_removes_the_url_leaving_surrounding_text() -> None:
    text = f"{_VISIT} https://x.co {_NOW}"
    # Delete mode removes the URL span itself; the spaces that flanked it stay (two now adjacent).
    assert CleanURLs()(text) == f"{_VISIT}  {_NOW}"


def test_clean_urls_placeholder_mode_default_token_is_english() -> None:
    step = CleanURLs(mode=CleanMode.PLACEHOLDER)
    assert step("see https://x.co/page now") == "see [URL] now"
    # www.-prefixed URLs are matched too, case-insensitively.
    assert step("HTTP://A WWW.b.com") == "[URL] [URL]"


def test_clean_urls_placeholder_token_is_configurable() -> None:
    arabic_token = "[" + chr(0x0631) + chr(0x0627) + chr(0x0628) + chr(0x0637) + "]"  # [رابط]
    step = CleanURLs(mode=CleanMode.PLACEHOLDER, placeholder=arabic_token)
    assert step("x https://x.co y") == f"x {arabic_token} y"


def test_clean_urls_leaves_non_url_text_untouched() -> None:
    # No scheme / www. anchor -> nothing is a URL; Arabic prose and a bare dotted word survive.
    text = f"{_VISIT} {_NOW} example.com"
    assert CleanURLs()(text) == text


def test_clean_urls_safety_is_cleaning() -> None:
    assert CleanURLs().safety is SafetyClass.CLEANING


def test_clean_urls_free_function_agrees_with_step() -> None:
    text = "a https://x.co b"
    assert clean_urls(text) == CleanURLs()(text)
    assert clean_urls(text, mode=CleanMode.PLACEHOLDER) == CleanURLs(mode=CleanMode.PLACEHOLDER)(
        text
    )


def test_clean_urls_serializes_its_mode_and_token_and_round_trips() -> None:
    step = CleanURLs(mode=CleanMode.PLACEHOLDER, placeholder="[link]")
    assert step.to_dict() == {
        "name": "CleanURLs",
        "config": {"mode": "placeholder", "placeholder": "[link]"},
    }
    rebuilt = CleanURLs.from_dict(step.to_dict()["config"])
    assert rebuilt == step
    # Bare config -> the delete default, reconstructed through the registry.
    built = registry.build("CleanURLs", {})
    assert built == CleanURLs()
    assert built("x https://x.co") == "x "


@given(st.text())
def test_clean_urls_is_total_and_idempotent(text: str) -> None:
    for mode in ("delete", "placeholder"):
        once = clean_urls(text, mode=mode)  # type: ignore[arg-type]
        assert clean_urls(once, mode=mode) == once  # type: ignore[arg-type]


# "محمد" (Muhammad) as an @-handle target, in code points.
_HANDLE = chr(0x0645) + chr(0x062D) + chr(0x0645) + chr(0x062F)  # محمد


def test_clean_mentions_delete_removes_the_mention() -> None:
    text = f"hi @user and @{_HANDLE} done"
    # Both an ASCII handle and an Arabic handle (\w is Unicode-aware) are removed.
    assert CleanMentions()(text) == "hi  and  done"


def test_clean_mentions_placeholder_default_token_is_english() -> None:
    step = CleanMentions(mode=CleanMode.PLACEHOLDER)
    assert step("hi @user") == "hi [MENTION]"


def test_clean_mentions_placeholder_token_is_configurable() -> None:
    # [مستخدم] = "user", the SOCIAL Arabic token.
    arabic_token = (
        "["
        + chr(0x0645)
        + chr(0x0633)
        + chr(0x062A)
        + chr(0x062E)
        + chr(0x062F)
        + chr(0x0645)
        + "]"
    )
    step = CleanMentions(mode=CleanMode.PLACEHOLDER, placeholder=arabic_token)
    assert step("@user!") == f"{arabic_token}!"


def test_clean_mentions_leaves_a_bare_at_sign_untouched() -> None:
    # An @ with no following word character is not a mention.
    assert CleanMentions()("price @ 5") == "price @ 5"


def test_clean_mentions_safety_is_cleaning() -> None:
    assert CleanMentions().safety is SafetyClass.CLEANING


def test_clean_mentions_free_function_agrees_with_step() -> None:
    text = "hey @user"
    assert clean_mentions(text) == CleanMentions()(text)
    placeholder_fn = clean_mentions(text, mode=CleanMode.PLACEHOLDER)
    assert placeholder_fn == CleanMentions(mode=CleanMode.PLACEHOLDER)(text)


def test_clean_mentions_serializes_its_mode_and_token_and_round_trips() -> None:
    step = CleanMentions(mode=CleanMode.PLACEHOLDER, placeholder="[u]")
    assert step.to_dict() == {
        "name": "CleanMentions",
        "config": {"mode": "placeholder", "placeholder": "[u]"},
    }
    assert CleanMentions.from_dict(step.to_dict()["config"]) == step
    assert registry.build("CleanMentions", {}) == CleanMentions()


@given(st.text())
def test_clean_mentions_is_total_and_idempotent(text: str) -> None:
    for mode in ("delete", "placeholder"):
        once = clean_mentions(text, mode=mode)  # type: ignore[arg-type]
        assert clean_mentions(once, mode=mode) == once  # type: ignore[arg-type]


# "نص" (text) U+0646 U+0635 and "المزيد" (more), in code points.
_TEXT = chr(0x0646) + chr(0x0635)  # نص
_MORE = chr(0x0627) + chr(0x0644) + chr(0x0645) + chr(0x0632) + chr(0x064A) + chr(0x062F)  # المزيد


def test_clean_html_strips_tags_and_unescapes_entities() -> None:
    # The worked example (story 34): tags removed AND &amp; decoded to &.
    text = f"<b>{_TEXT}</b> &amp; {_MORE}"
    assert CleanHTML()(text) == f"{_TEXT} & {_MORE}"


def test_clean_html_unescapes_entities_even_without_tags() -> None:
    assert CleanHTML()("a &lt; b &gt; c &amp; d") == "a < b > c & d"


def test_clean_html_placeholder_mode_replaces_each_tag() -> None:
    step = CleanHTML(mode=CleanMode.PLACEHOLDER, placeholder="[HTML]")
    assert step(f"<b>{_TEXT}</b>") == f"[HTML]{_TEXT}[HTML]"


def test_clean_html_strips_tags_before_unescaping_so_escaped_brackets_stay_literal() -> None:
    # &lt;b&gt; is escaped text, not markup; stripping tags FIRST then unescaping keeps it literal
    # rather than decoding it into a <b> tag and then deleting it.
    assert CleanHTML()("&lt;b&gt;") == "<b>"


def test_clean_html_safety_is_cleaning() -> None:
    assert CleanHTML().safety is SafetyClass.CLEANING


def test_clean_html_free_function_agrees_with_step() -> None:
    text = "<i>x</i> &amp; y"
    assert clean_html(text) == CleanHTML()(text)
    assert clean_html(text, mode=CleanMode.PLACEHOLDER) == CleanHTML(mode=CleanMode.PLACEHOLDER)(
        text
    )


def test_clean_html_serializes_its_mode_and_token_and_round_trips() -> None:
    step = CleanHTML(mode=CleanMode.PLACEHOLDER, placeholder="[tag]")
    assert step.to_dict() == {
        "name": "CleanHTML",
        "config": {"mode": "placeholder", "placeholder": "[tag]"},
    }
    assert CleanHTML.from_dict(step.to_dict()["config"]) == step
    assert registry.build("CleanHTML", {}) == CleanHTML()


def test_clean_html_is_idempotent_on_realistic_markup() -> None:
    # Strict idempotence cannot hold over arbitrary text: html.unescape decodes only one level, so
    # a multiply-encoded entity (&amp;amp; -> &amp; -> &) changes on each pass — a documented limit.
    # On realistic single-encoded markup the step is a fixed point.
    text = f"<p>{_TEXT}</p> &amp; <a href='https://x'>{_MORE}</a>"
    once = CleanHTML()(text)
    assert CleanHTML()(once) == once


@given(st.text())
def test_clean_html_never_raises(text: str) -> None:
    for mode in ("delete", "placeholder"):
        clean_html(text, mode=mode)  # type: ignore[arg-type]


# --- HandleEmoji (issue 0013, story 35) — keep / strip / demojize ---

# Code points, not glyphs, so the expectation is immune to how this file is saved. "أحبه" (I love
# it) U+0623 U+062D U+0628 U+0647; 😍 is U+1F60D (smiling face with heart-eyes).
_LOVE = chr(0x0623) + chr(0x062D) + chr(0x0628) + chr(0x0647)  # أحبه
_HEART_EYES = chr(0x1F60D)  # 😍


def test_handle_emoji_strip_removes_emoji_keeping_surrounding_text() -> None:
    # The worked example (story 35): the emoji is removed, the text and the space before it stay.
    assert HandleEmoji(mode=EmojiMode.STRIP)(f"{_LOVE} {_HEART_EYES}") == f"{_LOVE} "


def test_handle_emoji_default_mode_is_keep_and_leaves_emoji_untouched() -> None:
    # Default keeps affective signal: the emoji (and everything else) survives verbatim.
    text = f"{_LOVE} {_HEART_EYES}"
    assert HandleEmoji().mode is EmojiMode.KEEP
    assert HandleEmoji()(text) == text
    assert HandleEmoji(mode=EmojiMode.KEEP)(text) == text


def test_handle_emoji_strip_removes_a_zwj_sequence_whole() -> None:
    # A ZWJ family sequence (👨‍👩‍👧 = man ZWJ woman ZWJ girl) strips as one unit — no dangling
    # joiner is left behind (the joiner is consumed only between emoji).
    family = chr(0x1F468) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F467)
    assert HandleEmoji(mode=EmojiMode.STRIP)(f"a{family}b") == "ab"


def test_handle_emoji_strip_does_not_touch_arabic_or_digits() -> None:
    # Soundness: STRIP recognizes only emoji, so Arabic letters and digits pass through untouched.
    text = f"{_LOVE} {ARABIC_INDIC_123} 42"
    assert HandleEmoji(mode=EmojiMode.STRIP)(text) == text


def test_handle_emoji_keep_safety_is_encoding_repair() -> None:
    # KEEP is a pure no-op, so it is lossless — safe to classify as ENCODING_REPAIR (ADR-0011).
    assert HandleEmoji().safety is SafetyClass.ENCODING_REPAIR
    assert HandleEmoji(mode=EmojiMode.KEEP).safety is SafetyClass.ENCODING_REPAIR


def test_handle_emoji_strip_and_demojize_safety_is_cleaning() -> None:
    # STRIP/DEMOJIZE discard or rewrite non-linguistic noise -> CLEANING, opt-in (not under LIGHT).
    assert HandleEmoji(mode=EmojiMode.STRIP).safety is SafetyClass.CLEANING
    assert HandleEmoji(mode=EmojiMode.DEMOJIZE).safety is SafetyClass.CLEANING


def test_handle_emoji_demojize_replaces_emoji_with_a_text_alias() -> None:
    # DEMOJIZE rewrites the emoji to a colon-wrapped text alias (the `emoji` extra is installed in
    # dev); the literal emoji is gone and readable words take its place.
    result = HandleEmoji(mode=EmojiMode.DEMOJIZE)(_HEART_EYES)
    assert _HEART_EYES not in result
    assert result.startswith(":") and result.endswith(":")


def test_handle_emoji_demojize_without_the_extra_raises_a_clear_error() -> None:
    # With the optional `emoji` backend unavailable, building a DEMOJIZE step fails fast at
    # construction with an actionable error naming the extra (ADR-0003 lean core).
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "emoji", None)  # make `import emoji` fail
        with pytest.raises(EmojiSupportNotInstalledError, match=r"araclean\[emoji\]"):
            HandleEmoji(mode=EmojiMode.DEMOJIZE)
        with pytest.raises(EmojiSupportNotInstalledError):
            handle_emoji(_HEART_EYES, mode=EmojiMode.DEMOJIZE)


def test_handle_emoji_serializes_its_mode_and_round_trips() -> None:
    step = HandleEmoji(mode=EmojiMode.STRIP)
    assert step.to_dict() == {"name": "HandleEmoji", "config": {"mode": "strip"}}
    rebuilt = HandleEmoji.from_dict(step.to_dict()["config"])
    assert rebuilt == step
    assert rebuilt(f"x{_HEART_EYES}") == "x"
    # Bare config -> the keep default, reconstructed through the registry.
    built = registry.build("HandleEmoji", {})
    assert built == HandleEmoji()
    assert built(_HEART_EYES) == _HEART_EYES


def test_handle_emoji_free_function_agrees_with_step() -> None:
    text = f"{_LOVE} {_HEART_EYES}"
    assert handle_emoji(text) == HandleEmoji()(text)
    assert handle_emoji(text, mode=EmojiMode.STRIP) == HandleEmoji(mode=EmojiMode.STRIP)(text)
    assert handle_emoji(_HEART_EYES, mode=EmojiMode.DEMOJIZE) == HandleEmoji(
        mode=EmojiMode.DEMOJIZE
    )(_HEART_EYES)


@given(st.text())
def test_handle_emoji_keep_and_strip_are_total_and_idempotent(text: str) -> None:
    # The AC: never raises on arbitrary text in keep/strip, and both are fixed points.
    for mode in ("keep", "strip"):
        once = handle_emoji(text, mode=mode)  # type: ignore[arg-type]
        assert handle_emoji(once, mode=mode) == once  # type: ignore[arg-type]


# --- RemoveStopwords (issue 0017, stories 36/37) — flat curated stopword list ------------------

# الكتاب علي الطاولة — "the book on the table" in FOLDED form (the list ships folded, so the
# preposition على reads علي after FoldAlefMaqsura — the text RemoveStopwords actually sees). The
# two content words keep their definite-article "ال" prefix (flat, not clitic-aware — ADR-0001).
_SENTENCE = "الكتاب علي الطاولة"
_RAW_SENTENCE = "الكتاب على الطاولة"  # the unfolded spelling, as a user would type it


def test_remove_stopwords_removes_listed_stopwords_keeping_content() -> None:
    # The stopword is deleted in place; the surrounding whitespace is left as written (so a gap is
    # left where the preposition was), exactly like the delete-style cleaning steps (CleanURLs).
    assert RemoveStopwords()(_SENTENCE) == "الكتاب  الطاولة"


def test_remove_stopwords_matches_only_the_folded_spelling() -> None:
    # The version-2 contract: the list ships FOLDED, so the bare step does nothing to an unfolded
    # spelling (على with alef maqsura) — the required folds are what route every variant onto the
    # list entry (the Pipeline enforces them; see the end-to-end test below).
    assert RemoveStopwords()(_RAW_SENTENCE) == _RAW_SENTENCE


def test_remove_stopwords_keeps_negation_particles() -> None:
    # Negation safety (story 37): the polarity-bearing particles ما/لا/لم/لن/ليس are excluded from
    # the list, so a sentence made only of them is returned UNCHANGED — removal can never silently
    # flip the sentiment by deleting a negation.
    negations = "ما لا لم لن ليس"
    assert RemoveStopwords()(negations) == negations
    # And in a real sentence: "هذا" (a demonstrative stopword) goes, "ليس" (negation) stays.
    assert "ليس" in RemoveStopwords()("هذا ليس صحيحا")


def test_remove_stopwords_is_flat_not_clitic_aware() -> None:
    # The list is flat (ADR-0001 — no morphology): it only removes a WHOLE-token stopword, never a
    # clitic glued to a content word. "والكتاب" (and-the-book = و + الكتاب) and "فيها" (in-it =
    # في + ها) keep their stopword-shaped affixes, because an Arabic letter on the boundary blocks
    # the whole-word match. A bare standalone "في", by contrast, is removed.
    assert RemoveStopwords()("والكتاب") == "والكتاب"
    assert RemoveStopwords()("فيها") == "فيها"
    assert RemoveStopwords()("في البيت") == " البيت"


def test_remove_stopwords_safety_is_linguistic_folding() -> None:
    # It discards linguistic content from within the Arabic text (function words), so it is lossy
    # LINGUISTIC_FOLDING — not CLEANING (which is non-linguistic noise: URLs/mentions/HTML/emoji).
    assert RemoveStopwords().safety is SafetyClass.LINGUISTIC_FOLDING


def test_remove_stopwords_free_function_agrees_with_step() -> None:
    assert remove_stopwords(_SENTENCE) == RemoveStopwords()(_SENTENCE)


def test_remove_stopwords_serializes_its_list_version() -> None:
    # The list version is pinned in the config so a serialized profile reproduces the exact removal
    # (story 36); it round-trips through to_dict/from_dict and the registry.
    step = RemoveStopwords()
    assert step.to_dict() == {
        "name": "RemoveStopwords",
        "config": {"version": stopwords.STOPWORDS_VERSION},
    }
    assert RemoveStopwords.from_dict(step.to_dict()["config"]) == step
    built = registry.build("RemoveStopwords", {})  # bare config -> the current bundled list
    assert isinstance(built, RemoveStopwords)
    assert built(_SENTENCE) == step(_SENTENCE)


def test_remove_stopwords_from_dict_rejects_a_mismatched_list_version() -> None:
    # A profile pinned to a DIFFERENT list version cannot reproduce removal with this install, so it
    # fails loudly rather than silently using a different list (the reproducibility footgun the
    # version pin exists to close).
    with pytest.raises(ValueError, match="version"):
        RemoveStopwords.from_dict({"version": "0.0.0-not-a-real-version"})


@given(st.text())
def test_remove_stopwords_is_total_and_idempotent(text: str) -> None:
    # Never raises on arbitrary text (incl. surrogates) and is a fixed point: removing the same
    # whole-token stopwords twice changes nothing the second time.
    once = remove_stopwords(text)
    assert remove_stopwords(once) == once


def test_remove_stopwords_works_end_to_end_in_a_pipeline() -> None:
    # End-to-end through Pipeline (story 36): the required folds run first (the version-2 ordering
    # contract), routing the RAW spelling (على with alef maqsura, hamza spellings, vocalization)
    # onto the folded list; a downstream CollapseWhitespace tidies the gaps a removal leaves.
    pipe = Pipeline(
        [
            RemoveTashkeel(),
            FoldAlef(),
            FoldAlefMaqsura(),
            FoldHamza(),
            RemoveStopwords(),
            CollapseWhitespace(),
        ]
    )
    assert pipe(_RAW_SENTENCE) == "الكتاب الطاولة"
    # Robustness across real typed variants: canonical hamza, hamza-less, and vocalized spellings
    # of "I am going to the house" all reduce to the same content words.
    assert pipe("أنا ذاهب إلى البيت") == pipe("انا ذاهب الى البيت") == " ذاهب البيت"
    assert pipe("فِي البيت") == " البيت"
    # The pipeline (and so the pinned list version) round-trips through (de)serialization.
    rebuilt = Pipeline.from_dict(pipe.to_dict())
    assert rebuilt(_RAW_SENTENCE) == pipe(_RAW_SENTENCE)


def test_remove_stopwords_ordering_contract_is_enforced_at_construction() -> None:
    # The folded list assumes the folds ran first; a pipeline missing any of them is rejected when
    # BUILT (fail fast, never a silent recall hole), naming what is missing.
    with pytest.raises(ValueError, match="requires"):
        Pipeline([RemoveStopwords()])
    with pytest.raises(ValueError, match="FoldHamza"):
        Pipeline([RemoveTashkeel(), FoldAlef(), FoldAlefMaqsura(), RemoveStopwords()])
    # With every required fold ahead of it, construction succeeds.
    Pipeline([RemoveTashkeel(), FoldAlef(), FoldAlefMaqsura(), FoldHamza(), RemoveStopwords()])


# --- ReduceElongation min_run: the trigger knob (roadmap 0.1) -----------------------------------

# Legitimately doubled-letter words (assimilated definite article, verb prefix, lexical doubles) —
# the words cap=1's old runs-of-2 trigger used to corrupt.
_DOUBLED_WORDS = ["الله", "اللغة", "الليل", "تتكلم", "ممكن", "مما"]


@pytest.mark.parametrize("word", _DOUBLED_WORDS)
def test_reduce_elongation_default_trigger_spares_legitimate_doubles(word: str) -> None:
    # The 0.1 fix: with the default trigger (min_run = max(cap+1, 3) = 3 for cap=1), a legitimate
    # doubled letter is NOT elongation — الله stays الله, ممكن stays ممكن, مما never becomes the
    # negation particle ما.
    assert ReduceElongation()(word) == word


def test_reduce_elongation_default_trigger_still_collapses_triples() -> None:
    # A TRIPLED letter is virtually nonexistent in real spelling, so 3+ is the elongation signal:
    # a 3-run collapses all the way to the canonical single letter under cap=1.
    triple = chr(0x062C) + chr(0x0645) + chr(0x064A) * 3 + chr(0x0644)  # جميييل
    single = chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644)  # جميل
    assert ReduceElongation()(triple) == single


def test_reduce_elongation_explicit_min_run_two_restores_the_aggressive_collapse() -> None:
    # The trigger is a knob: min_run=2 deliberately opts back into collapsing doubles.
    assert ReduceElongation(min_run=2)("ممكن") == "مكن"
    assert reduce_elongation("ممكن", min_run=2) == "مكن"


def test_reduce_elongation_resolves_and_round_trips_an_explicit_min_run() -> None:
    step = ReduceElongation(cap=1, min_run=4)
    assert step.to_dict() == {"name": "ReduceElongation", "config": {"cap": 1, "min_run": 4}}
    rebuilt = ReduceElongation.from_dict(step.to_dict()["config"])
    assert rebuilt == step
    quad = chr(0x064A) * 4
    assert rebuilt("ج" + quad) == "ج" + chr(0x064A)  # a 4-run collapses
    assert rebuilt("ج" + chr(0x064A) * 3) == "ج" + chr(0x064A) * 3  # a 3-run is below the trigger
    # An unset min_run resolves at construction, so equality is canonical either way.
    assert ReduceElongation(cap=1) == ReduceElongation(cap=1, min_run=3)


@pytest.mark.parametrize(("cap", "min_run"), [(1, 1), (2, 2), (2, 1), (3, 2)])
def test_reduce_elongation_rejects_a_trigger_at_or_below_the_cap(cap: int, min_run: int) -> None:
    # min_run <= cap would EXPAND short runs up to the cap instead of collapsing long ones.
    with pytest.raises(ValueError, match="min_run"):
        ReduceElongation(cap=cap, min_run=min_run)
    with pytest.raises(ValueError, match="min_run"):
        reduce_elongation("نص", cap=cap, min_run=min_run)


@given(st.text())
def test_reduce_elongation_with_min_run_is_total_and_idempotent(text: str) -> None:
    for cap, min_run in ((1, None), (1, 2), (2, None), (1, 5)):
        once = reduce_elongation(text, cap=cap, min_run=min_run)
        assert reduce_elongation(once, cap=cap, min_run=min_run) == once


# --- StripBidi: the contextual ZWJ rule (roadmap 0.2) -------------------------------------------

_FAMILY = chr(0x1F468) + chr(0x200D) + chr(0x1F469) + chr(0x200D) + chr(0x1F467)  # 👨‍👩‍👧
_DOCTOR = chr(0x1F468) + chr(0x200D) + chr(0x2695) + chr(0xFE0F)  # 👨‍⚕️
_HEART_ON_FIRE = chr(0x2764) + chr(0xFE0F) + chr(0x200D) + chr(0x1F525)  # ❤️‍🔥 (VS16 before ZWJ)


@pytest.mark.parametrize("sequence", [_FAMILY, _DOCTOR, _HEART_ON_FIRE])
def test_strip_bidi_keeps_the_joiner_inside_an_emoji_sequence(sequence: str) -> None:
    # Inside an emoji sequence the ZWJ is CONTENT: stripping it would split 👨‍👩‍👧 into three
    # emoji (and change what a later HandleEmoji sees), so an emoji-flanked joiner survives.
    assert StripBidi()(sequence) == sequence


def test_strip_bidi_still_strips_the_joiner_between_arabic_letters() -> None:
    # Outside emoji the ZWJ is invisible formatting, exactly as before.
    assert StripBidi()(chr(0x0645) + chr(0x200D) + chr(0x062D)) == chr(0x0645) + chr(0x062D)


def test_strip_bidi_strips_the_joiner_on_an_emoji_to_arabic_boundary() -> None:
    # The documented residual: only an emoji-to-emoji joiner is content; one joining an emoji to
    # an Arabic letter still goes.
    text = chr(0x1F468) + chr(0x200D) + chr(0x0645)
    assert StripBidi()(text) == chr(0x1F468) + chr(0x0645)


def test_strip_bidi_then_emoji_strip_removes_a_sequence_whole() -> None:
    # The 0.2 composition this fix exists for: LIGHT's StripBidi no longer pre-splits a ZWJ
    # sequence, so a later HandleEmoji(strip) removes it as ONE unit, never leaving fragments.
    pipe = Pipeline([StripBidi(), HandleEmoji(mode=EmojiMode.STRIP)])
    assert pipe("a" + _FAMILY + "b") == "ab"
    assert pipe("a" + _DOCTOR + "b") == "ab"


# --- HandleEmoji: extended ranges + keycaps (roadmap 0.3) ---------------------------------------


@pytest.mark.parametrize(
    "emoji_char",
    [
        chr(0x2B50),  # ⭐ star
        chr(0x23F0),  # ⏰ alarm clock
        chr(0x231A),  # ⌚ watch
        chr(0x23F3),  # ⏳ hourglass
        chr(0x25B6) + chr(0xFE0F),  # ▶️ play (text-default + VS16)
        chr(0x25C0) + chr(0xFE0F),  # ◀️ reverse
        chr(0x1F197),  # 🆗 OK button
        chr(0x1F170) + chr(0xFE0F),  # 🅰️ A button
        chr(0x203C) + chr(0xFE0F),  # ‼️ double exclamation
        chr(0x2049) + chr(0xFE0F),  # ⁉️ exclamation question
        chr(0x1F0CF),  # 🃏 joker
        chr(0x1F004),  # 🀄 mahjong red dragon
        chr(0x2B55),  # ⭕ heavy circle
        chr(0x2B05) + chr(0xFE0F),  # ⬅️ left arrow
    ],
)
def test_handle_emoji_strip_covers_the_supplementary_singletons(emoji_char: str) -> None:
    # The 0.3 gap: these are top-frequency emoji from blocks outside the original ranges (and the
    # text-default singletons riding their VS16); strip removes each cleanly.
    assert HandleEmoji(mode=EmojiMode.STRIP)(f"x{emoji_char}y") == "xy"


def test_handle_emoji_strip_removes_a_keycap_sequence_with_its_ascii_base() -> None:
    # A keycap emoji is [0-9#*] + optional VS16 + U+20E3; the ASCII base is part of the emoji, so
    # 1️⃣ strips whole — no stray "1" is left behind.
    keycap_one = "1" + chr(0xFE0F) + chr(0x20E3)
    keycap_hash = "#" + chr(0x20E3)
    assert HandleEmoji(mode=EmojiMode.STRIP)(f"a{keycap_one}b{keycap_hash}c") == "abc"


def test_handle_emoji_strip_keycap_soundness_never_consumes_an_arabic_digit() -> None:
    # Soundness: only the ASCII keycap bases join the sequence. A stray keycap mark on an
    # Arabic-Indic digit strips alone, keeping the digit — numbers are never corrupted.
    arabic_keycap = chr(0x0661) + chr(0x20E3)  # ١ + combining keycap
    assert HandleEmoji(mode=EmojiMode.STRIP)(arabic_keycap) == chr(0x0661)
    # And ordinary digits/text (no keycap) are untouched, as ever.
    assert HandleEmoji(mode=EmojiMode.STRIP)("42 #tag") == "42 #tag"


def test_handle_emoji_strip_leaves_plain_text_typography_alone() -> None:
    # The stated exclusions: ©/®/™ are emoji-capable but their DOMINANT use is plain typography,
    # so stripping them would corrupt ordinary text; they stay out of the set.
    legal = "© 2026 araclean® — Arabic™"
    assert HandleEmoji(mode=EmojiMode.STRIP)(legal) == legal


# --- CleanMentions: email awareness (roadmap 0.5) -----------------------------------------------


def test_clean_mentions_keeps_an_email_address_verbatim() -> None:
    # user@example.com is an ADDRESS, not a mention: the email shape is matched first and passed
    # through, in both delete and placeholder modes.
    text = "راسلني user@example.com الآن"
    assert CleanMentions()(text) == text
    assert CleanMentions(mode=CleanMode.PLACEHOLDER)(text) == text


def test_clean_mentions_still_rewrites_a_real_mention_next_to_an_email() -> None:
    text = "via @user user@example.com"
    assert CleanMentions()(text) == "via  user@example.com"


def test_clean_mentions_dotless_host_residual_still_reads_as_a_mention() -> None:
    # The documented residual: the email shape requires a dotted domain, so a dotless user@example
    # has its host consumed as a mention (unchanged v1 behavior).
    assert CleanMentions()("user@example") == "user"


@given(st.text())
def test_clean_mentions_email_aware_matching_is_total_and_idempotent(text: str) -> None:
    for mode in (CleanMode.DELETE, CleanMode.PLACEHOLDER):
        step = CleanMentions(mode=mode)
        once = step(text)
        assert step(once) == once


# --- MapDigits: the dedicated-separator knob (roadmap 0.5) --------------------------------------

_ARABIC_DECIMAL = chr(0x0661) + chr(0x0662) + chr(0x066B) + chr(0x0665)  # ١٢٫٥
_ARABIC_GROUPED = chr(0x0661) + chr(0x066C) + chr(0x0660) * 3  # ١٬٠٠٠


def test_map_digits_keeps_dedicated_separators_by_default() -> None:
    # Without the knob the separators stay, producing the mixed-script number the roadmap flags.
    assert MapDigits()(_ARABIC_DECIMAL) == "12" + chr(0x066B) + "5"


def test_map_digits_map_separators_rewrites_digit_flanked_separators() -> None:
    # Opt-in: a digit-flanked ٫ becomes '.' and ٬ becomes ',', so the number parses as ASCII.
    step = MapDigits(map_separators=True)
    assert step(_ARABIC_DECIMAL) == "12.5"
    assert step(_ARABIC_GROUPED) == "1,000"
    assert map_digits(_ARABIC_DECIMAL, map_separators=True) == "12.5"


def test_map_digits_map_separators_leaves_a_stray_separator_alone() -> None:
    # The digit-flanked guard (the inverse of MapPunctuation's): a separator NOT between digits is
    # not a number separator, so it is left as written.
    stray = "نص " + chr(0x066B) + " نص"
    assert MapDigits(map_separators=True)(stray) == stray


def test_map_digits_map_separators_serializes_and_round_trips() -> None:
    step = MapDigits(map_separators=True)
    assert step.to_dict() == {
        "name": "MapDigits",
        "config": {"target": "ascii", "map_separators": True},
    }
    rebuilt = MapDigits.from_dict(step.to_dict()["config"])
    assert rebuilt == step
    assert rebuilt(_ARABIC_DECIMAL) == "12.5"


@given(st.text())
def test_map_digits_map_separators_is_total_and_idempotent(text: str) -> None:
    once = map_digits(text, map_separators=True)
    assert map_digits(once, map_separators=True) == once


# --- RemoveTashkeel: the position knob (roadmap Phase 1, PyArabic strip_lastharaka parity) ------

_VOCALIZED_BOOK = (
    chr(0x0643) + chr(0x0650) + chr(0x062A) + chr(0x064E) + chr(0x0627) + chr(0x0628) + chr(0x064C)
)  # كِتَابٌ
_BOOK_NO_FINAL = _VOCALIZED_BOOK[:-1]  # كِتَاب — word-internal vocalization kept


def test_remove_tashkeel_final_drops_only_the_word_final_run() -> None:
    # The i3rab fold: the case vowel at the word end goes; the internal vocalization stays.
    assert RemoveTashkeel(position="final")(_VOCALIZED_BOOK) == _BOOK_NO_FINAL
    assert remove_tashkeel(_VOCALIZED_BOOK, position="final") == _BOOK_NO_FINAL


def test_remove_tashkeel_final_handles_every_word_in_a_sentence() -> None:
    vocalized = _VOCALIZED_BOOK + " " + chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E)
    expected = _BOOK_NO_FINAL + " " + chr(0x0643) + chr(0x064E) + chr(0x062A)
    assert RemoveTashkeel(position="final")(vocalized) == expected


def test_remove_tashkeel_final_respects_the_class_selection() -> None:
    # Only SELECTED classes are removed at the final position: with HARAKAT alone, a final
    # shadda+fatha stack keeps its shadda (shadda is not selected; the fatha after it goes).
    word = chr(0x062F) + chr(0x0651) + chr(0x064E)  # د + shadda + fatha
    kept_shadda = chr(0x062F) + chr(0x0651)
    assert RemoveTashkeel(classes={MarkClass.HARAKAT}, position="final")(word) == kept_shadda
    # With every class selected the whole final run goes.
    assert RemoveTashkeel(position="final")(word) == chr(0x062F)


def test_remove_tashkeel_final_serializes_and_round_trips() -> None:
    step = RemoveTashkeel(classes={MarkClass.HARAKAT, MarkClass.TANWEEN}, position="final")
    spec = step.to_dict()
    assert spec == {
        "name": "RemoveTashkeel",
        "config": {"classes": ["harakat", "tanween"], "position": "final"},
    }
    rebuilt = RemoveTashkeel.from_dict(spec["config"])
    assert rebuilt == step
    assert rebuilt(_VOCALIZED_BOOK) == step(_VOCALIZED_BOOK)
    # A pre-position serialized form (no "position" key) still rehydrates to the default.
    assert RemoveTashkeel.from_dict({"classes": ["harakat"]}).position == "all"


def test_remove_tashkeel_rejects_an_unknown_position() -> None:
    with pytest.raises(ValueError, match="position"):
        RemoveTashkeel(position="middle")  # type: ignore[arg-type]  # prove runtime validation


@given(st.text())
def test_remove_tashkeel_final_is_total_and_idempotent(text: str) -> None:
    once = remove_tashkeel(text, position="final")
    assert remove_tashkeel(once, position="final") == once


# --- CleanHashtags (roadmap Phase 1) -------------------------------------------------------------

_ARABIC_TAG = (
    "#"
    + chr(0x0627)
    + chr(0x0644)
    + chr(0x064A)
    + chr(0x0648)
    + chr(0x0645)
    + "_"
    + (chr(0x0627) + chr(0x0644) + chr(0x0648) + chr(0x0637) + chr(0x0646) + chr(0x064A))
)  # #اليوم_الوطني
_SEGMENTED_TAG = _ARABIC_TAG[1:].replace("_", " ")  # اليوم الوطني


def test_clean_hashtags_segment_drops_hash_and_maps_underscore_to_space() -> None:
    # The entrenched AraBERT recipe (the SEGMENT default): the tag's words stay as content.
    assert CleanHashtags()(_ARABIC_TAG) == _SEGMENTED_TAG
    assert clean_hashtags(f"x {_ARABIC_TAG} y") == f"x {_SEGMENTED_TAG} y"


def test_clean_hashtags_delete_placeholder_and_keep_modes() -> None:
    assert CleanHashtags(mode=HashtagMode.DELETE)(f"x {_ARABIC_TAG} y") == "x  y"
    assert CleanHashtags(mode=HashtagMode.PLACEHOLDER)(_ARABIC_TAG) == "[HASHTAG]"
    token = "[" + chr(0x0648) + chr(0x0633) + chr(0x0645) + "]"  # [وسم]
    assert CleanHashtags(mode=HashtagMode.PLACEHOLDER, placeholder=token)(_ARABIC_TAG) == token
    assert CleanHashtags(mode=HashtagMode.KEEP)(_ARABIC_TAG) == _ARABIC_TAG


def test_clean_hashtags_leaves_a_bare_hash_sign_alone() -> None:
    assert CleanHashtags()("C# and # alone") == "C# and # alone"


def test_clean_hashtags_safety_is_mode_dependent() -> None:
    # KEEP is a lossless no-op; the rewriting modes discard social-metadata markup (ADR-0011).
    assert CleanHashtags(mode=HashtagMode.KEEP).safety is SafetyClass.ENCODING_REPAIR
    for mode in (HashtagMode.SEGMENT, HashtagMode.DELETE, HashtagMode.PLACEHOLDER):
        assert CleanHashtags(mode=mode).safety is SafetyClass.CLEANING


def test_clean_hashtags_free_function_agrees_with_step() -> None:
    text = f"قال {_ARABIC_TAG} #tag_b"
    assert clean_hashtags(text) == CleanHashtags()(text)
    assert clean_hashtags(text, mode=HashtagMode.DELETE) == CleanHashtags(mode=HashtagMode.DELETE)(
        text
    )


def test_clean_hashtags_serializes_its_mode_and_token_and_round_trips() -> None:
    step = CleanHashtags(mode=HashtagMode.PLACEHOLDER, placeholder="[TAG]")
    assert step.to_dict() == {
        "name": "CleanHashtags",
        "config": {"mode": "placeholder", "placeholder": "[TAG]"},
    }
    assert CleanHashtags.from_dict(step.to_dict()["config"]) == step
    built = registry.build("CleanHashtags", {})  # bare config -> the segment default
    assert isinstance(built, CleanHashtags)
    assert built(_ARABIC_TAG) == _SEGMENTED_TAG


@given(st.text())
def test_clean_hashtags_is_total_and_idempotent(text: str) -> None:
    for mode in HashtagMode:
        step = CleanHashtags(mode=mode)
        once = step(text)
        assert step(once) == once


# --- RemovePunctuation (roadmap Phase 1) ----------------------------------------------------------


def test_remove_punctuation_deletes_arabic_and_ascii_punctuation_alike() -> None:
    # One stated principle (category P*): the Arabic marks and the ASCII set go in the same pass.
    text = "كتاب" + chr(0x060C) + " قلم" + chr(0x061F) + ' "نعم"! (j.k.)'
    assert RemovePunctuation()(text) == "كتاب قلم نعم jk"
    assert remove_punctuation(text) == RemovePunctuation()(text)


def test_remove_punctuation_leaves_symbols_digits_and_letters() -> None:
    # S* (math/currency), digits and letters are NOT punctuation; the boundary is the category.
    text = "x + y = 3 $5 ١٢٣"
    assert RemovePunctuation()(text) == text


def test_remove_punctuation_keep_set_preserves_named_characters() -> None:
    step = RemovePunctuation(keep=("-",))
    assert step("a-b, c") == "a-b c"
    with pytest.raises(ValueError, match="single character"):
        RemovePunctuation(keep=("--",))


def test_remove_punctuation_is_fusible_and_serializes_its_keep_set() -> None:
    step = RemovePunctuation(keep=("-",))
    assert step.to_dict() == {"name": "RemovePunctuation", "config": {"keep": ["-"]}}
    assert RemovePunctuation.from_dict(step.to_dict()["config"]) == step
    assert isinstance(registry.build("RemovePunctuation", {}), RemovePunctuation)
    # The whole behavior is one translate table (the fused-engine seam).
    assert step.translate_table[ord(",")] is None
    assert ord("-") not in step.translate_table


def test_remove_punctuation_safety_is_linguistic_folding() -> None:
    assert RemovePunctuation().safety is SafetyClass.LINGUISTIC_FOLDING


@given(st.text())
def test_remove_punctuation_is_total_and_idempotent(text: str) -> None:
    once = remove_punctuation(text)
    assert remove_punctuation(once) == once


# --- FoldTanweenAlef (roadmap Phase 1) ------------------------------------------------------------

_KITAB = chr(0x0643) + chr(0x062A) + chr(0x0627) + chr(0x0628)  # كتاب
_KITABAN_ALEF_FIRST = _KITAB + chr(0x0627) + chr(0x064B)  # كتاباً (alef then fathatan)
_KITABAN_MARK_FIRST = _KITAB + chr(0x064B) + chr(0x0627)  # كتابًا (fathatan then alef)


def test_fold_tanween_alef_drops_the_carrier_in_both_typed_orders() -> None:
    assert FoldTanweenAlef()(_KITABAN_ALEF_FIRST) == _KITAB
    assert FoldTanweenAlef()(_KITABAN_MARK_FIRST) == _KITAB
    assert fold_tanween_alef(_KITABAN_ALEF_FIRST) == _KITAB


def test_fold_tanween_alef_only_fires_word_finally() -> None:
    # A word-internal alef+fathatan pair (not the adverbial ending) is left alone.
    internal = chr(0x0628) + chr(0x0627) + chr(0x064B) + chr(0x0628)  # باًب
    assert FoldTanweenAlef()(internal) == internal


def test_fold_tanween_alef_leaves_a_carrierless_tanween_to_remove_tashkeel() -> None:
    # A tanween seated directly on a letter (خطأً) has no carrier alef: out of scope here.
    khata = chr(0x062E) + chr(0x0637) + chr(0x0623) + chr(0x064B)  # خطأً
    assert FoldTanweenAlef()(khata) == khata


def test_fold_tanween_alef_safety_is_linguistic_folding() -> None:
    assert FoldTanweenAlef().safety is SafetyClass.LINGUISTIC_FOLDING


def test_fold_tanween_alef_serializes_and_round_trips() -> None:
    step = FoldTanweenAlef()
    assert step.to_dict() == {"name": "FoldTanweenAlef", "config": {}}
    assert FoldTanweenAlef.from_dict({}) == step
    assert isinstance(registry.build("FoldTanweenAlef", {}), FoldTanweenAlef)


@given(st.text())
def test_fold_tanween_alef_is_total_and_idempotent(text: str) -> None:
    once = fold_tanween_alef(text)
    assert fold_tanween_alef(once) == once


# --- RemoveForeign (roadmap Phase 1) --------------------------------------------------------------


def test_remove_foreign_deletes_non_arabic_letter_spans() -> None:
    text = "النص hello world نص"
    assert RemoveForeign()(text) == "النص   نص"
    assert remove_foreign(text) == RemoveForeign()(text)


def test_remove_foreign_takes_combining_marks_with_their_letters() -> None:
    # A decomposed café (e + combining acute) travels whole — no orphaned accent is left.
    decomposed = "caf" + "e" + chr(0x0301)
    assert RemoveForeign()(f"نص {decomposed} نص") == "نص  نص"


def test_remove_foreign_keeps_digits_punctuation_symbols_and_emoji() -> None:
    # Script filtering removes foreign WORDS, not structure: digits (any system), punctuation,
    # symbols and emoji — including the VS16 riding an emoji — pass through.
    text = "نص 42 ١٢٣ ،؟ $+ " + chr(0x25B6) + chr(0xFE0F)
    assert RemoveForeign()(text) == text


def test_remove_foreign_placeholder_mode_swaps_in_the_token() -> None:
    token = "[" + chr(0x0623) + chr(0x062C) + chr(0x0646) + chr(0x0628) + chr(0x064A) + "]"
    step = RemoveForeign(mode=CleanMode.PLACEHOLDER, placeholder=token)
    assert step("نص hello نص") == f"نص {token} نص"


def test_remove_foreign_safety_is_cleaning() -> None:
    assert RemoveForeign().safety is SafetyClass.CLEANING


def test_remove_foreign_serializes_its_mode_and_token_and_round_trips() -> None:
    step = RemoveForeign(mode=CleanMode.PLACEHOLDER, placeholder="[X]")
    assert step.to_dict() == {
        "name": "RemoveForeign",
        "config": {"mode": "placeholder", "placeholder": "[X]"},
    }
    assert RemoveForeign.from_dict(step.to_dict()["config"]) == step
    assert isinstance(registry.build("RemoveForeign", {}), RemoveForeign)


@given(st.text())
def test_remove_foreign_is_total_and_idempotent(text: str) -> None:
    once = remove_foreign(text)
    assert remove_foreign(once) == once


# --- Trim (roadmap Phase 1) -----------------------------------------------------------------------


def test_trim_strips_leading_and_trailing_unicode_whitespace() -> None:
    text = chr(0x00A0) + " نص داخلي محفوظ \n"
    assert Trim()(text) == "نص داخلي محفوظ"
    assert trim(text) == Trim()(text)


def test_trim_complements_collapse_whitespace_which_never_trims() -> None:
    # The two contracts stay separate: collapse keeps an edge run (as one space); trim removes it.
    edge = "  نص  "
    assert CollapseWhitespace()(edge) == " نص "
    assert Pipeline([CollapseWhitespace(), Trim()])(edge) == "نص"


def test_trim_safety_is_encoding_repair() -> None:
    assert Trim().safety is SafetyClass.ENCODING_REPAIR


def test_trim_serializes_and_round_trips() -> None:
    assert Trim().to_dict() == {"name": "Trim", "config": {}}
    assert Trim.from_dict({}) == Trim()
    assert isinstance(registry.build("Trim", {}), Trim)


@given(st.text())
def test_trim_is_total_and_idempotent(text: str) -> None:
    once = trim(text)
    assert trim(once) == once


# --- MapQuotes (roadmap Phase 1) ------------------------------------------------------------------


def test_map_quotes_folds_typographic_quotes_by_visual_family() -> None:
    # Arabic's standard «» and the word-processor curly/low-9 variants land on the ASCII pair.
    text = (
        chr(0x00AB)
        + "نص"
        + chr(0x00BB)
        + " "
        + chr(0x201C)
        + "x"
        + chr(0x201D)
        + " "
        + chr(0x2018)
        + "y"
        + chr(0x2019)
        + " "
        + chr(0x201E)
        + "z"
        + chr(0x201F)
    )
    assert MapQuotes()(text) == '"نص" "x" \'y\' "z"'
    assert map_quotes(text) == MapQuotes()(text)


def test_map_quotes_leaves_ascii_quotes_and_primes_alone() -> None:
    # Already-straight quotes are untouched; primes are measurement marks, not quotes.
    text = "\"x\" 'y' 5" + chr(0x2032) + " 10" + chr(0x2033)
    assert MapQuotes()(text) == text


def test_map_quotes_safety_is_linguistic_folding() -> None:
    assert MapQuotes().safety is SafetyClass.LINGUISTIC_FOLDING


def test_map_quotes_is_fusible_and_serializes() -> None:
    step = MapQuotes()
    assert step.translate_table[0x00AB] == '"'
    assert step.to_dict() == {"name": "MapQuotes", "config": {}}
    assert MapQuotes.from_dict({}) == step
    assert isinstance(registry.build("MapQuotes", {}), MapQuotes)


@given(st.text())
def test_map_quotes_is_total_and_idempotent(text: str) -> None:
    once = map_quotes(text)
    assert map_quotes(once) == once
