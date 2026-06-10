"""The `Step` family — pure `str -> str` transforms, the extension seam of the library.

A `Step` is the minimal contract (a `safety` class + `__call__`), so a user can drop in their
own `str -> str` callable (story 47). Each built-in step's behavior is also exported as a free
function for standalone use (Layer 1, ADR-0003).

Built-in steps additionally serialize themselves (`to_dict`/`from_dict`) and register under a
canonical name, so a `Pipeline` can be persisted and rehydrated. The serialization contract is
fixed here because every later step must follow it.
"""

import html
import re
import unicodedata
from collections.abc import Callable, Collection, Mapping
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

    A step satisfies the contract by exposing a readable `safety` attribute — the natural idiom is
    a class-level ``safety = SafetyClass.…`` assignment (what built-in and custom steps both use).
    It is a *read-only* member: a step's safety class is an intrinsic trait, never reassigned, so a
    class variable, a frozen field (when the class varies it by config, like `HandleEmoji`), or a
    property all satisfy it.
    """

    @property
    def safety(self) -> SafetyClass: ...

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


def fold_alef(s: str, /) -> str:
    """Fold every alef-variant letter to bare alef — lossy linguistic folding."""
    return s.translate(chars.FOLD_ALEF)


@dataclass(frozen=True, slots=True)
class FoldAlef:
    """Fold the alef variants أ إ آ ٱ to bare alef ا — lossy linguistic folding.

    English: *alef folding*. The hamza-/madda-bearing alef letters, alef-wasla, and the wavy-hamza
    alefs collapse to the plain alef (أ/إ/آ/ٱ/ٲ/ٳ → ا), so spelling variation in how an initial alef
    was written stops splitting otherwise-identical words. It discards a real orthographic
    distinction, so `safety` is `LINGUISTIC_FOLDING`: opt-in via a lossy profile or an explicit
    step, never under `LIGHT`. (Historical/manuscript alefs that are not contemporary Arabic — e.g.
    the high-hamza alef U+0675, the Extended-B annotation alefs — are deliberately left alone.)
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "FoldAlef"

    def __call__(self, s: str, /) -> str:
        return fold_alef(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(FoldAlef.name, FoldAlef.from_dict)


def fold_alef_maqsura(s: str, /) -> str:
    """Fold alef maqsura to yeh — lossy linguistic folding."""
    return s.translate(chars.FOLD_ALEF_MAQSURA)


@dataclass(frozen=True, slots=True)
class FoldAlefMaqsura:
    """Fold alef maqsura ى to yeh ي — lossy linguistic folding.

    English: *alef-maqsura folding*. The dotless final ى (a long-alef sound) folds to yeh ي so the
    two spellings stop splitting a word. This merges على and علي, a genuine distinction, so the fold
    is `LINGUISTIC_FOLDING` and never runs under `LIGHT`: it is opt-in for recall (SEARCH).
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "FoldAlefMaqsura"

    def __call__(self, s: str, /) -> str:
        return fold_alef_maqsura(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(FoldAlefMaqsura.name, FoldAlefMaqsura.from_dict)


def _hamza_fold_table(*, drop_standalone_hamza: bool) -> dict[int, str | None]:
    """Build the `str.translate` table for `FoldHamza`: fold the waw/yeh carriers and delete the
    combining hamza marks always; delete the standalone hamza letters (ء and the high hamza ٴ) only
    in the heavy mode."""
    table: dict[int, str | None] = dict(chars.FOLD_HAMZA_CARRIERS)
    table.update(dict.fromkeys(chars.COMBINING_HAMZA))
    if drop_standalone_hamza:
        table[chars.STANDALONE_HAMZA] = None
        table[chars.HIGH_HAMZA] = None
    return table


def fold_hamza(s: str, /, *, drop_standalone_hamza: bool = False) -> str:
    """Fold hamza off the waw/yeh carriers; optionally drop the standalone ء — lossy folding."""
    return s.translate(_hamza_fold_table(drop_standalone_hamza=drop_standalone_hamza))


@dataclass(frozen=True, slots=True)
class FoldHamza:
    """Fold hamza off its carriers ؤ→و, ئ→ي — separate and configurably aggressive — lossy folding.

    English: *hamza folding*. A toggle kept separate from `FoldAlef` so hamza can be neutralized on
    the waw/yeh carriers (ؤ→و, ئ→ي) without folding alef. Folding *lightly* (the default) folds the
    carriers and deletes the combining hamza marks U+0654/U+0655 (hamza seated on a carrier — the
    letter content issue 0006 routes here, not to `RemoveTashkeel`). Folding *heavily*
    (``drop_standalone_hamza=True``) also drops the standalone hamza ء U+0621 and the high hamza
    ٴ U+0674. The precomposed alef-hamza letters أ/إ are alef variants, left to `FoldAlef`.
    `safety` is `LINGUISTIC_FOLDING`.
    """

    drop_standalone_hamza: bool = False
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `drop_standalone_hamza`.
    _table: dict[int, str | None] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "FoldHamza"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_table", _hamza_fold_table(drop_standalone_hamza=self.drop_standalone_hamza)
        )

    def __call__(self, s: str, /) -> str:
        return s.translate(self._table)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"drop_standalone_hamza": self.drop_standalone_hamza}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(FoldHamza.name, FoldHamza.from_dict)


class TehMarbutaTarget(StrEnum):
    """What `FoldTehMarbuta` rewrites the teh marbuta ة to (story 29).

    English: *teh-marbuta target*. `HEH` (the common search fold, default) and `TEH` (its underlying
    value) are the standard targets; `KEEP` leaves ة in place so a profile can pin "do not fold".
    """

    HEH = "heh"  # ة -> heh ه (default)
    TEH = "teh"  # ة -> teh ت
    KEEP = "keep"  # leave ة untouched (the no-op target)


_TEH_MARBUTA_TARGET_CODE_POINT: dict[TehMarbutaTarget, int | None] = {
    TehMarbutaTarget.HEH: chars.HEH,
    TehMarbutaTarget.TEH: chars.TEH,
    TehMarbutaTarget.KEEP: None,
}


def _teh_marbuta_table(target: TehMarbutaTarget) -> dict[int, str]:
    """Build the `str.translate` table mapping every teh-marbuta form to the chosen target (an empty
    table — identity — for ``KEEP``)."""
    code_point = _TEH_MARBUTA_TARGET_CODE_POINT[target]
    if code_point is None:
        return {}
    return {source: chr(code_point) for source in chars.TEH_MARBUTA}


def fold_teh_marbuta(s: str, /, *, target: TehMarbutaTarget = TehMarbutaTarget.HEH) -> str:
    """Fold teh marbuta ة to a target (heh by default; `keep` is a no-op) — lossy folding."""
    return s.translate(_teh_marbuta_table(target))


@dataclass(frozen=True, slots=True)
class FoldTehMarbuta:
    """Fold teh marbuta ة to a configurable target (heh by default) — lossy linguistic folding.

    English: *teh-marbuta folding*. The word-final "tied taa" ة (and its goal form ۃ) folds to
    `TehMarbutaTarget.HEH` ه (the common search fold, default), `TEH` ت (its underlying value), or
    is left in place with `KEEP`. ة marks a real grammatical ending, so the fold discards
    information: `safety` is `LINGUISTIC_FOLDING`, never run under `LIGHT`.
    """

    target: TehMarbutaTarget = TehMarbutaTarget.HEH
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `target`.
    _table: dict[int, str] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "FoldTehMarbuta"

    def __post_init__(self) -> None:
        # Coerce a plain string ("heh") to the enum so equality, serialization and the table are
        # stable regardless of how the target was passed, then precompute the table once.
        target = TehMarbutaTarget(self.target)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "_table", _teh_marbuta_table(target))

    def __call__(self, s: str, /) -> str:
        return s.translate(self._table)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"target": self.target.value}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "target" in kwargs:
            kwargs["target"] = TehMarbutaTarget(kwargs["target"])
        return cls(**kwargs)


registry.register(FoldTehMarbuta.name, FoldTehMarbuta.from_dict)


class DigitTarget(StrEnum):
    """Which digit system `MapDigits` converts every digit to (story 31).

    English: *digit target*. `ASCII` (default) makes numbers parse and match consistently; the two
    Arabic systems are `ARABIC_INDIC` (Eastern ٠-٩) and `EXTENDED_ARABIC_INDIC` (Persian/Urdu ۰-۹).
    """

    ASCII = "ascii"  # 0-9 (default)
    ARABIC_INDIC = "arabic_indic"  # ٠-٩
    EXTENDED_ARABIC_INDIC = "extended_arabic_indic"  # ۰-۹ (Persian/Urdu)


_DIGIT_TARGET_ZERO: dict[DigitTarget, int] = {
    DigitTarget.ASCII: chars.ASCII_DIGIT_ZERO,
    DigitTarget.ARABIC_INDIC: chars.ARABIC_INDIC_DIGIT_ZERO,
    DigitTarget.EXTENDED_ARABIC_INDIC: chars.EXTENDED_ARABIC_INDIC_DIGIT_ZERO,
}


def _digit_table(target: DigitTarget) -> dict[int, str]:
    """Build the `str.translate` table mapping every non-target digit system to the target, by
    numeric value (the digit in position d of one system -> position d of the target system)."""
    target_zero = _DIGIT_TARGET_ZERO[target]
    table: dict[int, str] = {}
    for zero in chars.DIGIT_ZEROS:
        if zero == target_zero:
            continue  # the target system is already in the target — leave it untouched
        for offset in range(10):
            table[zero + offset] = chr(target_zero + offset)
    return table


def map_digits(s: str, /, *, target: DigitTarget = DigitTarget.ASCII) -> str:
    """Convert digits among Arabic-Indic / Extended / ASCII to a target (ASCII default) — lossy."""
    return s.translate(_digit_table(target))


@dataclass(frozen=True, slots=True)
class MapDigits:
    """Convert digits among Arabic-Indic / Extended / ASCII to a target — lossy linguistic folding.

    English: *digit mapping*. Every digit — Arabic-Indic ٠-٩, Extended (Persian/Urdu) ۰-۹, or ASCII
    0-9 — is rewritten to the chosen `DigitTarget` by numeric value, so numbers parse and match
    consistently regardless of how they were typed (story 31). The default target is `ASCII`. The
    map erases which script a digit was written in, so `safety` is `LINGUISTIC_FOLDING`: opt-in via
    a lossy profile or an explicit step, never under `LIGHT`.
    """

    target: DigitTarget = DigitTarget.ASCII
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `target`.
    _table: dict[int, str] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "MapDigits"

    def __post_init__(self) -> None:
        # Coerce a plain string ("ascii") to the enum so equality, serialization and the table are
        # stable regardless of how the target was passed, then precompute the table once.
        target = DigitTarget(self.target)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "_table", _digit_table(target))

    def __call__(self, s: str, /) -> str:
        return s.translate(self._table)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"target": self.target.value}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "target" in kwargs:
            kwargs["target"] = DigitTarget(kwargs["target"])
        return cls(**kwargs)


registry.register(MapDigits.name, MapDigits.from_dict)


def map_punctuation(s: str, /) -> str:
    """Map Arabic sentence punctuation ، ؛ ؟ to Latin , ; ? (number-separator-safe) — lossy."""
    return chars.ARABIC_PUNCTUATION_RUN.sub(lambda m: chars.ARABIC_PUNCTUATION[m.group()], s)


@dataclass(frozen=True, slots=True)
class MapPunctuation:
    """Map Arabic punctuation ، ؛ ؟ to Latin , ; ? — number-separator-safe — lossy folding.

    English: *punctuation mapping*. The Arabic comma ،, semicolon ؛ and question mark ؟ fold to
    their Latin equivalents so one tokenizer/sentence-splitter works on Arabic text (story 32). A
    mark sitting between two digits is a numeric separator (e.g. a thousands-grouped number) and is
    preserved, not turned into sentence punctuation; the dedicated decimal/thousands/date separators
    are never touched. The fold erases the script of the punctuation, so `safety` is
    `LINGUISTIC_FOLDING`, never run under `LIGHT`.
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "MapPunctuation"

    def __call__(self, s: str, /) -> str:
        return map_punctuation(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(MapPunctuation.name, MapPunctuation.from_dict)


def _compile_elongation(cap: int) -> tuple[re.Pattern[str], str]:
    """Build the (pattern, replacement) for capping a repeated-letter run at `cap` copies.

    The pattern matches a letter followed by `cap`-or-more of the same letter (a run longer than
    `cap`); the replacement re-emits the captured letter `cap` times. `cap` must be >= 1 — `cap < 1`
    would match a lone letter and replace it with nothing, i.e. delete letters, so it is rejected.
    """
    if cap < 1:
        raise ValueError(f"ReduceElongation cap must be >= 1, got {cap}")
    pattern = re.compile(rf"(?P<c>[{chars.ELONGATABLE_CLASS}])(?P=c){{{cap},}}")
    replacement = "\\g<c>" * cap
    return pattern, replacement


def reduce_elongation(s: str, /, *, cap: int = 1) -> str:
    """Cap runs of a repeated Arabic letter at `cap` copies (default 1) — lossy linguistic folding.

    English: *elongation reduction*. Collapses emphatic word-lengthening (جمييييل → جميل) so the
    vocabulary does not explode. ``cap=1`` reduces to a single letter; ``cap=2`` keeps a doubled
    letter so emphasis survives. ``cap`` must be >= 1.
    """
    pattern, replacement = _compile_elongation(cap)
    return pattern.sub(replacement, s)


@dataclass(frozen=True, slots=True)
class ReduceElongation:
    """Cap runs of a repeated Arabic letter at `cap` copies — lossy linguistic folding.

    English: *elongation reduction*. Word-lengthening repeats a letter for emphasis (جمييييل,
    راااائع); this collapses any run of the same Arabic letter to at most `cap` copies so emphatic
    spellings stop exploding the vocabulary. ``cap=1`` (the default) reduces a run to a single
    letter; ``cap=2`` keeps a doubled letter so emphasis is retained (what SOCIAL wants). A run no
    longer than `cap` — an ordinary doubled letter — is left untouched: the cap is the contract.

    Only contemporary Arabic letters are capped; digits are never touched (a repeated digit is a
    number, not emphasis, so 1000 stays 1000), nor are tashkeel marks or tatweel. The fold discards
    the emphasis, so `safety` is `LINGUISTIC_FOLDING`: opt-in via a lossy profile or an explicit
    step, never under `LIGHT`. It is a contextual `re` rule, so it stays its own pass and is not a
    candidate for the 0018 fused-translate engine (ADR-0006).
    """

    cap: int = 1
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since they are a derived view of `cap`.
    _pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)
    _replacement: str = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "ReduceElongation"

    def __post_init__(self) -> None:
        pattern, replacement = _compile_elongation(self.cap)
        object.__setattr__(self, "_pattern", pattern)
        object.__setattr__(self, "_replacement", replacement)

    def __call__(self, s: str, /) -> str:
        return self._pattern.sub(self._replacement, s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"cap": self.cap}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(ReduceElongation.name, ReduceElongation.from_dict)


class CleanMode(StrEnum):
    """Whether a cleaning step deletes the matched noise or replaces it with a placeholder token.

    English: *cleaning mode*. `DELETE` (default) removes the span outright; `PLACEHOLDER` swaps in a
    fixed token (e.g. ``[URL]``) so a model keeps "a link was here" as a feature without a noisy
    unique value — the entrenched AraBERT expectation, so it is first-class, not just delete.
    """

    DELETE = "delete"  # remove the matched span (default)
    PLACEHOLDER = "placeholder"  # replace the matched span with the `placeholder` token


def _clean_replacement(mode: CleanMode, placeholder: str) -> str:
    """The literal string a cleaning step substitutes for a match: the placeholder token in
    `PLACEHOLDER` mode, the empty string (i.e. deletion) in `DELETE` mode."""
    return placeholder if CleanMode(mode) is CleanMode.PLACEHOLDER else ""


def clean_urls(s: str, /, *, mode: CleanMode = CleanMode.DELETE, placeholder: str = "[URL]") -> str:
    """Remove URLs, or replace each with a placeholder token (default ``[URL]``) — cleaning.

    English: *URL cleaning*. Scheme- (http/https) or ``www.``-prefixed runs are deleted (default) or
    swapped for `placeholder`. Use an Arabic token (e.g. ``[رابط]``) by passing it explicitly.
    """
    replacement = _clean_replacement(mode, placeholder)
    return chars.URL.sub(lambda _m: replacement, s)


@dataclass(frozen=True, slots=True)
class CleanURLs:
    """Remove URLs or replace them with a placeholder token — cleaning (non-linguistic noise).

    English: *URL cleaning*. A scheme- (http/https) or ``www.``-prefixed run is metadata noise, not
    Arabic content, so it is `DELETE`d (the default) or, in `PLACEHOLDER` mode, replaced by the
    `placeholder` token — the AraBERT ``[رابط]``/``[URL]`` expectation, kept first-class. The
    default token is the English ``[URL]``; pass ``placeholder="[رابط]"`` for the Arabic one.
    Matching is conservative (only http(s):// and ``www.`` anchor it), so ordinary prose is safe.

    `safety` is `CLEANING`: it discards non-linguistic noise, a sibling of linguistic folding, so it
    never runs under `LIGHT` — opt-in via a lossy profile (SOCIAL) or an explicit step (ADR-0011).
    """

    mode: CleanMode = CleanMode.DELETE
    placeholder: str = "[URL]"
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `mode`/`placeholder`.
    _replacement: str = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.CLEANING
    name: ClassVar[str] = "CleanURLs"

    def __post_init__(self) -> None:
        # Coerce a plain string ("delete") to the enum so equality and serialization are stable
        # regardless of how the mode was passed, then precompute the replacement once.
        mode = CleanMode(self.mode)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "_replacement", _clean_replacement(mode, self.placeholder))

    def __call__(self, s: str, /) -> str:
        replacement = self._replacement
        return chars.URL.sub(lambda _m: replacement, s)

    def to_dict(self) -> StepDict:
        return {
            "name": self.name,
            "config": {"mode": self.mode.value, "placeholder": self.placeholder},
        }

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "mode" in kwargs:
            kwargs["mode"] = CleanMode(kwargs["mode"])
        return cls(**kwargs)


