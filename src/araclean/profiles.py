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


# --- The shared closing tail of the lossy profiles -----------------------------------------------
#
# The three lossy profiles below (SEARCH, ML, SOCIAL) each END WITH THE SAME TAIL as LIGHT -- a
# CollapseWhitespace then an NFC pass -- re-applied AFTER their own folds. It is load-bearing, not
# redundant: LIGHT's copies of those two steps run mid-pipeline (inside the embedded *LIGHT.steps),
# and the folds that follow can undo the postcondition each established:
#
#   - WHITESPACE. FoldPresentationForms (a per-glyph NFKC fold) expands the isolated-form tashkeel
#     ligatures to a mark on a SPACE carrier -- NFKC(U+FC5E) = space + dammatan + shadda -- so a
#     mark can sit between two spaces; RemoveTashkeel / FoldHamza then delete it, and SOCIAL's
#     cleaning deletes whole spans, each leaving two spaces adjacent. The closing CollapseWhitespace
#     re-collapses them (reusing LIGHT's line-preserving config, so line structure is unchanged).
#   - CANONICAL ORDER. Deleting a *blocking* combining mark can EXPOSE a composition the
#     mid-pipeline NFC already passed: NFC(alef + Qur'anic mark U+06DC + hamza U+0654) keeps the
#     alef bare (the mark blocks the alef+hamza compose), but RemoveTashkeel strips that blocker and
#     leaves alef + combining hamza, which is NOT NFC. SEARCH's FoldHamza deletes the hamza too, but
#     ML/SOCIAL keep it -- so rather than reason per profile about which composable marks each fold
#     leaves behind (easy to get wrong), every profile simply re-canonicalizes with a closing NFC.
#
# The result is one uniform postcondition -- every profile's output is whitespace-collapsed NFC, by
# construction -- pinned by the idempotence / LIGHT-stability property tests (with the U+FC5E,
# floating-hamza and exposed-hamza inputs as explicit examples), not by a per-profile argument.
# -------------------------------------------------------------------------------------------------

# SEARCH: maximize recall by composing every lossy fold on top of LIGHT's encoding repair, in the
# PRD ordering contract -- encoding repair -> tashkeel removal -> letter folding ->
# digit/punctuation mapping -> cleanup. Spelling/vocalization distinctions that split
# otherwise-identical words are deliberately collapsed (على == علي, مدرسة == مدرسه, ١٢٣ == 123),
# so every added step is
# LINGUISTIC_FOLDING -- SEARCH is lossy and opt-in (ADR-0004), never the default.
#
# It is defined as LIGHT's steps verbatim, then the folds, then the shared closing tail (see the
# note above). So search ⊇ light -- "SEARCH does everything LIGHT does", LIGHT(SEARCH(x)) ==
# SEARCH(x). Each fold uses its step default, which is exactly what SEARCH wants -- RemoveTashkeel
# removes every mark class, MapDigits targets ASCII, FoldTehMarbuta targets heh, ReduceElongation
# caps at 1 -- so no config is pinned here.
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
        # Shared closing tail (see the note above): re-collapse whitespace the folds re-expose, then
        # re-canonicalize. Sits last, after every fold.
        StepSpec(name="CollapseWhitespace"),
        StepSpec(name="NormalizeUnicode", config={"form": "NFC"}),
    ],
)

