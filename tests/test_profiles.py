"""Behavior of profiles: the named presets that assemble pipelines."""

import unicodedata
from collections import Counter

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import LIGHT, Pipeline, Profile, SafetyClass, normalize


def _combining_marks(text: str) -> Counter[str]:
    """The count of each combining mark (ccc > 0) in `text` — order-independent mark accounting."""
    return Counter(c for c in text if unicodedata.combining(c))


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


# --- ML profile (issue 0011, story 6): conservative-on-letters cleaning for model input ---

# كَتَبَ fully vocalized: every letter carries a fatha.
VOCALIZED = chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E) + chr(0x0628) + chr(0x064E)


def test_ml_removes_tashkeel() -> None:
    # ML is lossy where LIGHT is not: it strips vocalization, so كَتَبَ -> كتب.
    assert normalize(VOCALIZED, profile="ml") == chr(0x0643) + chr(0x062A) + chr(0x0628)


def test_ml_reduces_elongation() -> None:
    # Emphatic word-lengthening is collapsed to the cap-1 default (جمييييل -> جميل), so a model's
    # vocabulary does not explode on stretched spellings.
    lengthened = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل
    assert normalize(lengthened, profile="ml") == chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(
        0x0644
    )  # جميل


def test_ml_preserves_letter_distinctions() -> None:
    # ML's thesis (the AraToken finding): the alef/hamza/alef-maqsura/teh-marbuta variants are
    # disambiguating, so ML keeps them all — unlike SEARCH, none of the 0007 letter folds run.
    ala_maqsura = chr(0x0639) + chr(0x0644) + chr(0x0649)  # على (alef maqsura)
    ala_yeh = chr(0x0639) + chr(0x0644) + chr(0x064A)  # علي (yeh)
    assert normalize(ala_maqsura, profile="ml") == ala_maqsura
    assert normalize(ala_yeh, profile="ml") == ala_yeh
    assert normalize(ala_maqsura, profile="ml") != normalize(ala_yeh, profile="ml")  # stay distinct

    ahmad = chr(0x0623) + chr(0x062D) + chr(0x0645) + chr(0x062F)  # أحمد keeps its hamza-alef
    assert normalize(ahmad, profile="ml") == ahmad
    marbuta_word = chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629)  # مدرسة
    assert normalize(marbuta_word, profile="ml") == marbuta_word  # teh marbuta kept


def test_ml_is_lossy_contains_linguistic_folding_steps() -> None:
    # The audit complement of LIGHT (story 41): ML is NOT lossless — it carries RemoveTashkeel and
    # ReduceElongation, so a safety audit must surface that it loses information.
    from araclean import ML

    safeties = [step.safety for step in Pipeline.from_profile(ML).steps]
    assert SafetyClass.LINGUISTIC_FOLDING in safeties
    assert not all(safety is SafetyClass.ENCODING_REPAIR for safety in safeties)


def test_ml_facade_equals_explicit_pipeline() -> None:
    # normalize(text, profile="ml") is exactly Pipeline.from_profile(ML) (the facade is thin).
    from araclean import ML

    pipe = Pipeline.from_profile(ML)
    lengthened = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل
    for text in (VOCALIZED, lengthened, ALA_MAQSURA, "abc", ""):
        assert normalize(text, profile="ml") == pipe(text)
    assert normalize(VOCALIZED, profile="ml") == normalize(VOCALIZED, profile=ML)


@given(ANY_TEXT)
def test_ml_output_is_light_stable(text: str) -> None:
    # ML ⊇ LIGHT (AC: LIGHT(ML(x)) == ML(x)): ML does everything LIGHT does, so its output is a
    # LIGHT fixed point. This also pins that ML's output is NFC (LIGHT's closing pass is a no-op on
    # it), justifying that ML appends no trailing NFC of its own — exactly as SEARCH does.
    light = Pipeline.from_profile(LIGHT)
    cleaned = normalize(text, profile="ml")
    assert light(cleaned) == cleaned


