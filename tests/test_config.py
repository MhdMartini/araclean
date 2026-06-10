"""Config & reproducibility (issue 0016): the validation boundary, JSON Schema, safety audit."""

import pytest

from araclean import CLASSICAL, LIGHT, ML, SEARCH, SOCIAL, Pipeline, normalize

# Code points (not glyphs) so the corpus is deterministic regardless of file encoding.
_ARABIC_INDIC_123 = chr(0x0661) + chr(0x0662) + chr(0x0663)  # ١٢٣
_ALA_MAQSURA = chr(0x0639) + chr(0x0644) + chr(0x0649)  # على (alef maqsura — a real distinction)
_AHMAD = chr(0x0623) + chr(0x062D) + chr(0x0645) + chr(0x062F)  # أحمد (hamza)
# مدرسة (teh marbuta) — a teh-marbuta word ML preserves.
_MADRASA = chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629)


def test_audit_reports_light_and_classical_as_lossless() -> None:
    # Story 41: a "lossless" profile contains only ENCODING_REPAIR steps; the audit says so.
    assert Pipeline.from_profile(LIGHT).audit().lossless
    assert Pipeline.from_profile(CLASSICAL).audit().lossless


def test_audit_enumerates_the_linguistic_folding_steps_in_search_and_ml() -> None:
    # Story 41: a lossy profile is NOT lossless, and the audit names exactly which folds it carries
    # (not merely "it is lossy") — the auditability the safety contract promises.
    search = Pipeline.from_profile(SEARCH).audit()
    assert not search.lossless
    assert set(search.linguistic_folding) == {
        "RemoveTashkeel",
        "FoldAlef",
        "FoldHamza",
        "FoldTehMarbuta",
        "FoldAlefMaqsura",
        "MapDigits",
        "MapPunctuation",
        "ReduceElongation",
    }
    assert not search.cleaning  # SEARCH removes no non-linguistic noise

    ml = Pipeline.from_profile(ML).audit()
    assert not ml.lossless
    assert set(ml.linguistic_folding) == {"RemoveTashkeel", "ReduceElongation"}


def test_audit_separates_cleaning_from_linguistic_folding_in_social() -> None:
    # SOCIAL loses both kinds: the audit reports them in distinct buckets (ADR-0011) so an auditor
    # sees it strips noise (URLs/mentions/HTML) AND folds the language (tashkeel/elongation).
    social = Pipeline.from_profile(SOCIAL).audit()
    assert not social.lossless
    assert set(social.cleaning) == {"CleanURLs", "CleanMentions", "CleanHTML"}
    assert set(social.linguistic_folding) == {"RemoveTashkeel", "ReduceElongation"}
    # HandleEmoji(keep) is a lossless no-op, so it audits as ENCODING_REPAIR, not as loss.
    assert "HandleEmoji" in social.encoding_repair
    assert set(social.lossy_steps) == set(social.cleaning) | set(social.linguistic_folding)


# --- NormalizeConfig: the validation trust boundary (story 39) ---


def test_normalize_config_accepts_a_known_profile_and_defaults_to_light() -> None:
    from araclean import NormalizeConfig, ProfileName

    assert NormalizeConfig().profile is ProfileName.LIGHT  # default
    # model_validate is the untrusted-input boundary (dict/JSON): a bare name coerces to the enum.
    assert NormalizeConfig.model_validate({"profile": "search"}).profile is ProfileName.SEARCH


def test_normalize_config_rejects_an_unknown_profile_name() -> None:
    from pydantic import ValidationError

    from araclean import NormalizeConfig

    with pytest.raises(ValidationError):
        NormalizeConfig.model_validate({"profile": "nope"})


def test_normalize_config_rejects_a_bad_option_value() -> None:
    # A closed option set (StrEnum) is caught at the boundary: an unknown emoji mode is rejected.
    from pydantic import ValidationError

    from araclean import NormalizeConfig

    with pytest.raises(ValidationError):
        NormalizeConfig.model_validate({"profile": "social", "emoji": "sparkle"})