registry.register(CleanURLs.name, CleanURLs.from_dict)


def clean_mentions(
    s: str, /, *, mode: CleanMode = CleanMode.DELETE, placeholder: str = "[MENTION]"
) -> str:
    """Remove @mentions, or replace each with a placeholder (default ``[MENTION]``) — cleaning.

    English: *mention cleaning*. An ``@`` followed by word characters (Unicode-aware, so an Arabic
    handle @محمد counts) is deleted (default) or swapped for `placeholder`. Pass an Arabic token
    (e.g. ``[مستخدم]``) explicitly. Email handling is out of v1 scope, so the host of
    ``user@example`` reads as a mention.
    """
    replacement = _clean_replacement(mode, placeholder)
    return chars.MENTION.sub(lambda _m: replacement, s)


@dataclass(frozen=True, slots=True)
class CleanMentions:
    """Remove @mentions or replace them with a placeholder token — cleaning (non-linguistic noise).

    English: *mention cleaning*. An ``@``-handle is metadata noise, so it is `DELETE`d (the default)
    or, in `PLACEHOLDER` mode, replaced by the `placeholder` token (the AraBERT ``[مستخدم]``/
    ``[MENTION]`` expectation, kept first-class; the default token is the English ``[MENTION]``). A
    handle is ``@`` plus Unicode word characters, so an Arabic handle @محمد is matched as readily as
    @user; a bare ``@`` with no following word character is left alone. Email local-parts are not
    special-cased (email is out of v1 scope), so ``user@example`` has its host read as a mention.

    `safety` is `CLEANING`: it discards non-linguistic noise, never run under `LIGHT` (ADR-0011).
    """

    mode: CleanMode = CleanMode.DELETE
    placeholder: str = "[MENTION]"
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `mode`/`placeholder`.
    _replacement: str = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.CLEANING
    name: ClassVar[str] = "CleanMentions"

    def __post_init__(self) -> None:
        mode = CleanMode(self.mode)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "_replacement", _clean_replacement(mode, self.placeholder))

    def __call__(self, s: str, /) -> str:
        replacement = self._replacement
        return chars.MENTION.sub(lambda _m: replacement, s)

    def to_dict(self) -> StepDict:
        return {
            "name": self.name,
            "config": {"mode": self.mode.value, "placeholder": self.placeholder},
        }

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "mode" in kwargs:
            kwargs["mode"] = CleanMode(kwargs["mode"])
        return cls(**kwargs)


