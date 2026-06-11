"""Throughput benchmarks for the normalization engine (issue 0019, ADR-0006).

Run over time by asv so a regression in throughput is detectable across commits. Each class is an
asv benchmark: ``setup`` (excluded from timing) builds the pipeline and corpus once, and every
``time_*`` method is timed. Keep imports to ``araclean`` only — asv imports this module inside an
isolated env that has nothing else installed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from araclean import (
    CLASSICAL,
    LIGHT,
    ML,
    SEARCH,
    SOCIAL,
    FoldAlef,
    FoldAlefMaqsura,
    FoldHamza,
    FoldPresentationForms,
    FoldTehMarbuta,
    MapDigits,
    Pipeline,
    RemoveTashkeel,
    RemoveTatweel,
    Step,
    fusion,
)

# A representative mixed corpus (MSA, vocalized/Qur'anic, noisy social, folds/digits), sized so the
# per-string cost dominates fixed overhead.
_CORPUS = [
    "ﻷمحـ__ـمد‏ كَتَبَ على مدرسة ١٢٣ کیف",
    "السَّلامُ عَلَيْكُمْ ورحمة الله وبركاته يا أصدقائي الكرام",
    "جمييييل جدًا يا @user 😍😍 https://example.com والمزيد من النصوص",
    "هٰذا على مدرسةٍ كبيرةٍ ١٢٣٤٥، نعم؟ لا بأس؛ شكراً جزيلاً",
] * 200

_PROFILES = {
    "light": LIGHT,
    "search": SEARCH,
    "ml": ML,
    "social": SOCIAL,
    "classical": CLASSICAL,
}


class NormalizeProfiles:
    """Per-profile throughput: how fast each named profile normalizes the mixed corpus."""

    params: ClassVar[list[str]] = list(_PROFILES)
    param_names: ClassVar[list[str]] = ["profile"]

    pipe: Pipeline
    corpus: list[str]

    def setup(self, profile: str) -> None:
        self.pipe = Pipeline.from_profile(_PROFILES[profile])
        self.corpus = _CORPUS

    def time_normalize_each(self, profile: str) -> None:
        for text in self.corpus:
            self.pipe(text)

    def time_normalize_batch(self, profile: str) -> None:
        for _ in self.pipe.batch(self.corpus):
            pass


class FusedCharEngine:
    """The fused char-level engine (issue 0018): the whole run of single-char folds, one pass."""

    fused: Callable[[str], str]
    corpus: list[str]

    def setup(self) -> None:
        steps: list[Step] = [
            RemoveTatweel(),
            FoldPresentationForms(),
            RemoveTashkeel(),
            FoldAlef(),
            FoldHamza(),
            FoldTehMarbuta(),
            FoldAlefMaqsura(),
            MapDigits(),
        ]
        passes = [op for op in fusion.build_plan(steps) if isinstance(op, fusion.TranslatePass)]
        self.fused = passes[0]
        self.corpus = _CORPUS

    def time_fused_char_pass(self) -> None:
        for text in self.corpus:
            self.fused(text)