def test_normalize_config_rejects_an_unknown_override_key() -> None:
    # extra="forbid": a typo'd / unknown knob fails loudly rather than silently doing nothing.
    from pydantic import ValidationError

    from araclean import NormalizeConfig

    with pytest.raises(ValidationError):
        NormalizeConfig.model_validate({"profile": "ml", "map_digit": True})  # typo for map_digits


# --- ML digit-fold override via the facade (closes issue 0011's deferred [~] criterion) ---


def test_normalize_ml_map_digits_override_folds_digits_off_by_default() -> None:
    # ML's optional digit fold is OFF by default (preserve everything); the override turns it on.
    assert normalize(_ARABIC_INDIC_123, profile="ml") == _ARABIC_INDIC_123  # default: kept
    assert normalize(_ARABIC_INDIC_123, profile="ml", map_digits=True) == "123"  # folded to ASCII


def test_normalize_ml_map_digits_override_leaves_letter_distinctions_intact() -> None:
    # The override only touches digits: every alef/hamza/maqsura/teh-marbuta distinction ML
    # preserves is still preserved with the fold on (the property 0011 pinned, now via the facade).
    for word in (_ALA_MAQSURA, _AHMAD, _MADRASA):
        assert normalize(word, profile="ml", map_digits=True) == normalize(word, profile="ml")


def test_normalize_ml_map_digits_rejects_a_non_boolean() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        normalize(_ARABIC_INDIC_123, profile="ml", map_digits="yes-please")


# --- SOCIAL overrides via the facade (closes issue 0014's deferred [~] criterion) ---

_LOVE = chr(0x0623) + chr(0x062D) + chr(0x0628) + chr(0x0647)  # أحبه (no marks)
_HEART_EYES = chr(0x1F60D)  # 😍
_STRETCHED = chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)  # جمييييل
_CAP_ONE = chr(0x062C) + chr(0x0645) + chr(0x064A) + chr(0x0644)  # جميل
_URL_TOKEN = "[" + chr(0x0631) + chr(0x0627) + chr(0x0628) + chr(0x0637) + "]"  # [رابط]


def test_normalize_social_emoji_override_strips() -> None:
    text = f"{_LOVE} {_HEART_EYES * 2}"
    assert normalize(text, profile="social") == text  # default keeps the emoji (the signal)
    assert normalize(text, profile="social", emoji="strip") == f"{_LOVE} "  # override strips


def test_normalize_social_elongation_cap_override() -> None:
    # SOCIAL caps elongation at 2 by default (جمييل); cap=1 collapses all the way to جميل.
    assert normalize(_STRETCHED, profile="social", elongation_cap=1) == _CAP_ONE


def test_normalize_social_url_mention_mode_and_token_overrides() -> None:
    # Default: Arabic placeholder token. delete mode removes outright; an English token swaps in.
    assert _URL_TOKEN in normalize("see https://x.co", profile="social")
    deleted = normalize("see https://x.co", profile="social", url_mode="delete")
    assert "https" not in deleted and _URL_TOKEN not in deleted
    english = normalize(
        "hi @user", profile="social", mention_mode="placeholder", mention_token="[MENTION]"
    )
    assert "[MENTION]" in english


def test_override_naming_an_absent_step_is_rejected_not_a_silent_noop() -> None:
    # LIGHT has no HandleEmoji step; an emoji override must fail loudly, never silently do nothing.
    with pytest.raises(ValueError, match="emoji"):
        normalize(_LOVE, profile="light", emoji="strip")


# --- JSON Schema emit + validate: paper-reproducible preprocessing (story 40) ---

_JSON_CORPUS = (
    _ALA_MAQSURA,
    _AHMAD,
    _ARABIC_INDIC_123,
    "Hello, world!",
    f"{_LOVE} {_HEART_EYES}",
    "",
)


