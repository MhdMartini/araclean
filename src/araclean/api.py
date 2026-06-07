"""Layer 3 — the one-call `normalize` facade (a thin adapter over `Pipeline`, ADR-0003)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from araclean.pipeline import Pipeline
from araclean.profiles import LIGHT

if TYPE_CHECKING:
    from araclean.profiles import Profile


def normalize(text: str, *, profile: str | Profile | None = None) -> str:
    """Normalize Arabic text with a named profile (default `LIGHT` — lossless encoding repair).

    `profile=None` applies `LIGHT`; pass ``profile="search"`` (etc.) or a `Profile` for more.
    """
    chosen: str | Profile = LIGHT if profile is None else profile
    return Pipeline.from_profile(chosen)(text)
