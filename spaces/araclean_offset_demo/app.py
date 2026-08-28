"""Gradio entry point for the AraClean offset-map Hugging Face Space."""

from __future__ import annotations

from typing import Any

import gradio as gr
from demo import (
    PROFILE_NAMES,
    Direction,
    ProjectionResult,
    prepare_normalization,
    utf16_span_to_codepoints,
)

DEFAULT_TEXT = "كتاب أحمـد الكبير"
DEFAULT_PROFILE = "search"


def _highlight(text: str, span: tuple[int, int] | None, label: str) -> dict[str, Any]:
    entities: list[dict[str, str | int]] = []
    if span is not None and span[0] != span[1]:
        entities.append({"entity": label, "start": span[0], "end": span[1]})
    return {"text": text, "entities": entities}


def _status(result: ProjectionResult) -> str:
    if result.direction is Direction.NORMALIZED_TO_ORIGINAL:
        return (
            "**Normalized → original** · "
            f"normalized `[{result.source_span[0]}, {result.source_span[1]})` → "
            f"original `[{result.projected_span[0]}, {result.projected_span[1]})`"
        )
    return (
        "**Original → normalized** · "
        f"original `[{result.source_span[0]}, {result.source_span[1]})` → "
        f"normalized `[{result.projected_span[0]}, {result.projected_span[1]})`"
    )


def normalize_ui(
    original: str, profile: str
) -> tuple[str, dict[str, Any], dict[str, Any], list[list[str | int]], str]:
    """Normalize input and reset the selection display."""
    prepared = prepare_normalization(original, profile)
    return (
        prepared.normalized,
        _highlight(original, None, "Original"),
        _highlight(prepared.normalized, None, "Normalized"),
        prepared.offset_rows(),
        "Select a span in either text box to project it through the offset map.",
    )


def _event_span(text: str, event: gr.SelectData) -> tuple[int, int]:
    index = event.index
    if isinstance(index, int):
        utf16_span = (index, index)
    elif isinstance(index, list | tuple) and len(index) == 2:
        utf16_span = (int(index[0]), int(index[1]))
    else:
        raise ValueError(f"unexpected text selection index: {index!r}")
    return utf16_span_to_codepoints(text, utf16_span)


def select_original(
    original: str, profile: str, event: gr.SelectData
) -> tuple[str, dict[str, Any], dict[str, Any], list[list[str | int]], str]:
    """Project a browser selection in original text to normalized text."""
    span = _event_span(original, event)
    prepared = prepare_normalization(original, profile)
    result = prepared.project(Direction.ORIGINAL_TO_NORMALIZED, span)
    return (
        result.normalized,
        _highlight(result.original, result.source_span, "Selected original"),
        _highlight(result.normalized, result.projected_span, "Projected normalized"),
        prepared.offset_rows(),
        _status(result),
    )


def select_normalized(
    original: str, profile: str, event: gr.SelectData
) -> tuple[str, dict[str, Any], dict[str, Any], list[list[str | int]], str]:
    """Project a browser selection in normalized text back to original text."""
    prepared = prepare_normalization(original, profile)
    span = _event_span(prepared.normalized, event)
    result = prepared.project(Direction.NORMALIZED_TO_ORIGINAL, span)
    return (
        result.normalized,
        _highlight(result.original, result.projected_span, "Projected original"),
        _highlight(result.normalized, result.source_span, "Selected normalized"),
        prepared.offset_rows(),
        _status(result),
    )


initial_normalized, initial_original_highlight, initial_normalized_highlight, initial_rows, _ = (
    normalize_ui(DEFAULT_TEXT, DEFAULT_PROFILE)
)

CSS = """
.arabic-text textarea { direction: rtl; text-align: right; font-size: 1.15rem; }
.arabic-highlight { direction: rtl; text-align: right; }
"""

with gr.Blocks(title="AraClean Offset Map") as demo:
    gr.Markdown(
        """
# AraClean: keep the original span

Normalize Arabic for **RAG retrieval** or **NER model input**, then map every result back to the
untouched source. Choose a profile, normalize, and select text in either box. The paired highlight
shows the projection produced by `OffsetMap.to_original` or `OffsetMap.to_normalized`.
"""
    )

    with gr.Row():
        original_text = gr.Textbox(
            value=DEFAULT_TEXT,
            label="Original Arabic text — select a span",
            lines=5,
            elem_classes="arabic-text",
        )
        normalized_text = gr.Textbox(
            value=initial_normalized,
            label="Normalized text — select a span",
            lines=5,
            interactive=True,
            elem_classes="arabic-text",
        )

    with gr.Row():
        profile = gr.Dropdown(
            choices=[(name.upper(), name) for name in PROFILE_NAMES],
            value=DEFAULT_PROFILE,
            label="Profile",
        )
        normalize_button = gr.Button("Normalize and map", variant="primary")

    status = gr.Markdown("Select a span in either text box to project it through the offset map.")

    with gr.Row():
        original_highlight = gr.HighlightedText(
            value=initial_original_highlight,
            label="Original projection",
            show_legend=True,
            elem_classes="arabic-highlight",
        )
        normalized_highlight = gr.HighlightedText(
            value=initial_normalized_highlight,
            label="Normalized projection",
            show_legend=True,
            elem_classes="arabic-highlight",
        )

    gr.Markdown("### Character-level offset map")
    offset_table = gr.Dataframe(
        value=initial_rows,
        headers=["Normalized index", "Character", "Original interval", "Original slice"],
        datatype=["number", "str", "str", "str"],
        interactive=False,
    )

    gr.Examples(
        examples=[
            ["كتاب أحمـد الكبير", "search"],
            ["قال الرئيسُ محمـدٌ في المؤتمرِ", "ml"],
            ["ﻻ تزالُ العربيةُ جميلةً", "classical"],
            ["زوروا https://example.com يا @صديقي 😍", "social"],
        ],
        inputs=[original_text, profile],
    )

    outputs = [
        normalized_text,
        original_highlight,
        normalized_highlight,
        offset_table,
        status,
    ]
    normalize_button.click(normalize_ui, [original_text, profile], outputs)
    original_text.submit(normalize_ui, [original_text, profile], outputs)
    normalized_text.input(normalize_ui, [original_text, profile], outputs)
    profile.change(normalize_ui, [original_text, profile], outputs)
    original_text.select(select_original, [original_text, profile], outputs)
    normalized_text.select(select_normalized, [original_text, profile], outputs)


if __name__ == "__main__":
    demo.launch(css=CSS)
