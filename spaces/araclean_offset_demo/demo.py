"""Framework-independent behavior for the offset-map demo."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from araclean import OffsetMap, Pipeline, ProfileName

PROFILE_NAMES: tuple[str, ...] = tuple(profile.value for profile in ProfileName)


class Direction(StrEnum):
    """Direction in which a selected span is projected."""

    NORMALIZED_TO_ORIGINAL = "normalized_to_original"
    ORIGINAL_TO_NORMALIZED = "original_to_normalized"


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """One selected span and its offset-map projection."""

    original: str
    normalized: str
    direction: Direction
    source_span: tuple[int, int]
    projected_span: tuple[int, int]
    source_text: str
    projected_text: str


@dataclass(frozen=True, slots=True)
class PreparedNormalization:
    """Original and normalized text bundled with the map between them."""

    original: str
    normalized: str
    offset_map: OffsetMap

    def project(self, direction: Direction, span: tuple[int, int]) -> ProjectionResult:
        """Project a selection in either direction through this normalization."""
        if direction is Direction.NORMALIZED_TO_ORIGINAL:
            projected_span = self.offset_map.to_original(span)
            source_text = self.normalized[slice(*span)]
            projected_text = self.original[slice(*projected_span)]
        else:
            projected_span = self.offset_map.to_normalized(span)
            source_text = self.original[slice(*span)]
            projected_text = self.normalized[slice(*projected_span)]
        return ProjectionResult(
            original=self.original,
            normalized=self.normalized,
            direction=direction,
            source_span=span,
            projected_span=projected_span,
            source_text=source_text,
            projected_text=projected_text,
        )

    def offset_rows(self) -> list[list[str | int]]:
        """Render the normalized-to-original character map as table rows."""
        rows: list[list[str | int]] = []
        for normalized_index, character in enumerate(self.normalized):
            original_start, original_end = self.offset_map.to_original(
                (normalized_index, normalized_index + 1)
            )
            rows.append(
                [
                    normalized_index,
                    character,
                    f"[{original_start}, {original_end})",
                    self.original[original_start:original_end],
                ]
            )
        return rows


def prepare_normalization(text: str, profile: str) -> PreparedNormalization:
    """Normalize *text* with a named profile and retain its original and offset map."""
    normalized_profile = profile.strip().lower()
    if normalized_profile not in PROFILE_NAMES:
        raise ValueError(f"unknown profile {profile!r}; choose one of {', '.join(PROFILE_NAMES)}")
    normalized, offset_map = Pipeline.from_profile(normalized_profile).apply_aligned(text)
    return PreparedNormalization(text, normalized, offset_map)


def project_selection(
    original: str,
    profile: str,
    direction: Direction,
    span: tuple[int, int],
) -> ProjectionResult:
    """Project a half-open selected span through a named profile's offset map."""
    return prepare_normalization(original, profile).project(direction, span)


def utf16_span_to_codepoints(text: str, span: tuple[int, int]) -> tuple[int, int]:
    """Convert browser UTF-16 selection offsets to Python Unicode code-point offsets."""

    def to_codepoint_index(utf16_index: int) -> int:
        if utf16_index < 0:
            raise ValueError("selection offsets must be non-negative")
        consumed_units = 0
        for codepoint_index, character in enumerate(text):
            if consumed_units == utf16_index:
                return codepoint_index
            consumed_units += 2 if ord(character) > 0xFFFF else 1
            if consumed_units > utf16_index:
                raise ValueError("selection offset falls inside a UTF-16 surrogate pair")
        if consumed_units == utf16_index:
            return len(text)
        raise ValueError(f"selection offset {utf16_index} is outside the text")

    start, end = span
    if start > end:
        raise ValueError("selection start must not exceed selection end")
    return to_codepoint_index(start), to_codepoint_index(end)
