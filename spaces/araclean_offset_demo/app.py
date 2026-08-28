"""Gradio entry point for the AraClean offset-map Hugging Face Space."""

from __future__ import annotations

import gradio as gr
from demo import (
    DEFAULT_NORMALIZED_SPAN,
    DEFAULT_PROFILE,
    DEFAULT_TEXT,
    EXAMPLES,
    PROFILE_NAMES,
    Direction,
    HighlightedText,
    ProjectionResult,
    highlight,
    normalize_ui,
    prepare_normalization,
    utf16_span_to_codepoints,
)


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


def _normalized_projection_ui(
    result: ProjectionResult,
) -> tuple[str, HighlightedText, HighlightedText, str]:
    """Render a normalized selection and its original projection."""
    return (
        result.normalized,
        highlight(result.original, result.projected_span, "Projected original"),
        highlight(result.normalized, result.source_span, "Selected normalized"),
        _status(result),
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
) -> tuple[str, HighlightedText, HighlightedText, str]:
    """Project a browser selection in original text to normalized text."""
    span = _event_span(original, event)
    prepared = prepare_normalization(original, profile)
    result = prepared.project(Direction.ORIGINAL_TO_NORMALIZED, span)
    return (
        result.normalized,
        highlight(result.original, result.source_span, "Selected original"),
        highlight(result.normalized, result.projected_span, "Projected normalized"),
        _status(result),
    )


def select_normalized(
    original: str, profile: str, event: gr.SelectData
) -> tuple[str, HighlightedText, HighlightedText, str]:
    """Project a browser selection in normalized text back to original text."""
    prepared = prepare_normalization(original, profile)
    span = _event_span(prepared.normalized, event)
    result = prepared.project(Direction.NORMALIZED_TO_ORIGINAL, span)
    return _normalized_projection_ui(result)


initial_result = prepare_normalization(DEFAULT_TEXT, DEFAULT_PROFILE).project(
    Direction.NORMALIZED_TO_ORIGINAL,
    DEFAULT_NORMALIZED_SPAN,
)
(
    initial_normalized,
    initial_original_highlight,
    initial_normalized_highlight,
    initial_status,
) = _normalized_projection_ui(initial_result)

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

    status = gr.Markdown(initial_status)

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

    outputs = [
        normalized_text,
        original_highlight,
        normalized_highlight,
        status,
    ]
    gr.Examples(
        examples=[list(example) for example in EXAMPLES],
        inputs=[original_text, profile],
        outputs=outputs,
        fn=normalize_ui,
        cache_examples=False,
        run_on_click=True,
    )

    normalize_button.click(normalize_ui, [original_text, profile], outputs)
    original_text.submit(normalize_ui, [original_text, profile], outputs)
    normalized_text.input(normalize_ui, [original_text, profile], outputs)
    profile.change(normalize_ui, [original_text, profile], outputs)
    original_text.select(select_original, [original_text, profile], outputs)
    normalized_text.select(select_normalized, [original_text, profile], outputs)


if __name__ == "__main__":
    demo.launch(css=CSS)
