"""The fused `str.translate` engine (ADR-0006).

`str.translate` is a context-free, single-pass, per-character map: it replaces each input code
point independently and never re-scans its own output. So applying a *run* of consecutive
translate steps is the same as applying one combined table whose per-code-point value is the run
composed through that code point. Collapsing the run to a single table turns N traversals of the
string into one C-level pass — ADR-0006's single biggest optimization — with no change in output.

This module is the engine behind that: `fuse_tables` composes a run of tables into one, and
`build_plan` compiles a pipeline's steps into an execution plan that fuses each maximal run of
`SupportsTranslate` steps while leaving every *contextual* step (the regex cleaning/normalization
steps and `unicodedata`-based `NormalizeUnicode`) as its own pass, in order. It adds no public
interface — `Pipeline` runs the plan inside `__call__`; everything observable stays the same.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from araclean.steps import SupportsTranslate

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from araclean.steps import Step


def _render(value: str | int | None) -> str:
    """The string a `str.translate` value produces: ``None`` → ``""`` (delete), an ordinal → its
    character, a string → itself."""
    if value is None:
        return ""
    if isinstance(value, int):
        return chr(value)
    return value


def _compose(
    first: Mapping[int, str | int | None], second: Mapping[int, str | int | None]
) -> dict[int, str]:
    """Compose two `str.translate` tables into one applied-first-then-second table ``T`` such that
    ``s.translate(T) == s.translate(first).translate(second)`` for every string ``s``.

    A code point touched by *either* table needs an explicit entry. For a key of ``first``, render
    what ``first`` produces (handling multi-character expansion like a lam-alef ligature, and
    deletion → ``""``) and rewrite that through ``second``. A key only in ``second`` maps as
    ``second`` says. Exact because `str.translate` is single-pass and per-character.
    """
    composed: dict[int, str] = {}
    for code_point, value in first.items():
        composed[code_point] = _render(value).translate(second)
    for code_point, value in second.items():
        if code_point not in first:
            composed[code_point] = _render(value)
    return composed


def fuse_tables(tables: Sequence[Mapping[int, str | int | None]]) -> dict[int, str]:
    """Fuse a run of `str.translate` tables (applied left-to-right) into ONE combined table.

    Left-fold of `_compose`: ``fuse([t1, t2, t3])`` is ``compose(compose(t1, t2), t3)``, so a single
    `str.translate` over the result reproduces ``s.translate(t1).translate(t2).translate(t3)``. The
    empty run fuses to the identity (an empty table).
    """
    fused: dict[int, str] = {}
    for table in tables:
        fused = _compose(fused, table)
    return fused


@dataclass(frozen=True, slots=True)
class TranslatePass:
    """One fused `str.translate` pass over a combined table — a plan entry that stands in for a run
    of consecutive fusible steps. Callable as ``str -> str``, like a `Step`, so the plan is uniform.
    """

    table: dict[int, str]

    def __call__(self, text: str, /) -> str:
        return text.translate(self.table)


def _fusible_table(step: Step) -> Mapping[int, str | int | None] | None:
    """The step's translate table if it is fusible HERE, else ``None``.

    A config-dependent step (`RemoveTashkeel(position="final")`,
    `MapDigits(map_separators=True)`) keeps the `translate_table` property on its class but raises
    `AttributeError` in its contextual mode — `isinstance` alone cannot see that, so the table is
    read eagerly and the raise is read as "not fusible".
    """
    if not isinstance(step, SupportsTranslate):
        return None
    try:
        return step.translate_table
    except AttributeError:
        return None


def build_plan(steps: Sequence[Step]) -> tuple[Callable[[str], str], ...]:
    """Compile a pipeline's steps into an execution plan, fusing each maximal run of consecutive
    `SupportsTranslate` steps into a single `TranslatePass`.

    Every non-fusible step (a custom step, or a contextual one: `NormalizeUnicode`, the whitespace/
    punctuation/elongation/cleaning regex steps, a translate step in a contextual config mode)
    stays its own pass and never moves, so ordering across the contract boundaries is preserved
    exactly. A run of a single fusible step is left as that step (nothing to fuse); a run of two or
    more collapses to one combined table.
    """
    plan: list[Callable[[str], str]] = []
    run: list[tuple[Step, Mapping[int, str | int | None]]] = []

    def flush() -> None:
        if len(run) >= 2:
            plan.append(TranslatePass(fuse_tables([table for _step, table in run])))
        elif run:
            plan.append(run[0][0])
        run.clear()

    for step in steps:
        table = _fusible_table(step)
        if table is not None:
            run.append((step, table))
        else:
            flush()
            plan.append(step)
    flush()
    return tuple(plan)