@given(ANY_TEXT)
def test_ml_never_raises_and_is_idempotent(text: str) -> None:
    once = normalize(text, profile="ml")  # total over arbitrary text, incl. lone surrogates
    assert normalize(once, profile="ml") == once  # idempotent fixed point


# Shared fixture pinning where ML and SEARCH agree vs diverge (AC: ML differs from SEARCH exactly
# on the letter-folding / digit / punctuation steps). Each row is (input, ml_out, search_out):
# both strip tashkeel and reduce elongation identically; only the letter-fold / digit / punctuation
# rows differ, because ML runs none of those steps. Words are double-free so the cap-1 elongation
# reducer leaves the non-elongated ones alone.
_ML_VS_SEARCH: list[tuple[str, str, str]] = [
    # vocalized, no fold target: both -> bare كتب (agree)
    (
        chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E) + chr(0x0628) + chr(0x064E),
        chr(0x0643) + chr(0x062A) + chr(0x0628),
        chr(0x0643) + chr(0x062A) + chr(0x0628),
    ),
    # elongation, no fold target: both collapse the yeh run -> جميل (agree)
    (
        chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644),
        chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644),
        chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644),
    ),
    # alef maqsura: ML keeps على, SEARCH folds -> علي (DIFFER — letter folding)
    (
        chr(0x0639) + chr(0x0644) + chr(0x0649),
        chr(0x0639) + chr(0x0644) + chr(0x0649),
        chr(0x0639) + chr(0x0644) + chr(0x064A),
    ),
    # teh marbuta: ML keeps مدرسة, SEARCH folds -> مدرسه (DIFFER — letter folding)
    (
        chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629),
        chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629),
        chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0647),
    ),
    # Arabic-Indic digits: ML keeps ١٢٣, SEARCH maps -> 123 (DIFFER — digit mapping)
    (
        chr(0x0661) + chr(0x0662) + chr(0x0663),
        chr(0x0661) + chr(0x0662) + chr(0x0663),
        "123",
    ),
    # Arabic question mark: ML keeps ؟, SEARCH maps -> ? (DIFFER — punctuation mapping)
    (chr(0x061F), chr(0x061F), "?"),
]


def test_ml_differs_from_search_exactly_on_folds_digits_punctuation() -> None:
    from araclean import ML, SEARCH

    ml = Pipeline.from_profile(ML)
    search = Pipeline.from_profile(SEARCH)
    for text, ml_out, search_out in _ML_VS_SEARCH:
        assert ml(text) == ml_out
        assert search(text) == search_out
    # Where ML == SEARCH the row carries no fold/digit/punctuation target (encoding/tashkeel/
    # elongation only); where they differ it is exactly a letter-fold / digit / punctuation row.
    agree = [text for text, m, s in _ML_VS_SEARCH if m == s]
    differ = [text for text, m, s in _ML_VS_SEARCH if m != s]
    assert agree and differ  # the fixture exercises both halves of the contrast


def test_ml_optional_digit_fold_does_not_affect_letter_distinctions() -> None:
    # The story's optional MapDigits fold is OFF by default (preserving distinctions is ML's
    # contract); the config *mechanism* to switch it on belongs to the config boundary (0016). The
    # property that makes the toggle safe is pinned here: folding digits maps the digits but leaves
    # every letter distinction exactly as plain ML leaves it — digit folding never touches a letter.
    from araclean import ML, MapDigits

    ml = Pipeline.from_profile(ML)
    ml_with_digits = Pipeline([*ml.steps, MapDigits()])

    arabic_indic_123 = chr(0x0661) + chr(0x0662) + chr(0x0663)  # ١٢٣
    assert ml(arabic_indic_123) == arabic_indic_123  # default: digits kept
    assert ml_with_digits(arabic_indic_123) == "123"  # toggled on: digits folded

    # Every letter/distinction is identical with the fold on vs off (it only touches digits).
    for word in (
        chr(0x0639) + chr(0x0644) + chr(0x0649),  # على (maqsura)
        chr(0x0623) + chr(0x062D) + chr(0x0645) + chr(0x062F),  # أحمد (hamza)
        chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629),  # مدرسة (teh marbuta)
    ):
        assert ml_with_digits(word) == ml(word) == word


