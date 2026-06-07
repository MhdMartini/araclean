"""Guard the cSpell terminology contract (ADR-0007).

The canonical Arabic romanizations must be accepted and the common-but-wrong ones
must be forbidden, so a wrong spelling fails CI and the canonical one passes. This
checks the *config* that drives cSpell, so it needs no node toolchain to run.
"""

from __future__ import annotations

import json
import pathlib

import pytest

_CSPELL = pathlib.Path(__file__).resolve().parent.parent / "cspell.json"

# (wrong romanization that must fail, canonical spelling that must pass)
# cspell:disable  -- this list deliberately contains the forbidden spellings
_TERMINOLOGY: list[tuple[str, str]] = [
    ("tashkil", "tashkeel"),
    ("alif", "alef"),
    ("maksura", "maqsura"),
]
# cspell:enable


@pytest.fixture(scope="module")
def cspell_lists() -> tuple[set[str], set[str]]:
    """Return (accepted words, forbidden words) from the cSpell config."""
    data: dict[str, list[str]] = json.loads(_CSPELL.read_text(encoding="utf-8"))
    return set(data["words"]), set(data["flagWords"])


def test_forbidden_words_listed(cspell_lists: tuple[set[str], set[str]]) -> None:
    _words, flag_words = cspell_lists
    for wrong, _canonical in _TERMINOLOGY:
        assert wrong in flag_words, f"{wrong!r} must be a cSpell flagWord"


def test_canonical_words_accepted(cspell_lists: tuple[set[str], set[str]]) -> None:
    words, flag_words = cspell_lists
    for wrong, canonical in _TERMINOLOGY:
        assert canonical in words, f"{canonical!r} must be in the cSpell dictionary"
        assert canonical not in flag_words, f"{canonical!r} must not be forbidden"
        assert wrong not in words, f"the wrong spelling {wrong!r} must not be accepted"
