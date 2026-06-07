"""The composition layer: an ordered, serializable sequence of `Step`s (ADR-0003).

A `Pipeline` is a deep module — a tiny interface (call it like a function; (de)serialize it)
over the whole compose/invoke/persist behavior. It is modeled on HuggingFace `tokenizers`'
`Sequence` of normalizers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from araclean import registry
from araclean.profiles import Profile, get_profile
from araclean.steps import (
    AlignmentNotSupportedError,
    SerializableStep,
    Step,
    SupportsAlignment,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class PipelineDict(TypedDict):
    """The serialized form of a `Pipeline`: its ordered steps."""

    steps: list[dict[str, Any]]


class Pipeline:
    """An ordered, serializable sequence of `Step`s, callable like a single `str -> str`."""

    def __init__(self, steps: Sequence[Step]) -> None:
        self._steps: tuple[Step, ...] = tuple(steps)

    @property
    def steps(self) -> tuple[Step, ...]:
        """The ordered steps, for inspection (e.g. the safety-class audit, story 41)."""
        return self._steps

    def __call__(self, text: str, /) -> str:
        for step in self._steps:
            text = step(text)
        return text

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
