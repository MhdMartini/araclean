"""Cross-tool benchmark — araclean's fused engine vs pyarabic (issue 0019, story 46, ADR-0006).

ADR-0006's central performance claim is that fusing a profile's single-char `str.translate` steps
into one C-level pass beats a tool that applies each fold as its own scan. pyarabic is exactly that
shape: its char-level normalization runs a separate full-string pass per operation (and
`strip_tashkeel` is itself a `str.replace` per mark). This module pins the claim two ways:

  * a deterministic, min-of-N timing assertion that araclean's *single fused pass* is faster than
    pyarabic's *multi-pass char loop* on the same char-level work, and
  * `pytest-benchmark` micro-benchmarks (one per tool, same group) that emit comparable throughput
    numbers when the suite runs in CI — the published "vs pyarabic" figures.

pyarabic is a dev-only oracle (ADR-0002), so the module skips wherever it is absent. The heavier
oracle CAMeL Tools is opt-in only (torch + GPU runtime, downgrades typer); see
``benchmarks/README.md``.
"""

from __future__ import annotations

import gc
import math
import time
from collections.abc import Callable
from typing import cast

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from araclean import (
    FoldAlef,
    FoldAlefMaqsura,
    FoldHamza,
    FoldPresentationForms,
    FoldTehMarbuta,
    MapDigits,
    RemoveTashkeel,
    RemoveTatweel,
    Step,
    fusion,
)

araby = pytest.importorskip("pyarabic.araby")


def _oracle(name: str) -> Callable[[str], str]:
    fn: Callable[[str], str] = getattr(araby, name)
    return fn


_py_strip_tatweel = _oracle("strip_tatweel")
_py_strip_tashkeel = _oracle("strip_tashkeel")
_py_normalize_alef = _oracle("normalize_alef")
_py_normalize_teh = _oracle("normalize_teh")
_py_normalize_hamza = _oracle("normalize_hamza")
_py_normalize_ligature = _oracle("normalize_ligature")


# A representative mixed corpus (MSA news, vocalized/Qur'anic, noisy social, folds/digits), repeated
# so per-pass cost dominates fixed call overhead — the regime where fusion's "one scan, not N" wins.
_CORPUS = [
    "ﻷمحـ__ـمد‏ كَتَبَ على مدرسة ١٢٣ کیف",
    "السَّلامُ عَلَيْكُمْ ورحمة الله وبركاته يا أصدقائي الكرام",
    "جمييييل جدًا يا @user 😍😍 https://example.com والمزيد من النصوص",
    "هٰذا على مدرسةٍ كبيرةٍ ١٢٣٤٥، نعم؟ لا بأس؛ شكراً جزيلاً",
] * 250

# araclean's char-level normalization: every fusible single-char `str.translate` fold. The engine
# (issue 0018) composes the whole run into ONE combined table applied in a single pass.
_CHAR_STEPS: list[Step] = [
    RemoveTatweel(),
    FoldPresentationForms(),
    RemoveTashkeel(),
    FoldAlef(),
    FoldHamza(),
    FoldTehMarbuta(),
    FoldAlefMaqsura(),
    MapDigits(),
]


def _araclean_fused_char_pass() -> Callable[[str], str]:
    """The single fused `str.translate` pass araclean compiles the char-level folds into."""
    plan = fusion.build_plan(_CHAR_STEPS)
    passes = [op for op in plan if isinstance(op, fusion.TranslatePass)]
    assert len(passes) == 1  # the whole char-level run fuses to exactly one pass
    return passes[0]


def _pyarabic_char_normalization(s: str) -> str:
    """The equivalent char-level normalization in pyarabic — one full-string pass per operation."""
    s = _py_strip_tatweel(s)
    s = _py_strip_tashkeel(s)
    s = _py_normalize_alef(s)
    s = _py_normalize_teh(s)
    s = _py_normalize_hamza(s)
    s = _py_normalize_ligature(s)
    return s


def _corpus_pass(run: Callable[[str], str]) -> None:
    for text in _CORPUS:
        run(text)


def _min_of_interleaved(runs: dict[str, Callable[[str], str]], reps: int = 15) -> dict[str, float]:
    """Min-of-N wall-clock per run, measured INTERLEAVED with GC paused.

    Two precautions make the strict `<` comparison stable in CI: timing both runs inside the same
    loop iteration means a transient slowdown hits whichever is executing, not one run
    systematically (an alternating cold-start would otherwise penalize whichever is timed first);
    and pausing the cycle collector removes the single largest source of micro-benchmark jitter.
    Min-of-N then reports each run's least-noisy observation.
    """
    for run in runs.values():  # warm up caches / interning / import paths before timing
        _corpus_pass(run)
    best = dict.fromkeys(runs, math.inf)
    gc.disable()
    try:
        for _ in range(reps):
            for name, run in runs.items():
                start = time.perf_counter()
                _corpus_pass(run)
                best[name] = min(best[name], time.perf_counter() - start)
    finally:
        gc.enable()
    return best


def test_fused_char_pass_faster_than_pyarabic_multipass() -> None:
    # ADR-0006's headline: araclean does its char-level normalization in ONE fused C-level pass,
    # where pyarabic makes a separate full-string pass per operation. On a representative corpus the
    # single pass wins decisively (the pytest-benchmark table records the margin at ~1.7x); the
    # interleaved, GC-paused min-of-N here keeps the strict comparison robust against noise.
    best = _min_of_interleaved(
        {"araclean": _araclean_fused_char_pass(), "pyarabic": _pyarabic_char_normalization}
    )
    assert best["araclean"] < best["pyarabic"]


def test_benchmark_araclean_fused_char_pass(benchmark: BenchmarkFixture) -> None:
    # Emits araclean's throughput row. `benchmark.__call__` is unannotated, so cast its result to
    # the known type to keep the strict gate clean while still timing the real path.
    benchmark.group = "char-normalization"
    fused = _araclean_fused_char_pass()
    result = cast("list[str]", benchmark(lambda: [fused(t) for t in _CORPUS]))
    assert len(result) == len(_CORPUS)


def test_benchmark_pyarabic_char_normalization(benchmark: BenchmarkFixture) -> None:
    # Emits pyarabic's throughput row in the same group, so the CI benchmark table reports the two
    # side by side — the published "vs pyarabic" comparison (story 46).
    benchmark.group = "char-normalization"

    def run() -> list[str]:
        return [_pyarabic_char_normalization(t) for t in _CORPUS]

    result = cast("list[str]", benchmark(run))
    assert len(result) == len(_CORPUS)
