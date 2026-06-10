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


# The default profile: lossless encoding repair only, now complete (0002-0004). Step order follows
# the PRD ordering contract -- Unicode form -> strip invisibles -> fold presentation forms ->
# remove tatweel -> unify look-alike letters -> collapse whitespace (line breaks kept, ADR-0010).
#
# Two load-bearing ordering constraints:
#
#   1. FoldPresentationForms BEFORE RemoveTatweel: the medial-form tashkeel glyphs decompose to
#      tatweel + mark, so the fold must run first for RemoveTatweel to clean the stray tatweel.
#
#   2. NormalizeUnicode (NFC) runs FIRST *and* LAST. Both passes are needed, and they do different
#      jobs (this is the surprising part -- do not "simplify" by dropping either):
#        - The opening NFC composes the input so every later step sees canonical text.
#        - But two of those steps can *create* a non-canonical combining sequence that the opening
#          NFC has already passed and cannot fix: FoldPresentationForms expands a ligature into
#          `base + combining mark`, and StripBidi deletes a format char (e.g. a BOM) that was
#          separating two marks -- either move can leave two combining marks adjacent in the wrong
#          canonical order. Without a closing NFC the output is then not NFC, `normalize` is not
#          idempotent, and an OCR'd ligature fails to match its hand-typed spelling.
#      The closing NFC re-applies canonical ordering, making "output is NFC" a pipeline
#      postcondition. It is lossless: araclean treats canonically-equivalent sequences as the same
#      text, so reordering marks into canonical order never loses signal (ADR-0009). It sits dead
#      last; CollapseWhitespace only emits ASCII spaces, which are NFC-stable, so the two never
#      interfere.
LIGHT = Profile(
    name="light",
    steps=[
        StepSpec(name="NormalizeUnicode", config={"form": "NFC"}),
        StepSpec(name="StripBidi"),
        StepSpec(name="FoldPresentationForms"),
        StepSpec(name="RemoveTatweel"),
        StepSpec(name="UnifyLookalikes"),
        StepSpec(name="CollapseWhitespace"),
        StepSpec(name="NormalizeUnicode", config={"form": "NFC"}),
    ],
)

# SEARCH: maximize recall by composing every lossy fold on top of LIGHT's encoding repair, in the
# PRD ordering contract -- encoding repair -> tashkeel removal -> letter folding ->
# digit/punctuation mapping -> cleanup. Spelling/vocalization distinctions that split
# otherwise-identical words are deliberately collapsed (على == علي, مدرسة == مدرسه, ١٢٣ == 123),
# so every added step is
# LINGUISTIC_FOLDING -- SEARCH is lossy and opt-in (ADR-0004), never the default.
#
# It is defined as LIGHT's steps verbatim plus the folds, so "SEARCH does everything LIGHT does"
# (search ⊇ light) holds by construction: LIGHT(SEARCH(x)) == SEARCH(x). Each fold uses its step
# default, which is exactly what SEARCH wants -- RemoveTashkeel removes every mark class, MapDigits
# targets ASCII, FoldTehMarbuta targets heh, ReduceElongation caps at 1 -- so no config is pinned
# here. No closing NFC pass is appended: the folds only delete marks or rewrite a base letter to
# another base letter, and the only NFC-composing Arabic marks (madda U+0653, hamza U+0654/U+0655)
# are deleted by RemoveTashkeel / FoldHamza, so SEARCH's output is already NFC. That postcondition
# is pinned by the LIGHT-stability property test rather than asserted by a redundant pass.
SEARCH = Profile(
    name="search",
    steps=[
        *LIGHT.steps,
        StepSpec(name="RemoveTashkeel"),  # all mark classes (harakat/tanween/shadda/madda/...)
        StepSpec(name="FoldAlef"),
        StepSpec(name="FoldHamza"),
        StepSpec(name="FoldTehMarbuta"),  # -> heh (default target)
        StepSpec(name="FoldAlefMaqsura"),
        StepSpec(name="MapDigits"),  # -> ASCII (default target)
        StepSpec(name="MapPunctuation"),  # -> Latin , ; ?
        StepSpec(name="ReduceElongation"),  # cap 1 (default)
    ],
)

_PROFILES: dict[str, Profile] = {LIGHT.name: LIGHT, SEARCH.name: SEARCH}


def get_profile(name: str) -> Profile:
    """Look up a named profile (case-insensitive on the canonical name), or raise a clear error."""
    try:
        return _PROFILES[name.lower()]
    except KeyError:
        raise ValueError(f"Unknown profile {name!r}; known profiles: {sorted(_PROFILES)}") from None