# ML: clean text for model input while staying CONSERVATIVE ON LETTERS. It strips noise that only
# hurts a tokenizer -- vocalization (RemoveTashkeel) and emphatic word-lengthening
# (ReduceElongation) -- but, unlike SEARCH, it PRESERVES every alef/hamza/alef-maqsura/teh-marbuta
# distinction, because those variants are disambiguating: the AraToken finding is that aggressive
# letter folding raises language-model loss (على != علي carries real signal). So ML composes none
# of the 0007 letter folds and neither digit nor punctuation map -- it sits strictly between LIGHT
# and SEARCH (LIGHT ⊆ ML ⊊ SEARCH on what it removes).
#
# Like SEARCH, ML is defined as LIGHT's steps verbatim, then its two folds, then the shared closing
# tail (see the note above), so "ML does everything LIGHT does" (ML ⊇ LIGHT, LIGHT(ML(x)) == ML(x))
# holds. Each fold uses its step default (RemoveTashkeel removes every mark class; ReduceElongation
# caps at 1 -- the maximal collapse a model-input pipeline wants), so no config is pinned here.
# Ordering follows the PRD contract: encoding repair -> tashkeel removal -> elongation cleanup.
# RemoveTashkeel runs BEFORE ReduceElongation so that marks between repeated letters (e.g. a
# vocalized elongation) are gone first, leaving the letters adjacent for the cap to collapse. ML
# keeps combining hamza (it runs no FoldHamza), so the closing NFC of the shared tail is what
# guarantees its output is canonical -- the CANONICAL ORDER case in the note above is an ML input.
#
# The OPTIONAL digit fold (MapDigits) the story names is deliberately OFF by default here so ML's
# letter-and-distinction-preserving guarantee is the contract; turning it on is a config override,
# which the config boundary (issue 0016) owns for every profile. Folding digits never touches a
# letter, so the toggle cannot affect any distinction -- pinned by a property test below.
ML = Profile(
    name="ml",
    steps=[
        *LIGHT.steps,
        StepSpec(name="RemoveTashkeel"),  # all mark classes (dediacritization for model input)
        StepSpec(name="ReduceElongation"),  # cap 1 (default): collapse emphatic lengthening
        # Shared closing tail (see the note above): re-collapse re-exposed whitespace, then
        # re-canonicalize (ML keeps hamza, so this NFC is load-bearing). Sits last, after the folds.
        StepSpec(name="CollapseWhitespace"),
        StepSpec(name="NormalizeUnicode", config={"form": "NFC"}),
    ],
)

# CLASSICAL: lossless encoding repair that PRESERVES vocalization and Qur'anic annotation marks, so
# vocalized / Qur'anic text survives intact (story 8). Because LIGHT already removes no marks (it is
# all ENCODING_REPAIR), CLASSICAL is LIGHT's encoding repair under a distinct name -- a separate,
# serializable preset whose contract is the explicit *guarantee* that:
#
#   1. no vocalization mark is removed -- harakat / tanween / shadda / madda / dagger-alef / the
#      Qur'anic-annotation block (chars.QURANIC) all ride through untouched (RemoveTashkeel, the
#      only step that would strip them, is never composed here), and
#   2. presentation-form / lam-alef folding (FoldPresentationForms) decomposes ligatures WITHOUT
#      disturbing the surrounding combining marks -- the fold is a per-glyph substitution and the
#      single source of canonical ordering is the closing NFC (ADR-0009), which never reorders marks
#      across a base letter.
#
# It is defined as LIGHT's steps verbatim, so the two stay behaviorally identical by construction
# and CLASSICAL inherits any future LIGHT change; the value it adds is the named, paper-citable
# preset plus the preservation guarantee pinned by its tests. Like every profile, CLASSICAL emits
# canonical (NFC) order -- it preserves every mark, not the byte-exact ordering of a non-canonical
# input (ADR-0009).
CLASSICAL = Profile(name="classical", steps=[*LIGHT.steps])

