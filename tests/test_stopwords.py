"""Integrity of the curated, versioned Arabic stopword list (issue 0017, story 36).

The list's hard invariants — **no duplicates**, bare canonical (NFC) Arabic letters, and no negation
particle — are enforced at *import* by `araclean.stopwords` itself (a malformed edit raises, failing
CI), so importing the module here already exercises them on the real data. These tests pin the same
observable properties through the public `STOPWORDS` set, plus the version/license provenance.
"""

import unicodedata

from araclean import stopwords


def test_stopwords_are_bare_arabic_letters_in_normalized_form() -> None:
    # Every entry is a non-empty, whitespace-free, canonical (NFC) token made only of Arabic LETTERS
    # (Unicode category Lo): no tashkeel/combining marks (Mn), no tatweel, no digits. This keeps the
    # list clean and predictable, and lets it match surface MSA text directly.
    for word in stopwords.STOPWORDS:
        assert word, "empty stopword entry"
        assert word == unicodedata.normalize("NFC", word), f"{word!r} is not NFC"
        assert "ـ" not in word, f"{word!r} contains tatweel"
        for ch in word:
            assert not ch.isspace(), f"{word!r} contains whitespace"
            assert unicodedata.category(ch) == "Lo", (
                f"{word!r} has {ch!r} ({unicodedata.category(ch)}), not an Arabic letter (Lo)"
            )


def test_stopwords_exclude_negation_particles() -> None:
    # Negation safety (story 37): the polarity-bearing particles are disjoint from the removal list,
    # so RemoveStopwords can never delete a negation and flip sentiment.
    assert stopwords.NEGATION_PARTICLES.isdisjoint(stopwords.STOPWORDS)
    for particle in ("ما", "لا", "لم", "لن", "ليس"):
        assert particle in stopwords.NEGATION_PARTICLES
        assert particle not in stopwords.STOPWORDS


def test_stopwords_carry_a_version_and_open_license_provenance() -> None:
    # The list is versioned (so a Profile pins it) and freshly authored under an open, non-GPL
    # license (so it does not encumber the MIT core) — both stated, not implicit.
    assert isinstance(stopwords.STOPWORDS_VERSION, str) and stopwords.STOPWORDS_VERSION
    assert stopwords.STOPWORDS_LICENSE == "CC0-1.0"
    provenance = stopwords.__doc__ or ""
    assert "CC0" in provenance
    assert "GPL" in provenance  # explicitly states it is NOT derived from a GPL source
    assert "freshly authored" in provenance


def test_stopwords_list_is_substantial() -> None:
    # A real curated list, not a token placeholder.
    assert len(stopwords.STOPWORDS) >= 50


def test_stopwords_ship_in_letter_folded_form() -> None:
    # The version-2 contract: every entry is a FIXED POINT of the letter folds RemoveStopwords
    # requires before it (FoldAlef, FoldAlefMaqsura, FoldHamza, FoldTehMarbuta->heh), so the list
    # can only ever be matched against — never missed by — post-fold text. Re-applied here through
    # the public step functions (the import-time guard uses the raw tables).
    from araclean import fold_alef, fold_alef_maqsura, fold_hamza, fold_teh_marbuta

    for word in stopwords.STOPWORDS:
        folded = fold_teh_marbuta(fold_hamza(fold_alef_maqsura(fold_alef(word))))
        assert folded == word, f"{word!r} is not letter-folded (folds to {folded!r})"


def test_stopwords_homograph_policy_drops_the_lopsided_entries() -> None:
    # One stated principle: an entry is kept iff its function-word reading dominates its content
    # readings in the folded spelling. The policy-dropped homographs must stay out (in canonical
    # AND folded spellings), and the kept-despite-collision entries must stay in.
    dropped = (
        "أم",  # *or* — commonly *mother* (أم محمد)
        "ام",  # its folded spelling
        "كم",  # *how many* — also *km* (٥ كم)
        "نفس",  # *same* — commonly *soul/self/breath*
        "كأن",  # *as if* — folds onto…
        "كان",  # …the verb *was*, one of the most frequent words
        "أية",  # *any* (fem.) — rare standalone; folded ايه is dialectal *what?*
        "ايه",
    )
    for word in dropped:
        assert word not in stopwords.STOPWORDS, f"{word!r} should be dropped by the policy"
    kept = (
        "علي",  # fold of the preposition على — dwarfs the name *Ali* in running text
        "لان",  # fold of لأن *because* — the verb reading is rare
        "ان",  # shared fold of إن/أن — the rare آن *time* is accepted
        "حول",  # *around* — the noun reading (لا حول…) is mostly one fixed phrase
    )
    for word in kept:
        assert word in stopwords.STOPWORDS, f"{word!r} should be kept by the policy"


def test_stopwords_canonical_hamza_spellings_are_not_in_the_list() -> None:
    # The folded list carries no hamza-bearing alef spellings: the canonical forms match only
    # AFTER the required folds run (the design that makes hamza-less typed text match too).
    for canonical in ("إلى", "أنا", "أو", "إذا", "إن", "أن", "أين", "هؤلاء", "أولئك"):
        assert canonical not in stopwords.STOPWORDS
