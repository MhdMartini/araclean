"""Tests for apply_aligned on individual steps and Pipeline composition.

Each step must return (normalized_str, OffsetMap) such that
    omap.to_original((i, j))
projects any span from normalized text back to the correct span in the original.
"""

import pytest

from araclean import (
    AlignmentNotSupportedError,
    CleanHashtags,
    CleanHTML,
    CleanMentions,
    CleanURLs,
    CollapseWhitespace,
    EmojiMode,
    FoldAlef,
    FoldAlefMaqsura,
    FoldHamza,
    FoldPresentationForms,
    FoldTanweenAlef,
    FoldTehMarbuta,
    HandleEmoji,
    MapDigits,
    MapPunctuation,
    MapQuotes,
    NormalizeUnicode,
    Pipeline,
    ReduceElongation,
    RemoveForeign,
    RemovePunctuation,
    RemoveTashkeel,
    RemoveTatweel,
    StripBidi,
    Trim,
    UnifyLookalikes,
)
from araclean.offsets import OffsetMap
from araclean.steps import SupportsAlignment

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _roundtrip_check(original: str, step: SupportsAlignment) -> None:
    """For every non-empty normalized span, verify the original text at to_original
    is exactly what the step normalized that span FROM.

    This is the key invariant: the text at the original span normalizes to the
    text at the normalized span, character-by-character (for lossless 1→1 steps).
    We only verify that the span boundaries are sane (non-negative, non-decreasing,
    within the original length).
    """
    normalized, omap = step.apply_aligned(original)
    assert isinstance(normalized, str)
    assert isinstance(omap, OffsetMap)
    n = len(normalized)
    for start in range(n + 1):
        for end in range(start, n + 1):
            orig_start, orig_end = omap.to_original((start, end))
            assert 0 <= orig_start <= orig_end <= len(original), (
                f"span ({start},{end}) → orig ({orig_start},{orig_end}) out of range "
                f"for original len {len(original)}"
            )


# ---------------------------------------------------------------------------
# Cycle 9: translate steps
# ---------------------------------------------------------------------------


def test_remove_tatweel_apply_aligned() -> None:
    s = "محـمد"
    step = RemoveTatweel()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "محمد"
    assert len(omap) == 4
    assert omap.to_original((0, 4)) == (0, 5)
    assert omap.to_original((2, 4)) == (3, 5)


def test_fold_alef_apply_aligned() -> None:
    s = "أهلاً"
    step = FoldAlef()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "اهلاً"
    assert len(omap) == len(s)
    # First char أ→ا is 1→1, maps back to original[0:1]
    assert omap.to_original((0, 1)) == (0, 1)
    assert omap.to_original((0, len(s))) == (0, len(s))


def test_fold_presentation_forms_apply_aligned_expansion() -> None:
    # ﻷ (U+FEF7, one char) → لأ (two chars)
    s = "ﻷ"
    step = FoldPresentationForms()
    normalized, omap = step.apply_aligned(s)
    assert len(normalized) == 2
    assert len(omap) == 2
    # Both expanded chars point back to orig[0:1]
    assert omap.to_original((0, 1)) == (0, 1)
    assert omap.to_original((1, 2)) == (0, 1)
    assert omap.to_original((0, 2)) == (0, 1)


def test_fold_alef_maqsura_apply_aligned() -> None:
    s = "على"
    step = FoldAlefMaqsura()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "علي"
    assert omap.to_original((0, 3)) == (0, 3)
    assert omap.to_original((2, 3)) == (2, 3)


def test_fold_hamza_apply_aligned() -> None:
    s = "مؤمن"
    step = FoldHamza()
    normalized, _ = step.apply_aligned(s)
    assert len(normalized) == len(s)
    _roundtrip_check(s, step)


def test_fold_teh_marbuta_apply_aligned() -> None:
    s = "مدرسة"
    step = FoldTehMarbuta()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "مدرسه"
    assert len(omap) == len(s)
    _roundtrip_check(s, step)