registry.register(CleanMentions.name, CleanMentions.from_dict)


def clean_html(
    s: str, /, *, mode: CleanMode = CleanMode.DELETE, placeholder: str = "[HTML]"
) -> str:
    """Strip HTML tags (or replace each with a placeholder) and unescape entities — cleaning.

    English: *HTML cleaning*. Tags are deleted (default) or swapped for `placeholder`, then HTML
    entities are unescaped (``&amp;`` → ``&``). Tags are removed BEFORE unescaping, so an escaped
    ``&lt;b&gt;`` stays literal text rather than being decoded into a tag and then stripped.
    """
    replacement = _clean_replacement(mode, placeholder)
    stripped = chars.HTML_TAG.sub(lambda _m: replacement, s)
    return html.unescape(stripped)


@dataclass(frozen=True, slots=True)
class CleanHTML:
    """Strip HTML tags and unescape entities — cleaning (non-linguistic noise).

    English: *HTML cleaning*. Markup is noise around the text: each tag is `DELETE`d (the default,
    so you keep the inner text) or, in `PLACEHOLDER` mode, replaced by the `placeholder` token, and
    HTML entities are **always** unescaped (``&amp;`` → ``&``, ``&lt;`` → ``<``), which a tag-only
    strip would miss. Tags are removed BEFORE unescaping, so an intentionally escaped ``&lt;b&gt;``
    stays literal text instead of being decoded into a ``<b>`` tag and then stripped.

    `safety` is `CLEANING`: it discards non-linguistic noise, never run under `LIGHT` (ADR-0011).
    Strict idempotence does not hold over arbitrary text — ``html.unescape`` decodes only one level,
    so a multiply-encoded entity (``&amp;amp;`` → ``&amp;`` → ``&``) changes on each pass — but on
    realistic single-encoded markup the step is a fixed point.
    """

    mode: CleanMode = CleanMode.DELETE
    placeholder: str = "[HTML]"
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `mode`/`placeholder`.
    _replacement: str = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.CLEANING
    name: ClassVar[str] = "CleanHTML"

    def __post_init__(self) -> None:
        mode = CleanMode(self.mode)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "_replacement", _clean_replacement(mode, self.placeholder))

    def __call__(self, s: str, /) -> str:
        replacement = self._replacement
        stripped = chars.HTML_TAG.sub(lambda _m: replacement, s)
        return html.unescape(stripped)

    def to_dict(self) -> StepDict:
        return {
            "name": self.name,
            "config": {"mode": self.mode.value, "placeholder": self.placeholder},
        }

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "mode" in kwargs:
            kwargs["mode"] = CleanMode(kwargs["mode"])
        return cls(**kwargs)


