"""Layer 3 — the one-call `normalize` facade (a thin adapter over `Pipeline`, ADR-0003).

This is the public trust boundary: `@validate_call` validates the call (the profile name, the
overrides) against `NormalizeConfig` before any work happens, so a bad option is rejected here with
a clear error and the validation-free core (`pipe(text)`, `pipe.batch()`, the bare step functions)
never validates per string (ADR-0003). The facade assembles the effective `Pipeline` once per call
and runs it.
"""

from __future__ import annotations

from pydantic import validate_call

from araclean.config import NormalizeConfig
from araclean.pipeline import Pipeline
from araclean.profiles import LIGHT, Profile


@validate_call
def normalize(
    text: str,
    *,
    profile: str | Profile | None = None,
    config: NormalizeConfig | None = None,
    **overrides: object,
) -> str:
    """Normalize Arabic text with a named profile (default `LIGHT` — lossless encoding repair).

    `profile=None` applies `LIGHT`. Pass ``profile="search"`` (etc.) for a named preset, a `Profile`
    object for a fully custom pipeline, or per-knob `**overrides` to tune a named profile —
    ``normalize(text, profile="ml", map_digits=True)`` folds digits, ``profile="social",
    emoji="strip"`` drops emoji. Overrides are validated against `NormalizeConfig`, so an unknown
    knob or a bad value is rejected here. A prebuilt `config=NormalizeConfig(...)` may be passed
    instead, but not together with `profile`/overrides.
    """
    if config is not None:
        if profile is not None or overrides:
            raise TypeError("normalize(): pass either `config=` or `profile=`/overrides, not both.")
        effective: Profile = config.resolve()
    elif isinstance(profile, Profile):
        if overrides:
            raise TypeError(
                "normalize(): **overrides require a profile name (a str), not a Profile object; "
                "build the Profile with the steps you want instead."
            )
        effective = profile
    else:
        # profile is a name (or None -> LIGHT). model_validate runs the full pydantic boundary over
        # the untrusted name + overrides (rejecting an unknown name, knob, or value), so the
        # validation-free core never sees an invalid option.
        data: dict[str, object] = {"profile": profile or LIGHT.name, **overrides}
        effective = NormalizeConfig.model_validate(data).resolve()
    return Pipeline.from_profile(effective)(text)