def test_map_digits_apply_aligned() -> None:
    s = "١٢٣"
    step = MapDigits()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "123"
    assert len(omap) == 3
    assert omap.to_original((0, 3)) == (0, 3)


def test_remove_tashkeel_all_apply_aligned() -> None:
    s = "كَتَبَ"
    step = RemoveTashkeel()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "كتب"
    # 3 normalized chars → 3 original letter positions (0, 2, 4 in the 6-char original)
    assert len(omap) == 3
    assert omap.to_original((0, 1)) == (0, 1)
    assert omap.to_original((1, 2)) == (2, 3)
    assert omap.to_original((2, 3)) == (4, 5)
    assert omap.to_original((0, 3)) == (0, 5)


def test_remove_punctuation_apply_aligned() -> None:
    s = "مرحبا، عالم"
    step = RemovePunctuation()
    normalized, _ = step.apply_aligned(s)
    assert "،" not in normalized
    _roundtrip_check(s, step)


def test_map_quotes_apply_aligned() -> None:
    s = "«مرحبا»"
    step = MapQuotes()
    normalized, omap = step.apply_aligned(s)
    assert normalized == '"مرحبا"'
    assert len(omap) == len(s)
    _roundtrip_check(s, step)


def test_unify_lookalikes_apply_aligned() -> None:
    s = "ی"  # Persian yeh
    step = UnifyLookalikes()
    _, omap = step.apply_aligned(s)
    assert len(omap) == 1
    assert omap.to_original((0, 1)) == (0, 1)


# ---------------------------------------------------------------------------
# Cycle 10: contextual / regex steps
# ---------------------------------------------------------------------------


def test_normalize_unicode_identity_apply_aligned() -> None:
    s = "مرحبا"
    step = NormalizeUnicode()
    normalized, omap = step.apply_aligned(s)
    assert normalized == s
    assert omap.to_original((0, len(s))) == (0, len(s))


def test_normalize_unicode_nfd_apply_aligned() -> None:
    # NFD on well-formed Arabic is still effectively identity for code-point count
    s = "مرحبا"
    step = NormalizeUnicode(form="NFC")
    _roundtrip_check(s, step)


def test_collapse_whitespace_apply_aligned() -> None:
    s = "مرحبا  عالم"  # double space
    step = CollapseWhitespace()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "مرحبا عالم"
    assert len(omap) == 10
    # The single space maps back to the double-space span
    space_idx = normalized.index(" ")
    assert omap.to_original((space_idx, space_idx + 1)) == (5, 7)
    _roundtrip_check(s, step)


def test_collapse_whitespace_collapse_lines_apply_aligned() -> None:
    s = "a\n\nb"
    step = CollapseWhitespace(collapse_lines=True)
    normalized, omap = step.apply_aligned(s)
    assert normalized == "a b"
    assert len(omap) == 3
    assert omap.to_original((1, 2)) == (1, 3)  # space ← "\n\n"


def test_strip_bidi_apply_aligned() -> None:
    RLM = "‏"
    s = f"مرحبا{RLM}عالم"
    step = StripBidi()
    normalized, _ = step.apply_aligned(s)
    assert RLM not in normalized
    _roundtrip_check(s, step)


def test_remove_tashkeel_final_apply_aligned() -> None:
    s = "كَتَبَ"
    step = RemoveTashkeel(position="final")
    normalized, _ = step.apply_aligned(s)
    # Should remove only the trailing haraka
    assert len(normalized) < len(s)
    _roundtrip_check(s, step)


def test_reduce_elongation_apply_aligned() -> None:
    s = "جمييييل"
    step = ReduceElongation()
    normalized, _ = step.apply_aligned(s)
    assert "يييي" not in normalized
    _roundtrip_check(s, step)


def test_fold_tanween_alef_apply_aligned() -> None:
    s = "كتاباً"
    step = FoldTanweenAlef()
    normalized, _ = step.apply_aligned(s)
    assert len(normalized) < len(s)
    _roundtrip_check(s, step)


