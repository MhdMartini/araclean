"""Behavior of profiles: the named presets that assemble pipelines."""

import unicodedata
from collections import Counter

import pytest
from hypothesis import example, given
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

# Whitespace re-exposed AFTER LIGHT's mid-pipeline CollapseWhitespace, the regression these pin.
# U+FC5E (ARABIC LIGATURE SHADDA WITH DAMMATAN ISOLATED FORM) is a presentation form whose per-glyph
# NFKC fold carries its marks on a SPACE: NFKC(U+FC5E) = space + dammatan + shadda. So
# FoldPresentationForms turns "U+FC5E " into " <marks> " (a space, the marks, the trailing space);
# the lossy profiles' RemoveTashkeel then deletes the marks, leaving two adjacent spaces that the
# LIGHT block's CollapseWhitespace already passed. Without the profiles' closing CollapseWhitespace
# this breaks idempotence and LIGHT-stability. Pinned as an explicit example so the regression is
# caught deterministically, not only when Hypothesis' shared example DB happens to replay it.
ISOLATED_TASHKEEL_THEN_SPACE = chr(0xFC5E) + " "
# A bare combining hamza floating between two spaces: SEARCH's FoldHamza deletes U+0654 the same way
# RemoveTashkeel deletes a mark, re-exposing adjacent whitespace via a different fold (SEARCH only).
FLOATING_HAMZA = " " + chr(0x0654) + " "

# A composition the lossy profiles' mid-pipeline NFC can't see coming: alef + a Qur'anic mark
# (U+06DC) + combining hamza (U+0654). The Qur'anic mark BLOCKS the alef+hamza compose, so this is
# valid NFC; but RemoveTashkeel strips the blocker, exposing alef + hamza, which IS composable.
# ML/SOCIAL keep the hamza (they run no FoldHamza), so without the profiles' closing NFC their
# output is the non-NFC decomposed form — breaking the NFC postcondition, LIGHT-stability and
# idempotence. (SEARCH's FoldHamza deletes the hamza, so it was never affected; the shared closing
# tail covers every profile uniformly regardless.)
BLOCKED_HAMZA = unicodedata.normalize("NFC", chr(0x0627) + chr(0x06DC) + chr(0x0654))


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
@example(ISOLATED_TASHKEEL_THEN_SPACE)  # RemoveTashkeel re-exposes whitespace LIGHT collapsed
@example(FLOATING_HAMZA)  # FoldHamza does the same on a floating combining hamza
@example(BLOCKED_HAMZA)  # exposed alef+hamza -> non-NFC without the closing tail's NFC
def test_search_output_is_light_stable(text: str) -> None:
    # search ⊇ light (AC3): SEARCH does everything LIGHT does, so its output is a LIGHT fixed point.
    # This also pins that SEARCH's output is NFC and whitespace-collapsed -- the shared closing tail
    # (CollapseWhitespace + NFC) makes LIGHT a no-op on it. The three explicit examples exercise the
    # whitespace and canonical-order cases that tail exists to handle.
    light = Pipeline.from_profile(LIGHT)
    searched = normalize(text, profile="search")
    assert light(searched) == searched


@given(ANY_TEXT)
@example(ISOLATED_TASHKEEL_THEN_SPACE)  # was '  ' (two spaces) on the second pass before the fix
@example(FLOATING_HAMZA)
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
@example(ISOLATED_TASHKEEL_THEN_SPACE)  # RemoveTashkeel re-exposes whitespace LIGHT collapsed
@example(BLOCKED_HAMZA)  # RemoveTashkeel exposes alef+hamza -> non-NFC without the closing NFC
def test_ml_output_is_light_stable(text: str) -> None:
    # ML ⊇ LIGHT (AC: LIGHT(ML(x)) == ML(x)): ML does everything LIGHT does, so its output is a
    # LIGHT fixed point. This also pins that ML's output is NFC and whitespace-collapsed -- the
    # shared closing tail (CollapseWhitespace + NFC) makes LIGHT a no-op on it. The two explicit
    # examples exercise the whitespace and canonical-order cases that tail exists to handle.
    light = Pipeline.from_profile(LIGHT)
    cleaned = normalize(text, profile="ml")
    assert light(cleaned) == cleaned


@given(ANY_TEXT)
@example(ISOLATED_TASHKEEL_THEN_SPACE)  # was '  ' (two spaces) on the second pass before the fix
@example(BLOCKED_HAMZA)  # was the non-NFC decomposed alef+hamza on the second pass before the fix
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


# --- SOCIAL profile (issue 0014, story 7): make noisy user text tractable, keep the signal ---
#
# SOCIAL composes LIGHT's encoding repair with cleaning (URL/mention -> Arabic placeholder, HTML
# strip+unescape) and the lossy folds noisy text wants (tashkeel removal, cap-2 elongation), while
# KEEPING emoji by default — the emoji *is* the affective signal SOCIAL exists to preserve.
# Code points, not glyphs, so the corpus is deterministic regardless of how this file is saved.
_URL_TOKEN = "[" + chr(0x0631) + chr(0x0627) + chr(0x0628) + chr(0x0637) + "]"  # [رابط] = "link"
_MENTION_TOKEN = (  # [مستخدم] = "user"
    "[" + chr(0x0645) + chr(0x0633) + chr(0x062A) + chr(0x062E) + chr(0x062F) + chr(0x0645) + "]"
)
_HEART_EYES = chr(0x1F60D)  # 😍