registry.register(CleanHTML.name, CleanHTML.from_dict)


class EmojiMode(StrEnum):
    """How `HandleEmoji` treats emoji (story 35).

    English: *emoji handling*. `KEEP` (default) leaves emoji in place so affective signal survives;
    `STRIP` removes them; `DEMOJIZE` replaces each with its text alias (😍 → ``:heart_eyes:``),
    which needs the optional ``emoji`` library (the ``[emoji]`` extra).
    """

    KEEP = "keep"  # leave emoji untouched (default — a lossless no-op)
    STRIP = "strip"  # remove emoji
    DEMOJIZE = "demojize"  # replace each emoji with its text alias (needs the [emoji] extra)


class EmojiSupportNotInstalledError(ImportError):
    """Raised when `HandleEmoji(mode="demojize")` is built without the optional ``emoji`` extra.

    `KEEP`/`STRIP` need no dependency; only `DEMOJIZE` requires the ``emoji`` library, kept out of
    the lean MIT core (ADR-0003). Subclasses `ImportError` so a caller probing for the capability
    can catch it; the message says how to install the extra.
    """


def _load_demojize() -> Callable[[str], str]:
    """Resolve ``emoji.demojize`` (the `DEMOJIZE` backend), or raise a clear, actionable error.

    A module-level seam so the optional dependency is imported lazily (never at package import) and
    its absence can be simulated in tests. Catches `ImportError` broadly so both a missing package
    and a stubbed-out module surface as `EmojiSupportNotInstalledError`.
    """
    try:
        import emoji
    except ImportError as exc:
        raise EmojiSupportNotInstalledError(
            "HandleEmoji(mode='demojize') needs the optional `emoji` library, which is not "
            "installed. Install it with: pip install 'araclean[emoji]'."
        ) from exc
    return emoji.demojize


