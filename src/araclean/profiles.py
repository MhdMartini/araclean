"""Profiles — named, serializable presets that assemble a `Pipeline` (the trust boundary).

`Profile` and `StepSpec` are pydantic v2 models, so a profile is validated on construction and
can later emit/validate JSON Schema (the reproducibility surface built out in issue 0016). The
named presets (`LIGHT`, …) are defined here in code; `Pipeline.from_profile` rehydrates them.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StepSpec(BaseModel):
    """The serialized spec of one step in a profile: its registry name and constructor config."""

    model_config = ConfigDict(frozen=True)

    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class Profile(BaseModel):
    """A named preset: an ordered list of step specs that assemble into a `Pipeline`."""

    model_config = ConfigDict(frozen=True)

    name: str
    steps: list[StepSpec]


# The default profile: lossless encoding repair only. For now just NFC; it grows in 0003/0004.
LIGHT = Profile(
    name="light",
    steps=[StepSpec(name="NormalizeUnicode", config={"form": "NFC"})],
)

_PROFILES: dict[str, Profile] = {LIGHT.name: LIGHT}


def get_profile(name: str) -> Profile:
    """Look up a named profile (case-insensitive on the canonical name), or raise a clear error."""
    try:
        return _PROFILES[name.lower()]
    except KeyError:
        raise ValueError(f"Unknown profile {name!r}; known profiles: {sorted(_PROFILES)}") from None
