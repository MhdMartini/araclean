"""araclean — Arabic text normalization and cleaning."""

from importlib.metadata import PackageNotFoundError, version

from araclean.api import normalize
from araclean.pipeline import Pipeline
from araclean.profiles import LIGHT, Profile
from araclean.safety import SafetyClass
from araclean.steps import (
    AlignmentNotSupportedError,
    CollapseWhitespace,
    FoldAlef,
    FoldAlefMaqsura,
    FoldHamza,
    FoldPresentationForms,
    FoldTehMarbuta,
    MarkClass,
    NormalizeUnicode,
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
    normalize_unicode,
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
    "FoldAlef",
    "FoldAlefMaqsura",
    "FoldHamza",
    "FoldPresentationForms",
    "FoldTehMarbuta",
    "MarkClass",
    "NormalizeUnicode",
    "Pipeline",
    "Profile",
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
    "normalize",
    "normalize_unicode",
    "remove_tashkeel",
    "remove_tatweel",
    "strip_bidi",
    "unify_lookalikes",
]