def _keep_emoji(s: str, /) -> str:
    return s


def _strip_emoji(s: str, /) -> str:
    return chars.EMOJI.sub("", s)


def handle_emoji(s: str, /, *, mode: EmojiMode = EmojiMode.KEEP) -> str:
    """Keep, strip, or demojize emoji (default: keep) — cleaning, except `KEEP` (a no-op).

    English: *emoji handling*. ``mode="strip"`` removes emoji; ``mode="demojize"`` replaces each
    with its text alias (needs the ``[emoji]`` extra, else raises `EmojiSupportNotInstalledError`);
    ``mode="keep"`` leaves them untouched.
    """
    mode = EmojiMode(mode)
    if mode is EmojiMode.KEEP:
        return _keep_emoji(s)
    if mode is EmojiMode.STRIP:
        return _strip_emoji(s)
    return _load_demojize()(s)


# `KEEP` is a pure no-op, so it is lossless `ENCODING_REPAIR` (safe even under LIGHT); `STRIP` and
# `DEMOJIZE` discard or rewrite non-linguistic noise, so they are `CLEANING` (ADR-0011).
_EMOJI_SAFETY: dict[EmojiMode, SafetyClass] = {
    EmojiMode.KEEP: SafetyClass.ENCODING_REPAIR,
    EmojiMode.STRIP: SafetyClass.CLEANING,
    EmojiMode.DEMOJIZE: SafetyClass.CLEANING,
}


