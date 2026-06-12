"""Tests for OffsetMap — the alignment core of offset-preserving normalization."""

from araclean.offsets import OffsetMap

# ---------------------------------------------------------------------------
# Cycle 1: identity map
# ---------------------------------------------------------------------------


def test_identity_to_original_full_span() -> None:
    omap = OffsetMap.identity(4)
    assert omap.to_original((0, 4)) == (0, 4)


def test_identity_to_original_sub_span() -> None:
    omap = OffsetMap.identity(4)
    assert omap.to_original((1, 3)) == (1, 3)


def test_identity_to_original_single_char() -> None:
    omap = OffsetMap.identity(4)
    assert omap.to_original((2, 3)) == (2, 3)


def test_identity_to_original_empty_span() -> None:
    omap = OffsetMap.identity(4)
    # empty span at position 2 maps to the insertion point in original
    assert omap.to_original((2, 2)) == (2, 2)


def test_identity_to_normalized_full_span() -> None:
    omap = OffsetMap.identity(4)
    assert omap.to_normalized((0, 4)) == (0, 4)


def test_identity_to_normalized_sub_span() -> None:
    omap = OffsetMap.identity(4)
    assert omap.to_normalized((1, 3)) == (1, 3)


# ---------------------------------------------------------------------------
# Cycle 2: from_translate — deletion (1→0)
# ---------------------------------------------------------------------------


def test_from_translate_delete_single_char() -> None:
    # "محـمد" (5 chars): tatweel ـ at index 2 is deleted → "محمد" (4 chars)
    TATWEEL = 0x0640
    s = "محـمد"
    table: dict[int, str | int | None] = {TATWEEL: None}
    omap = OffsetMap.from_translate(s, table)
    assert len(omap) == 4  # 4 chars in normalized
    # First two chars: orig[0:1], orig[1:2]
    assert omap.to_original((0, 2)) == (0, 2)
    # After the deletion: chars 2,3 in normalized → orig[3:4], orig[4:5]
    assert omap.to_original((2, 4)) == (3, 5)
    # Full span
    assert omap.to_original((0, 4)) == (0, 5)


def test_from_translate_delete_leaves_surrounding_chars_correct() -> None:
    TATWEEL = 0x0640
    s = "محـمد"
    table: dict[int, str | int | None] = {TATWEEL: None}
    omap = OffsetMap.from_translate(s, table)
    # single char at position 3 in normalized → orig[4:5] ("د")
    assert omap.to_original((3, 4)) == (4, 5)


# ---------------------------------------------------------------------------
# Cycle 3: from_translate — replacement (1→1)
# ---------------------------------------------------------------------------


def test_from_translate_replace_one_to_one() -> None:
    # أ (U+0623) → ا (U+0627): 1→1, same length
    ALEF_HAMZA = 0x0623
    ALEF = 0x0627
    s = "أهلاً"
    table: dict[int, str | int | None] = {ALEF_HAMZA: chr(ALEF)}
    omap = OffsetMap.from_translate(s, table)
    assert len(omap) == len(s)  # same length
    assert omap.to_original((0, 1)) == (0, 1)  # replaced char maps back to its original position
    assert omap.to_original((0, len(s))) == (0, len(s))


# ---------------------------------------------------------------------------
# Cycle 4: from_translate — expansion (1→N)
# ---------------------------------------------------------------------------


def test_from_translate_expand_one_to_two() -> None:
    # ﻷ (lam-alef presentation form, U+FEF7) → لأ (lam + alef-hamza, 2 chars)
    LAM_ALEF_PF = 0xFEF7
    lam_alef_expanded = "لأ"  # 2 chars
    s = "ﻷ"  # 1 char
    table: dict[int, str | int | None] = {LAM_ALEF_PF: lam_alef_expanded}
    omap = OffsetMap.from_translate(s, table)
    assert len(omap) == 2  # 2 chars in normalized
    # Both normalized chars map back to original[0:1]
    assert omap.to_original((0, 1)) == (0, 1)
    assert omap.to_original((1, 2)) == (0, 1)
    assert omap.to_original((0, 2)) == (0, 1)


# ---------------------------------------------------------------------------
# Cycle 5: to_normalized
# ---------------------------------------------------------------------------


