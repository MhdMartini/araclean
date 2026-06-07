"""The offset/alignment hook is reserved but not implemented in v1 (ADR-0005)."""

import pytest

from araclean import AlignmentNotSupportedError, NormalizeUnicode, Pipeline


def test_requesting_alignment_raises_clear_error() -> None:
    pipe = Pipeline([NormalizeUnicode()])
    with pytest.raises(AlignmentNotSupportedError) as excinfo:
        pipe.apply_aligned("نص")
    # The error is actionable: it names the offending step and points at the reserved hook.
    message = str(excinfo.value)
    assert "NormalizeUnicode" in message
    assert "apply_aligned" in message


def test_alignment_error_is_a_notimplementederror() -> None:
    # Subclasses the stdlib base, so callers probing for the capability can fall back.
    assert issubclass(AlignmentNotSupportedError, NotImplementedError)
