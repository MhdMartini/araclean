"""The configuration trust boundary (ADR-0003): validate untrusted input, then build a `Profile`.

`NormalizeConfig` is the pydantic v2 model the `normalize` facade validates a call against — a
profile name plus a small set of per-knob overrides. It is the seam between untrusted input and
the validation-free core: every option is a closed set (`StrEnum`) or a bounded scalar, so a bad
value is rejected here with a clear pydantic error and never reaches the per-string hot path.

`resolve()` turns a validated config into an effective `Profile` (the named preset with its
overrides applied), so the same config both *runs* and *serializes* — a paper can publish the
exact preprocessing it used (story 40) including the overrides, and others reproduce it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from araclean.profiles import Profile, StepSpec, get_profile
from araclean.steps import CleanMode, EmojiMode


class ProfileName(StrEnum):
    """The closed set of named profiles `normalize` accepts (story 39).

    A `StrEnum` so an unknown profile name is rejected at the config boundary with a clear error,
    rather than only when the pipeline is assembled.
    """

    LIGHT = "light"
    SEARCH = "search"
    ML = "ml"
    CLASSICAL = "classical"
    SOCIAL = "social"


# Each per-knob override patches the config of exactly one step in the resolved profile, addressed
# by its registry name. (attribute on NormalizeConfig, step name, the step-config key it sets.)
# `map_digits` is handled apart: it APPENDS a step rather than patching one, so it is not here.
_STEP_PATCHES: tuple[tuple[str, str, str], ...] = (
    ("emoji", "HandleEmoji", "mode"),
    ("elongation_cap", "ReduceElongation", "cap"),
    ("url_mode", "CleanURLs", "mode"),
    ("url_token", "CleanURLs", "placeholder"),
    ("mention_mode", "CleanMentions", "mode"),
    ("mention_token", "CleanMentions", "placeholder"),
)


class NormalizeConfig(BaseModel):
    """A validated `normalize` call: a profile plus optional per-knob overrides (stories 39/40).

    Frozen and `extra="forbid"`, so a typo'd knob (`map_digit=` for `map_digits=`) or an unknown
    option value fails loudly at construction instead of silently doing nothing — a reproducibility
    footgun the trust boundary exists to close. Each override is `None` by default, meaning "use the
    profile's own default for that step"; setting one rewrites exactly that step when `resolve()`
    assembles the effective `Profile`.

    The override surface is the profile name **plus** per-knob scalars (the shape issue 0016 fixes):
    `map_digits` is ML's optional digit fold (story 6); `emoji` / `elongation_cap` / the URL &
    mention `*_mode` + `*_token` knobs are SOCIAL's (story 7). An override that names a step the
    chosen profile does not contain is rejected by `resolve()`, so it can never be a silent no-op.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: ProfileName = ProfileName.LIGHT

    # ML (story 6): the optional digit fold, OFF by default so ML keeps every letter distinction.
    # When True it APPENDS MapDigits (→ ASCII, its default target) to the resolved pipeline.
    map_digits: bool = False

    # SOCIAL (story 7): each rewrites one step's config when set; left None, the step keeps its
    # profile default. `elongation_cap` reuses ReduceElongation's own >= 1 constraint.
    emoji: EmojiMode | None = None
    elongation_cap: Annotated[int, Field(ge=1)] | None = None
    url_mode: CleanMode | None = None
    url_token: str | None = None
    mention_mode: CleanMode | None = None
    mention_token: str | None = None

    def resolve(self) -> Profile:
        """Assemble the effective `Profile`: the named preset with this config's overrides applied.

        Pure construction (no per-string work): it patches the matching step specs and, if
        `map_digits` is set, appends a `MapDigits` step. Raises `ValueError` if an override names a
        step the profile lacks (e.g. `emoji=` on `LIGHT`), so an override is never a silent no-op.
        """
        base = get_profile(self.profile.value)
        applied: set[str] = set()
        steps: list[StepSpec] = []
        for spec in base.steps:
            config = dict(spec.config)
            for attr, step_name, key in _STEP_PATCHES:
                if spec.name != step_name:
                    continue
                value = getattr(self, attr)
                if value is not None:
                    config[key] = value.value if isinstance(value, StrEnum) else value
                    applied.add(attr)
            steps.append(StepSpec(name=spec.name, config=config))

        if self.map_digits and not any(spec.name == "MapDigits" for spec in steps):
            # Append the optional digit fold (ML's knob); the appended step uses its default target.
            steps.append(StepSpec(name="MapDigits"))

        unapplied = [
            attr
            for attr, _step_name, _key in _STEP_PATCHES
            if getattr(self, attr) is not None and attr not in applied
        ]
        if unapplied:
            raise ValueError(
                f"override(s) {sorted(set(unapplied))} do not apply to profile "
                f"{self.profile.value!r}: it has no matching step to configure."
            )
        return Profile(name=base.name, steps=steps)
