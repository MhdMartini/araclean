"""Differential-oracle tests — araclean vs pyarabic (issue 0019, story 46, ADR-0002).

pyarabic is a **reference oracle, never a dependency** (ADR-0002): it is GPL-3.0 and is installed
only in the dev group, so ``pip install araclean`` pulls none of it. These tests
`pytest.importorskip` it, so they run wherever the oracle is installed (the whole CI matrix) and
skip cleanly otherwise.

For every operation both libraries implement we do one of two things, never neither:

  * **Assert agreement** on the shared domain — so if araclean ever drifts from the behavior an
    independent, widely-used tool establishes (a tatweel strip that stops deleting U+0640, a
    dediacritization that misses a haraka), a differential test catches it.
  * **Assert the divergence** where araclean deliberately differs, *and document why*. An
    intentional difference (araclean's lossless presentation-form fold, its fuller mark coverage,
    its finer alef/alef-maqsura/hamza taxonomy) must be pinned explicitly — never left to pass
    silently, where a real regression could hide behind "well, they were always different".

The heavier oracle, CAMeL Tools, is intentionally **not** wired in: it drags in torch + the full
GPU runtime stack and downgrades typer, so it is opt-in only (see ``benchmarks/README.md``).
pyarabic covers the shared char-level operations this suite asserts.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from araclean import (
    MarkClass,
    fold_alef,
    fold_hamza,
    fold_presentation_forms,
    fold_teh_marbuta,
    remove_tashkeel,
    remove_tatweel,
)

# Import the oracle by string, so the type checkers never try to resolve the (stub-less) module and
# the suite skips wherever pyarabic is absent. `getattr` yields the function as `Any`; pinning each
# to an explicit `Callable[[str], str]` keeps the strict gate clean without a single type-ignore.
araby = pytest.importorskip("pyarabic.araby")


def _oracle(name: str) -> Callable[[str], str]:
    fn: Callable[[str], str] = getattr(araby, name)
    return fn


py_strip_tatweel = _oracle("strip_tatweel")
py_strip_tashkeel = _oracle("strip_tashkeel")
py_normalize_alef = _oracle("normalize_alef")
py_normalize_teh = _oracle("normalize_teh")
py_normalize_ligature = _oracle("normalize_ligature")
py_normalize_hamza = _oracle("normalize_hamza")


# Plain Arabic consonants — no alef variants, no teh marbuta, no marks — so a generated word's only
# foldable content is whatever mark/letter alphabet we add to this base, per operation.
_BASE = "بتثجحدرزسشصضطعفقكلمنهوي"
# The classic, contiguous tashkeel block U+064B-U+0652 (tanween, harakat, shadda, sukun) — the
# set BOTH libraries strip identically; araclean strips a superset (asserted as a divergence
# below), so restricting the generated alphabet to this block is what makes agreement exact.
_CORE_TASHKEEL = "ًٌٍَُِّْ"
# The alef variants both libraries fold to bare alef ا: hamza-on/under alef, madda-alef, alef-wasla.
_SHARED_ALEFS = "أإآٱ"  # أ إ آ ٱ


# --- Agreement: araclean matches an independent oracle on the shared domain ----------------------


@given(text=st.text())
def test_remove_tatweel_agrees_with_pyarabic_on_all_text(text: str) -> None:
    # Both operations are exactly "delete every tatweel (U+0640)", so they agree on *every* string,
    # not just Arabic — the strongest form of differential agreement.
    assert remove_tatweel(text) == py_strip_tatweel(text)


@pytest.mark.parametrize("text", ["محـــمد", "الــعـربـيـة", "ـtـ", "no-tatweel", ""])
def test_remove_tatweel_matches_pyarabic_on_examples(text: str) -> None:
    assert remove_tatweel(text) == py_strip_tatweel(text)


@given(text=st.text(alphabet=_BASE + _CORE_TASHKEEL))
def test_remove_tashkeel_agrees_with_pyarabic_on_the_core_block(text: str) -> None:
    # On text whose only marks are the classic U+064B-U+0652 block, araclean's full
    # dediacritization and pyarabic's strip_tashkeel remove the same code points, so outputs match.
    assert remove_tashkeel(text) == py_strip_tashkeel(text)


def test_remove_tashkeel_matches_pyarabic_on_a_vocalized_phrase() -> None:
    vocalized = "السَّلامُ عَلَيْكُمْ ورحمة الله"
    assert remove_tashkeel(vocalized) == py_strip_tashkeel(vocalized) == "السلام عليكم ورحمة الله"


@given(text=st.text(alphabet=_BASE + _SHARED_ALEFS))
def test_fold_alef_agrees_with_pyarabic_on_the_shared_alef_variants(text: str) -> None:
    # On the contemporary alef variants (أ إ آ ٱ) both libraries collapse to bare alef ا.
    assert fold_alef(text) == py_normalize_alef(text)


@given(text=st.text(alphabet=_BASE + "ة"))  # base letters + teh marbuta ة
def test_fold_teh_marbuta_agrees_with_pyarabic_on_standard_teh_marbuta(text: str) -> None:
    # araclean's default target is heh ه, which is exactly what pyarabic's normalize_teh produces.
    assert fold_teh_marbuta(text) == py_normalize_teh(text)


# --- Documented divergences: araclean deliberately differs, and the difference is pinned ----------


@pytest.mark.parametrize(
    ("mark", "mark_class"),
    [
        ("ٰ", MarkClass.DAGGER_ALEF),  # superscript (dagger) alef ٰ
        ("ٓ", MarkClass.MADDA),  # combining madda ٓ
        ("ۖ", MarkClass.QURANIC),  # a Qur'anic small-high annotation mark ۖ
    ],
)
def test_default_dediacritization_strips_marks_pyarabic_keeps(
    mark: str, mark_class: MarkClass
) -> None:
    # araclean's dediacritization is more complete than pyarabic's strip_tashkeel, which removes
    # only the contiguous U+064B-U+0652 block: the dagger alef, the combining madda and the Qur'anic
    # annotation marks are *also* vocalization and araclean strips them by default. Because removal
    # is per mark *class* (story 26), selecting just that class strips the mark too — and pyarabic
    # leaves it. The divergence is intentional (fuller coverage), so it is asserted, not glossed.
    word = "ب" + mark
    assert remove_tashkeel(word) == "ب"  # default: every mark class
    assert remove_tashkeel(word, classes={mark_class}) == "ب"  # the one class that owns this mark
    assert py_strip_tashkeel(word) == word  # pyarabic keeps it
    assert remove_tashkeel(word) != py_strip_tashkeel(word)


@pytest.mark.parametrize("alef", ["ٲ", "ٳ"])  # alef with wavy hamza above ٲ / below ٳ
def test_fold_alef_folds_wavy_hamza_alefs_pyarabic_keeps(alef: str) -> None:
    # araclean folds the wavy-hamza alefs to bare alef; pyarabic's alef set does not list them, so
    # it leaves them. araclean's alef coverage is broader by design.
    assert fold_alef(alef) == "ا"
    assert py_normalize_alef(alef) == alef
    assert fold_alef(alef) != py_normalize_alef(alef)


def test_fold_alef_keeps_alef_maqsura_unlike_pyarabic() -> None:
    # A taxonomy divergence, not a coverage one: araclean treats alef maqsura ى as its own letter
    # (FoldAlefMaqsura folds it to yeh ي, never to alef), so FoldAlef leaves it untouched. pyarabic
    # lumps ى into its alef-normalization and folds it to bare alef ا. araclean's split keeps the
    # ى→ي and the alef-variant→ا decisions independently selectable.
    assert fold_alef("ى") == "ى"  # araclean: alef folding never touches alef maqsura
    assert py_normalize_alef("ى") == "ا"  # pyarabic: folds it into alef
    assert fold_alef("ى") != py_normalize_alef("ى")


def test_presentation_form_fold_is_lossless_unlike_pyarabic_ligature() -> None:
    # The headline divergence. araclean's FoldPresentationForms is *lossless encoding repair*
    # (ADR-0004/0009): the lam-alef-hamza ligature ﻷ decomposes to lam + the matching hamza-alef
    # (لأ), keeping the hamza, and the word ligature ﷺ expands to its phrase. pyarabic's
    # normalize_ligature is a *lossy* fold: it collapses every lam-alef ligature to a bare لا
    # (discarding the hamza) and leaves the word ligature alone. The two answer different questions,
    # so neither is "wrong" — but the difference is pinned, not silent.
    assert fold_presentation_forms("ﻷ") == "لأ"  # hamza preserved
    assert py_normalize_ligature("ﻷ") == "لا"  # hamza discarded
    assert fold_presentation_forms("ﻷ") != py_normalize_ligature("ﻷ")

    assert fold_presentation_forms("ﷺ") == "صلى الله عليه وسلم"  # expanded
    assert py_normalize_ligature("ﷺ") == "ﷺ"  # left intact


@pytest.mark.parametrize(
    ("carrier", "araclean_target"),
    [("ؤ", "و"), ("ئ", "ي")],  # waw-hamza ؤ → waw و ; yeh-hamza ئ → yeh ي
)
def test_fold_hamza_neutralizes_carriers_opposite_to_pyarabic(
    carrier: str, araclean_target: str
) -> None:
    # Opposite philosophies. araclean's FoldHamza neutralizes the hamza by folding the carrier to
    # its plain letter (ؤ→و, ئ→ي), keeping the consonant skeleton. pyarabic's normalize_hamza
    # standardizes the *other* way — every hamza form becomes the standalone hamza ء. So on a hamza
    # carrier the two move in opposite directions; the divergence is asserted explicitly.
    assert fold_hamza(carrier) == araclean_target
    assert py_normalize_hamza(carrier) == "ء"
    assert fold_hamza(carrier) != py_normalize_hamza(carrier)


def test_fold_teh_marbuta_folds_goal_form_pyarabic_keeps() -> None:
    # araclean also folds the teh-marbuta *goal* form ۃ (U+06C3) to its heh target; pyarabic's
    # normalize_teh handles only the standard ة and leaves ۃ in place.
    assert fold_teh_marbuta("ۃ") == "ه"
    assert py_normalize_teh("ۃ") == "ۃ"
    assert fold_teh_marbuta("ۃ") != py_normalize_teh("ۃ")
