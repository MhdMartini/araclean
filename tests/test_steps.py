"""Behavior of individual normalization steps (the `Step` family)."""

from araclean import NormalizeUnicode, SafetyClass, normalize_unicode

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
