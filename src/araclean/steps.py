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
from difflib import SequenceMatcher
from enum import StrEnum
from typing import Any, ClassVar, Literal, Protocol, Self, TypedDict, runtime_checkable

from araclean import chars, registry, stopwords
from araclean.offsets import OffsetMap
from araclean.safety import SafetyClass

type UnicodeForm = Literal["NFC", "NFD", "NFKC", "NFKD"]

# The shape of a `str.translate` table: each Unicode code point maps to a replacement string, a
# replacement ordinal, or ``None`` (delete). The fused engine (issue 0018) reads such tables off
# the fusible steps and composes a run of them into one.
type TranslateTable = Mapping[int, str | int | None]


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
    """Optional capability a `Step` opts into to support offset-preserving normalization.

    Every built-in step implements this (ADR-0012). Custom steps that don't will cause
    ``Pipeline.apply_aligned`` to raise ``AlignmentNotSupportedError``.
    """

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]: ...


# ---------------------------------------------------------------------------
# Module-level helpers shared by step apply_aligned implementations
# ---------------------------------------------------------------------------


def _collect_regex_sub(
    s: str,
    pattern: re.Pattern[str],
    replacement: str | Callable[[re.Match[str]], str],
) -> tuple[str, list[tuple[int, int]], list[int]]:
    """Apply ``pattern.sub(replacement, s)``, collecting each match span and the length of the
    string it was replaced with.  Returns ``(normalized, spans, replacement_lens)``."""
    spans: list[tuple[int, int]] = []
    rep_lens: list[int] = []

    def _track(m: re.Match[str]) -> str:
        # A str replacement is a sub() TEMPLATE: expand it, so group references (\g<c>) and
        # escapes behave exactly as in `pattern.sub(replacement, s)`.
        result = replacement(m) if callable(replacement) else m.expand(replacement)
        spans.append(m.span())
        rep_lens.append(len(result))
        return result

    normalized = pattern.sub(_track, s)
    return normalized, spans, rep_lens


def _aligned_from_translate(s: str, table: Mapping[int, str | int | None]) -> tuple[str, OffsetMap]:
    """Apply ``str.translate(table)`` and return ``(normalized, OffsetMap)``."""
    return s.translate(table), OffsetMap.from_translate(s, table)


def _aligned_via_diff(s: str, normalized: str) -> OffsetMap:
    """Build an ``OffsetMap`` for an opaque ``s -> normalized`` rewrite via ``SequenceMatcher``.

    The fallback for transforms whose internals we don't control (``unicodedata.normalize``,
    ``emoji.demojize``): the normalized text is exactly the transform's own output, and alignment
    is recovered from the diff — coarse (a replaced run maps to the whole source run) but always
    consistent with the returned string.
    """
    if s == normalized:
        return OffsetMap.identity(len(s))
    sm = SequenceMatcher(None, s, normalized, autojunk=False)
    o: list[int] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(j2 - j1):
                o.append(i1 + k)
                o.append(i1 + k + 1)
        elif op == "replace":
            for _ in range(j2 - j1):
                o.append(i1)
                o.append(i2)
        elif op == "insert":
            for _ in range(j2 - j1):
                o.append(i1)
                o.append(i1)
        # "delete" — chars disappeared, no normalized chars emitted
    return OffsetMap(o)


def _aligned_unicode_normalize(s: str, form: UnicodeForm) -> tuple[str, OffsetMap]:
    """Apply ``unicodedata.normalize(form, s)`` and return ``(normalized, OffsetMap)``."""
    normalized = unicodedata.normalize(form, s)
    return normalized, _aligned_via_diff(s, normalized)


# Mirrors what `html.unescape` rewrites, INCLUDING the no-semicolon forms it accepts (legacy named
# references like `&amp` and bare numeric references like `&#65`) — the trailing `;` is optional.
_HTML_ENTITY: re.Pattern[str] = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#[xX][0-9a-fA-F]+);?")


def _aligned_html_unescape(s: str) -> tuple[str, OffsetMap]:
    """Run ``html.unescape`` and return ``(normalized, OffsetMap)``."""
    normalized, spans, rep_lens = _collect_regex_sub(
        s, _HTML_ENTITY, lambda m: html.unescape(m.group())
    )
    return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)


@runtime_checkable
class SupportsTranslate(Step, Protocol):
    """A `Step` whose entire behavior is one `str.translate` over a static table — *fusible*.

    The fused engine (`araclean.fusion`, issue 0018 / ADR-0006) collapses a run of consecutive
    `SupportsTranslate` steps into a single combined table applied in one C-level pass. This is
    exact because `str.translate` is a context-free, single-pass, per-character map — it never
    re-scans its own output — so composing the run per code point reproduces applying the steps in
    sequence. A step opts in by exposing the precomputed table its `__call__` applies. The
    *contextual* steps (`NormalizeUnicode`, and the regex `CollapseWhitespace` / `MapPunctuation` /
    `ReduceElongation` / cleaning steps) do not implement this and stay their own pass, so ordering
    across them is never disturbed.

    A step whose fusibility depends on its CONFIG (`RemoveTashkeel` is pure translate for
    ``position="all"`` but contextual for ``"final"``; `MapDigits` likewise with
    ``map_separators=True``) raises `AttributeError` from `translate_table` in its contextual
    mode — the fusion planner reads that as "not fusible here" and leaves the step its own pass.
    (An ``isinstance`` check alone cannot see this: the property exists on the class either way.)
    """

    @property
    def translate_table(self) -> TranslateTable: ...


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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_unicode_normalize(s, self.form)

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, str]:
        """The static `str.translate` table this step applies — the fused-engine seam (0018)."""
        return chars.PRESENTATION_FORMS

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, None]:
        """The static `str.translate` table this step applies — the fused-engine seam (0018)."""
        return chars.REMOVE_TATWEEL

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(RemoveTatweel.name, RemoveTatweel.from_dict)


