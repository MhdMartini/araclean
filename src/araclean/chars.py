"""Internal seam: precomputed Unicode tables for the character-level steps.

The single source of truth for the code points each `Step` maps, built once at import. This is
**not** a public interface — every step is tested through its `str -> str` behavior, so a table
here can later be fused into the single-pass engine (0018) without touching a test.
"""

from __future__ import annotations

import unicodedata

# Arabic Presentation Forms-A (U+FB50-U+FDFF) and -B (U+FE70-U+FEFF): the contextual glyph forms
# (isolated/initial/medial/final) and ligatures that OCR, legacy encodings and copy-paste leave in
# text. Each folds back to its base-letter sequence via the character's own compatibility (NFKC)
# decomposition -- including the lam-alef ligatures (U+FEF5-U+FEFC), which decompose to lam + the
# *matching* alef variant (ﻷ -> لأ, not bare لا). We take that decomposition per code point and
# apply it as a `str.translate` substitution, so -- unlike whole-string NFKC -- the fold never
# reorders the combining marks already present (keeping vocalized/Qur'anic text safe for CLASSICAL).
_PRESENTATION_FORM_RANGES: tuple[tuple[int, int], ...] = ((0xFB50, 0xFDFF), (0xFE70, 0xFEFF))


def _build_presentation_forms() -> dict[int, str]:
    table: dict[int, str] = {}
    for start, end in _PRESENTATION_FORM_RANGES:
        for code_point in range(start, end + 1):
            char = chr(code_point)
            folded = unicodedata.normalize("NFKC", char)
            if folded != char:
                table[code_point] = folded
    return table


PRESENTATION_FORMS: dict[int, str] = _build_presentation_forms()
