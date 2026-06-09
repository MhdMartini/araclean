"""araclean — Arabic text normalization and cleaning."""

from importlib.metadata import PackageNotFoundError, version

from araclean.api import normalize
from araclean.pipeline import Pipeline
from araclean.profiles import LIGHT, Profile
from araclean.safety import SafetyClass
from araclean.steps import (
    AlignmentNotSupportedError,
    CollapseWhitespace,
    DigitTarget,
    FoldAlef,
    FoldAlefMaqsura,
    FoldHamza,
    FoldPresentationForms,
    FoldTehMarbuta,
    MapDigits,
    MapPunctuation,
    MarkClass,
    NormalizeUnicode,
    ReduceElongation,
    RemoveTashkeel,
    RemoveTatweel,
    Step,
    StripBidi,
    TehMarbutaTarget,
    UnifyLookalikes,
    collapse_whitespace,
    fold_alef,
    fold_alef_maqsura,
    fold_hamza,
    fold_presentation_forms,
    fold_teh_marbuta,
    map_digits,
    map_punctuation,
    normalize_unicode,
    reduce_elongation,
    remove_tashkeel,
    remove_tatweel,
    strip_bidi,
    unify_lookalikes,
)

try:
    __version__: str = version("araclean")
except PackageNotFoundError:  # pragma: no cover - source tree without install metadata
    __version__ = "0.0.0"

__all__ = [
    "LIGHT",
    "AlignmentNotSupportedError",
    "CollapseWhitespace",
    "DigitTarget",
    "FoldAlef",
    "FoldAlefMaqsura",
    "FoldHamza",
    "FoldPresentationForms",
    "FoldTehMarbuta",
    "MapDigits",
    "MapPunctuation",
    "MarkClass",
    "NormalizeUnicode",
    "Pipeline",
    "Profile",
    "ReduceElongation",
    "RemoveTashkeel",
    "RemoveTatweel",
    "SafetyClass",
    "Step",
    "StripBidi",
    "TehMarbutaTarget",
    "UnifyLookalikes",
    "__version__",
    "collapse_whitespace",
    "fold_alef",
    "fold_alef_maqsura",
    "fold_hamza",
    "fold_presentation_forms",
    "fold_teh_marbuta",
    "map_digits",
    "map_punctuation",
    "normalize",
    "normalize_unicode",
    "reduce_elongation",
    "remove_tashkeel",
    "remove_tatweel",
    "strip_bidi",
    "unify_lookalikes",
]
