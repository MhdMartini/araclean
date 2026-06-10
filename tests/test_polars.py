"""Behavior of the polars Series namespace (issue 0022) — a thin adapter at the facade seam.

The namespace holds no normalization logic: it validates the profile + overrides once, builds the
effective pipeline, and maps it over the Series. So these tests build real Series, call the
registered `.araclean` namespace, and assert the values agree with mapping the `normalize` facade —
never the namespace's internals. The final test pins output parity with the pandas accessor (0021).
"""

from __future__ import annotations

import sys
from typing import cast

import pandas as pd
import polars as pl
import pytest
from pydantic import ValidationError

import araclean.pandas as pandas_accessor  # registers pandas's `.araclean` accessor (for parity)
import araclean.polars as polars_accessor  # registers polars's `.araclean` namespace on import
from araclean import normalize

TATWEEL_WORD = "محـــمد"  # محمد with three tatweel; LIGHT removes them.


def _araclean(s: pl.Series) -> polars_accessor.AracleanNamespace:
    """The registered `.araclean` namespace, typed.

    polars registers the namespace at runtime, so the type checker cannot see `Series.araclean`
    (unlike pandas-stubs, which permits it); the ignore + cast recover the static type while
    ``s.araclean`` still exercises the real registration.
    """
    namespace = s.araclean  # type: ignore[attr-defined]  # registered at runtime
    return cast("polars_accessor.AracleanNamespace", namespace)


def test_normalize_equals_mapping_the_facade() -> None:
    # The headline ergonomic (story 44): one call on a column == mapping `normalize` element-wise.
    s = pl.Series("text", [TATWEEL_WORD, "على", "abc"])
    result = _araclean(s).normalize(profile="light")
    expected = [normalize(value, profile="light") for value in s.to_list()]
    assert result.to_list() == expected


def test_no_profile_defaults_to_light() -> None:
    s = pl.Series("text", [TATWEEL_WORD, "على"])
    result = _araclean(s).normalize()
    expected = [normalize(value) for value in s.to_list()]  # facade default == LIGHT
    assert result.to_list() == expected


def test_profile_passes_through_to_the_core() -> None:
    # SEARCH folds alef-maqsura (على -> علي), which LIGHT leaves alone — proving the profile routes.
    s = pl.Series("text", ["على", TATWEEL_WORD])
    result = _araclean(s).normalize(profile="search")
    expected = [normalize(value, profile="search") for value in s.to_list()]
    assert result.to_list() == expected
    assert result.to_list()[0] == "علي"


def test_map_digits_override_passes_through_to_the_core() -> None:
    s = pl.Series("text", ["١٢٣", "كتاب"])
    result = _araclean(s).normalize(profile="ml", map_digits=True)
    expected = [normalize(value, profile="ml", map_digits=True) for value in s.to_list()]
    assert result.to_list() == expected
    assert result.to_list()[0] == "123"  # the override folded Arabic-Indic digits to ASCII


def test_emoji_override_passes_through_to_the_core() -> None:
    s = pl.Series("text", ["جميل 😍", "نص"])
    result = _araclean(s).normalize(profile="social", emoji="strip")
    expected = [normalize(value, profile="social", emoji="strip") for value in s.to_list()]
    assert result.to_list() == expected


def test_invalid_profile_raises_the_same_clear_error_as_the_facade() -> None:
    s = pl.Series("text", ["x"])
    with pytest.raises(ValidationError, match="profile"):
        _araclean(s).normalize(profile="nope")
    # The facade rejects the same input with the same error class — the namespace adds no new path.
    with pytest.raises(ValidationError, match="profile"):
        normalize("x", profile="nope")


def test_override_that_does_not_apply_raises_like_the_facade() -> None:
    # `emoji=` on LIGHT has no step to configure: rejected (never a silent no-op), like the facade.
    s = pl.Series("text", ["x"])
    with pytest.raises(ValueError, match="emoji"):
        _araclean(s).normalize(profile="light", emoji="strip")
    with pytest.raises(ValueError, match="emoji"):
        normalize("x", profile="light", emoji="strip")


def test_preserves_the_series_name() -> None:
    s = pl.Series("body", [TATWEEL_WORD, "abc"])
    result = _araclean(s).normalize(profile="light")
    assert result.name == "body"


def test_null_values_pass_through_unchanged() -> None:
    # Nulls are skipped (map_elements skip_nulls); the surrounding strings are still normalized.
    s = pl.Series("text", [TATWEEL_WORD, None, "abc"])
    result = _araclean(s).normalize(profile="light")
    assert result.to_list() == [normalize(TATWEEL_WORD, profile="light"), None, "abc"]


def test_empty_and_whitespace_strings() -> None:
    s = pl.Series("text", ["", "  ", "x"])
    result = _araclean(s).normalize(profile="light")
    expected = [normalize(value, profile="light") for value in s.to_list()]
    assert result.to_list() == expected
    assert result.to_list()[0] == ""  # an empty string normalizes to an empty string


def test_output_parity_with_the_pandas_accessor() -> None:
    # 0022's distinguishing criterion: the same input through both adapters yields the same
    # normalized values. A noisy mixed fixture run through SEARCH exercises folds + digits.
    data = [TATWEEL_WORD, "على", "كتابًا", "جمييييل", "ﻷحمد", "العدد ١٢٣؟"]
    polars_values = _araclean(pl.Series("text", data)).normalize(profile="search").to_list()
    pandas_series = cast("pandas_accessor.AracleanAccessor", pd.Series(data).araclean).normalize(
        profile="search"
    )
    assert polars_values == pandas_series.tolist()


def test_register_without_the_polars_extra_raises_a_clear_error() -> None:
    # With polars unavailable, registering the namespace (what `import araclean.polars` does on
    # import) fails fast with an actionable error naming the extra, not a bare ImportError.
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "polars", None)  # make `import polars` fail
        with pytest.raises(
            polars_accessor.PolarsExtraNotInstalledError, match=r"araclean\[polars\]"
        ):
            polars_accessor.register()