@pytest.mark.parametrize("profile", [LIGHT, SEARCH, ML, CLASSICAL, SOCIAL])
def test_profile_round_trips_through_json_reproducing_behavior(profile: object) -> None:
    # A profile serializes to JSON and back, reproducing both its identity and its behavior, so a
    # paper can ship its exact preprocessing and others rebuild the same pipeline.
    from araclean import Profile

    assert isinstance(profile, Profile)
    restored = Profile.model_validate_json(profile.model_dump_json())
    assert restored == profile
    original_pipe, restored_pipe = Pipeline.from_profile(profile), Pipeline.from_profile(restored)
    for text in _JSON_CORPUS:
        assert restored_pipe(text) == original_pipe(text)


@pytest.mark.parametrize("profile", [LIGHT, SEARCH, ML, CLASSICAL, SOCIAL])
def test_profile_json_validates_against_its_published_schema(profile: object) -> None:
    # The emitted JSON validates against the emitted JSON Schema, checked by an INDEPENDENT
    # validator (jsonschema) — so the schema is genuinely publishable, not merely pydantic-internal.
    import json

    import jsonschema

    from araclean import Profile

    assert isinstance(profile, Profile)
    schema = Profile.model_json_schema()
    jsonschema.validate(json.loads(profile.model_dump_json()), schema)  # must not raise


def test_malformed_profile_json_fails_pydantic_validation() -> None:
    from pydantic import ValidationError

    from araclean import Profile

    with pytest.raises(ValidationError):
        Profile.model_validate_json('{"name": "x", "steps": [{"name": 123}]}')


def test_malformed_profile_fails_the_published_json_schema() -> None:
    import jsonschema

    from araclean import Profile

    schema = Profile.model_json_schema()
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"name": "x", "steps": "not-a-list"}, schema)


# --- A prebuilt NormalizeConfig can drive the facade (the JSON/kwargs adapter, story 40) ---


def test_a_prebuilt_config_object_drives_the_facade() -> None:
    from araclean import NormalizeConfig

    cfg = NormalizeConfig.model_validate({"profile": "ml", "map_digits": True})
    assert normalize(_ARABIC_INDIC_123, config=cfg) == "123"  # same effect as the kwargs form


def test_passing_both_config_and_profile_overrides_is_rejected() -> None:
    from araclean import NormalizeConfig

    with pytest.raises(TypeError):
        normalize("x", profile="ml", config=NormalizeConfig())


def test_a_config_with_overrides_round_trips_through_json() -> None:
    # Reproducibility for the override case: a tuned config (not just a bare profile) serializes
    # to JSON and back to the same effective profile — so the exact preprocessing is publishable.
    from araclean import NormalizeConfig

    cfg = NormalizeConfig.model_validate(
        {"profile": "social", "emoji": "strip", "elongation_cap": 1}
    )
    restored = NormalizeConfig.model_validate_json(cfg.model_dump_json())
    assert restored == cfg
    assert restored.resolve() == cfg.resolve()


# --- The validation boundary is the facade only; the per-string core is validation-free (AC5) ---


def test_the_facade_validates_but_the_per_string_core_does_not() -> None:
    import pydantic

    from araclean import Pipeline, reduce_elongation, remove_tashkeel

    # The facade IS the trust boundary: a non-string `text` is rejected with a pydantic error.
    with pytest.raises(pydantic.ValidationError):
        normalize(123)  # type: ignore[arg-type]  # intentional: prove the boundary validates

    # The per-string hot path carries NO @validate_call wrapper (ADR-0003): neither the Pipeline
    # call/stream surface nor the bare step functions validate per string.
    assert not hasattr(Pipeline.__call__, "raw_function")
    assert not hasattr(Pipeline.batch, "raw_function")
    assert not hasattr(reduce_elongation, "raw_function")
    assert not hasattr(remove_tashkeel, "raw_function")
