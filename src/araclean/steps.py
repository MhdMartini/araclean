"""The `Step` family — pure `str -> str` transforms, the extension seam of the library.

A `Step` is the minimal contract (a `safety` class + `__call__`), so a user can drop in their
own `str -> str` callable (story 47). Each built-in step's behavior is also exported as a free
function for standalone use (Layer 1, ADR-0003).

Built-in steps additionally serialize themselves (`to_dict`/`from_dict`) and register under a
canonical name, so a `Pipeline` can be persisted and rehydrated. The serialization contract is
fixed here because every later step must follow it.
"""

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Protocol, Self, TypedDict, runtime_checkable

from araclean import chars, registry
from araclean.safety import SafetyClass

type UnicodeForm = Literal["NFC", "NFD", "NFKC", "NFKD"]


class StepDict(TypedDict):
    """The serialized form of one `Step`: its registry name and its constructor config."""

    name: str
    config: dict[str, Any]


@runtime_checkable
class Step(Protocol):
    """A single normalization transform: a `safety` class plus a pure `str -> str` call.

    The reserved, optional alignment hook ``apply_aligned(s) -> (str, OffsetMap)`` (ADR-0005)
    is intentionally absent from this contract; a `Pipeline` detects it when present and raises
    a clear error otherwise. Steps precompute any table/regex at construction so `__call__` does
    no setup and no validation (ADR-0006).

    A step satisfies the contract by exposing a `safety` attribute — the natural idiom is a
    class-level ``safety = SafetyClass.…`` assignment (what built-in and custom steps both use).
    """

    safety: SafetyClass

    def __call__(self, s: str, /) -> str: ...


@runtime_checkable
class SerializableStep(Protocol):
    """A `Step` that can serialize itself to a `StepDict` (built-in steps do; custom ones may)."""

    def to_dict(self) -> StepDict: ...


class AlignmentNotSupportedError(NotImplementedError):
    """Raised when offsets/alignment are requested through a step that lacks `apply_aligned`.

    Offset tracking is reserved but not implemented in v1 (ADR-0005). Subclasses
    `NotImplementedError` so callers probing for the capability can fall back.
    """


@runtime_checkable
class SupportsAlignment(Protocol):
    """The reserved, optional capability a `Step` opts into to support offset tracking.

    Not implemented by any v1 step. The placeholder second element stands in for the future
    ``OffsetMap`` (ADR-0005).
    """

    def apply_aligned(self, s: str, /) -> tuple[str, object]: ...


def normalize_unicode(s: str, /, form: UnicodeForm = "NFC") -> str:
    """Apply a Unicode normalization form (default NFC) — lossless encoding repair."""
    return unicodedata.normalize(form, s)


@dataclass(frozen=True, slots=True)
class NormalizeUnicode:
    """Compose to a Unicode normalization form (default NFC) — lossless encoding repair.

    English: *Unicode normalization*. Composing to NFC is the canonical first step so visually
    identical text compares equal regardless of how it was encoded.
    """

    form: UnicodeForm = "NFC"
    # Unannotated, so it is a plain class attribute (not a dataclass field / __init__ arg) and
    # matches the instance-variable `Step.safety` protocol member, exactly like a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "NormalizeUnicode"

    def __call__(self, s: str, /) -> str:
        return normalize_unicode(s, self.form)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"form": self.form}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(NormalizeUnicode.name, NormalizeUnicode.from_dict)


def fold_presentation_forms(s: str, /) -> str:
    """Fold Arabic presentation-form glyphs to base letters — lossless encoding repair."""
    return s.translate(chars.PRESENTATION_FORMS)


@dataclass(frozen=True, slots=True)
class FoldPresentationForms:
    """Fold Arabic presentation forms back to base letters — lossless encoding repair.

    English: *presentation-form folding*. OCR, legacy encodings and copy-paste leave letters as
    their contextual presentation glyphs (Forms-A/-B); folding them to the base letters lets such
    text match normally. The lam-alef ligatures decompose to lam + their *matching* alef variant
    (ﻷ → لأ), and combining marks keep their order (a per-character fold, not whole-string NFKC).
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "FoldPresentationForms"

    def __call__(self, s: str, /) -> str:
        return fold_presentation_forms(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(FoldPresentationForms.name, FoldPresentationForms.from_dict)
