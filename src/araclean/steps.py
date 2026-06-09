"""The `Step` family — pure `str -> str` transforms, the extension seam of the library.

A `Step` is the minimal contract (a `safety` class + `__call__`), so a user can drop in their
own `str -> str` callable (story 47). Each built-in step's behavior is also exported as a free
function for standalone use (Layer 1, ADR-0003).

Built-in steps additionally serialize themselves (`to_dict`/`from_dict`) and register under a
canonical name, so a `Pipeline` can be persisted and rehydrated. The serialization contract is
fixed here because every later step must follow it.
"""

import re
import unicodedata
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
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


def remove_tatweel(s: str, /) -> str:
    """Strip tatweel (the elongation / kashida character) — lossless encoding repair."""
    return s.translate(chars.REMOVE_TATWEEL)


@dataclass(frozen=True, slots=True)
class RemoveTatweel:
    """Strip tatweel ـ (U+0640) — lossless encoding repair.

    English: *tatweel / kashida removal*. Tatweel only stretches a word visually for
    justification; deleting it collapses elongated spellings (محـــمد → محمد) without touching
    any letter or vocalization mark.
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "RemoveTatweel"

    def __call__(self, s: str, /) -> str:
        return remove_tatweel(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(RemoveTatweel.name, RemoveTatweel.from_dict)


def strip_bidi(s: str, /) -> str:
    """Remove bidi controls, zero-width characters and the BOM — lossless encoding repair."""
    return s.translate(chars.STRIP_BIDI)


@dataclass(frozen=True, slots=True)
class StripBidi:
    """Remove bidi controls, zero-width characters and the BOM — lossless encoding repair.

    English: *bidi/zero-width stripping*. RLM/LRM/ALM and the embedding/isolate controls, the
    zero-width joiner/non-joiner/space/word-joiner, and the BOM are invisible: they carry no
    Arabic letter content yet break equality and tokenization, so they are deleted outright.
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "StripBidi"

    def __call__(self, s: str, /) -> str:
        return strip_bidi(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(StripBidi.name, StripBidi.from_dict)


def unify_lookalikes(s: str, /) -> str:
    """Fold script look-alike letters to their Arabic form — lossless encoding repair."""
    return s.translate(chars.UNIFY_LOOKALIKES)


@dataclass(frozen=True, slots=True)
class UnifyLookalikes:
    """Unify look-alike kaf/yeh/heh to Arabic letters — lossless encoding repair.

    English: *look-alike unification*. Under the Arabic-language assumption, letters from other
    Arabic-script orthographies (Persian keheh ک, Farsi yeh ی, the heh-family forms) are encoding
    artifacts and fold to the Arabic letter (ک→ك, ی→ي, ھ/ہ/ە→ه). One accepted residual: a Persian
    yeh used word-finally merges على→علي (U+06CC is indistinguishable from alef maqsura).
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "UnifyLookalikes"

    def __call__(self, s: str, /) -> str:
        return unify_lookalikes(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(UnifyLookalikes.name, UnifyLookalikes.from_dict)


def _collapse_whitespace_run(match: re.Match[str], /) -> str:
    # A run that crossed a line boundary collapses to a single newline; a purely horizontal run
    # collapses to a single ASCII space. Preserving the break is what keeps the default lossless
    # (ADR-0010).
    run = match.group()
    return "\n" if any(ch in chars.LINE_BREAKS for ch in run) else " "


def collapse_whitespace(s: str, /, *, collapse_lines: bool = False) -> str:
    """Collapse whitespace runs, keeping line breaks by default — lossless encoding repair.

    A horizontal run becomes one ASCII space; a run containing a line break becomes one ``"\\n"``.
    Pass ``collapse_lines=True`` to flatten every run (line breaks included) to a single space.
    """
    if collapse_lines:
        return chars.WHITESPACE_RUN.sub(" ", s)
    return chars.WHITESPACE_RUN.sub(_collapse_whitespace_run, s)


@dataclass(frozen=True, slots=True)
class CollapseWhitespace:
    """Collapse whitespace runs — keeping line breaks by default — lossless encoding repair.

    English: *whitespace collapse*. Each whitespace run collapses to a single character, so equality
    and tokenization stop depending on how many (or which) spaces a source used: a horizontal run
    becomes one ASCII space, and a run containing a line break becomes a single ``"\\n"``. Line
    structure is preserved by default — flattening it to spaces is lossy, not lossless, so it is
    opt-in via ``collapse_lines=True`` (the recall-oriented behavior SEARCH wants). See ADR-0010.
    Runs collapse but are not trimmed, so the step stays a fixed point.
    """

    collapse_lines: bool = False
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "CollapseWhitespace"

    def __call__(self, s: str, /) -> str:
        return collapse_whitespace(s, collapse_lines=self.collapse_lines)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"collapse_lines": self.collapse_lines}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(CollapseWhitespace.name, CollapseWhitespace.from_dict)


class MarkClass(StrEnum):
    """A class of tashkeel marks `RemoveTashkeel` can remove independently (story 26).

    English: *diacritic class*. The vocalization-mark taxonomy (GLOSSARY: Tashkeel) split into the
    units a caller selects between. `SUKUN` is not a member — it is the vowelless mark (the
    *absence* of a vowel, not a haraka), removed together with `HARAKAT` for convenience and not
    selectable on its own (GLOSSARY: Harakat).
    """

    HARAKAT = "harakat"  # short vowels: fatha/damma/kasra and their typographic variants
    TANWEEN = "tanween"  # nunation: fathatan/dammatan/kasratan and their variants
    SHADDA = "shadda"  # gemination / consonant-doubling mark
    MADDA = "madda"  # the orthographic combining madda U+0653 (not the letter آ)
    DAGGER_ALEF = "dagger_alef"  # the standard superscript alef U+0670
    QURANIC = "quranic"  # Qur'anic recitation/annotation signs + extended marks (catch-all)


ALL_MARK_CLASSES: frozenset[MarkClass] = frozenset(MarkClass)

# Bridge the public class enum to its internal code-point seam in `chars`. SUKUN is handled apart
# (it always rides with HARAKAT, never on its own), so it is not in any class's base set.
_MARK_CLASS_CODE_POINTS: dict[MarkClass, frozenset[int]] = {
    MarkClass.HARAKAT: chars.HARAKAT,
    MarkClass.TANWEEN: chars.TANWEEN,
    MarkClass.SHADDA: frozenset((chars.SHADDA,)),
    MarkClass.MADDA: frozenset((chars.MADDA,)),
    MarkClass.DAGGER_ALEF: frozenset((chars.DAGGER_ALEF,)),
    MarkClass.QURANIC: chars.QURANIC,
}


def _tashkeel_removal_table(classes: Collection[MarkClass]) -> dict[int, None]:
    """Build the `str.translate` deletion table for the selected mark classes (a set of code points
    each mapped to ``None`` = delete). Sukun joins the set only when HARAKAT is selected — it rides
    with the harakat for convenience and never on its own (GLOSSARY: Harakat)."""
    code_points: set[int] = set()
    for mark_class in classes:
        code_points |= _MARK_CLASS_CODE_POINTS[mark_class]
    if MarkClass.HARAKAT in classes:
        code_points |= chars.SUKUN
    return dict.fromkeys(code_points)


def remove_tashkeel(s: str, /, *, classes: Collection[MarkClass] | None = None) -> str:
    """Remove the selected tashkeel mark classes (default: all) — lossy linguistic folding.

    English: *dediacritization*. Deletes only the vocalization marks of the chosen `MarkClass`es,
    never their carrier letters. ``classes=None`` removes every class. Sukun rides with `HARAKAT`.
    """
    selected = ALL_MARK_CLASSES if classes is None else classes
    return s.translate(_tashkeel_removal_table(selected))


@dataclass(frozen=True, slots=True)
class RemoveTashkeel:
    """Remove tashkeel — diacritics / vocalization marks — by class — lossy linguistic folding.

    English: *dediacritization*. The first lossy step and araclean's headline differentiator: which
    mark classes to remove is chosen *independently* (story 26), so a caller can strip harakat while
    keeping a meaningful shadda, drop only tanween, etc. Removal deletes the marks alone and never a
    carrier letter (a tanween over an alef goes; the alef stays). `safety` is `LINGUISTIC_FOLDING`,
    so it never runs under `LIGHT`: it is opt-in via a lossy profile or an explicit step (ADR-0004).

    `classes` defaults to every `MarkClass`. Sukun rides with `HARAKAT` (it is the *absence* of a
    vowel, not a haraka, but stripping the vowels while leaving a bare sukun is never wanted). The
    orthographic combining madda U+0653 is removed with `MADDA`; the alef-with-madda letter آ U+0622
    is letter folding (issue 0007), kept here.
    """

    classes: Collection[MarkClass] = ALL_MARK_CLASSES
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `classes`.
    _table: dict[int, None] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "RemoveTashkeel"

    def __post_init__(self) -> None:
        # Normalize any selection (set/list/...) to a frozenset so equality and serialization are
        # order-insensitive and stable, then precompute the deletion table once.
        classes = frozenset(self.classes)
        object.__setattr__(self, "classes", classes)
        object.__setattr__(self, "_table", _tashkeel_removal_table(classes))

    def __call__(self, s: str, /) -> str:
        return s.translate(self._table)

    def to_dict(self) -> StepDict:
        return {
            "name": self.name,
            "config": {"classes": sorted(mark_class.value for mark_class in self.classes)},
        }

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "classes" in kwargs:
            kwargs["classes"] = frozenset(MarkClass(value) for value in kwargs["classes"])
        return cls(**kwargs)


registry.register(RemoveTashkeel.name, RemoveTashkeel.from_dict)
