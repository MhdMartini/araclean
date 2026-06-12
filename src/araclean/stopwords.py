"""The curated, versioned Arabic stopword list backing `RemoveStopwords`.

Provenance — this list is **freshly authored for araclean** from common Modern Standard Arabic
function words (prepositions, pronouns, demonstratives, relative pronouns, conjunctions, and
neutral particles). It is **not** derived from the GPL-licensed ``Arabic-Stopwords`` package or any
other copyleft source, so it does not encumber araclean's MIT core; the list itself is dedicated to
the public domain under **CC0-1.0** (`STOPWORDS_LICENSE`). It carries a `STOPWORDS_VERSION` so a
`Profile` can pin an exact list and stopword removal stays reproducible across releases.

Design properties (surfaced in the docs):

- **FOLDED FORM — run AFTER the letter folds** (list version 2). Every entry is stored in its
  letter-folded spelling (no hamza-bearing alef أ/إ, no alef maqsura ى, no hamza carrier ؤ/ئ — the
  output of `FoldAlef` + `FoldAlefMaqsura` + `FoldHamza`), and `RemoveStopwords` requires those
  folds plus `RemoveTashkeel` to run before it (`Pipeline` enforces this at construction). The
  pipeline itself is the spelling-variant generator: the canonical إلى, the routinely-typed
  hamza-less الى, and the vocalized إلَى all fold to the one entry الى→الي, so matching is robust
  without enumerating variants. `_validated` enforces fold-stability per entry at import.
- **Flat, not clitic-aware** (ADR-0001 — no morphology). Each entry is a whole bare token; the list
  does not know about proclitics/enclitics, so ``والكتاب`` (and-the-book) and ``فيها`` (in-it) are
  kept — only a standalone ``و`` / ``في`` token would be removed.
- **Negation-safe by default.** The polarity-bearing particles ``ما`` / ``لا`` / ``لم`` / ``لن`` /
  ``ليس`` (`NEGATION_PARTICLES`) are deliberately **excluded**, so `RemoveStopwords` can never
  silently flip the sentiment of a sentence by deleting its negation.
- **Homograph policy — one stated principle.** An entry is kept iff its FUNCTION-word reading
  dominates its content readings by token frequency in running text (in the folded spelling, since
  folding merges words). Dropped under that principle: أم (*or* — but commonly *mother*: أم محمد),
  كم (*how many* — but also *km*), نفس (*same* — but commonly *soul/self/breath*), كأن (*as if* —
  folds onto كان *was*, one of the most frequent verbs), أية (*any* fem. — rare standalone, and its
  folded ايه is the dialectal *what?*). Kept despite a known collision: علي (the fold of the
  preposition على — the preposition dwarfs the name *Ali* in running text; the residual is that a
  bare standalone علي is removed), لان (the fold of لأن *because* — the verb reading *softened* is
  rare), ان (the shared fold of إن and أن — the rare آن *time* also lands there and is accepted).
"""

from __future__ import annotations

import re
import unicodedata

from araclean import chars

STOPWORDS_VERSION = "2.0.0"
"""The version of the bundled stopword list a `Profile` pins for reproducible removal."""

STOPWORDS_LICENSE = "CC0-1.0"
"""The list is freshly authored and dedicated to the public domain (no GPL source)."""

# The negation / polarity particles kept OUT of the list so removal cannot flip sentiment.
# Named here so the disjointness is testable and self-documenting, not implicit. All five are
# fixed points of the letter folds, so the exclusion is fold-stable too.
NEGATION_PARTICLES: frozenset[str] = frozenset(
    {
        "ما",  # mā — negation / interrogative
        "لا",  # lā — negation
        "لم",  # lam — negation (past)
        "لن",  # lan — negation (future)
        "ليس",  # negation copula
    }
)

# The curated list — bare Modern Standard Arabic function words in FOLDED, canonical (NFC) form: no
# tashkeel/tatweel, and no foldable letter (the spelling RemoveStopwords sees after the required
# folds — see the module docstring). Authored as a tuple (the source of truth, grouped by part of
# speech; a comment notes the canonical spelling where folding changed it); the `_validated` guard
# below turns it into the deduplicated `STOPWORDS` set used for matching, raising at import on any
# integrity slip — including an entry that is not a fixed point of the folds. Negation / polarity
# particles and the policy-dropped homographs (module docstring) are intentionally absent.
_STOPWORDS: tuple[str, ...] = (
    # Prepositions
    "في",
    "من",
    "الي",  # إلى
    "علي",  # على (accepted collision with the name علي — see the homograph policy)
    "عن",
    "مع",
    "عند",
    "لدي",  # لدى
    "بين",
    "حول",
    "خلال",
    "منذ",
    "حتي",  # حتى
    "نحو",
    "ضمن",
    # Personal pronouns
    "انا",  # أنا
    "نحن",
    "انت",  # أنت
    "انتم",  # أنتم
    "انتن",  # أنتن
    "انتما",  # أنتما
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
    "هولاء",  # هؤلاء
    "ذلك",
    "ذاك",
    "تلك",
    "اوليك",  # أولئك
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
    "اللايي",  # اللائي
    # Conjunctions and subordinators (neutral — no negation particles)
    "او",  # أو
    "ثم",
    "بل",
    "لكن",
    "حيث",
    "اذ",  # إذ
    "اذا",  # إذا
    "ان",  # the shared fold of إن and أن (one entry covers both)
    "لان",  # لأن
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
    "بعد",
    "قبل",
    "فقط",
    "ايضا",  # أيضا
    "كذلك",
    "اي",  # أي
    "هل",
    "كيف",
    "متي",  # متى
    "اين",  # أين
    "عندما",
    "حينما",
    "بينما",
    "حين",
)


def _letter_fold(word: str) -> str:
    """Apply the letter folds `RemoveStopwords` requires before it (`FoldAlef`,
    `FoldAlefMaqsura`, the always-on part of `FoldHamza`, `FoldTehMarbuta`→heh), straight from the
    `chars` tables (importing `steps` here would be circular). An entry must be a fixed point of
    this fold — otherwise the post-fold text could never contain it and removal would silently
    miss it."""
    folded = word.translate(chars.FOLD_ALEF)
    folded = folded.translate(chars.FOLD_ALEF_MAQSURA)
    folded = folded.translate(chars.FOLD_HAMZA_CARRIERS)
    folded = folded.translate(dict.fromkeys(chars.COMBINING_HAMZA))
    return folded.translate({cp: chr(chars.HEH) for cp in chars.TEH_MARBUTA})


def _validated(words: tuple[str, ...]) -> frozenset[str]:
    """Enforce the list's integrity at import and return it as a matching set.

    Raises `ValueError` if any entry is empty, contains whitespace, tatweel or a non-letter (so the
    list is bare, canonical-form Arabic), if any entry is non-NFC, if an entry is not a FIXED POINT
    of the letter folds (the list ships folded — version 2's contract), if a `NEGATION_PARTICLES`
    member slipped in (negation safety), or if there is a duplicate (which also guards
    the إن/أن-style fold merges: both must be authored as the single folded entry). A bad edit
    therefore fails at import — in CI and every test run — rather than silently shipping a
    malformed list.
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
        if _letter_fold(word) != word:  # pragma: no cover
            raise ValueError(
                f"stopword {word!r} is not letter-folded; author it as {_letter_fold(word)!r}"
            )
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