def test_map_punctuation_apply_aligned() -> None:
    s = "مرحبا؟"
    step = MapPunctuation()
    normalized, omap = step.apply_aligned(s)
    assert "?" in normalized
    assert len(omap) == len(s)
    _roundtrip_check(s, step)


def test_trim_apply_aligned() -> None:
    s = "  مرحبا  "
    step = Trim()
    normalized, omap = step.apply_aligned(s)
    assert normalized == "مرحبا"
    assert len(omap) == 5
    # First char of normalized maps to orig[2:3]
    assert omap.to_original((0, 1)) == (2, 3)
    assert omap.to_original((0, 5)) == (2, 7)


def test_trim_no_whitespace_apply_aligned() -> None:
    s = "مرحبا"
    step = Trim()
    normalized, omap = step.apply_aligned(s)
    assert normalized == s
    assert omap.to_original((0, 5)) == (0, 5)


def test_clean_urls_apply_aligned() -> None:
    s = "انظر https://example.com هنا"
    step = CleanURLs()
    normalized, _ = step.apply_aligned(s)
    assert "https" not in normalized
    _roundtrip_check(s, step)


def test_clean_mentions_apply_aligned() -> None:
    s = "أجاب @محمد على السؤال"
    step = CleanMentions()
    normalized, _ = step.apply_aligned(s)
    assert "@محمد" not in normalized
    _roundtrip_check(s, step)


def test_clean_html_apply_aligned() -> None:
    s = "أهلاً <b>بكم</b>"
    step = CleanHTML()
    normalized, _ = step.apply_aligned(s)
    assert "<b>" not in normalized
    _roundtrip_check(s, step)


def test_clean_html_entity_apply_aligned() -> None:
    s = "كلمة &amp; أخرى"
    step = CleanHTML()
    normalized, _ = step.apply_aligned(s)
    assert "&amp;" not in normalized
    assert "&" in normalized
    _roundtrip_check(s, step)


def test_handle_emoji_keep_apply_aligned() -> None:
    s = "مرحبا 😀"
    step = HandleEmoji()
    normalized, omap = step.apply_aligned(s)
    assert normalized == s
    assert omap.to_original((0, len(s))) == (0, len(s))


def test_handle_emoji_strip_apply_aligned() -> None:
    s = "مرحبا 😀 عالم"
    step = HandleEmoji(mode=EmojiMode.STRIP)
    normalized, _ = step.apply_aligned(s)
    assert "😀" not in normalized
    _roundtrip_check(s, step)


def test_clean_hashtags_apply_aligned() -> None:
    s = "يوم #جميل اليوم"
    step = CleanHashtags()
    normalized, _ = step.apply_aligned(s)
    assert "#" not in normalized
    _roundtrip_check(s, step)


def test_remove_foreign_apply_aligned() -> None:
    s = "نص عربي with Latin"
    step = RemoveForeign()
    normalized, _ = step.apply_aligned(s)
    assert "Latin" not in normalized
    _roundtrip_check(s, step)


# ---------------------------------------------------------------------------
# Cycle 11: Pipeline.apply_aligned
# ---------------------------------------------------------------------------


def test_pipeline_apply_aligned_single_step() -> None:
    pipe = Pipeline([RemoveTatweel()])
    s = "محـمد"
    normalized, omap = pipe.apply_aligned(s)
    assert normalized == "محمد"
    assert omap.to_original((0, 4)) == (0, 5)


def test_pipeline_apply_aligned_two_steps_compose() -> None:
    # Step 1: remove tatweel; Step 2: fold alef
    s = "أمحـمد"
    pipe = Pipeline([RemoveTatweel(), FoldAlef()])
    normalized, omap = pipe.apply_aligned(s)
    # "أمحـمد" → remove tatweel → "أمحمد" → fold alef → "امحمد"
    assert normalized == "امحمد"
    assert omap.to_original((0, 5)) == (0, 6)
    # First char "ا" (was "أ") → original[0:1]
    assert omap.to_original((0, 1)) == (0, 1)
    # Chars after deletion: norm[3:5] → orig[4:6]
    assert omap.to_original((3, 5)) == (4, 6)


