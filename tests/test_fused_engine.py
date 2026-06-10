"""The fused `str.translate` engine (issue 0018): a profile's compatible single-char translate
steps collapse into ONE combined table applied in a single C-level pass, with no change in output.

The engine is invisible to the `Pipeline` interface (repr/select/audit/to_dict are unchanged); the
only new surfaces are this equivalence property and the benchmark. The safety net is the existing
behavior suite, which now runs through the fused engine unchanged.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pytest_benchmark.fixture import BenchmarkFixture

from araclean import CLASSICAL, LIGHT, ML, SEARCH, SOCIAL, Pipeline, Profile, fusion

ALL_PROFILES = [LIGHT, SEARCH, ML, CLASSICAL, SOCIAL]

# A noisy mixed string touching every fusible step's domain: a presentation-form lam-alef ligature
# that decomposes (ﻷ), tatweel, a bidi mark, a Persian look-alike, a vocalized word, an alef
# variant, a teh marbuta, an alef maqsura, and Arabic-Indic digits.
MIXED = "ﻷمحـ__ـمد‏ كَتَبَ على مدرسة ١٢٣ کیف"


def _apply_in_sequence(steps: Iterable[Callable[[str], str]], text: str) -> str:
    """Apply each step one at a time — the unfused reference semantics (the contract order)."""
    for step in steps:
        text = step(text)
    return text


def test_build_plan_fuses_each_run_of_translate_steps_into_one_pass() -> None:
    # LIGHT is: NFC | [StripBidi, FoldPresentationForms, RemoveTatweel, UnifyLookalikes] | Collapse
    # | NFC. The four consecutive translate steps collapse to ONE fused pass; the contextual steps
    # (NFC, CollapseWhitespace) stay their own pass, in their original positions.
    steps = Pipeline.from_profile(LIGHT).steps
    plan = fusion.build_plan(steps)

    fused_passes = [op for op in plan if isinstance(op, fusion.TranslatePass)]
    assert len(fused_passes) == 1  # the run of four translate steps fused into a single char pass

    contextual = [type(op).__name__ for op in plan if not isinstance(op, fusion.TranslatePass)]
    assert contextual == ["NormalizeUnicode", "CollapseWhitespace", "NormalizeUnicode"]

    # The fused pass reproduces applying exactly those four translate steps in sequence.
    block = steps[1:5]
    for text in [MIXED, "", "abc"]:
        assert fused_passes[0](text) == _apply_in_sequence(block, text)


def test_build_plan_makes_one_fused_pass_per_run_preserving_order() -> None:
    # SEARCH has TWO maximal runs of translate steps (the LIGHT block, then the lossy-fold block),
    # split by the contextual CollapseWhitespace/NFC, MapPunctuation and ReduceElongation passes.
    # Fusion makes exactly one char pass per run and never reorders across a contextual boundary.
    steps = Pipeline.from_profile(SEARCH).steps
    plan = fusion.build_plan(steps)

    fused_passes = [op for op in plan if isinstance(op, fusion.TranslatePass)]
    assert len(fused_passes) == 2  # one fused char pass per consecutive translate run

    # The whole plan, run end to end, equals applying every step one at a time (order preserved).
    for text in [MIXED, "نصٌّ مُشَكَّل", "@user https://x.co 😀"]:
        assert _apply_in_sequence(plan, text) == _apply_in_sequence(steps, text)


def test_fuse_tables_collapses_a_run_into_one_equivalent_table() -> None:
    # The core guarantee: composing N translate tables yields ONE table whose single str.translate
    # reproduces applying the N tables in sequence -- including a multi-character expansion (a -> X
    # -> "YZ") and a deletion (b -> nothing). str.translate is a context-free, single-pass,
    # per-character map, so this composition is exact.
    first = {ord("a"): "X"}
    second = {ord("X"): "YZ", ord("b"): None}

    fused = fusion.fuse_tables([first, second])

    for text in ["ab", "", "abab", "Xb", "cab"]:
        sequential = text.translate(first).translate(second)
        assert text.translate(fused) == sequential


@pytest.mark.parametrize("profile", ALL_PROFILES, ids=lambda p: p.name)
@given(text=st.text())
def test_fused_pipeline_output_equals_the_unfused_composition(profile: Profile, text: str) -> None:
    # The headline equivalence: a profile's pipeline (which now executes the fused plan) returns
    # EXACTLY what applying its steps one at a time returns, for arbitrary text. Fusion changes no
    # output -- it only changes how many passes over the string it takes.
    pipe = Pipeline.from_profile(profile)
    assert pipe(text) == _apply_in_sequence(pipe.steps, text)


@pytest.mark.parametrize("profile", ALL_PROFILES, ids=lambda p: p.name)
def test_fused_pipeline_matches_unfused_on_a_realistic_corpus(profile: Profile) -> None:
    pipe = Pipeline.from_profile(profile)
    corpus = [
        MIXED,
        "السَّلامُ عَلَيْكُمْ ورحمة الله",  # vocalized MSA
        "جمييييل جدًا يا @user 😍😍 https://example.com",  # noisy social
        "<b>نص</b> &amp; المزيد ﷺ",  # html + a phrase ligature
        "هٰذا على مدرسة ١٢٣، نعم؟",  # dagger alef, maqsura, teh marbuta, digits, punctuation
        "",
    ]
    assert list(pipe.batch(corpus)) == [_apply_in_sequence(pipe.steps, t) for t in corpus]


# A representative mixed corpus (MSA, vocalized, noisy social, folds/digits/punctuation), sized so
# the per-pass cost dominates fixed overhead. SEARCH is the heaviest profile — ten single-char
# translate steps — so it is the fusion engine's clearest showcase.
_BENCH_CORPUS = [
    "ﻷمحـ__ـمد‏ كَتَبَ على مدرسة ١٢٣ کیف",
    "السَّلامُ عَلَيْكُمْ ورحمة الله وبركاته يا أصدقائي الكرام",
    "جمييييل جدًا يا @user 😍😍 https://example.com والمزيد من النصوص",
    "هٰذا على مدرسةٍ كبيرةٍ ١٢٣٤٥، نعم؟ لا بأس؛ شكراً جزيلاً",
] * 250


def test_fused_search_profile_throughput(benchmark: BenchmarkFixture) -> None:
    # The pytest-benchmark micro-benchmark (issue 0018; its numbers feed 0019). It times the fused
    # SEARCH pipeline over the representative corpus and asserts the benchmarked output still equals
    # the unfused composition — the optimization is timed AND proven correct in one place.
    pipe = Pipeline.from_profile(SEARCH)
    # `benchmark.__call__` is unannotated (returns its callable's value), so cast its result to the
    # known type to keep the strict gate clean while still asserting the timed path is correct.
    benchmarked = cast("list[str]", benchmark(lambda: [pipe(t) for t in _BENCH_CORPUS]))
    assert benchmarked == [_apply_in_sequence(pipe.steps, t) for t in _BENCH_CORPUS]


def test_fused_pipeline_runs_in_fewer_passes_and_is_faster_than_unfused() -> None:
    # The story-42 claim: char-level normalization runs as a SINGLE fused pass per run, and faster.
    # SEARCH's ten single-char translate steps collapse to TWO fused passes (one per contiguous
    # run), so the plan makes strictly fewer passes over each string than the seventeen-step unfused
    # composition (deterministic) — and is measurably faster on the corpus (min-of-N timing, the
    # most stable statistic, guards against scheduler noise; the measured margin is ~2x).
    pipe = Pipeline.from_profile(SEARCH)
    steps = pipe.steps

    plan = fusion.build_plan(steps)
    fused_passes = [op for op in plan if isinstance(op, fusion.TranslatePass)]
    assert len(fused_passes) == 2  # one fused char pass per contiguous translate run
    assert len(plan) < len(steps)  # strictly fewer passes than the unfused step count

    def time_min(run: Callable[[str], str], reps: int = 5) -> float:
        best = math.inf
        for _ in range(reps):
            start = time.perf_counter()
            for text in _BENCH_CORPUS:
                run(text)
            best = min(best, time.perf_counter() - start)
        return best

    fused = time_min(pipe)
    unfused = time_min(lambda text: _apply_in_sequence(steps, text))
    assert fused < unfused