# SOCIAL: make noisy user-generated text tractable WITHOUT deleting its affective signal (story 7).
# It composes LIGHT's encoding repair with the two sibling concerns social text needs -- CLEANING
# (strip the metadata noise: URLs, @mentions, HTML markup) and the lossy normalization folds a
# vocabulary explosion demands (vocalization removal, emphatic-elongation capping) -- but it KEEPS
# emoji, because in social text the emoji *is* the signal (😍 is sentiment, not noise).
#
# It is defined as LIGHT's steps verbatim plus those steps, so "SOCIAL begins with everything LIGHT
# does" holds by construction and SOCIAL inherits any future LIGHT change. Defaults (every one
# overridable at the config boundary, issue 0016) follow the AraBERT recipe:
#
#   - URLs/mentions -> a PLACEHOLDER token, in ARABIC ([رابط] / [مستخدم]), so "a link/user was here"
#     survives as a feature without a noisy unique value. (The step default token is the English
#     [URL]/[MENTION]; SOCIAL pins the Arabic ones explicitly.)
#   - HTML -> tags stripped (DELETE) and entities unescaped, so you keep the inner text.
#   - tashkeel -> removed (every mark class), as the PRD SOCIAL composition specifies.
#   - elongation -> capped at 2 (not 1), so emphasis survives: جمييل stays distinct from جميل.
#   - emoji -> kept (the default; KEEP is a lossless no-op).
#
# Two load-bearing ordering decisions:
#
#   1. Cleaning runs BEFORE the linguistic folds: strip the URL/mention/HTML noise first, so the
#      folds never waste work on (or corrupt) a span that is about to become a placeholder, and so
#      CleanURLs precedes CleanMentions (a URL like https://x/@h contains an @, so the mention
#      strip must not see it first).
#   2. RemoveTashkeel runs BEFORE ReduceElongation -- the PRD ordering contract (tashkeel removal is
#      an earlier band than cleanup) and the same reason ML orders them this way: a vocalized
#      elongation interleaves marks between the repeated letters (يَيَيَ), so the marks must be gone
#      first to leave the letters adjacent for the cap to collapse. Reversing them would leave a
#      vocalized stretch un-capped. (This is why this profile diverges from the issue's informal
#      "ReduceElongation + RemoveTashkeel" listing.)
#
# HandleEmoji(keep) is a no-op here, but keeping it explicit makes emoji a named, overridable SOCIAL
# knob (strip / demojize, issue 0016) rather than an omission.
#
# SOCIAL then ends with the shared closing tail (see the note above), which earns its keep here more
# than in any other profile: its cleaning steps delete whole spans (a stripped HTML tag leaves a
# whitespace gap) and an emoji-strip override deletes emoji from between spaces, both re-exposing
# whitespace; and like ML it keeps combining hamza, so the closing NFC re-canonicalizes. SOCIAL is
# lossy (it carries CLEANING + LINGUISTIC_FOLDING steps), so it is never the default and never
# lossless. (Strict idempotence still holds only on realistic markup -- CleanHTML's html.unescape
# decodes one level, an unrelated documented limit of that step.)
SOCIAL = Profile(
    name="social",
    steps=[
        *LIGHT.steps,
        # Cleaning first; CleanURLs before CleanMentions (a URL can contain an @). Arabic tokens.
        StepSpec(name="CleanURLs", config={"mode": "placeholder", "placeholder": "[رابط]"}),
        StepSpec(name="CleanMentions", config={"mode": "placeholder", "placeholder": "[مستخدم]"}),
        StepSpec(name="CleanHTML"),  # delete (strip tags) + unescape entities -- the defaults
        StepSpec(name="RemoveTashkeel"),  # all mark classes; BEFORE ReduceElongation (see above)
        StepSpec(
            name="ReduceElongation", config={"cap": 2}
        ),  # keep emphasis up to a doubled letter
        StepSpec(name="HandleEmoji"),  # keep (default): emoji is the affective signal
        # Shared closing tail (see the note above): re-collapse whitespace the cleaning steps /
        # emoji-strip re-expose, then re-canonicalize. Sits last, after every step.
        StepSpec(name="CollapseWhitespace"),
        StepSpec(name="NormalizeUnicode", config={"form": "NFC"}),
    ],
)

_PROFILES: dict[str, Profile] = {
    LIGHT.name: LIGHT,
    SEARCH.name: SEARCH,
    ML.name: ML,
    CLASSICAL.name: CLASSICAL,
    SOCIAL.name: SOCIAL,
}


def get_profile(name: str) -> Profile:
    """Look up a named profile (case-insensitive on the canonical name), or raise a clear error."""
    try:
        return _PROFILES[name.lower()]
    except KeyError:
        raise ValueError(f"Unknown profile {name!r}; known profiles: {sorted(_PROFILES)}") from None