def strip_bidi(s: str, /) -> str:
    """Remove bidi controls, zero-width characters and the BOM — lossless encoding repair."""
    return chars.ZWJ_OUTSIDE_EMOJI.sub("", s).translate(chars.STRIP_BIDI)


@dataclass(frozen=True, slots=True)
class StripBidi:
    """Remove bidi controls, zero-width characters and the BOM — lossless encoding repair.

    English: *bidi/zero-width stripping*. RLM/LRM/ALM and the embedding/isolate controls, the
    zero-width non-joiner/space/word-joiner, and the BOM are invisible: they carry no Arabic
    letter content yet break equality and tokenization, so they are deleted outright.

    The zero-width JOINER U+200D is the one CONTEXTUAL case: inside an emoji sequence (👨‍👩‍👧,
    👨‍⚕️) the joiner is content — deleting it would split the sequence into its component emoji
    (and alter what a later `HandleEmoji` sees), so a ZWJ flanked by emoji is KEPT and every other
    ZWJ is stripped. Residual: a joiner between an emoji and an Arabic letter still goes. That one
    rule is a regex pass, so unlike the other LIGHT repairs this step is contextual and stays its
    own pass — it does not join the 0018 fused-translate engine (ADR-0006).
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "StripBidi"

    def __call__(self, s: str, /) -> str:
        return strip_bidi(s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        # Two passes: regex ZWJ deletion, then translate.
        after_regex, spans, rep_lens = _collect_regex_sub(s, chars.ZWJ_OUTSIDE_EMOJI, "")
        m1 = OffsetMap.from_regex_sub(s, spans, rep_lens)
        after_trans, m2 = _aligned_from_translate(after_regex, chars.STRIP_BIDI)
        return after_trans, m1.compose(m2)

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, str]:
        """The static `str.translate` table this step applies — the fused-engine seam (0018)."""
        return chars.UNIFY_LOOKALIKES

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        repl: str | Callable[[re.Match[str]], str] = (
            " " if self.collapse_lines else _collapse_whitespace_run
        )
        normalized, spans, rep_lens = _collect_regex_sub(s, chars.WHITESPACE_RUN, repl)
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

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


type TashkeelPosition = Literal["all", "final"]


def _final_tashkeel_pattern(code_points: Collection[int]) -> re.Pattern[str]:
    """Compile the WORD-FINAL matcher for the selected marks: a run of them not followed by a
    character that continues an Arabic word (a letter or any combining mark). A run followed by an
    UNSELECTED mark is word-internal and kept — only the trailing run at the very word end goes."""
    mark_class = "".join(re.escape(chr(cp)) for cp in sorted(code_points))
    return re.compile(rf"[{mark_class}]+(?![{chars.ARABIC_WORD_CLASS}])")


def remove_tashkeel(
    s: str,
    /,
    *,
    classes: Collection[MarkClass] | None = None,
    position: TashkeelPosition = "all",
) -> str:
    """Remove the selected tashkeel mark classes (default: all) — lossy linguistic folding.

    English: *dediacritization*. Deletes only the vocalization marks of the chosen `MarkClass`es,
    never their carrier letters. ``classes=None`` removes every class. Sukun rides with `HARAKAT`.
    ``position="final"`` removes only a word-final run of the selected marks (the i3rab case-vowel
    fold: كَتَبَ → كَتَب), everywhere by default.
    """
    selected = ALL_MARK_CLASSES if classes is None else classes
    table = _tashkeel_removal_table(selected)
    if position == "final":
        return _final_tashkeel_pattern(table).sub("", s)
    return s.translate(table)


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

    `position` selects WHERE the chosen marks are removed: ``"all"`` (the default) everywhere via
    one `str.translate` pass; ``"final"`` only a WORD-FINAL run of them — the i3rab fold (drop the
    case vowel, keep the word-internal vocalization: كِتَابٌ → كِتَاب), PyArabic's
    ``strip_lastharaka`` parity. A trailing run followed by an *unselected* mark counts as
    word-internal and is kept. ``"final"`` is a contextual regex rule, so in that mode the step
    stays its own pass and does not join the 0018 fused-translate engine (its `translate_table`
    raises `AttributeError`, which the planner reads as "not fusible").
    """

    classes: Collection[MarkClass] = ALL_MARK_CLASSES
    position: TashkeelPosition = "all"
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since they are a derived view of `classes`/`position`.
    _table: dict[int, None] = field(init=False, repr=False, compare=False)
    _apply: Callable[[str], str] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "RemoveTashkeel"

    def __post_init__(self) -> None:
        # Normalize any selection (set/list/...) to a frozenset so equality and serialization are
        # order-insensitive and stable, then precompute the deletion table (or final-run regex)
        # once.
        classes = frozenset(self.classes)
        object.__setattr__(self, "classes", classes)
        table = _tashkeel_removal_table(classes)
        object.__setattr__(self, "_table", table)
        if self.position == "all":

            def apply(s: str, /) -> str:
                return s.translate(table)
        elif self.position == "final":
            pattern = _final_tashkeel_pattern(table)

            def apply(s: str, /) -> str:
                return pattern.sub("", s)
        else:
            raise ValueError(
                f"RemoveTashkeel position must be 'all' or 'final', got {self.position!r}"
            )
        object.__setattr__(self, "_apply", apply)

    def __call__(self, s: str, /) -> str:
        return self._apply(s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        if self.position == "all":
            return _aligned_from_translate(s, self._table)
        # position == "final": regex substitution
        pattern = _final_tashkeel_pattern(self._table)
        normalized, spans, rep_lens = _collect_regex_sub(s, pattern, "")
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

    @property
    def translate_table(self) -> dict[int, None]:
        """The precomputed `str.translate` deletion table — the fused-engine seam (0018).

        Only ``position="all"`` IS one translate pass; ``"final"`` is contextual, so this raises
        `AttributeError` and the fusion planner leaves the step as its own pass.
        """
        if self.position != "all":
            raise AttributeError(
                "RemoveTashkeel(position='final') is contextual — no single translate table"
            )
        return self._table

    def to_dict(self) -> StepDict:
        return {
            "name": self.name,
            "config": {
                "classes": sorted(mark_class.value for mark_class in self.classes),
                "position": self.position,
            },
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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, str]:
        """The static `str.translate` table this step applies — the fused-engine seam (0018)."""
        return chars.FOLD_ALEF

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, str]:
        """The static `str.translate` table this step applies — the fused-engine seam (0018)."""
        return chars.FOLD_ALEF_MAQSURA

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, str | None]:
        """The precomputed `str.translate` table — the fused-engine seam (0018)."""
        return self._table

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, str]:
        """The precomputed `str.translate` table (empty for ``KEEP``) — fused-engine seam (0018)."""
        return self._table

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


