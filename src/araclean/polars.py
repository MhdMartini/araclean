"""araclean polars Series namespace (issue 0022) — a thin adapter at the facade seam (ADR-0003).

Registers a ``.araclean`` namespace on polars Series so a dataframe workflow normalizes a text
column in one idiomatic call::

    import araclean.polars  # registers the namespace (needs the [polars] extra)

    df = df.with_columns(df["text"].araclean.normalize(profile="search").alias("text"))

It holds no normalization logic: it validates ``profile`` + ``**overrides`` once through the config
trust boundary (`NormalizeConfig`), builds the effective `Pipeline`, and maps it over the Series —
every behavior lives in the deep core, so the namespace mirrors the pandas accessor (issue 0021)
and the CLI adapter (issue 0020). Together with the pandas accessor it makes the `normalize` facade
a real seam (two adapters), and it produces output parity with the pandas accessor.

polars lives behind the optional ``[polars]`` extra (ADR-0003 lean core). Importing this module
registers the namespace and therefore needs polars; without it, `register` raises
`PolarsExtraNotInstalledError` naming the extra (mirroring `PandasExtraNotInstalledError` and the
CLI's `CLIExtraNotInstalledError`). The lean core never imports this module, so ``import araclean``
stays polars-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from araclean.api import build_pipeline

if TYPE_CHECKING:
    from types import ModuleType

    import polars as pl


_POLARS_EXTRA_HINT = (
    "The araclean polars namespace needs the optional [polars] extra, which is not installed. "
    "Install it with: pip install 'araclean[polars]'."
)


class PolarsExtraNotInstalledError(ImportError):
    """Raised when the polars namespace is used without the optional ``[polars]`` extra installed.

    Subclasses `ImportError` (so a caller probing for the capability can catch it); the message
    says how to install it. Mirrors `PandasExtraNotInstalledError` / `CLIExtraNotInstalledError`.
    """


def _load_polars() -> ModuleType:
    """Import polars, or raise a clear, actionable error naming the ``[polars]`` extra.

    A seam so the optional dependency is imported lazily and its absence can be simulated in tests
    (mirrors `_load_pandas` / `_load_demojize`). Catches `ImportError` broadly so both a missing
    package and a stubbed-out module surface as `PolarsExtraNotInstalledError`.
    """
    try:
        import polars
    except ImportError as exc:
        raise PolarsExtraNotInstalledError(_POLARS_EXTRA_HINT) from exc
    return polars


class AracleanNamespace:
    """The ``.araclean`` Series namespace: ``series.araclean.normalize(profile=..., **overrides)``.

    polars instantiates this with the Series the namespace was reached through.
    """

    def __init__(self, series: pl.Series) -> None:
        self._series = series

    def normalize(self, *, profile: str | None = None, **overrides: object) -> pl.Series:
        """Normalize each value in the Series with a named profile (default `LIGHT`) + overrides.

        Equivalent to mapping ``normalize(x, profile=..., **overrides)`` element-wise but builds
        the pipeline once. ``profile`` and the per-knob ``**overrides`` (e.g. ``map_digits=True``,
        ``emoji="strip"``) are validated through the config trust boundary, so an unknown profile,
        knob, or value raises the same clear error as the `normalize` facade. Null values pass
        through unchanged (``map_elements`` skips nulls); empty strings normalize to empty strings.
        The result is a String Series, matching the pandas accessor value-for-value.
        """
        import polars as pl

        pipe = build_pipeline(profile, overrides)
        return self._series.map_elements(pipe, return_dtype=pl.String)


def register() -> None:
    """Register the ``.araclean`` namespace on polars Series (called on import).

    Needs polars (the ``[polars]`` extra); raises `PolarsExtraNotInstalledError` if it is absent.
    """
    polars = _load_polars()
    polars.api.register_series_namespace("araclean")(AracleanNamespace)


register()