def test_ml_end_to_end_respects_the_ordering_contract() -> None:
    # One string crossing ML's bands — encoding repair -> tashkeel removal -> elongation cleanup —
    # matched to a hand-composed result. The mirror image of the SEARCH end-to-end test: the hamza
    # alef, the alef maqsura, the digits and the Arabic comma all SURVIVE, because ML runs no letter
    # fold and no digit/punctuation map.
    bom = chr(0xFEFF)  # leading BOM (StripBidi removes it)
    ahmad = (
        chr(0x0623) + chr(0x062D) + chr(0x0645) + chr(0x0640) * 2 + chr(0x062F)
    )  # أحمــد (tatweel)
    vocalized = (
        chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E) + chr(0x0628) + chr(0x064E)
    )  # كَتَبَ
    elongated = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل
    maqsura_word = chr(0x0639) + chr(0x0644) + chr(0x0649)  # على (kept by ML)
    digits = chr(0x0661) + chr(0x0662) + chr(0x0663) + chr(0x060C)  # ١٢٣، (kept by ML)
    # A double space after أحمــد exercises the whitespace collapse; single spaces elsewhere.
    sentence = f"{bom}{ahmad}  {vocalized} {elongated} {maqsura_word} {digits}"

    expected = " ".join(
        (
            chr(0x0623) + chr(0x062D) + chr(0x0645) + chr(0x062F),  # أحمد: tatweel gone, hamza kept
            chr(0x0643) + chr(0x062A) + chr(0x0628),  # كتب (tashkeel removed)
            chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644),  # جميل (elongation capped to 1)
            chr(0x0639) + chr(0x0644) + chr(0x0649),  # على (maqsura NOT folded)
            chr(0x0661) + chr(0x0662) + chr(0x0663) + chr(0x060C),  # ١٢٣، (digits & comma KEPT)
        )
    )
    assert normalize(sentence, profile="ml") == expected


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


# --- CLASSICAL profile (issue 0015, story 8): encoding repair that PRESERVES vocalization ---
#
# CLASSICAL is the lossless sibling of LIGHT for vocalized / Qur'anic text: it repairs encoding
# exactly as LIGHT does, but its contract is the explicit guarantee that no vocalization mark
# (harakat/tanween/shadda/madda/dagger-alef/Qur'anic annotation) is ever removed and that
# presentation-form folding never disturbs the surrounding combining marks. The contrast partner is
# SEARCH, whose RemoveTashkeel strips exactly those marks.

# هٰذا: heh + dagger alef (U+0670) + U+0630 + alef. The "dagger alef preserved" golden fixture.
DAGGER_WORD = chr(0x0647) + chr(0x0670) + chr(0x0630) + chr(0x0627)


def test_classical_preserves_dagger_alef() -> None:
    # "dagger alef preserved" (AC1): CLASSICAL keeps هٰذا verbatim, where SEARCH folds it to هذا.
    assert normalize(DAGGER_WORD, profile="classical") == DAGGER_WORD
    assert normalize(DAGGER_WORD, profile="search") != DAGGER_WORD  # the contrast: SEARCH strips it


