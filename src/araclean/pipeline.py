"""The composition layer: an ordered, serializable sequence of `Step`s (ADR-0003).

A `Pipeline` is a deep module — a tiny interface (call it like a function; (de)serialize it)
over the whole compose/invoke/persist behavior. It is modeled on HuggingFace `tokenizers`'
`Sequence` of normalizers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from araclean import fusion, registry
from araclean.offsets import OffsetMap
from araclean.profiles import Profile, get_profile
from araclean.safety import SafetyClass, SafetyReport
from araclean.steps import (
    AlignmentNotSupportedError,
    SerializableStep,
    Step,
    SupportsAlignment,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence


class PipelineDict(TypedDict):
    """The serialized form of a `Pipeline`: its ordered steps."""

    steps: list[dict[str, Any]]


def _step_name(step: Step) -> str:
    """The display/selection name of a step: its registry ``name`` if it has one, else the class
    name. Built-in steps expose a ``name`` ClassVar equal to their class name; a user `Step`
    without one is named by its class, so custom steps participate in `repr`/`select` uniformly."""
    name = getattr(step, "name", None)
    return name if isinstance(name, str) else type(step).__name__


def _check_step_ordering(steps: Sequence[Step]) -> None:
    """Enforce each step's declared ordering contract at construction (fail fast, not per string).

    A step may declare ``requires_before`` — a tuple of step names that must appear EARLIER in the
    pipeline (e.g. `RemoveStopwords` requires the folds its folded list assumes). The check is
    generic: any step, custom ones included, can declare it.
    """
    seen: set[str] = set()
    for step in steps:
        required: tuple[str, ...] = getattr(step, "requires_before", ())
        missing = [name for name in required if name not in seen]
        if missing:
            raise ValueError(
                f"Step {_step_name(step)!r} requires {missing} to run before it in the pipeline "
                "(its matching assumes their transforms have been applied — see the step's "
                "docstring for the recipe). Add the missing step(s) earlier; they are idempotent, "
                "so including them is safe even for already-normalized text."
            )
        seen.add(_step_name(step))


class Pipeline:
    """An ordered, serializable sequence of `Step`s, callable like a single `str -> str`."""

    def __init__(self, steps: Sequence[Step]) -> None:
        self._steps: tuple[Step, ...] = tuple(steps)
        _check_step_ordering(self._steps)
        # Compile the execution plan once: maximal runs of consecutive single-char `str.translate`
        # steps fuse into one combined table applied in a single C-level pass (issue 0018), while
        # the contextual steps stay their own pass, in order. This is purely an execution
        # optimization behind the fixed interface -- `_steps` remains the source of truth for
        # repr/select/audit/to_dict, so the plan changes nothing observable (ADR-0006).
        self._plan: tuple[Callable[[str], str], ...] = fusion.build_plan(self._steps)

    @property
    def steps(self) -> tuple[Step, ...]:
        """The ordered steps, for inspection (e.g. the safety-class audit, story 41)."""
        return self._steps

    def __repr__(self) -> str:
        names = ", ".join(_step_name(step) for step in self._steps)
        return f"Pipeline([{names}])"

    def __call__(self, text: str, /) -> str:
        for op in self._plan:
            text = op(text)
        return text

    def batch(self, texts: Iterable[str]) -> Iterator[str]:
        """Normalize each text lazily — a streaming generator, so a corpus larger than memory
        (or an unbounded stream) processes without materializing the input (story 13)."""
        for text in texts:
            yield self(text)

    def select(self, *names: str) -> Pipeline:
        """Build a NEW pipeline holding exactly the named steps, in the order given (story 16).

        One primitive covers both adapting operations: name a subset to *filter*, or name every
        step in a different order to *reorder*. Steps are addressed by `_step_name` (the registry
        name, or the class name for a custom step). This pipeline is left unchanged. Raises
        `KeyError` for an unknown name, or if a name matches more than one step *with differing
        configs* (genuinely ambiguous). EQUAL duplicates are interchangeable, not ambiguous —
        every profile runs its `NormalizeUnicode` NFC bookends as identical value objects, so
        naming ``"NormalizeUnicode"`` (once, or once per copy you want) just works; only a name
        whose duplicates differ (SEARCH's two differently-configured `CollapseWhitespace`) is
        rejected, because a name cannot say which one you meant.
        """
        by_name: dict[str, list[Step]] = {}
        for step in self._steps:
            by_name.setdefault(_step_name(step), []).append(step)
        chosen: list[Step] = []
        for name in names:
            matches = by_name.get(name)
            if not matches:
                raise KeyError(f"No step named {name!r} in this pipeline; have {sorted(by_name)}.")
            if any(match != matches[0] for match in matches[1:]):
                raise KeyError(
                    f"Step name {name!r} is ambiguous: it matches {len(matches)} differently-"
                    "configured steps, and a name cannot say which one you meant. Use drop() to "
                    "remove steps by name, or build the Pipeline from explicit steps."
                )
            chosen.append(matches[0])
        return Pipeline(chosen)

    def drop(self, *names: str) -> Pipeline:
        """Build a NEW pipeline WITHOUT every step matching each name (the subtractive adapter).

        The common profile adaptation — "SEARCH minus `MapDigits`" — is subtraction, which
        `select` cannot express on a built-in profile without re-naming every kept step. `drop`
        removes ALL steps carrying a name (removing every match is well-defined, so duplicates
        need no disambiguation) and keeps the rest in order. This pipeline is left unchanged.
        Raises `KeyError` for a name no step carries, so a typo is never a silent no-op.
        """
        present = {_step_name(step) for step in self._steps}
        unknown = [name for name in names if name not in present]
        if unknown:
            raise KeyError(
                f"No step named {unknown[0]!r} in this pipeline; have {sorted(present)}."
            )
        dropped = set(names)
        return Pipeline([step for step in self._steps if _step_name(step) not in dropped])

    def audit(self) -> SafetyReport:
        """Audit this pipeline's safety: is it lossless, and if not, what it loses (story 41).

        Pure in-process computation: it reads each step's declared `safety` (fixed at construction)
        and buckets the step names by class, so an auditor can verify a pipeline is lossless or
        enumerate exactly the lossy steps it carries. The buckets preserve pipeline order.
        """
        buckets: dict[SafetyClass, list[str]] = {safety_class: [] for safety_class in SafetyClass}
        for step in self._steps:
            buckets[step.safety].append(_step_name(step))
        return SafetyReport(
            encoding_repair=tuple(buckets[SafetyClass.ENCODING_REPAIR]),
            linguistic_folding=tuple(buckets[SafetyClass.LINGUISTIC_FOLDING]),
            cleaning=tuple(buckets[SafetyClass.CLEANING]),
        )

    def apply_aligned(self, text: str, /) -> tuple[str, OffsetMap]:
        """Normalize *text* while tracking how every position maps back to the original.

        Returns ``(normalized, offset_map)`` where ``offset_map.to_original(span)`` projects
        any span in the normalized string back to the corresponding span in *text*.

        Raises ``AlignmentNotSupportedError`` for any custom step that does not implement
        ``apply_aligned()`` — the error names the offending step so the caller can add the hook.
        """
        current = text
        running: OffsetMap | None = None
        for step in self._steps:
            if not isinstance(step, SupportsAlignment):
                raise AlignmentNotSupportedError(
                    f"Step {type(step).__name__!r} does not implement apply_aligned(); "
                    "add apply_aligned() to the step to use offset-preserving normalization."
                )
            normalized, step_map = step.apply_aligned(current)
            running = step_map if running is None else running.compose(step_map)
            current = normalized
        if running is None:
            running = OffsetMap.identity(len(text))
        return current, running

    def to_dict(self) -> PipelineDict:
        """Serialize to a plain, JSON-friendly dict; raises if a step can't serialize itself."""
        steps: list[dict[str, Any]] = []
        for step in self._steps:
            if not isinstance(step, SerializableStep):
                raise TypeError(
                    f"Cannot serialize {step!r}: it has no to_dict(). Give the step a to_dict()"
                    " (and register it) to serialize a pipeline containing it."
                )
            steps.append(dict(step.to_dict()))
        return {"steps": steps}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Pipeline:
        """Rehydrate a pipeline from `to_dict()` output via the step registry."""
        steps = [registry.build(s["name"], s.get("config", {})) for s in data["steps"]]
        return cls(steps)

    @classmethod
    def from_profile(cls, profile: str | Profile) -> Pipeline:
        """Build a pipeline from a named profile (e.g. ``"light"``) or a `Profile` object."""
        resolved = get_profile(profile) if isinstance(profile, str) else profile
        steps = [registry.build(spec.name, spec.config) for spec in resolved.steps]
        return cls(steps)
