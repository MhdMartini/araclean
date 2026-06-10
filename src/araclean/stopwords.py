"""The curated, versioned Arabic stopword list backing `RemoveStopwords` (issue 0017).

Provenance — this list is **freshly authored for araclean** from common Modern Standard Arabic
function words (prepositions, pronouns, demonstratives, relative pronouns, conjunctions, and
neutral particles). It is **not** derived from the GPL-licensed ``Arabic-Stopwords`` package or any
other copyleft source, so it does not encumber araclean's MIT core; the list itself is dedicated to
the public domain under **CC0-1.0** (`STOPWORDS_LICENSE`). It carries a `STOPWORDS_VERSION` so a
`Profile` can pin an exact list and stopword removal stays reproducible across releases.

Two deliberate design properties (surfaced in the docs, issue 0023):

- **Flat, not clitic-aware** (ADR-0001 — no morphology). Each entry is a whole bare token; the list
  does not know about proclitics/enclitics, so ``والكتاب`` (and-the-book) and ``فيها`` (in-it) are
  kept — only a standalone ``و`` / ``في`` token would be removed. Matching is on surface forms in
  canonical (NFC) order, so the list should run **before** any lossy letter folding.
- **Negation-safe by default.** The polarity-bearing particles ``ما`` / ``لا`` / ``لم`` / ``لن`` /
  ``ليس`` (`NEGATION_PARTICLES`) are deliberately **excluded**, so `RemoveStopwords` can never
  silently flip the sentiment of a sentence by deleting its negation (story 37).
"""

from __future__ import annotations

import re
import unicodedata

STOPWORDS_VERSION = "1.0.0"
"""The version of the bundled stopword list a `Profile` pins for reproducible removal."""

STOPWORDS_LICENSE = "CC0-1.0"
"""The list is freshly authored and dedicated to the public domain (no GPL source)."""

# The negation / polarity particles kept OUT of the list so removal cannot flip sentiment (story
# 37). Named here so the disjointness is testable and self-documenting, not implicit.
NEGATION_PARTICLES: frozenset[str] = frozenset(
    {
        "ما",  # mā — negation / interrogative
        "لا",  # lā — negation
        "لم",  # lam — negation (past)
        "لن",  # lan — negation (future)
        "ليس",  # negation copula
    }
)

# The curated list — bare Modern Standard Arabic function words, in canonical (NFC) form, no
# tashkeel/tatweel. Authored as a tuple (the source of truth, grouped by part of speech); the
# `_validated` guard below turns it into the deduplicated `STOPWORDS` set used for matching, raising
# at import on any integrity slip. Negation / polarity / exception particles are intentionally
# absent (see NEGATION_PARTICLES and the module docstring) so the list is sentiment-safe.
_STOPWORDS: tuple[str, ...] = (
    # Prepositions
    "في",
    "من",
    "إلى",
    "على",
    "عن",
    "مع",
    "عند",
    "لدى",
    "بين",
    "حول",
    "خلال",
    "منذ",
    "حتى",
    "نحو",
    "ضمن",
    # Personal pronouns
    "أنا",
    "نحن",
    "أنت",
    "أنتم",
    "أنتن",
    "أنتما",
    "هو",
    "هي",
    "هم",
    "هن",
    "هما",
    # Demonstratives
    "هذا",
    "هذه",
    "هذان",
    "هذين",
    "هاتان",
    "هاتين",
    "هؤلاء",
    "ذلك",
    "ذاك",
    "تلك",
    "أولئك",
    "هنا",
    "هناك",
    "هنالك",
    # Relative pronouns
    "الذي",
    "التي",
    "الذين",
    "اللذان",
    "اللذين",
    "اللتان",
    "اللتين",
    "اللاتي",
    "اللواتي",
    "اللائي",
    # Conjunctions and subordinators (neutral — no negation particles)
    "أو",
    "ثم",
    "بل",
    "أم",
    "لكن",
    "حيث",
    "إذ",
    "إذا",
    "إن",
    "أن",
    "كأن",
    "لأن",
    "لكي",
    "كي",
    "كما",
    # Neutral particles, quantifiers and adverbs
    "قد",
    "لقد",
    "سوف",
    "كل",
    "بعض",
    "جميع",
    "نفس",
    "بعد",
    "قبل",
    "فقط",
    "أيضا",
    "كذلك",
    "أي",
    "أية",
    "كم",
    "هل",
    "كيف",
    "متى",
    "أين",
    "عندما",
    "حينما",
    "بينما",
    "حين",
)


def _validated(words: tuple[str, ...]) -> frozenset[str]:
    """Enforce the list's integrity at import (story 36) and return it as a matching set.

    Raises `ValueError` if any entry is empty, contains whitespace, tatweel or a non-letter (so the
    list is bare, canonical-form Arabic), if any entry is non-NFC, if a `NEGATION_PARTICLES` member
    slipped in (negation safety, story 37), or if there is a duplicate. A bad edit therefore fails
    at import — in CI and every test run — rather than silently shipping a malformed list.
    """
    seen: set[str] = set()
    for word in words:
        if word in seen:
            raise ValueError(f"duplicate stopword {word!r}")  # pragma: no cover
        if word in NEGATION_PARTICLES:  # pragma: no cover
            raise ValueError(f"negation particle {word!r} must not be a stopword")
        if not word or word != unicodedata.normalize("NFC", word):  # pragma: no cover
            raise ValueError(f"stopword {word!r} is empty or not in NFC form")
        if any(ch.isspace() or ch == "ـ" or unicodedata.category(ch) != "Lo" for ch in word):
            raise ValueError(f"stopword {word!r} is not bare Arabic letters")  # pragma: no cover
        seen.add(word)
    return frozenset(seen)


STOPWORDS: frozenset[str] = _validated(_STOPWORDS)
"""The bundled stopword set used for matching (deduplicated, integrity-checked `_STOPWORDS`)."""


def _build_pattern(words: frozenset[str]) -> re.Pattern[str]:
    """Compile a whole-word matcher for `words`: ``\\b(w1|w2|…)\\b`` with the alternatives sorted
    longest-first so a longer stopword wins over a shorter prefix of it. The ``\\b`` boundaries make
    matching whole-token (and so clitic-insensitive): an Arabic letter on either side blocks the
    boundary, so a prefixed/suffixed form like ``والكتاب`` / ``فيها`` is never matched."""
    alternatives = "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternatives})\b")


STOPWORD_PATTERN: re.Pattern[str] = _build_pattern(STOPWORDS)
"""The precompiled whole-word matcher for the bundled list (used by `RemoveStopwords`)."""
