"""araclean — Arabic text normalization and cleaning."""

from importlib.metadata import PackageNotFoundError, version

from araclean.api import normalize
from araclean.pipeline import Pipeline
from araclean.profiles import LIGHT, Profile
from araclean.safety import SafetyClass
from araclean.steps import (
    AlignmentNotSupportedError,
    CollapseWhitespace,
    FoldPresentationForms,
    NormalizeUnicode,
    RemoveTatweel,
    Step,
    StripBidi,
    UnifyLookalikes,
    collapse_whitespace,
    fold_presentation_forms,
    normalize_unicode,
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
    "FoldPresentationForms",
    "NormalizeUnicode",
    "Pipeline",
    "Profile",
    "RemoveTatweel",
    "SafetyClass",
    "Step",
    "StripBidi",
    "UnifyLookalikes",
    "__version__",
    "collapse_whitespace",
    "fold_presentation_forms",
    "normalize",
    "normalize_unicode",
    "remove_tatweel",
    "strip_bidi",
    "unify_lookalikes",
]
