"""Behavior of the pandas Series accessor — a thin adapter at the facade seam.

The accessor holds no normalization logic: it validates the profile + overrides once, builds the
effective pipeline, and maps it over the Series. So these tests build real Series, call the
registered `.araclean` accessor, and assert the values agree with mapping the `normalize` facade —
never the accessor's internals.
"""

from __future__ import annotations

import sys
from typing import Any, cast

import pandas as pd
import pytest
from pandas.testing import assert_series_equal
from pydantic import ValidationError

import araclean.pandas as pandas_accessor  # registers the `.araclean` accessor on import
from araclean import normalize

TATWEEL_WORD = "محـــمد"  # محمد with three tatweel; LIGHT removes them.


def _araclean(s: pd.Series[Any]) -> pandas_accessor.AracleanAccessor:
    """The registered `.araclean` accessor, typed.

    pandas registers the accessor at runtime, so the stubs cannot see `Series.araclean`; the cast
    recovers the static type while ``s.araclean`` still exercises the real registration.
    """
    return cast("pandas_accessor.AracleanAccessor", s.araclean)


def test_normalize_equals_mapping_the_facade() -> None:
    # The headline ergonomic: one call on a Series == mapping `normalize` element-wise.
    s = pd.Series([TATWEEL_WORD, "على", "abc"])
    result = _araclean(s).normalize(profile="light")
    # `str(value)` is identity on real strings; it only widens pandas-stubs' `str | NAType` to the
    # `str` the facade expects, so this stays the criterion's `s.map(lambda x: normalize(x, ...))`.
    expected = s.map(lambda value: normalize(str(value), profile="light"))
    assert_series_equal(result, expected)


def test_no_profile_defaults_to_light() -> None:
    s = pd.Series([TATWEEL_WORD, "على"])
    result = _araclean(s).normalize()
    expected = s.map(lambda value: normalize(str(value)))  # facade default == LIGHT
    assert_series_equal(result, expected)


def test_profile_passes_through_to_the_core() -> None:
    # SEARCH folds alef-maqsura (على -> علي), which LIGHT leaves alone — proving the profile routes.
    s = pd.Series(["على", TATWEEL_WORD])
    result = _araclean(s).normalize(profile="search")
    expected = s.map(lambda value: normalize(str(value), profile="search"))
    assert_series_equal(result, expected)
    assert result.iloc[0] == "علي"


def test_map_digits_override_passes_through_to_the_core() -> None:
    s = pd.Series(["١٢٣", "كتاب"])
    result = _araclean(s).normalize(profile="ml", map_digits=True)
    expected = s.map(lambda value: normalize(str(value), profile="ml", map_digits=True))
    assert_series_equal(result, expected)
    assert result.iloc[0] == "123"  # the override folded Arabic-Indic digits to ASCII


def test_emoji_override_passes_through_to_the_core() -> None:
    s = pd.Series(["جميل 😍", "نص"])
    result = _araclean(s).normalize(profile="social", emoji="strip")
    expected = s.map(lambda value: normalize(str(value), profile="social", emoji="strip"))
    assert_series_equal(result, expected)


def test_invalid_profile_raises_the_same_clear_error_as_the_facade() -> None:
    s = pd.Series(["x"])
    with pytest.raises(ValidationError, match="profile"):
        _araclean(s).normalize(profile="nope")
    # The facade rejects the same input with the same error class — the accessor adds no new path.
    with pytest.raises(ValidationError, match="profile"):
        normalize("x", profile="nope")


def test_override_that_does_not_apply_raises_like_the_facade() -> None:
    # `emoji=` on LIGHT has no step to configure: rejected (never a silent no-op), like the facade.
    s = pd.Series(["x"])
    with pytest.raises(ValueError, match="emoji"):
        _araclean(s).normalize(profile="light", emoji="strip")
    with pytest.raises(ValueError, match="emoji"):
        normalize("x", profile="light", emoji="strip")


def test_preserves_the_series_index() -> None:
    s = pd.Series([TATWEEL_WORD, "abc"], index=["row-a", "row-b"])
    result = _araclean(s).normalize(profile="light")
    assert result.index.tolist() == ["row-a", "row-b"]


def test_missing_values_pass_through_unchanged() -> None:
    # NaN/None are skipped (na_action="ignore"); the surrounding strings are still normalized.
    s = pd.Series([TATWEEL_WORD, None, "abc"])
    result = _araclean(s).normalize(profile="light")
    assert result.isna().tolist() == [False, True, False]
    assert result.iloc[0] == normalize(TATWEEL_WORD, profile="light")
    assert result.iloc[2] == normalize("abc", profile="light")


def test_empty_and_whitespace_strings() -> None:
    s = pd.Series(["", "  ", "x"])
    result = _araclean(s).normalize(profile="light")
    expected = s.map(lambda value: normalize(str(value), profile="light"))
    assert_series_equal(result, expected)
    assert result.iloc[0] == ""  # an empty string normalizes to an empty string


def test_register_without_the_pandas_extra_raises_a_clear_error() -> None:
    # With pandas unavailable, registering the accessor (what `import araclean.pandas` does on
    # import) fails fast with an actionable error naming the extra, not a bare ImportError.
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, "pandas", None)  # make `import pandas` fail
        with pytest.raises(
            pandas_accessor.PandasExtraNotInstalledError, match=r"araclean\[pandas\]"
        ):
            pandas_accessor.register()
