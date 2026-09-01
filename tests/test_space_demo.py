"""Behavior tests for the Hugging Face offset-map demo."""

from __future__ import annotations

from spaces.araclean_offset_demo.demo import (
    DEFAULT_NORMALIZED_SPAN,
    DEFAULT_PROFILE,
    DEFAULT_TEXT,
    EXAMPLES,
    Direction,
    normalize_ui,
    prepare_normalization,
    project_selection,
    utf16_span_to_codepoints,
)


def test_default_example_starts_with_a_visible_normalized_to_original_projection() -> None:
    """The initial view demonstrates span projection without requiring a first click."""
    assert DEFAULT_TEXT == "ﻻ يَحْــمِلُ الحِــقدَ مَــنْ تَعـلُــو بِــهِ الرُّتَبُ"

    result = project_selection(
        DEFAULT_TEXT,
        DEFAULT_PROFILE,
        Direction.NORMALIZED_TO_ORIGINAL,
        DEFAULT_NORMALIZED_SPAN,
    )

    assert result.normalized == "لا يحمل الحقد من تعلو به الرتب"
    assert result.source_span == (8, 13)
    assert result.projected_span == (13, 21)
    assert result.source_text == "الحقد"
    assert result.projected_text == "الحِــقد"


def test_switching_examples_recomputes_the_current_rows_normalized_text() -> None:
    """Repeated A→B→A→B selection never retains the previous example's output."""
    default_example = EXAMPLES[0]
    ner_example = EXAMPLES[1]

    normalized_texts = [
        normalize_ui(*example)[0]
        for example in (default_example, ner_example, default_example, ner_example)
    ]

    assert normalized_texts == [
        "لا يحمل الحقد من تعلو به الرتب",
        "أراك عصي الدمع شيمتك الصبر",
        "لا يحمل الحقد من تعلو به الرتب",
        "أراك عصي الدمع شيمتك الصبر",
    ]


def test_normalized_selection_projects_to_the_original_rag_citation() -> None:
    """A normalized SEARCH hit highlights its original spelling and tatweel."""
    original = "كتاب أحمـد الكبير"

    result = project_selection(original, "search", Direction.NORMALIZED_TO_ORIGINAL, (5, 9))

    assert result.normalized == "كتاب احمد الكبير"
    assert result.source_span == (5, 9)
    assert result.projected_span == (5, 10)
    assert result.source_text == "احمد"
    assert result.projected_text == "أحمـد"


def test_original_selection_projects_to_normalized_model_input() -> None:
    """An original NER annotation projects onto the text a model receives."""
    original = "قال الرئيسُ محمـدٌ في المؤتمرِ"
    prepared = prepare_normalization(original, "ml")
    person_start = original.index("محمـد")
    person_end = person_start + len("محمـد")

    result = project_selection(
        original,
        "ml",
        Direction.ORIGINAL_TO_NORMALIZED,
        (person_start, person_end),
    )

    normalized_start = prepared.normalized.index("محمد")
    assert result.normalized == prepared.normalized
    assert result.source_span == (person_start, person_end)
    assert result.projected_span == (normalized_start, normalized_start + len("محمد"))
    assert result.source_text == "محمـد"
    assert result.projected_text == "محمد"


def test_expanded_ligature_characters_map_to_one_original_code_point() -> None:
    """Either character emitted by a lam-alef ligature points to its source glyph."""
    result = project_selection("ﻻ", "light", Direction.NORMALIZED_TO_ORIGINAL, (1, 2))

    assert result.normalized == "لا"
    assert result.projected_span == (0, 1)
    assert result.projected_text == "ﻻ"


def test_browser_utf16_selection_offsets_are_converted_to_python_code_points() -> None:
    """A browser selection after an emoji does not shift the Arabic span by one."""
    text = "😀أحمـد"

    assert utf16_span_to_codepoints(text, (2, 7)) == (1, 6)
