"""Behavior of profiles: the named presets that assemble pipelines."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import LIGHT, Pipeline, Profile, SafetyClass, normalize

# Arbitrary text, including lone surrogates, so the total/idempotence properties are real.
ANY_TEXT = st.text(
    alphabet=st.one_of(
        st.characters(),
        st.characters(min_codepoint=0xD800, max_codepoint=0xDFFF),
    )
)

# alef + combining hamza (decomposed) so LIGHT's NFC has real work to do; tail = three letters.
DECOMPOSED = chr(0x0627) + chr(0x0654) + chr(0x062D) + chr(0x0645) + chr(0x062F)


def test_light_profile_applies_only_nfc() -> None:
    pipe = Pipeline.from_profile(LIGHT)
    from araclean import normalize_unicode

    assert pipe(DECOMPOSED) == normalize_unicode(DECOMPOSED)


def test_from_profile_accepts_canonical_name() -> None:
    by_name = Pipeline.from_profile("light")
    by_object = Pipeline.from_profile(LIGHT)
    assert by_name(DECOMPOSED) == by_object(DECOMPOSED)


def test_from_profile_is_case_insensitive_on_name() -> None:
    assert Pipeline.from_profile("LIGHT")(DECOMPOSED) == Pipeline.from_profile("light")(DECOMPOSED)


def test_unknown_profile_name_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="nope") as excinfo:
        Pipeline.from_profile("nope")
    assert "light" in str(excinfo.value)  # the message lists known profiles


def test_light_is_lossless_all_encoding_repair() -> None:
    # A "lossless" profile must contain only ENCODING_REPAIR steps (story 41 / ADR-0004).
    pipe = Pipeline.from_profile(LIGHT)
    assert all(step.safety is SafetyClass.ENCODING_REPAIR for step in pipe.steps)


def test_profile_is_a_pydantic_model_validated_on_construction() -> None:
    # The config boundary (validating untrusted input) rejects a malformed step spec.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Profile.model_validate({"name": "bad", "steps": [{"name": 123}]})


# --- SEARCH profile (issue 0010, story 5): aggressive recall via the lossy folds ---

# على: ain + lam + alef maqsura. SEARCH folds the maqsura to yeh, merging it with علي.
ALA_MAQSURA = chr(0x0639) + chr(0x0644) + chr(0x0649)
ALA_YEH = chr(0x0639) + chr(0x0644) + chr(0x064A)


def test_search_folds_alef_maqsura() -> None:
    # "maqsura folds under search": على -> علي (the opt-in fold LIGHT never applies).
    assert normalize(ALA_MAQSURA, profile="search") == ALA_YEH


def test_search_removes_dagger_alef_to_standard_spelling() -> None:
    # "dagger alef -> standard spelling": هٰذا (heh + dagger alef U+0670 + U+0630 + alef) -> هذا.
    dagger_word = chr(0x0647) + chr(0x0670) + chr(0x0630) + chr(0x0627)
    assert normalize(dagger_word, profile="search") == chr(0x0647) + chr(0x0630) + chr(0x0627)


def test_search_is_lossy_contains_linguistic_folding_steps() -> None:
    # The audit complement of LIGHT (story 41): SEARCH is NOT lossless -- it carries the opt-in
    # LINGUISTIC_FOLDING folds, so a safety audit must surface that it loses information.
    from araclean import SEARCH

    safeties = [step.safety for step in Pipeline.from_profile(SEARCH).steps]
    assert SafetyClass.LINGUISTIC_FOLDING in safeties
    assert not all(safety is SafetyClass.ENCODING_REPAIR for safety in safeties)


def test_search_facade_equals_explicit_pipeline() -> None:
    # normalize(text, profile="search") is exactly Pipeline.from_profile(SEARCH) (story 5 / AC6).
    from araclean import SEARCH

    pipe = Pipeline.from_profile(SEARCH)
    for text in (ALA_MAQSURA, chr(0x0647) + chr(0x0670) + chr(0x0630) + chr(0x0627), "abc", ""):
        assert normalize(text, profile="search") == pipe(text)
    assert normalize(ALA_MAQSURA, profile="search") == normalize(ALA_MAQSURA, profile=SEARCH)


@given(ANY_TEXT)
def test_search_output_is_light_stable(text: str) -> None:
    # search ⊇ light (AC3): SEARCH does everything LIGHT does, so its output is a LIGHT fixed point.
    # This also pins the postcondition that SEARCH's output is NFC (the closing pass LIGHT applies
    # is a no-op on it), justifying that SEARCH needs no trailing NFC of its own.
    light = Pipeline.from_profile(LIGHT)
    searched = normalize(text, profile="search")
    assert light(searched) == searched


@given(ANY_TEXT)
def test_search_never_raises_and_is_idempotent(text: str) -> None:
    once = normalize(text, profile="search")  # total over arbitrary text, incl. lone surrogates
    assert normalize(once, profile="search") == once  # idempotent fixed point


def test_search_end_to_end_respects_the_ordering_contract() -> None:
    # One string crossing every band of the ordering contract, matched to a hand-composed result:
    #   encoding repair -> tashkeel removal -> letter folding -> digit/punctuation -> cleanup.
    bom = chr(0xFEFF)  # a leading BOM (StripBidi removes it)
    ahmad = (
        chr(0x0623) + chr(0x062D) + chr(0x0645) + chr(0x0640) * 2 + chr(0x062F)
    )  # أحمــد (tatweel)
    dagger_word = chr(0x0647) + chr(0x0670) + chr(0x0630) + chr(0x0627)  # هٰذا (dagger alef)
    hamza_word = chr(0x0645) + chr(0x0624) + chr(0x0645) + chr(0x0646)  # مؤمن (hamza carrier ؤ)
    marbuta_word = chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629)  # مدرسة (ة)
    maqsura_word = chr(0x0639) + chr(0x0644) + chr(0x0649)  # على (alef maqsura)
    digits = chr(0x0661) + chr(0x0662) + chr(0x0663) + chr(0x060C)  # ١٢٣، (Arabic-Indic + comma)
    elongated = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل (elongation)
    # A double space after أحمــد exercises the whitespace collapse; single spaces elsewhere.
    sentence = (
        f"{bom}{ahmad}  {dagger_word} {hamza_word} "
        f"{marbuta_word} {maqsura_word} {digits} {elongated}"
    )

    expected = " ".join(
        (
            chr(0x0627) + chr(0x062D) + chr(0x0645) + chr(0x062F),  # احمد (tatweel gone, أ -> ا)
            chr(0x0647) + chr(0x0630) + chr(0x0627),  # هذا (dagger alef removed)
            chr(0x0645) + chr(0x0648) + chr(0x0645) + chr(0x0646),  # مومن (ؤ -> و)
            chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0647),  # مدرسه (ة -> ه)
            chr(0x0639) + chr(0x0644) + chr(0x064A),  # علي (ى -> ي)
            "123,",  # digits -> ASCII; comma -> Latin (a digit on one side only is not a separator)
            chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644),  # جميل (elongation capped to 1)
        )
    )
    assert normalize(sentence, profile="search") == expected
