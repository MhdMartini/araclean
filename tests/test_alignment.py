"""Offset-preserving normalization — the v2 flagship feature (ADR-0012).

The old placeholder tests (ADR-0005 "raise on any call") are superseded here:
apply_aligned now works for all built-in steps, and still raises a clear error
for custom steps that have not implemented the hook.
"""

import pytest

from araclean import AlignmentNotSupportedError, NormalizeUnicode, Pipeline
from araclean.offsets import OffsetMap
from araclean.safety import SafetyClass


def test_apply_aligned_returns_normalized_and_offset_map() -> None:
    pipe = Pipeline([NormalizeUnicode()])
    normalized, omap = pipe.apply_aligned("مرحبا")
    assert isinstance(normalized, str)
    assert isinstance(omap, OffsetMap)


def test_apply_aligned_normalized_matches_call() -> None:
    pipe = Pipeline([NormalizeUnicode()])
    text = "مرحبا"
    assert pipe(text) == pipe.apply_aligned(text)[0]


def test_alignment_error_is_a_notimplementederror() -> None:
    # AlignmentNotSupportedError is still a NotImplementedError (for fallback probing).
    assert issubclass(AlignmentNotSupportedError, NotImplementedError)


def test_custom_step_without_apply_aligned_raises() -> None:
    class CustomStep:
        safety = SafetyClass.ENCODING_REPAIR

        def __call__(self, s: str, /) -> str:
            return s

    pipe = Pipeline([CustomStep()])
    with pytest.raises(AlignmentNotSupportedError) as excinfo:
        pipe.apply_aligned("نص")
    message = str(excinfo.value)
    assert "CustomStep" in message
    assert "apply_aligned" in message
