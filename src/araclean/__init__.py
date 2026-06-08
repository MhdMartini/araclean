"""araclean — Arabic text normalization and cleaning."""

from importlib.metadata import PackageNotFoundError, version

from araclean.api import normalize
from araclean.pipeline import Pipeline
from araclean.profiles import LIGHT, Profile
from araclean.safety import SafetyClass
from araclean.steps import (
    AlignmentNotSupportedError,
    FoldPresentationForms,
    NormalizeUnicode,
    Step,
    fold_presentation_forms,
    normalize_unicode,
)

try:
    __version__: str = version("araclean")
except PackageNotFoundError:  # pragma: no cover - source tree without install metadata
    __version__ = "0.0.0"

__all__ = [
    "LIGHT",
    "AlignmentNotSupportedError",
    "FoldPresentationForms",
    "NormalizeUnicode",
    "Pipeline",
    "Profile",
    "SafetyClass",
    "Step",
    "__version__",
    "fold_presentation_forms",
    "normalize",
    "normalize_unicode",
]