def test_social_worked_example() -> None:
    # The golden worked example (AC1): cap-2 elongation, tashkeel removed, mention/URL -> the Arabic
    # placeholder, emoji kept. جمييييل جدًا يا @user 😍😍 https://example.com
    stretched = (
        chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)
    )  # جمييييل (4 repeated yeh)
    with_tanween = (
        chr(0x062C) + chr(0x062F) + chr(0x064B) + chr(0x0627)
    )  # جدًا (tanween fath on the dal)
    ya = chr(0x064A) + chr(0x0627)  # يا
    text = f"{stretched} {with_tanween} {ya} @user {_HEART_EYES * 2} https://example.com"

    capped_two = chr(0x062C) + chr(0x0645) + chr(0x064A) * 2 + chr(0x0644)  # جمييل (capped to 2)
    tanween_gone = chr(0x062C) + chr(0x062F) + chr(0x0627)  # جدا (tanween removed, alef kept)
    expected = f"{capped_two} {tanween_gone} {ya} {_MENTION_TOKEN} {_HEART_EYES * 2} {_URL_TOKEN}"

    assert normalize(text, profile="social") == expected


def test_social_strips_html_tags_and_unescapes_entities() -> None:
    # AC3: SOCIAL strips tags and unescapes entities -- <b>نص</b> &amp; X -> نص & X. The inner
    # text is kept (DELETE/strip mode), and the entity that survives the strip is decoded.
    inner = chr(0x0646) + chr(0x0635)  # نص ("text")
    text = f"<b>{inner}</b> &amp; X"
    assert normalize(text, profile="social") == f"{inner} & X"


def test_social_preserves_emoji_by_default() -> None:
    # AC4: the affective signal is preserved -- SOCIAL keeps emoji by default (it exists to). The
    # surrounding Arabic is still cleaned (tashkeel removed), so this is not a vacuous identity.
    love = chr(0x0623) + chr(0x062D) + chr(0x0628) + chr(0x0647)  # أحبه ("I love it"), no marks
    text = f"{love} {_HEART_EYES}"
    assert normalize(text, profile="social") == text  # emoji (and text) survive verbatim


def test_social_is_lossy_contains_cleaning_and_linguistic_folding_steps() -> None:
    # The audit complement of LIGHT (story 41): SOCIAL is NOT lossless. It carries CLEANING steps
    # (URL/mention/HTML noise removal) and LINGUISTIC_FOLDING steps (tashkeel removal, elongation),
    # so a safety audit must surface both kinds of loss -- and the kept emoji (KEEP) is a no-op, so
    # it audits as ENCODING_REPAIR, not as loss.
    from araclean import SOCIAL

    safeties = [step.safety for step in Pipeline.from_profile(SOCIAL).steps]
    assert SafetyClass.CLEANING in safeties
    assert SafetyClass.LINGUISTIC_FOLDING in safeties
    assert not all(safety is SafetyClass.ENCODING_REPAIR for safety in safeties)


def test_social_removes_tashkeel_before_capping_a_vocalized_elongation() -> None:
    # The load-bearing ordering decision: RemoveTashkeel runs BEFORE ReduceElongation. A *vocalized*
    # elongation interleaves a haraka between the repeated letters (جم + يَيَيَ + ل), so the marks
    # must be stripped first to leave the yeh adjacent for the cap-2 reducer to collapse to جمييل.
    # If the two were reversed, the reducer would see non-adjacent yeh (split by the fatha), leave
    # them, and tashkeel removal would then yield an UN-capped جميييل (3 yeh) — this test would
    # fail. It is the SOCIAL analogue of ML's tashkeel-before-elongation ordering.
    vocalized_stretch = chr(0x062C) + chr(0x0645) + (chr(0x064A) + chr(0x064E)) * 3 + chr(0x0644)
    capped = chr(0x062C) + chr(0x0645) + chr(0x064A) * 2 + chr(0x0644)  # جمييل (2 yeh, no marks)
    assert normalize(vocalized_stretch, profile="social") == capped


def test_social_facade_equals_explicit_pipeline() -> None:
    # normalize(text, profile="social") is exactly Pipeline.from_profile(SOCIAL): a thin facade.
    from araclean import SOCIAL

    pipe = Pipeline.from_profile(SOCIAL)
    stretched = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل
    for text in (f"@user {_HEART_EYES} https://x.co", stretched, "<b>hi</b> &amp; x", "abc", ""):
        assert normalize(text, profile="social") == pipe(text)
    assert normalize(stretched, profile="social") == normalize(stretched, profile=SOCIAL)


