"""OffsetMap — alignment between normalized text and the original it was derived from.

Every position in the normalized string carries the half-open interval ``[orig_start, orig_end)``
in the original string that produced it.  The two query methods are the complete public surface:

- ``to_original(span)`` — map a normalized span to the original span it came from
- ``to_normalized(span)`` — map an original span to the normalized span it projects to

Factory helpers build an ``OffsetMap`` from the three kinds of normalization operations araclean
performs:

- ``identity(n)`` — for a text that was left completely unchanged
- ``from_translate(original, table)`` — for a ``str.translate`` pass
- ``from_regex_sub(original, match_spans, replacement_lens)`` — for a regex substitution

``compose(other)`` chains two maps so the final map links normalized text all the way back to the
original, across an arbitrary sequence of steps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class OffsetMap:
    """Alignment from normalized-text positions back to original-text positions.

    Internally stores a flat ``list[int]`` of length ``2 * len(normalized)``: entries
    ``[2*i, 2*i+1]`` are ``(orig_start, orig_end)`` for normalized character ``i``.
    """

    __slots__ = ("_o",)

    def __init__(self, offsets: list[int]) -> None:
        self._o = offsets

    def __len__(self) -> int:
        return len(self._o) // 2

    @staticmethod
    def identity(n: int) -> OffsetMap:
        """Build identity map: normalized char ``i`` maps to original ``[i, i+1)``."""
        o: list[int] = []
        for i in range(n):
            o.append(i)
            o.append(i + 1)
        return OffsetMap(o)

    @staticmethod
    def from_translate(original: str, table: Mapping[int, str | int | None]) -> OffsetMap:
        """Build offset map from *original* string + its ``str.translate`` table.

        Handles all three operation kinds:
        - ``None`` value → 1→0 deletion (no normalized chars emitted)
        - ``int`` value → 1→1 replacement (one normalized char)
        - ``str`` value → 1→N expansion (each result char maps back to the one original char)
        - no entry → identity (one normalized char = one original char)
        """
        o: list[int] = []
        for i, ch in enumerate(original):
            cp = ord(ch)
            if cp not in table:
                o.append(i)
                o.append(i + 1)
            else:
                val = table[cp]
                if val is None:
                    pass  # deleted — emit no normalized char
                else:
                    result = chr(val) if isinstance(val, int) else val
                    for _ in result:
                        o.append(i)
                        o.append(i + 1)
        return OffsetMap(o)

    @staticmethod
    def from_regex_sub(
        original: str,
        match_spans: Sequence[tuple[int, int]],
        replacement_lens: Sequence[int],
    ) -> OffsetMap:
        """Build offset map from match spans collected during a regex substitution.

        Each match at ``original[start:end]`` was replaced by ``replacement_len`` normalized
        chars that all map back to ``[start, end)``.  Non-matched chars are identity.
        """
        o: list[int] = []
        orig_pos = 0
        for (match_start, match_end), rep_len in zip(match_spans, replacement_lens, strict=True):
            for i in range(orig_pos, match_start):
                o.append(i)
                o.append(i + 1)
            for _ in range(rep_len):
                o.append(match_start)
                o.append(match_end)
            orig_pos = match_end
        for i in range(orig_pos, len(original)):
            o.append(i)
            o.append(i + 1)
        return OffsetMap(o)

    def compose(self, other: OffsetMap) -> OffsetMap:
        """Chain two maps: *self* maps norm1→orig; *other* maps norm2→norm1.

        Returns a new map that maps norm2→orig, so a caller accumulates after each step:
        ``running = running.compose(step_map)`` starting from the first step's map.
        """
        n2 = len(other)
        o: list[int] = []
        for i in range(n2):
            norm1_start = other._o[2 * i]
            norm1_end = other._o[2 * i + 1]
            orig_start, orig_end = self.to_original((norm1_start, norm1_end))
            o.append(orig_start)
            o.append(orig_end)
        return OffsetMap(o)

    def to_original(self, span: tuple[int, int]) -> tuple[int, int]:
        """Map half-open normalized span ``[start, end)`` to original span.

        For an empty span (``start == end``) returns a zero-width point in the original.
        """
        start, end = span
        n = len(self)
        if start < 0 or end < 0 or start > n or end > n or start > end:
            raise ValueError(f"span {span!r} out of range for normalized length {n}")
        if start == end:
            if n == 0:
                return (0, 0)
            if start == 0:
                return (self._o[0], self._o[0])
            if start == n:
                return (self._o[-1], self._o[-1])
            return (self._o[2 * start], self._o[2 * start])
        orig_start = self._o[2 * start]
        orig_end = self._o[2 * (end - 1) + 1]
        return (orig_start, orig_end)

    def to_normalized(self, span: tuple[int, int]) -> tuple[int, int]:
        """Map half-open original span ``[start, end)`` to normalized span (best-effort).

        For a span that was entirely deleted, returns a zero-width insertion point at the
        position in normalized text just before where the deleted content appeared.
        """
        orig_start, orig_end = span
        n = len(self)
        if orig_start == orig_end:
            for i in range(n):
                if self._o[2 * i] >= orig_start:
                    return (i, i)
            return (n, n)
        norm_start: int | None = None
        norm_end: int | None = None
        for i in range(n):
            o_s = self._o[2 * i]
            o_e = self._o[2 * i + 1]
            if o_e > orig_start and o_s < orig_end:
                if norm_start is None:
                    norm_start = i
                norm_end = i + 1
        if norm_start is None:
            # Entirely deleted span — find insertion point after orig_end
            for i in range(n):
                if self._o[2 * i] >= orig_end:
                    return (i, i)
            return (n, n)
        return (norm_start, norm_end)  # type: ignore[return-value]
