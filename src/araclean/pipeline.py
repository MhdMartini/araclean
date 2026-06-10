"""The composition layer: an ordered, serializable sequence of `Step`s (ADR-0003).

A `Pipeline` is a deep module — a tiny interface (call it like a function; (de)serialize it)
over the whole compose/invoke/persist behavior. It is modeled on HuggingFace `tokenizers`'
`Sequence` of normalizers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from araclean import registry
from araclean.profiles import Profile, get_profile
from araclean.safety import SafetyClass, SafetyReport
from araclean.steps import (
    AlignmentNotSupportedError,
    SerializableStep,
    Step,
    SupportsAlignment,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping, Sequence


class PipelineDict(TypedDict):
    """The serialized form of a `Pipeline`: its ordered steps."""

    steps: list[dict[str, Any]]


def _step_name(step: Step) -> str:
    """The display/selection name of a step: its registry ``name`` if it has one, else the class
    name. Built-in steps expose a ``name`` ClassVar equal to their class name; a user `Step`
    without one is named by its class, so custom steps participate in `repr`/`select` uniformly."""
    name = getattr(step, "name", None)
    return name if isinstance(name, str) else type(step).__name__


class Pipeline:
    """An ordered, serializable sequence of `Step`s, callable like a single `str -> str`."""

    def __init__(self, steps: Sequence[Step]) -> None:
        self._steps: tuple[Step, ...] = tuple(steps)

    @property
    def steps(self) -> tuple[Step, ...]:
        """The ordered steps, for inspection (e.g. the safety-class audit, story 41)."""
        return self._steps

    def __repr__(self) -> str:
        names = ", ".join(_step_name(step) for step in self._steps)
        return f"Pipeline([{names}])"

    def __call__(self, text: str, /) -> str:
        for step in self._steps:
            text = step(text)
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
        `KeyError` for an unknown name, or if a name matches more than one step (ambiguous).
        """
        by_name: dict[str, list[Step]] = {}
        for step in self._steps:
            by_name.setdefault(_step_name(step), []).append(step)
        chosen: list[Step] = []
        for name in names:
            matches = by_name.get(name)
            if not matches:
                raise KeyError(f"No step named {name!r} in this pipeline; have {sorted(by_name)}.")
            if len(matches) > 1:
                raise KeyError(
                    f"Step name {name!r} is ambiguous: it matches {len(matches)} steps. "
                    "select() addresses steps by name, so names must be unique to use it."
                )
            chosen.append(matches[0])
        return Pipeline(chosen)

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

    def apply_aligned(self, text: str, /) -> tuple[str, object]:
        """Reserved offset/alignment entry point — not implemented in v1 (ADR-0005).

        Every step must implement the optional `apply_aligned` hook for this to work; none do
        in v1, so this raises a clear, actionable `AlignmentNotSupportedError` naming the step.
        """
        for step in self._steps:
            if not isinstance(step, SupportsAlignment):
                raise AlignmentNotSupportedError(
                    f"Step {type(step).__name__!r} does not implement apply_aligned(); "
                    "offset/alignment tracking is reserved but not implemented in v1 (ADR-0005)."
                )
        raise AlignmentNotSupportedError(
            "Offset/alignment tracking is reserved but not implemented in v1 (ADR-0005)."
        )

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
