"""Behavior of profiles: the named presets that assemble pipelines."""

import pytest

from araclean import LIGHT, Pipeline, Profile, SafetyClass

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