def _map_separators(s: str, /) -> str:
    """Rewrite the dedicated Arabic number separators when digit-flanked: ٫ → '.', ٬ → ','."""
    return chars.NUMBER_SEPARATOR_BETWEEN_DIGITS.sub(
        lambda m: chars.ARABIC_NUMBER_SEPARATORS[m.group()], s
    )


def map_digits(
    s: str, /, *, target: DigitTarget = DigitTarget.ASCII, map_separators: bool = False
) -> str:
    """Convert digits among Arabic-Indic / Extended / ASCII to a target (ASCII default) — lossy.

    ``map_separators=True`` also rewrites the dedicated Arabic decimal/thousands separators when
    digit-flanked (٫ → ``.``, ٬ → ``,``), so ١٢٫٥ becomes 12.5 rather than the mixed-script 12٫5.
    """
    converted = s.translate(_digit_table(target))
    return _map_separators(converted) if map_separators else converted


@dataclass(frozen=True, slots=True)
class MapDigits:
    """Convert digits among Arabic-Indic / Extended / ASCII to a target — lossy linguistic folding.

    English: *digit mapping*. Every digit — Arabic-Indic ٠-٩, Extended (Persian/Urdu) ۰-۹, or ASCII
    0-9 — is rewritten to the chosen `DigitTarget` by numeric value, so numbers parse and match
    consistently regardless of how they were typed (story 31). The default target is `ASCII`. The
    map erases which script a digit was written in, so `safety` is `LINGUISTIC_FOLDING`: opt-in via
    a lossy profile or an explicit step, never under `LIGHT`.

    The dedicated Arabic number separators (decimal ٫ U+066B, thousands ٬ U+066C) are NOT digits,
    so by default they stay — ١٢٫٥ becomes the mixed-script 12٫5. The opt-in
    ``map_separators=True`` also rewrites a separator when digit-flanked on BOTH sides (٫ → ``.``,
    ٬ → ``,``; the inverse of `MapPunctuation`'s guard), giving 12.5; a stray separator outside a
    number is never touched. That guard is a contextual regex, so with the knob on the step stays
    its own pass and does not join the 0018 fused-translate engine (its `translate_table` raises
    `AttributeError`, which the planner reads as "not fusible").
    """

    target: DigitTarget = DigitTarget.ASCII
    map_separators: bool = False
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
        converted = s.translate(self._table)
        return _map_separators(converted) if self.map_separators else converted

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        if not self.map_separators:
            return _aligned_from_translate(s, self._table)
        # map_separators=True: translate first, then regex separator rewrite
        after_trans, m1 = _aligned_from_translate(s, self._table)
        after_sep, spans, rep_lens = _collect_regex_sub(
            after_trans,
            chars.NUMBER_SEPARATOR_BETWEEN_DIGITS,
            lambda m: chars.ARABIC_NUMBER_SEPARATORS[m.group()],
        )
        m2 = OffsetMap.from_regex_sub(after_trans, spans, rep_lens)
        return after_sep, m1.compose(m2)

    @property
    def translate_table(self) -> dict[int, str]:
        """The precomputed `str.translate` table this step applies — fused-engine seam (0018).

        Only the pure digit map IS one translate pass; with ``map_separators=True`` the
        digit-flanked guard is contextual, so this raises `AttributeError` and the fusion planner
        leaves the step as its own pass.
        """
        if self.map_separators:
            raise AttributeError(
                "MapDigits(map_separators=True) is contextual — no single translate table"
            )
        return self._table

    def to_dict(self) -> StepDict:
        return {
            "name": self.name,
            "config": {"target": self.target.value, "map_separators": self.map_separators},
        }

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        normalized, spans, rep_lens = _collect_regex_sub(
            s, chars.ARABIC_PUNCTUATION_RUN, lambda m: chars.ARABIC_PUNCTUATION[m.group()]
        )
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(MapPunctuation.name, MapPunctuation.from_dict)


def _resolve_min_run(cap: int, min_run: int | None) -> int:
    """Resolve the elongation trigger: ``max(cap + 1, 3)`` when unset (see `ReduceElongation`)."""
    return max(cap + 1, 3) if min_run is None else min_run


def _compile_elongation(cap: int, min_run: int | None) -> tuple[re.Pattern[str], str]:
    """Build the (pattern, replacement) collapsing runs of >= `min_run` letters to `cap` copies.

    The pattern matches a letter followed by ``min_run - 1``-or-more of the same letter (a run of
    at least `min_run`); the replacement re-emits the captured letter `cap` times. `cap` must be
    >= 1 — `cap < 1` would match a lone letter and replace it with nothing, i.e. delete letters,
    so it is rejected. `min_run` must be > `cap` — a trigger at or below the cap would EXPAND a
    short run up to `cap` copies instead of only collapsing long ones.
    """
    if cap < 1:
        raise ValueError(f"ReduceElongation cap must be >= 1, got {cap}")
    resolved = _resolve_min_run(cap, min_run)
    if resolved <= cap:
        raise ValueError(
            f"ReduceElongation min_run must be > cap so the step only collapses runs longer than "
            f"the cap; got min_run={resolved} with cap={cap}."
        )
    pattern = re.compile(rf"(?P<c>[{chars.ELONGATABLE_CLASS}])(?P=c){{{resolved - 1},}}")
    replacement = "\\g<c>" * cap
    return pattern, replacement


