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
        return Pipeline.from_profile(config.resolve())(text)
    if isinstance(profile, Profile):
        if overrides:
            raise TypeError(
                "normalize(): **overrides require a profile name (a str), not a Profile object; "
                "build the Profile with the steps you want instead."
            )
        return Pipeline.from_profile(profile)(text)
    # profile is a name (or None -> LIGHT): build_pipeline runs the full pydantic boundary over the
    # untrusted name + overrides (rejecting an unknown name, knob, or value) before any work, so the
    # validation-free core never sees an invalid option.
    return build_pipeline(profile, overrides)(text)


def build_pipeline(profile: str | None, overrides: dict[str, object]) -> Pipeline:
    """Validate a profile name + overrides at the trust boundary and assemble the pipeline once.

    The single source of truth behind the `normalize` facade's name-branch and the CLI/pandas/polars
    adapters (ADR-0003): `model_validate` runs the full pydantic boundary over the untrusted name +
    overrides before any work happens, so the validation-free core (`pipe(text)`, the bare step
    functions) never sees an invalid option. `profile=None` selects `LIGHT`. Assembling once (not
    per line/row/string) keeps the hot path validation-free.

    Raises `ValidationError` for a bad option value (or an empty/unknown profile name), `ValueError`
    for an override that does not apply to the profile (from `resolve()`), and
    `EmojiSupportNotInstalledError` for ``emoji="demojize"`` without the ``[emoji]`` extra — each
    caller catches what it needs to.
    """
    name = profile if profile is not None else LIGHT.name
    config = NormalizeConfig.model_validate({"profile": name, **overrides})
    return Pipeline.from_profile(config.resolve())
