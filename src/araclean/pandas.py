"""araclean pandas Series accessor (issue 0021) — a thin adapter at the facade seam (ADR-0003).

Registers a ``.araclean`` accessor on pandas Series so a dataframe workflow normalizes a text
column in one idiomatic call::

    import araclean.pandas  # registers the accessor (needs the [pandas] extra)

    df["text"] = df["text"].araclean.normalize(profile="search")

It holds no normalization logic: it validates ``profile`` + ``**overrides`` once through the config
trust boundary (`NormalizeConfig`), builds the effective `Pipeline`, and maps it over the Series —
every behavior lives in the deep core, so the accessor mirrors the CLI adapter (issue 0020). It is
the first of the two facade adapters (the polars accessor, issue 0022, is the other) that make the
`normalize` facade a real seam.

pandas lives behind the optional ``[pandas]`` extra (ADR-0003 lean core). Importing this module
registers the accessor and therefore needs pandas; without it, `register` raises
`PandasExtraNotInstalledError` naming the extra (mirroring `EmojiSupportNotInstalledError` and the
CLI's `CLIExtraNotInstalledError`). The lean core never imports this module, so ``import araclean``
stays pandas-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from araclean.config import NormalizeConfig, ProfileName
from araclean.pipeline import Pipeline

if TYPE_CHECKING:
    from types import ModuleType

    import pandas as pd


_PANDAS_EXTRA_HINT = (
    "The araclean pandas accessor needs the optional [pandas] extra, which is not installed. "
    "Install it with: pip install 'araclean[pandas]'."
)


class PandasExtraNotInstalledError(ImportError):
    """Raised when the pandas accessor is used without the optional ``[pandas]`` extra installed.

    Subclasses `ImportError` (so a caller probing for the capability can catch it); the message
    says how to install it. Mirrors `EmojiSupportNotInstalledError` / `CLIExtraNotInstalledError`.
    """


def _load_pandas() -> ModuleType:
    """Import pandas, or raise a clear, actionable error naming the ``[pandas]`` extra.

    A seam so the optional dependency is imported lazily and its absence can be simulated in tests
    (mirrors `_load_demojize`). Catches `ImportError` broadly so both a missing package and a
    stubbed-out module surface as `PandasExtraNotInstalledError`.
    """
    try:
        import pandas
    except ImportError as exc:
        raise PandasExtraNotInstalledError(_PANDAS_EXTRA_HINT) from exc
    return pandas


def _build_pipeline(profile: str | None, overrides: dict[str, object]) -> Pipeline:
    """Validate the profile + overrides at the trust boundary and assemble the effective pipeline.

    The same path the `normalize` facade and the CLI take, assembled once (not per row): a bad
    option value raises `ValidationError`, an override that does not apply to the profile raises
    `ValueError` (from `resolve()`). Building once keeps the per-row hot path validation-free.
    """
    name = profile if profile is not None else ProfileName.LIGHT.value
    config = NormalizeConfig.model_validate({"profile": name, **overrides})
    return Pipeline.from_profile(config.resolve())


class AracleanAccessor:
    """The ``.araclean`` Series accessor: ``series.araclean.normalize(profile=..., **overrides)``.

    pandas instantiates this with the Series the accessor was reached through.
    """

    def __init__(self, pandas_obj: pd.Series[Any]) -> None:
        self._series = pandas_obj

    def normalize(self, *, profile: str | None = None, **overrides: object) -> pd.Series[Any]:
        """Normalize each value in the Series with a named profile (default `LIGHT`) + overrides.

        Equivalent to ``series.map(lambda x: normalize(x, profile=..., **overrides))`` but builds
        the pipeline once. ``profile`` and the per-knob ``**overrides`` (e.g. ``map_digits=True``,
        ``emoji="strip"``) are validated through the config trust boundary, so an unknown profile,
        knob, or value raises the same clear error as the `normalize` facade. Missing values
        (``NaN``/``None``) pass through unchanged (``na_action="ignore"``); empty strings normalize
        to empty strings.
        """
        pipe = _build_pipeline(profile, overrides)
        return self._series.map(pipe, na_action="ignore")


def register() -> None:
    """Register the ``.araclean`` accessor on pandas Series (called on import).

    Needs pandas (the ``[pandas]`` extra); raises `PandasExtraNotInstalledError` if it is absent.
    """
    pandas = _load_pandas()
    pandas.api.extensions.register_series_accessor("araclean")(AracleanAccessor)


register()