def test_classical_preserves_quranic_annotation_marks_intact_and_in_order() -> None:
    # AC2: a vocalized fragment carrying every kind of mark CLASSICAL must keep — harakat (kasra),
    # sukun, shadda+fatha, dagger alef, and two Qur'anic small-high annotation signs —
    # round-trips with all marks intact and combining-mark order preserved. The fragment is taken in
    # its canonical (NFC) form, the order every profile emits (ADR-0009).
    raw = (
        chr(0x0628)
        + chr(0x0650)
        + chr(0x0633)
        + chr(0x0652)
        + chr(0x0645)
        + chr(0x0650)  # بِسْمِ
        + " "
        + chr(0x0631)
        + chr(0x0670)
        + chr(0x06DC)  # ر + dagger alef + small high seen
        + " "
        + chr(0x062D)
        + chr(0x0651)
        + chr(0x064E)
        + chr(0x06DA)  # ح + shadda + fatha + small high mark (U+06DA)
    )
    verse = unicodedata.normalize("NFC", raw)

    # Round-trips byte-exact: no mark removed, canonical mark order preserved.
    assert normalize(verse, profile="classical") == verse
    # Every combining mark survives, none added or dropped (order-independent accounting).
    assert _combining_marks(normalize(verse, profile="classical")) == _combining_marks(verse)
    # The contrast that gives CLASSICAL its meaning: SEARCH's RemoveTashkeel strips all of them.
    assert _combining_marks(normalize(verse, profile="search")) == Counter()


def test_classical_decomposes_lam_alef_without_disturbing_surrounding_marks() -> None:
    # AC3: a presentation-form lam-alef ligature embedded in vocalized text decomposes to its base
    # letters (keeping the alef variant) WITHOUT touching the combining marks on the letters around
    # it — FoldPresentationForms is a per-glyph substitution, never a mark mover.
    ligature = chr(0xFEF7)  # ﻷ : lam + alef-with-hamza-above, isolated presentation form
    text = chr(0x0628) + chr(0x064E) + ligature + chr(0x0631) + chr(0x0650)  # بَ + ﻷ + رِ
    expected = (
        chr(0x0628)
        + chr(0x064E)  # بَ unchanged
        + chr(0x0644)
        + chr(0x0623)  # ﻷ -> ل + أ (the alef-hamza-above variant kept, not bare alef)
        + chr(0x0631)
        + chr(0x0650)  # رِ unchanged
    )
    out = normalize(text, profile="classical")
    assert out == expected
    assert ligature not in out  # the ligature is gone
    assert _combining_marks(out) == _combining_marks(text)  # the surrounding marks are intact


def test_classical_is_lossless_all_encoding_repair() -> None:
    # AC4 (story 41 / ADR-0004): CLASSICAL is a "lossless" profile, so — like LIGHT — every step it
    # composes must be ENCODING_REPAIR. This is the audit complement of SEARCH/ML (which carry
    # LINGUISTIC_FOLDING steps); a future edit that slipped a lossy step in would fail here.
    from araclean import CLASSICAL

    pipe = Pipeline.from_profile(CLASSICAL)
    assert all(step.safety is SafetyClass.ENCODING_REPAIR for step in pipe.steps)


def test_classical_facade_equals_explicit_pipeline() -> None:
    # normalize(text, profile="classical") is exactly Pipeline.from_profile(CLASSICAL): thin facade.
    from araclean import CLASSICAL

    pipe = Pipeline.from_profile(CLASSICAL)
    for text in (DAGGER_WORD, chr(0xFEF7), DECOMPOSED, "Hello, world!", ""):
        assert normalize(text, profile="classical") == pipe(text)
    assert normalize(DAGGER_WORD, profile="classical") == normalize(DAGGER_WORD, profile=CLASSICAL)


@given(ANY_TEXT)
def test_classical_equals_light_behavior(text: str) -> None:
    # CLASSICAL IS LIGHT's encoding repair under a distinct name (the design decision): it composes
    # exactly LIGHT's steps, so the two produce identical output on arbitrary text. The value
    # CLASSICAL adds is the named, citable preset plus its preservation guarantee, not different
    # behavior — and this equivalence buys CLASSICAL LIGHT's totality and NFC-stability for free.
    assert normalize(text, profile="classical") == normalize(text, profile="light")


@given(ANY_TEXT)
def test_classical_never_raises_and_is_idempotent(text: str) -> None:
    # AC4: a lossless fixed point — total over arbitrary text (incl. surrogates) and idempotent.
    once = normalize(text, profile="classical")
    assert normalize(once, profile="classical") == once