def test_to_normalized_after_deletion() -> None:
    # "محـمد": tatweel at orig[2] is deleted
    TATWEEL = 0x0640
    s = "محـمد"
    table: dict[int, str | int | None] = {TATWEEL: None}
    omap = OffsetMap.from_translate(s, table)
    # orig[0:2] → norm[0:2]
    assert omap.to_normalized((0, 2)) == (0, 2)
    # orig[3:5] → norm[2:4]
    assert omap.to_normalized((3, 5)) == (2, 4)
    # orig[2:3] is deleted: maps to the insertion point between norm[1] and norm[2]
    assert omap.to_normalized((2, 3)) == (2, 2)


def test_to_normalized_full_span_after_deletion() -> None:
    TATWEEL = 0x0640
    s = "محـمد"
    table: dict[int, str | int | None] = {TATWEEL: None}
    omap = OffsetMap.from_translate(s, table)
    assert omap.to_normalized((0, 5)) == (0, 4)


# ---------------------------------------------------------------------------
# Cycle 6: compose
# ---------------------------------------------------------------------------


def test_compose_two_identity_maps() -> None:
    m1 = OffsetMap.identity(4)
    m2 = OffsetMap.identity(4)
    composed = m1.compose(m2)
    assert composed.to_original((0, 4)) == (0, 4)
    assert composed.to_original((1, 3)) == (1, 3)


def test_compose_delete_then_replace() -> None:
    # Step 1: delete tatweel at index 2; "محـمد" → "محمد"
    TATWEEL = 0x0640
    ALEF_HAMZA = 0x0623
    ALEF = 0x0627
    s = "محـمد"
    m1 = OffsetMap.from_translate(s, {TATWEEL: None})
    # Step 2: no-op translate on "محمد"
    m2 = OffsetMap.from_translate("محمد", {ALEF_HAMZA: chr(ALEF)})  # أ not present, identity
    composed = m1.compose(m2)
    # After two steps: "محمد" (4 chars), still maps back to original "محـمد"
    assert composed.to_original((0, 4)) == (0, 5)
    assert composed.to_original((2, 4)) == (3, 5)


def test_compose_identity_then_delete() -> None:
    # Step 1: identity on "محـمد"
    s = "محـمد"
    m1 = OffsetMap.identity(len(s))
    # Step 2: delete tatweel at index 2 of "محـمد"
    TATWEEL = 0x0640
    m2 = OffsetMap.from_translate(s, {TATWEEL: None})
    composed = m1.compose(m2)
    assert composed.to_original((0, 4)) == (0, 5)
    assert composed.to_original((2, 4)) == (3, 5)


# ---------------------------------------------------------------------------
# Cycle 7: from_regex_sub
# ---------------------------------------------------------------------------


def test_from_regex_sub_delete_match() -> None:
    # Remove runs of spaces
    s = "hello  world"  # space run at [5:7]
    spans = [(5, 7)]
    rep_lens = [1]  # replace with single space
    omap = OffsetMap.from_regex_sub(s, spans, rep_lens)
    # "hello world" (11 chars)
    assert len(omap) == 11
    # "hello" at [0:5] → orig[0:5]
    assert omap.to_original((0, 5)) == (0, 5)
    # the single space at [5] → orig[5:7]
    assert omap.to_original((5, 6)) == (5, 7)
    # "world" at [6:11] → orig[7:12]
    assert omap.to_original((6, 11)) == (7, 12)


def test_from_regex_sub_full_deletion() -> None:
    # Remove all spaces
    s = "هنا هناك"  # space at [3]
    spans = [(3, 4)]
    rep_lens = [0]  # delete
    omap = OffsetMap.from_regex_sub(s, spans, rep_lens)
    assert len(omap) == 7
    assert omap.to_original((0, 3)) == (0, 3)
    assert omap.to_original((3, 7)) == (4, 8)


# ---------------------------------------------------------------------------
# Cycle 8: empty and edge cases
# ---------------------------------------------------------------------------


def test_identity_empty_string() -> None:
    omap = OffsetMap.identity(0)
    assert len(omap) == 0
    assert omap.to_original((0, 0)) == (0, 0)


def test_from_translate_empty_string() -> None:
    omap = OffsetMap.from_translate("", {})
    assert len(omap) == 0


def test_from_translate_all_deleted() -> None:
    TATWEEL = 0x0640
    s = "ــ"
    omap = OffsetMap.from_translate(s, {TATWEEL: None})
    assert len(omap) == 0


def test_len_matches_normalized_string() -> None:
    """OffsetMap length always equals the number of chars in the normalized string."""
    TATWEEL = 0x0640
    s = "محـمد"
    normalized = s.translate({TATWEEL: None})
    omap = OffsetMap.from_translate(s, {TATWEEL: None})
    assert len(omap) == len(normalized)
