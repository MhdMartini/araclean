"""Behavior of the Layer-3 facade `normalize`, plus end-to-end properties."""

import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import LIGHT, Pipeline, normalize

# alef + combining hamza (decomposed); NFC composes it to alef-with-hamza.
DECOMPOSED = chr(0x0627) + chr(0x0654) + chr(0x062D) + chr(0x0645) + chr(0x062F)
COMPOSED = unicodedata.normalize("NFC", DECOMPOSED)
TATWEEL = chr(0x0645) + chr(0x0640) + chr(0x062D)  # a letter + tatweel + a letter

# Text that may include lone surrogates, so "never raises" is tested for real (ADR test pattern).
ANY_TEXT = st.text(
    alphabet=st.one_of(
        st.characters(),
        st.characters(min_codepoint=0xD800, max_codepoint=0xDFFF),
    )
)


def test_bare_call_composes_to_nfc() -> None:
    # No profile => LIGHT, whose first step is NFC: a decomposed sequence composes.
    assert normalize(DECOMPOSED) == COMPOSED


def test_already_nfc_text_is_unchanged() -> None:
    assert normalize(COMPOSED) == COMPOSED


# Each lam-alef ligature folds under LIGHT to lam + its MATCHING alef variant (story 20).
LAM = chr(0x0644)
LAM_ALEF_UNDER_LIGHT = [
    (chr(0xFEFB), LAM + chr(0x0627)),  # ﻻ -> ل + alef
    (chr(0xFEF7), LAM + chr(0x0623)),  # ﻷ -> ل + alef-with-hamza-above
    (chr(0xFEF9), LAM + chr(0x0625)),  # ﻹ -> ل + alef-with-hamza-below
    (chr(0xFEF5), LAM + chr(0x0622)),  # ﻵ -> ل + alef-with-madda
]


@pytest.mark.parametrize(("ligature", "expected"), LAM_ALEF_UNDER_LIGHT)
def test_light_folds_lam_alef_keeping_alef_variant(ligature: str, expected: str) -> None:
    # End-to-end through the facade: the ligature keeps its alef variant, not bare lam-alef.
    assert normalize(ligature) == expected


def test_light_folds_presentation_form_letters() -> None:
    # A word typed/OCR'd as presentation-form glyphs matches its base-letter spelling under LIGHT.
    word = chr(0xFE91) + chr(0xFEEA)  # beh-initial + heh-final
    assert normalize(word) == chr(0x0628) + chr(0x0647)  # -> beh + heh


# On text with nothing for LIGHT's later steps to repair (no tatweel/invisibles/look-alike/
# multi-space), LIGHT reduces to NFC. Tatweel is intentionally NOT here — LIGHT now removes it.
@pytest.mark.parametrize("text", ["", " ", "abc", COMPOSED])
def test_normalize_equals_nfc_when_only_nfc_applies(text: str) -> None:
    assert normalize(text) == unicodedata.normalize("NFC", text)


# --- LIGHT now completes (issue 0004): tatweel / invisibles / look-alike / whitespace ---


def test_light_removes_tatweel() -> None:
    # محـــمد (with three tatweel marks) -> محمد.
    word = chr(0x0645) + chr(0x062D) + chr(0x0640) * 3 + chr(0x0645) + chr(0x062F)
    assert normalize(word) == chr(0x0645) + chr(0x062D) + chr(0x0645) + chr(0x062F)


def test_light_strips_bidi_zero_width_and_bom() -> None:
    # Leading BOM + an embedded RLM + ZWJ/ZWNJ are removed; the visible letters are unchanged.
    noisy = chr(0xFEFF) + "ا" + chr(0x200F) + "ب" + chr(0x200D) + chr(0x200C) + "ت"
    assert normalize(noisy) == "ابت"


def test_light_unifies_lookalike_kaf_yeh_heh() -> None:
    # Persian keheh + Farsi yeh + heh goal -> Arabic kaf + yeh + heh.
    assert normalize(chr(0x06A9) + chr(0x06CC) + chr(0x06C1)) == chr(0x0643) + chr(0x064A) + chr(
        0x0647
    )


def test_light_accepted_residual_merges_maqsura_word() -> None:
    # The one non-strictly-lossless look-alike fold: a Persian-keyboard yeh merges علی -> علي.
    assert normalize(chr(0x0639) + chr(0x0644) + chr(0x06CC)) == chr(0x0639) + chr(0x0644) + chr(
        0x064A
    )


def test_light_collapses_whitespace() -> None:
    assert normalize("a  b") == "a b"


def test_light_is_a_lossless_fixed_point() -> None:
    # A string exercising every LIGHT step at once; running LIGHT again changes nothing.
    messy = (
        chr(0xFEFF)  # BOM
        + chr(0x0645)
        + chr(0x0640)
        + chr(0x062D)  # tatweel between letters
        + "  "  # a whitespace run
        + chr(0x06A9)  # a look-alike keheh
        + chr(0x200D)  # a zero-width joiner
        + chr(0xFE91)  # a presentation-form glyph
    )
    once = normalize(messy)
    assert normalize(once) == once
    assert once == chr(0x0645) + chr(0x062D) + " " + chr(0x0643) + chr(0x0628)


def test_default_profile_is_light() -> None:
    light_pipe = Pipeline.from_profile(LIGHT)
    for text in (DECOMPOSED, COMPOSED, "abc", TATWEEL):
        assert normalize(text) == light_pipe(text)


def test_profile_can_be_named_or_object() -> None:
    assert normalize(DECOMPOSED, profile="light") == normalize(DECOMPOSED, profile=LIGHT)


def test_unknown_profile_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="nope"):
        normalize("نص", profile="nope")


@given(ANY_TEXT)
def test_normalize_never_raises(text: str) -> None:
    normalize(text)  # total function over arbitrary text, including lone surrogates


@given(ANY_TEXT)
def test_normalize_is_idempotent_on_light(text: str) -> None:
    once = normalize(text)
    assert normalize(once) == once
