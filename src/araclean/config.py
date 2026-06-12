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
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import BaseModel, ConfigDict, Field

from araclean.profiles import Profile, StepSpec, get_profile
from araclean.steps import CleanMode, EmojiMode, HashtagMode, MarkClass, TehMarbutaTarget

if TYPE_CHECKING:
    from collections.abc import Collection


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
# A knob that matches more than one spec (collapse_lines, in the lossy profiles) patches them ALL —
# the knob speaks about the behavior, not about one copy of the step. `map_digits` and
# `remove_stopwords` are handled apart: they APPEND/INSERT a step rather than patching one.
_STEP_PATCHES: tuple[tuple[str, str, str], ...] = (
    ("emoji", "HandleEmoji", "mode"),
    ("elongation_cap", "ReduceElongation", "cap"),
    ("url_mode", "CleanURLs", "mode"),
    ("url_token", "CleanURLs", "placeholder"),
    ("mention_mode", "CleanMentions", "mode"),
    ("mention_token", "CleanMentions", "placeholder"),
    ("hashtag_mode", "CleanHashtags", "mode"),
    ("hashtag_token", "CleanHashtags", "placeholder"),
    ("teh_marbuta", "FoldTehMarbuta", "target"),
    ("tashkeel_classes", "RemoveTashkeel", "classes"),
    ("collapse_lines", "CollapseWhitespace", "collapse_lines"),
)


def _config_value(value: object) -> object:
    """Render an override value into the JSON-friendly form a `StepSpec` config carries: a StrEnum
    becomes its string value, a collection of StrEnums a sorted list of values, scalars pass."""
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, frozenset | set | tuple | list):
        members = cast("Collection[object]", value)
        return sorted(
            member.value if isinstance(member, StrEnum) else str(member) for member in members
        )
    return value


class NormalizeConfig(BaseModel):
    """A validated `normalize` call: a profile plus optional per-knob overrides (stories 39/40).

    Frozen and `extra="forbid"`, so a typo'd knob (`map_digit=` for `map_digits=`) or an unknown
    option value fails loudly at construction instead of silently doing nothing — a reproducibility
    footgun the trust boundary exists to close. Each override is `None` by default, meaning "use the
    profile's own default for that step"; setting one rewrites exactly that step when `resolve()`
    assembles the effective `Profile`.

    The override surface is the profile name **plus** per-knob scalars (the shape issue 0016 fixes):
    `map_digits` is ML's optional digit fold (story 6) and is valid ONLY with ML — it appends a
    lossy step, which on any other profile would silently break that profile's contract (LIGHT/
    CLASSICAL are lossless; SEARCH already folds digits). `remove_stopwords` is SEARCH's optional
    stopword removal — valid only there, because the folded list requires exactly SEARCH's letter
    folds before it (the `RemoveStopwords` ordering contract). The remaining knobs patch a step the
    profile carries; an override that names a step the chosen profile does not contain is rejected
    by `resolve()`, so it can never be a silent no-op.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: ProfileName = ProfileName.LIGHT

    # ML (story 6): the optional digit fold, OFF by default so ML keeps every letter distinction.
    # When True it APPENDS MapDigits (→ ASCII, its default target) to the resolved pipeline.
    # ML-only: on any other profile it would be a silent contract change (or a no-op), so it is
    # rejected by resolve().
    map_digits: bool = False

    # SEARCH: optional stopword removal, OFF by default. When True it INSERTS RemoveStopwords after
    # the letter folds (just before the closing whitespace/NFC tail, so removal gaps are tidied).
    # SEARCH-only: the folded stopword list requires exactly the folds SEARCH applies.
    remove_stopwords: bool = False

    # SOCIAL (story 7): each rewrites one step's config when set; left None, the step keeps its
    # profile default. `elongation_cap` reuses ReduceElongation's own >= 1 constraint.
    emoji: EmojiMode | None = None
    elongation_cap: Annotated[int, Field(ge=1)] | None = None
    url_mode: CleanMode | None = None
    url_token: str | None = None
    mention_mode: CleanMode | None = None
    mention_token: str | None = None
    hashtag_mode: HashtagMode | None = None
    hashtag_token: str | None = None

    # SEARCH/ML/SOCIAL: which teh-marbuta target / tashkeel mark classes the profile's fold uses.
    teh_marbuta: TehMarbutaTarget | None = None
    tashkeel_classes: frozenset[MarkClass] | None = None

    # Any profile (every profile carries CollapseWhitespace): preserve or flatten line structure
    # (ADR-0010). Patches EVERY CollapseWhitespace copy, so e.g. collapse_lines=False gives "SEARCH
    # but keep line structure". Note that collapse_lines=True flattens lines under an otherwise
    # lossless profile — an explicit, audit-visible choice.
    collapse_lines: bool | None = None

    def resolve(self) -> Profile:
        """Assemble the effective `Profile`: the named preset with this config's overrides applied.

        Pure construction (no per-string work): it patches the matching step specs, appends ML's
        optional `MapDigits` and inserts SEARCH's optional `RemoveStopwords`. Raises `ValueError`
        if an override names a step the profile lacks (e.g. `emoji=` on `LIGHT`) or a profile that
        does not own it (`map_digits` off ML, `remove_stopwords` off SEARCH), so an override is
        never a silent no-op.
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
                    config[key] = _config_value(value)
                    applied.add(attr)
            steps.append(StepSpec(name=spec.name, config=config))

        if self.map_digits:
            if self.profile is not ProfileName.ML:
                raise ValueError(
                    f"map_digits applies to the 'ml' profile only (its documented owner), not "
                    f"{self.profile.value!r}: it appends a lossy digit fold, which would silently "
                    "change this profile's contract (SEARCH already folds digits). Use "
                    "profile='ml', or compose an explicit Pipeline with MapDigits."
                )
            # Append the optional digit fold; the appended step uses its default (ASCII) target.
            steps.append(StepSpec(name="MapDigits"))

        if self.remove_stopwords:
            if self.profile is not ProfileName.SEARCH:
                raise ValueError(
                    f"remove_stopwords applies to the 'search' profile only, not "
                    f"{self.profile.value!r}: the folded stopword list requires exactly the "
                    "letter folds SEARCH runs before it (RemoveTashkeel, FoldAlef, "
                    "FoldAlefMaqsura, FoldHamza). Use profile='search', or compose an explicit "
                    "Pipeline with those folds."
                )
            # Insert just before the closing CollapseWhitespace + NormalizeUnicode tail: after
            # every fold (the ordering contract) and before the tail so removal gaps are tidied.
            # A removed EDGE stopword leaves a gap the collapse can only shrink to one space
            # (collapse, not trim — its fixed-point contract), so a closing Trim finishes the job.
            steps.insert(len(steps) - 2, StepSpec(name="RemoveStopwords"))
            steps.append(StepSpec(name="Trim"))

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