def reduce_elongation(s: str, /, *, cap: int = 1, min_run: int | None = None) -> str:
    """Collapse runs of >= `min_run` repeated Arabic letters to `cap` copies — lossy folding.

    English: *elongation reduction*. Collapses emphatic word-lengthening (جمييييل → جميل) so the
    vocabulary does not explode, while a legitimately doubled letter (الله، ممكن) is never touched:
    `min_run` (the trigger, default ``max(cap + 1, 3)``) decides what counts as elongation, `cap`
    what a run is reduced to. ``cap`` must be >= 1 and ``min_run`` > ``cap``.
    """
    pattern, replacement = _compile_elongation(cap, min_run)
    return pattern.sub(replacement, s)


@dataclass(frozen=True, slots=True)
class ReduceElongation:
    """Collapse runs of >= `min_run` repeated Arabic letters to `cap` copies — lossy folding.

    English: *elongation reduction*. Word-lengthening repeats a letter for emphasis (جمييييل,
    راااائع); this collapses such a run so emphatic spellings stop exploding the vocabulary. Two
    knobs, because the TRIGGER and the TARGET are different decisions:

    - `min_run` — what counts as elongation: only a run of at least `min_run` copies collapses.
      Defaults to ``max(cap + 1, 3)``: Arabic spells true doubled letters constantly (the
      assimilated definite article الله/اللغة, verb prefixes تتكلم, lexical doubles ممكن/مما),
      while a TRIPLED letter is virtually nonexistent in real spelling — so 3+ is the safe
      elongation signal (the literature's standard rule) and a double is presumed legitimate. A
      2-copy emphatic spelling is indistinguishable from a legitimate double without a lexicon, so
      it is deliberately left alone.
    - `cap` — what a run reduces to: ``cap=1`` (the default) collapses to the canonical single
      letter, so جمييييل merges with جميل (what ML/SEARCH want); ``cap=2`` keeps a doubled letter
      so emphasis survives as a feature (what SOCIAL wants — its trigger is already 3, so its
      behavior is identical with the default `min_run`).

    Only contemporary Arabic letters are capped; digits are never touched (a repeated digit is a
    number, not emphasis, so 1000 stays 1000), nor are tashkeel marks or tatweel. The fold discards
    the emphasis, so `safety` is `LINGUISTIC_FOLDING`: opt-in via a lossy profile or an explicit
    step, never under `LIGHT`. It is a contextual `re` rule, so it stays its own pass and is not a
    candidate for the 0018 fused-translate engine (ADR-0006).
    """

    cap: int = 1
    min_run: int | None = None
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since they are a derived view of `cap`/`min_run`.
    _pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)
    _replacement: str = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "ReduceElongation"

    def __post_init__(self) -> None:
        pattern, replacement = _compile_elongation(self.cap, self.min_run)
        # Pin the RESOLVED trigger (never None) so equality and serialization are stable however
        # the step was built: ReduceElongation(cap=1) == ReduceElongation(cap=1, min_run=3).
        object.__setattr__(self, "min_run", _resolve_min_run(self.cap, self.min_run))
        object.__setattr__(self, "_pattern", pattern)
        object.__setattr__(self, "_replacement", replacement)

    def __call__(self, s: str, /) -> str:
        return self._pattern.sub(self._replacement, s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        repl = self._replacement
        normalized, spans, rep_lens = _collect_regex_sub(s, self._pattern, repl)
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"cap": self.cap, "min_run": self.min_run}}

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        repl = self._replacement
        normalized, spans, rep_lens = _collect_regex_sub(s, chars.URL, lambda _m: repl)
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

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


def _mention_substitution(replacement: str) -> Callable[[re.Match[str]], str]:
    """The substitution callback for `chars.MENTION_OR_EMAIL`: an email match passes through
    verbatim (it is an address, not a mention); a mention match becomes `replacement`."""

    def substitute(match: re.Match[str]) -> str:
        return match.group() if match.group("email") is not None else replacement

    return substitute


def clean_mentions(
    s: str, /, *, mode: CleanMode = CleanMode.DELETE, placeholder: str = "[MENTION]"
) -> str:
    """Remove @mentions, or replace each with a placeholder (default ``[MENTION]``) — cleaning.

    English: *mention cleaning*. An ``@`` followed by word characters (Unicode-aware, so an Arabic
    handle @محمد counts) is deleted (default) or swapped for `placeholder`. Pass an Arabic token
    (e.g. ``[مستخدم]``) explicitly. An email address (dotted domain) is recognized first and kept
    verbatim — ``user@example.com`` is an address, not a mention; the dotless ``user@example``
    still has its host read as a mention (the documented residual).
    """
    return chars.MENTION_OR_EMAIL.sub(
        _mention_substitution(_clean_replacement(mode, placeholder)), s
    )


