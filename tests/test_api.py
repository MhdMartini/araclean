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


def test_bare_call_applies_only_nfc() -> None:
    # No profile => LIGHT => only NFC right now: it composes...
    assert normalize(DECOMPOSED) == COMPOSED
    # ...and does nothing else yet — e.g. tatweel survives (it is removed only by a later step).
    assert normalize(TATWEEL) == TATWEEL == unicodedata.normalize("NFC", TATWEEL)


def test_already_nfc_text_is_unchanged() -> None:
    assert normalize(COMPOSED) == COMPOSED


@pytest.mark.parametrize("text", ["", " ", "abc", COMPOSED, TATWEEL])
def test_normalize_equals_nfc_over_corpus(text: str) -> None:
    assert normalize(text) == unicodedata.normalize("NFC", text)


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