@dataclass(frozen=True, slots=True)
class HandleEmoji:
    """Keep, strip, or demojize emoji — cleaning (non-linguistic noise), or a no-op when kept.

    English: *emoji handling*. Social text carries affective signal in emoji, so the default `KEEP`
    leaves them untouched (a lossless no-op). `STRIP` removes them; `DEMOJIZE` rewrites each to its
    text alias (😍 → ``:smiling_face_with_heart_eyes:``) so the signal survives as words a tokenizer
    can read. `safety` is therefore *mode-dependent*: `KEEP` is `ENCODING_REPAIR` (lossless, safe
    under `LIGHT`); `STRIP`/`DEMOJIZE` are `CLEANING` (opt-in noise removal — ADR-0011).

    `DEMOJIZE` needs the optional ``emoji`` library (the ``[emoji]`` extra), resolved once at
    construction so the per-string call stays setup-free; building a `DEMOJIZE` step without the
    extra raises `EmojiSupportNotInstalledError`. `KEEP`/`STRIP` need no dependency — `STRIP`
    recognizes emoji from a built-in Unicode set, so the lean core covers it (it strips a whole
    ZWJ sequence, leaving a standalone joiner — invisible formatting owned by StripBidi — alone).
    """

    mode: EmojiMode = EmojiMode.KEEP
    # Derived from `mode`, precomputed at construction so __call__ does no setup (ADR-0003/0006);
    # excluded from equality and repr since both follow from `mode`.
    safety: SafetyClass = field(init=False, repr=False, compare=False)
    _apply: Callable[[str], str] = field(init=False, repr=False, compare=False)
    name: ClassVar[str] = "HandleEmoji"

    def __post_init__(self) -> None:
        # Coerce a plain string ("strip") to the enum so equality, serialization and dispatch are
        # stable regardless of how the mode was passed, then resolve the per-call transform once.
        mode = EmojiMode(self.mode)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "safety", _EMOJI_SAFETY[mode])
        if mode is EmojiMode.DEMOJIZE:
            apply = _load_demojize()
        elif mode is EmojiMode.STRIP:
            apply = _strip_emoji
        else:
            apply = _keep_emoji
        object.__setattr__(self, "_apply", apply)

    def __call__(self, s: str, /) -> str:
        return self._apply(s)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"mode": self.mode.value}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "mode" in kwargs:
            kwargs["mode"] = EmojiMode(kwargs["mode"])
        return cls(**kwargs)


registry.register(HandleEmoji.name, HandleEmoji.from_dict)