@dataclass(frozen=True, slots=True)
class CleanMentions:
    """Remove @mentions or replace them with a placeholder token — cleaning (non-linguistic noise).

    English: *mention cleaning*. An ``@``-handle is metadata noise, so it is `DELETE`d (the default)
    or, in `PLACEHOLDER` mode, replaced by the `placeholder` token (the AraBERT ``[مستخدم]``/
    ``[MENTION]`` expectation, kept first-class; the default token is the English ``[MENTION]``). A
    handle is ``@`` plus Unicode word characters, so an Arabic handle @محمد is matched as readily as
    @user; a bare ``@`` with no following word character is left alone. An EMAIL ADDRESS is
    recognized before the mention shape and kept verbatim — ``user@example.com`` is an address,
    not a mention to rewrite into ``user[MENTION].com``. The email shape requires a dotted domain,
    so the dotless ``user@example`` still has its host read as a mention (documented residual).

    `safety` is `CLEANING`: it discards non-linguistic noise, never run under `LIGHT` (ADR-0011).
    """

    mode: CleanMode = CleanMode.DELETE
    placeholder: str = "[MENTION]"
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `mode`/`placeholder`.
    _substitute: Callable[[re.Match[str]], str] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.CLEANING
    name: ClassVar[str] = "CleanMentions"

    def __post_init__(self) -> None:
        mode = CleanMode(self.mode)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(
            self, "_substitute", _mention_substitution(_clean_replacement(mode, self.placeholder))
        )

    def __call__(self, s: str, /) -> str:
        return chars.MENTION_OR_EMAIL.sub(self._substitute, s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        normalized, spans, rep_lens = _collect_regex_sub(
            s, chars.MENTION_OR_EMAIL, self._substitute
        )
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

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

    SCOPE BOUNDARY: this is a tag stripper, not an HTML parser. The *content* of a container
    element survives even when its tags go — including ``<script>`` and ``<style>``, whose
    JavaScript/CSS text is kept as text. Fine for the social-snippet case this step serves; for
    web-scrape corpora, strip script/style containers with a real HTML parser before araclean.
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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        repl = self._replacement
        after_tags, spans, rep_lens = _collect_regex_sub(s, chars.HTML_TAG, lambda _m: repl)
        m1 = OffsetMap.from_regex_sub(s, spans, rep_lens)
        after_unescape, m2 = _aligned_html_unescape(after_tags)
        return after_unescape, m1.compose(m2)

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

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        if self.mode is EmojiMode.KEEP:
            return s, OffsetMap.identity(len(s))
        if self.mode is EmojiMode.STRIP:
            normalized, spans, rep_lens = _collect_regex_sub(s, chars.EMOJI, "")
            return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)
        # DEMOJIZE: the emoji library segments sequences itself (and not always where our EMOJI
        # regex would — flags, keycaps), so align its whole-string output via the diff fallback
        # rather than trusting regex spans that could leave the map inconsistent with the text.
        normalized = self._apply(s)
        return normalized, _aligned_via_diff(s, normalized)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"mode": self.mode.value}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "mode" in kwargs:
            kwargs["mode"] = EmojiMode(kwargs["mode"])
        return cls(**kwargs)


registry.register(HandleEmoji.name, HandleEmoji.from_dict)


def remove_stopwords(s: str, /) -> str:
    """Remove the curated Arabic stopwords from `s` — lossy linguistic folding.

    English: *stopword removal*. Deletes each whole-token occurrence of a word in the bundled,
    versioned list (see `araclean.stopwords`); surrounding whitespace is left as written. The list
    is flat (not clitic-aware) and negation-safe — ``ما`` / ``لا`` / ``لم`` / ``لن`` / ``ليس`` are
    kept so sentiment is never silently flipped.

    PRECONDITION: the list ships in FOLDED form, so `s` must already be dediacritized and
    letter-folded (`remove_tashkeel`, `fold_alef`, `fold_alef_maqsura`, `fold_hamza` — the SEARCH
    recipe). On raw text the hamza/tashkeel spellings simply do not match. Inside a `Pipeline` the
    ordering is enforced at construction; this bare function trusts the caller.
    """
    return stopwords.STOPWORD_PATTERN.sub("", s)