@given(ANY_TEXT)
def test_social_never_raises(text: str) -> None:
    # Total over arbitrary text, incl. lone surrogates (the cleaning regexes + folds never crash).
    normalize(text, profile="social")


def test_social_is_idempotent_on_realistic_noisy_text() -> None:
    # SOCIAL is a fixed point on realistic noisy text. Strict idempotence cannot hold over ARBITRARY
    # text because CleanHTML's html.unescape decodes only one level (&amp;amp; -> &amp; -> &), a
    # documented limit inherited from the step; on realistic single-encoded markup it is stable.
    stretched = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل
    with_tanween = chr(0x062C) + chr(0x062F) + chr(0x064B) + chr(0x0627)  # جدًا
    text = f"<p>{stretched} {with_tanween}</p> @user &amp; {_HEART_EYES} https://example.com/path"
    once = normalize(text, profile="social")
    assert normalize(once, profile="social") == once


def test_social_output_is_idempotent_and_nfc_on_exposed_whitespace_and_composition() -> None:
    # SOCIAL re-tidies what its lossy folds / cleaning re-expose AFTER LIGHT's own closing tail has
    # run — the SOCIAL analogue of the SEARCH/ML property tests, which can't run over ARBITRARY text
    # here (CleanHTML's one-level html.unescape breaks strict idempotence). Three exposures, all
    # fixed by the shared closing tail (CollapseWhitespace + NFC):
    #   - RemoveTashkeel deletes a mark the isolated-form presentation fold left on a space;
    #   - an HTML tag strip leaves two spaces adjacent; and
    #   - RemoveTashkeel deletes a blocking mark, exposing an alef+hamza the closing NFC composes.
    tag_gap = "x </b><b> y"  # stripping both tags leaves "x  y" (two spaces) to re-collapse
    nested_gap = f"<b>{chr(0x0623)}</b>  <b>{chr(0x0628)}</b>"  # two literal spaces between tags
    for text in (ISOLATED_TASHKEEL_THEN_SPACE, tag_gap, nested_gap, BLOCKED_HAMZA):
        once = normalize(text, profile="social")
        assert normalize(once, profile="social") == once  # idempotent fixed point
        assert unicodedata.is_normalized("NFC", once)  # and the NFC postcondition holds


def _social_with(replacements: dict[type, object]) -> Pipeline:
    """A SOCIAL pipeline with each step of a given type replaced in place by the override instance.

    The override *mechanism* (`normalize(..., profile="social", emoji="strip")`) is the config
    boundary's surface (issue 0016, which owns per-knob overrides for every profile); this helper
    pins the override *properties* now — exactly the deferral pattern ML used for its digit fold.
    """
    from araclean import SOCIAL

    steps = [replacements.get(type(s), s) for s in Pipeline.from_profile(SOCIAL).steps]
    return Pipeline(steps)  # type: ignore[arg-type]


def test_social_override_properties_each_default_is_a_one_step_swap() -> None:
    # AC2 (the override *properties*; the kwargs mechanism is deferred to 0016). Each SOCIAL default
    # flips to the documented alternative by swapping exactly one step, with no other change.
    from araclean import (
        CleanMentions,
        CleanMode,
        CleanURLs,
        EmojiMode,
        HandleEmoji,
        ReduceElongation,
    )

    love = chr(0x0623) + chr(0x062D) + chr(0x0628) + chr(0x0647)  # أحبه (no marks)
    stretched = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل
    collapsed_one = chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644)  # جميل (cap 1)

    # emoji="strip" drops the 😍😍 (the default KEEP keeps it).
    emoji_text = f"{love} {_HEART_EYES * 2}"
    stripped = _social_with({HandleEmoji: HandleEmoji(mode=EmojiMode.STRIP)})
    assert normalize(emoji_text, profile="social") == emoji_text  # default keeps
    assert stripped(emoji_text) == f"{love} "  # override strips, surrounding text intact

    # elongation_cap=1 collapses جمييييل all the way to جميل (the default cap 2 stops at جمييل).
    capped_one = _social_with({ReduceElongation: ReduceElongation(cap=1)})
    assert capped_one(stretched) == collapsed_one

    # URL/mention mode="delete" removes them outright (the default replaces with an Arabic token).
    deleted = _social_with(
        {
            CleanURLs: CleanURLs(mode=CleanMode.DELETE),
            CleanMentions: CleanMentions(mode=CleanMode.DELETE),
        }
    )
    assert _URL_TOKEN not in deleted("see https://x.co") and "https" not in deleted(
        "see https://x.co"
    )
    assert _MENTION_TOKEN not in deleted("hi @user") and "@user" not in deleted("hi @user")

    # English-token mode yields [URL]/[MENTION] instead of the Arabic [رابط]/[مستخدم].
    english = _social_with(
        {
            CleanURLs: CleanURLs(mode=CleanMode.PLACEHOLDER, placeholder="[URL]"),
            CleanMentions: CleanMentions(mode=CleanMode.PLACEHOLDER, placeholder="[MENTION]"),
        }
    )
    assert "[URL]" in english("see https://x.co")
    assert "[MENTION]" in english("hi @user")