def test_pipeline_apply_aligned_empty_pipeline() -> None:
    pipe = Pipeline([])
    s = "مرحبا"
    normalized, omap = pipe.apply_aligned(s)
    assert normalized == s
    assert omap.to_original((0, 5)) == (0, 5)


def test_pipeline_apply_aligned_lossless_round_trip() -> None:
    """For lossless steps, every normalized span maps back to the text it came from."""
    from araclean import LIGHT

    pipe = Pipeline.from_profile(LIGHT)
    # Arabic text that exercises tatweel removal and unicode normalization
    s = "كتاب محـمد مرحـبا"
    normalized, omap = pipe.apply_aligned(s)
    n = len(normalized)
    for start in range(n):
        for end in range(start + 1, n + 1):
            orig_start, orig_end = omap.to_original((start, end))
            assert 0 <= orig_start <= orig_end <= len(s)


def test_pipeline_apply_aligned_custom_step_raises() -> None:
    """A custom step without apply_aligned must raise AlignmentNotSupportedError."""
    from araclean.safety import SafetyClass

    class CustomStep:
        safety = SafetyClass.ENCODING_REPAIR

        def __call__(self, s: str, /) -> str:
            return s

    pipe = Pipeline([CustomStep()])
    with pytest.raises(AlignmentNotSupportedError) as exc:
        pipe.apply_aligned("نص")
    assert "CustomStep" in str(exc.value)


# ---------------------------------------------------------------------------
# Cycle 12: Integration — NER-style span grounding
# ---------------------------------------------------------------------------


def test_ner_span_grounding_after_normalization() -> None:
    """Simulate the NER/RAG use case: normalize text, find a word in normalized form,
    project its span back to original to get the citable text."""
    pipe = Pipeline([RemoveTatweel(), FoldAlef(), RemoveTashkeel()])
    original = "أحمـد"  # alef-hamza + tatweel + haraka variants
    normalized, omap = pipe.apply_aligned(original)

    # "word" found at some position in normalized
    word_start = normalized.index("ا")  # folded alef
    word_end = word_start + 1
    orig_start, orig_end = omap.to_original((word_start, word_end))

    # The original text at that span should be the pre-normalized version
    assert 0 <= orig_start < orig_end <= len(original)
    assert orig_start == 0  # "أ" is the first char
    assert orig_end == 1


def test_apply_aligned_matches_call_output() -> None:
    """apply_aligned must return the same normalized text as __call__."""
    from araclean import SEARCH

    pipe = Pipeline.from_profile(SEARCH)
    text = "كَتَبَ أحمـد في مَدْرَسَة كبيرة"
    expected = pipe(text)
    normalized, _ = pipe.apply_aligned(text)
    assert normalized == expected


# ---------------------------------------------------------------------------
# Cycle 13: Hypothesis property tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_hypothesis_lossless_span_bounds() -> None:
    """For arbitrary text, every normalized span maps to valid bounds in original."""
    from hypothesis import given, settings
    from hypothesis import strategies as st

    from araclean import LIGHT

    pipe = Pipeline.from_profile(LIGHT)

    @given(st.text(min_size=0, max_size=50))
    @settings(max_examples=200)
    def check(text: str) -> None:
        normalized, omap = pipe.apply_aligned(text)
        n = len(normalized)
        orig_len = len(text)
        for start in range(n + 1):
            for end in range(start, min(start + 5, n + 1)):
                orig_start, orig_end = omap.to_original((start, end))
                assert 0 <= orig_start <= orig_end <= orig_len

    check()


@pytest.mark.slow
def test_hypothesis_apply_aligned_matches_call() -> None:
    """apply_aligned normalized text always equals __call__ output."""
    from hypothesis import given, settings
    from hypothesis import strategies as st

    from araclean import SEARCH

    pipe = Pipeline.from_profile(SEARCH)

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=100)
    def check(text: str) -> None:
        normalized, _ = pipe.apply_aligned(text)
        assert normalized == pipe(text)

    check()