@dataclass(frozen=True, slots=True)
class RemoveStopwords:
    """Remove curated Arabic stopwords — function-word filtering — lossy linguistic folding.

    English: *stopword removal*. Deletes whole-token occurrences of the bundled, versioned Arabic
    stopword list (`araclean.stopwords`) — prepositions, pronouns, demonstratives, relative
    pronouns, neutral conjunctions and particles — so high-frequency function words stop drowning
    out content words (IR/retrieval, bag-of-words features). It discards linguistic content from the
    Arabic text, so `safety` is `LINGUISTIC_FOLDING`: opt-in via a lossy profile or an explicit
    step, never under `LIGHT` (it is content removal, not non-linguistic-noise cleaning — ADR-0011).

    Two deliberate properties (story 37): the list is **flat, not clitic-aware** (ADR-0001), so a
    prefixed/suffixed form like ``والكتاب`` / ``فيها`` is kept — only a standalone token is removed;
    and it is **negation-safe** — the polarity particles ``ما`` / ``لا`` / ``لم`` / ``لن`` / ``ليس``
    are excluded so removal can never flip a sentence's polarity. A removed token leaves its
    whitespace as written (a gap), like the other delete-style steps (CleanURLs); a later
    `CollapseWhitespace` tidies the gaps. The list version is serialized so a `Profile` pins it
    reproducibly.

    ORDERING CONTRACT (enforced): the list ships in FOLDED form (`araclean.stopwords`), so this
    step must run AFTER dediacritization and the letter folds — `requires_before` names them, and
    `Pipeline` rejects at construction any pipeline where they do not precede this step. Folding
    first is what makes matching robust: real typed Arabic routinely omits hamza (انا، الى) and
    vocalized text never matches a bare list, but after `RemoveTashkeel` + `FoldAlef` +
    `FoldAlefMaqsura` + `FoldHamza` every spelling variant lands on the one folded form the list
    carries. The folds are idempotent and cheap, so a pipeline over already-normalized text simply
    includes them as no-ops.
    """

    # The construction-time ordering contract `Pipeline` enforces (see the class docstring): each
    # named step must appear somewhere before this one.
    requires_before: ClassVar[tuple[str, ...]] = (
        "RemoveTashkeel",
        "FoldAlef",
        "FoldAlefMaqsura",
        "FoldHamza",
    )
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "RemoveStopwords"

    def __call__(self, s: str, /) -> str:
        return remove_stopwords(s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        normalized, spans, rep_lens = _collect_regex_sub(s, stopwords.STOPWORD_PATTERN, "")
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

    def to_dict(self) -> StepDict:
        # Pin the list version so a serialized profile reproduces the exact removal (story 36).
        return {"name": self.name, "config": {"version": stopwords.STOPWORDS_VERSION}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        version = config.get("version")
        if version is not None and version != stopwords.STOPWORDS_VERSION:
            raise ValueError(
                f"RemoveStopwords was serialized against stopword list version {version!r}, but "
                f"this araclean ships {stopwords.STOPWORDS_VERSION!r}; the lists differ, so "
                "removal would not reproduce. Install the matching araclean version instead."
            )
        return cls()


registry.register(RemoveStopwords.name, RemoveStopwords.from_dict)


class HashtagMode(StrEnum):
    """How `CleanHashtags` treats a #hashtag (roadmap Phase 1).

    English: *hashtag handling*. `SEGMENT` (default — the entrenched AraBERT recipe) drops the
    ``#`` and maps ``_`` to a space, so the tag's words survive as text; `DELETE` removes the tag;
    `PLACEHOLDER` swaps in a fixed token; `KEEP` leaves it untouched (the no-op a config override
    can pin).
    """

    SEGMENT = "segment"  # drop '#', '_' -> ' ' (default — keep the tag's words as text)
    DELETE = "delete"  # remove the whole tag
    PLACEHOLDER = "placeholder"  # replace the tag with the `placeholder` token
    KEEP = "keep"  # leave hashtags untouched (a lossless no-op)


def _hashtag_substitution(mode: HashtagMode, placeholder: str) -> Callable[[re.Match[str]], str]:
    """The substitution callback for one `HashtagMode` (`KEEP` never substitutes)."""
    if mode is HashtagMode.SEGMENT:
        return lambda m: m.group(1).replace("_", " ")
    replacement = _clean_replacement(
        CleanMode.PLACEHOLDER if mode is HashtagMode.PLACEHOLDER else CleanMode.DELETE, placeholder
    )
    return lambda _m: replacement


def clean_hashtags(
    s: str, /, *, mode: HashtagMode = HashtagMode.SEGMENT, placeholder: str = "[HASHTAG]"
) -> str:
    """Segment, remove, or replace #hashtags (default: segment) — cleaning.

    English: *hashtag handling*. ``mode="segment"`` (default) applies the entrenched recipe —
    ``#اليوم_الوطني`` → ``اليوم الوطني`` (drop ``#``, ``_`` → space); ``"delete"`` removes the
    tag; ``"placeholder"`` swaps in `placeholder`; ``"keep"`` leaves tags untouched.
    """
    mode = HashtagMode(mode)
    if mode is HashtagMode.KEEP:
        return s
    return chars.HASHTAG.sub(_hashtag_substitution(mode, placeholder), s)


# `KEEP` is a pure no-op, so it is lossless `ENCODING_REPAIR`; the other modes rewrite or discard
# social-metadata markup, so they are `CLEANING` (ADR-0011) — the same mode-dependent split as
# `HandleEmoji`.
_HASHTAG_SAFETY: dict[HashtagMode, SafetyClass] = {
    HashtagMode.SEGMENT: SafetyClass.CLEANING,
    HashtagMode.DELETE: SafetyClass.CLEANING,
    HashtagMode.PLACEHOLDER: SafetyClass.CLEANING,
    HashtagMode.KEEP: SafetyClass.ENCODING_REPAIR,
}


@dataclass(frozen=True, slots=True)
class CleanHashtags:
    """Segment, remove, or replace #hashtags — cleaning (social-metadata markup), no-op when kept.

    English: *hashtag handling*. A ``#tag`` is social metadata wrapping real words — in Arabic
    social text often a full phrase (#اليوم_الوطني_السعودي). The default `SEGMENT` mode applies
    the entrenched AraBERT recipe: drop the ``#``, map ``_`` to a space, so the words stay in the
    text as content (what SOCIAL pins). `DELETE` removes the tag outright; `PLACEHOLDER` swaps in
    the `placeholder` token (default the English ``[HASHTAG]``; pass an Arabic one explicitly);
    `KEEP` leaves tags untouched, so a config override can pin "do not touch hashtags".

    A tag is ``#`` plus Unicode word characters (Arabic matches as readily as Latin; ``_`` is a
    word character, so multi-word tags match whole). In SOCIAL, `CleanURLs` runs FIRST, so a URL
    fragment (…/page#section) is gone before this step could read it as a tag. `safety` is
    mode-dependent, like `HandleEmoji`: `KEEP` is a lossless no-op (`ENCODING_REPAIR`); the
    rewriting modes are `CLEANING` (ADR-0011).
    """

    mode: HashtagMode = HashtagMode.SEGMENT
    placeholder: str = "[HASHTAG]"
    # Derived from `mode`, precomputed at construction so __call__ does no setup (ADR-0003/0006);
    # excluded from equality and repr since both follow from `mode`/`placeholder`.
    safety: SafetyClass = field(init=False, repr=False, compare=False)
    _substitute: Callable[[re.Match[str]], str] | None = field(
        init=False, repr=False, compare=False
    )
    name: ClassVar[str] = "CleanHashtags"

    def __post_init__(self) -> None:
        # Coerce a plain string ("segment") to the enum so equality, serialization and dispatch are
        # stable regardless of how the mode was passed, then resolve the substitution once.
        mode = HashtagMode(self.mode)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "safety", _HASHTAG_SAFETY[mode])
        substitute = (
            None if mode is HashtagMode.KEEP else _hashtag_substitution(mode, self.placeholder)
        )
        object.__setattr__(self, "_substitute", substitute)

    def __call__(self, s: str, /) -> str:
        if self._substitute is None:  # KEEP
            return s
        return chars.HASHTAG.sub(self._substitute, s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        if self._substitute is None:  # KEEP
            return s, OffsetMap.identity(len(s))
        normalized, spans, rep_lens = _collect_regex_sub(s, chars.HASHTAG, self._substitute)
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

    def to_dict(self) -> StepDict:
        return {
            "name": self.name,
            "config": {"mode": self.mode.value, "placeholder": self.placeholder},
        }

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "mode" in kwargs:
            kwargs["mode"] = HashtagMode(kwargs["mode"])
        return cls(**kwargs)


registry.register(CleanHashtags.name, CleanHashtags.from_dict)


def _punctuation_removal_table(keep: Collection[str]) -> dict[int, None]:
    """Build the deletion table: every Unicode P* code point except the `keep` characters. Each
    `keep` entry must be a single character — a longer string is a config error, rejected here."""
    keep_code_points: set[int] = set()
    for entry in keep:
        if len(entry) != 1:
            raise ValueError(
                f"RemovePunctuation keep entries must be single characters, got {entry!r}"
            )
        keep_code_points.add(ord(entry))
    return dict.fromkeys(chars.punctuation_code_points() - keep_code_points)


def remove_punctuation(s: str, /, *, keep: Collection[str] = ()) -> str:
    """Delete every Unicode punctuation character (category P*) — lossy linguistic folding.

    English: *punctuation removal*. The bag-of-words / classification staple: all punctuation —
    Arabic ، ؛ ؟ as much as the ASCII set and every other script's — is deleted in one pass.
    ``keep`` lists characters to preserve (e.g. ``keep=("-",)``).
    """
    return s.translate(_punctuation_removal_table(keep))


@dataclass(frozen=True, slots=True)
class RemovePunctuation:
    """Delete every Unicode punctuation character (category P*) — lossy linguistic folding.

    English: *punctuation removal*. The bag-of-words / classification staple every incumbent
    ships: for token-frequency features, punctuation is noise. One stated principle: a code point
    is removed iff its Unicode general category is P* (Po/Pd/Ps/Pe/Pi/Pf/Pc) — which covers the
    Arabic marks ، ؛ ؟ ٪ ۔ as much as ASCII and every other script's punctuation, re-derived from
    the live UCD so it tracks Unicode releases. Symbols (S*: ``$ + = ~``), digits and letters are
    not punctuation and pass through. `keep` carves out characters to preserve (each entry one
    character).

    Distinct from `MapPunctuation` (which REWRITES the three Arabic sentence marks to their Latin
    equivalents for tokenizer uniformity): this step DELETES, so the two compose — map first if
    you want the Latin marks, or just remove everything. Deleting sentence structure is lossy, so
    `safety` is `LINGUISTIC_FOLDING`: opt-in, never under `LIGHT`. The whole behavior is one
    `str.translate`, so it is fusible (0018).
    """

    keep: Collection[str] = ()
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since it is a derived view of `keep`.
    _table: dict[int, None] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "RemovePunctuation"

    def __post_init__(self) -> None:
        # Normalize the keep-set to a frozenset so equality and serialization are order-insensitive
        # and stable, then precompute the deletion table once (the first construction pays the
        # lazy UCD scan; see chars.punctuation_code_points).
        keep = frozenset(self.keep)
        object.__setattr__(self, "keep", keep)
        object.__setattr__(self, "_table", _punctuation_removal_table(keep))

    def __call__(self, s: str, /) -> str:
        return s.translate(self._table)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, None]:
        """The precomputed `str.translate` deletion table — the fused-engine seam (0018)."""
        return self._table

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {"keep": sorted(self.keep)}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        kwargs = dict(config)
        if "keep" in kwargs:
            kwargs["keep"] = frozenset(kwargs["keep"])
        return cls(**kwargs)


registry.register(RemovePunctuation.name, RemovePunctuation.from_dict)


def fold_tanween_alef(s: str, /) -> str:
    """Drop a word-final tanween-fath carrier alef (كتاباً → كتاب) — lossy linguistic folding."""
    return chars.TANWEEN_ALEF.sub("", s)


@dataclass(frozen=True, slots=True)
class FoldTanweenAlef:
    """Drop the word-final tanween-fath carrier alef: كتاباً → كتاب — lossy linguistic folding.

    English: *tanween-alef folding*. The adverbial-accusative ending writes its tanween-fath on a
    carrier alef (كتاباً, or the same pair typed tanween-first as كتابًا); for recall (SEARCH) the
    whole ending folds away so the inflected spelling matches the bare كتاب. `RemoveTashkeel`
    alone cannot do this — it strips only the mark, leaving كتابا, a different spelling — so this
    step MUST RUN BEFORE dediacritization, while the tanween still marks which alef is a carrier
    (the SEARCH ordering). A tanween seated directly on a letter (خطأً، مدرسةً) has no carrier and
    is left to `RemoveTashkeel`; only the standard fathatan U+064B participates.

    It discards a real grammatical ending, so `safety` is `LINGUISTIC_FOLDING`: opt-in via SEARCH
    or an explicit step, never under `LIGHT`. A contextual `re` rule (word-final anchoring), so it
    stays its own pass and is not a candidate for the 0018 fused-translate engine (ADR-0006).
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "FoldTanweenAlef"

    def __call__(self, s: str, /) -> str:
        return fold_tanween_alef(s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        normalized, spans, rep_lens = _collect_regex_sub(s, chars.TANWEEN_ALEF, "")
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(FoldTanweenAlef.name, FoldTanweenAlef.from_dict)


def remove_foreign(
    s: str, /, *, mode: CleanMode = CleanMode.DELETE, placeholder: str = "[FOREIGN]"
) -> str:
    """Remove non-Arabic-script letter spans, or replace each with a placeholder — cleaning.

    English: *foreign-span removal*. A maximal run of letters outside the Arabic script (Latin,
    Cyrillic, CJK, …, with their combining marks) is deleted (default) or swapped for
    `placeholder`. Digits, punctuation, whitespace, symbols and emoji are not letters and pass
    through. Pass an Arabic token (e.g. ``[أجنبي]``) explicitly.
    """
    replacement = _clean_replacement(mode, placeholder)
    return chars.foreign_span_pattern().sub(lambda _m: replacement, s)


@dataclass(frozen=True, slots=True)
class RemoveForeign:
    """Remove non-Arabic-script letter spans or replace them with a placeholder token — cleaning.

    English: *foreign-span removal*. The standard Arabic corpus-prep filter: for an Arabic corpus,
    embedded foreign words are noise, so a maximal run of non-Arabic-script LETTERS (category L*
    outside the Arabic blocks, with any combining marks riding along — a decomposed ``café``
    travels whole) is `DELETE`d (default) or, in `PLACEHOLDER` mode, replaced by the `placeholder`
    token (default the English ``[FOREIGN]``; pass ``[أجنبي]`` explicitly). A span must START with
    a letter, so a lone combining mark — the VS16 after an emoji, a stray accent — never opens a
    span and emoji are untouched. Digits, punctuation, whitespace and symbols pass through: this
    filters foreign WORDS, not structure (`RemovePunctuation` / `MapDigits` own those concerns).

    `safety` is `CLEANING`: for the Arabic-corpus contract, non-Arabic-script content is
    surrounding noise like a URL, not an Arabic-internal distinction (ADR-0011) — and like every
    cleaning step it is opt-in, never under `LIGHT`. Deletion leaves whitespace gaps; a later
    `CollapseWhitespace` tidies them. A contextual rule over a UCD-derived span pattern (built
    lazily, once per process), so it stays its own pass (ADR-0006).
    """

    mode: CleanMode = CleanMode.DELETE
    placeholder: str = "[FOREIGN]"
    # Precomputed at construction so __call__ does no setup (ADR-0003/0006); excluded from equality
    # and repr since they derive from `mode`/`placeholder` (the pattern from the process-wide UCD
    # scan).
    _replacement: str = field(init=False, repr=False, compare=False)
    _pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)
    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.CLEANING
    name: ClassVar[str] = "RemoveForeign"

    def __post_init__(self) -> None:
        mode = CleanMode(self.mode)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "_replacement", _clean_replacement(mode, self.placeholder))
        object.__setattr__(self, "_pattern", chars.foreign_span_pattern())

    def __call__(self, s: str, /) -> str:
        replacement = self._replacement
        return self._pattern.sub(lambda _m: replacement, s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        repl = self._replacement
        normalized, spans, rep_lens = _collect_regex_sub(s, self._pattern, lambda _m: repl)
        return normalized, OffsetMap.from_regex_sub(s, spans, rep_lens)

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


registry.register(RemoveForeign.name, RemoveForeign.from_dict)


def trim(s: str, /) -> str:
    """Strip leading and trailing whitespace — lossless encoding repair."""
    return s.strip()


@dataclass(frozen=True, slots=True)
class Trim:
    """Strip leading and trailing whitespace — lossless encoding repair.

    English: *trimming*. `CollapseWhitespace` deliberately does NOT trim — collapsing an edge run
    in place is what keeps it a fixed point — so edge whitespace survives every profile. This
    separate, explicit step removes it (``str.strip()``, so every Unicode whitespace counts),
    keeping both contracts clean: collapse stays a fixed point, trim is its own idempotent
    operation a caller composes when wanted. Edge whitespace carries no linguistic signal, so
    `safety` is `ENCODING_REPAIR`. Positional (start/end), hence contextual — its own pass, not a
    0018 fusion candidate.
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.ENCODING_REPAIR
    name: ClassVar[str] = "Trim"

    def __call__(self, s: str, /) -> str:
        return trim(s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        normalized = s.strip()
        if not normalized:
            return normalized, OffsetMap([])
        lead = len(s) - len(s.lstrip())
        o: list[int] = []
        for i in range(len(normalized)):
            o.append(lead + i)
            o.append(lead + i + 1)
        return normalized, OffsetMap(o)

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(Trim.name, Trim.from_dict)


def map_quotes(s: str, /) -> str:
    """Fold typographic quotes (« » " " ' ' …) to straight ASCII quotes — lossy folding."""
    return s.translate(chars.MAP_QUOTES)


@dataclass(frozen=True, slots=True)
class MapQuotes:
    """Fold typographic quotation marks to the straight ASCII pair — lossy linguistic folding.

    English: *quote normalization*. Arabic text quotes with guillemets «», and word processors
    emit the curly/low-9 variants; folding them all to ``"`` / ``'`` (by visual family — double
    to double, single to single) gives a tokenizer one quote vocabulary. It erases the quote
    style, so `safety` is `LINGUISTIC_FOLDING`: opt-in via an explicit step, never under `LIGHT`
    and in no built-in profile. One `str.translate` pass, so it is fusible (0018).
    """

    # Unannotated class attribute (not a dataclass field): matches `Step.safety`, as a custom step.
    safety = SafetyClass.LINGUISTIC_FOLDING
    name: ClassVar[str] = "MapQuotes"

    def __call__(self, s: str, /) -> str:
        return map_quotes(s)

    def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]:
        return _aligned_from_translate(s, self.translate_table)

    @property
    def translate_table(self) -> dict[int, str]:
        """The static `str.translate` table this step applies — the fused-engine seam (0018)."""
        return chars.MAP_QUOTES

    def to_dict(self) -> StepDict:
        return {"name": self.name, "config": {}}

    @classmethod
    def from_dict(cls, config: Mapping[str, Any]) -> Self:
        return cls(**config)


registry.register(MapQuotes.name, MapQuotes.from_dict)
