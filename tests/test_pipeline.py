"""Behavior of the composition layer (`Pipeline`): compose, serialize, rehydrate."""

import itertools
import unicodedata

import pytest
from hypothesis import given
from hypothesis import strategies as st
from syrupy.assertion import SnapshotAssertion

from araclean import (
    LIGHT,
    CollapseWhitespace,
    FoldPresentationForms,
    NormalizeUnicode,
    Pipeline,
    SafetyClass,
    StripBidi,
)

# alef + combining hamza (decomposed) so NFC has real work to do; tail = three more letters.
DECOMPOSED = chr(0x0627) + chr(0x0654) + chr(0x062D) + chr(0x0645) + chr(0x062F)
CORPUS = [DECOMPOSED, "", "abc", "نصٌّ"]


def test_single_step_pipeline_equals_the_step() -> None:
    # Layer 1 == Layer 2 for one step (composition-equivalence, base case).
    step = NormalizeUnicode()
    pipe = Pipeline([step])
    for text in CORPUS:
        assert pipe(text) == step(text)


def test_pipeline_composes_steps_left_to_right() -> None:
    # Pipeline([A, B])(x) == B(A(x)).
    a = NormalizeUnicode("NFD")
    b = NormalizeUnicode("NFC")
    pipe = Pipeline([a, b])
    for text in CORPUS:
        assert pipe(text) == b(a(text))


def test_to_dict_from_dict_round_trips_behavior() -> None:
    pipe = Pipeline([NormalizeUnicode("NFC")])
    rebuilt = Pipeline.from_dict(pipe.to_dict())
    for text in CORPUS:
        assert rebuilt(text) == pipe(text)


def test_fold_presentation_forms_round_trips_through_registry() -> None:
    # Every new step must serialize via to_dict/from_dict + the registry (DoD). A LIGHT pipeline
    # now contains FoldPresentationForms, so round-tripping it exercises the new step's contract.
    pipe = Pipeline([NormalizeUnicode("NFC"), FoldPresentationForms()])
    rebuilt = Pipeline.from_dict(pipe.to_dict())
    for text in [*CORPUS, chr(0xFEF7), chr(0xFEFB) + chr(0xFE91)]:
        assert rebuilt(text) == pipe(text)
    # The default LIGHT profile assembles and round-trips identically.
    light = Pipeline.from_profile(LIGHT)
    assert Pipeline.from_dict(light.to_dict())(chr(0xFEF7)) == light(chr(0xFEF7))


def test_to_dict_is_json_serializable() -> None:
    # Reproducible profiles must serialize to plain JSON (story 14 / 40).
    import json

    data = Pipeline([NormalizeUnicode("NFC")]).to_dict()
    assert json.loads(json.dumps(data)) == data


@given(st.lists(st.text()))
def test_batch_agrees_with_calling_the_pipeline(texts: list[str]) -> None:
    # batch(xs) is exactly [pipe(x) for x in xs] (0005 story 13).
    pipe = Pipeline.from_profile(LIGHT)
    assert list(pipe.batch(texts)) == [pipe(t) for t in texts]


def test_batch_is_lazy_over_an_unbounded_stream() -> None:
    # batch must not drain its input before yielding: an infinite generator sliced to N terminates.
    pipe = Pipeline.from_profile(LIGHT)
    stream = (str(n) for n in itertools.count())
    first_three = list(itertools.islice(pipe.batch(stream), 3))
    assert first_three == ["0", "1", "2"]


def test_repr_renders_ordered_step_names(snapshot: SnapshotAssertion) -> None:
    # repr shows the steps in application order, readably (story 15).
    assert repr(Pipeline([NormalizeUnicode("NFC"), StripBidi()])) == (
        "Pipeline([NormalizeUnicode, StripBidi])"
    )
    assert repr(Pipeline([])) == "Pipeline([])"
    # The full LIGHT profile's rendered order is pinned by snapshot.
    assert repr(Pipeline.from_profile(LIGHT)) == snapshot


def test_repr_names_a_custom_step_by_its_class() -> None:
    # A user Step without a registry name is shown by its class name, so it participates in repr.
    class Shout:
        safety = SafetyClass.LINGUISTIC_FOLDING

        def __call__(self, s: str, /) -> str:
            return s.upper()

    assert repr(Pipeline([NormalizeUnicode(), Shout()])) == ("Pipeline([NormalizeUnicode, Shout])")


def test_select_subsets_and_reorders_leaving_the_original_unchanged() -> None:
    # select(*names) yields a NEW pipeline with exactly those steps, in the order named -- covering
    # both subset (a filtered selection) and reorder (the same steps in a new order) (story 16).
    pipe = Pipeline([NormalizeUnicode("NFC"), StripBidi(), CollapseWhitespace()])
    samples = [*CORPUS, "a  b", chr(0x200F) + "x  y"]

    subset = pipe.select("NormalizeUnicode", "CollapseWhitespace")
    expected_subset = Pipeline([NormalizeUnicode("NFC"), CollapseWhitespace()])
    for text in samples:
        assert subset(text) == expected_subset(text)

    reordered = pipe.select("CollapseWhitespace", "StripBidi", "NormalizeUnicode")
    expected_reordered = Pipeline([CollapseWhitespace(), StripBidi(), NormalizeUnicode("NFC")])
    for text in samples:
        assert reordered(text) == expected_reordered(text)

    # The original pipeline is untouched by either call.
    original = Pipeline([NormalizeUnicode("NFC"), StripBidi(), CollapseWhitespace()])
    for text in samples:
        assert pipe(text) == original(text)


def test_custom_step_participates_in_select_and_batch() -> None:
    # A user Step (addressed by its class name) reorders/subsets and streams like a built-in.
    class Shout:
        safety = SafetyClass.LINGUISTIC_FOLDING

        def __call__(self, s: str, /) -> str:
            return s.upper()

    pipe = Pipeline([NormalizeUnicode("NFC"), Shout()])
    # select can drop the custom step (subset) and pick it out (reorder), addressing it by class.
    assert pipe.select("NormalizeUnicode")("café") == "café"
    assert pipe.select("Shout", "NormalizeUnicode")("café") == "CAFÉ"
    # batch streams a corpus through the custom step.
    assert list(pipe.batch(["ab", "cd"])) == ["AB", "CD"]


def test_select_rejects_unknown_and_ambiguous_names() -> None:
    # Unknown name -> clear KeyError. LIGHT runs NFC both first and last (the ordering contract),
    # so addressing "NormalizeUnicode" by name is genuinely ambiguous and is rejected, not guessed.
    light = Pipeline.from_profile(LIGHT)
    with pytest.raises(KeyError, match="No step named 'NotAStep'"):
        light.select("NotAStep")
    with pytest.raises(KeyError, match="ambiguous"):
        light.select("NormalizeUnicode")


def test_custom_step_runs_inside_pipeline() -> None:
    # A user-defined Step (safety + __call__) composes with built-ins (story 47).
    class Shout:
        safety = SafetyClass.LINGUISTIC_FOLDING

        def __call__(self, s: str, /) -> str:
            return s.upper()

    pipe = Pipeline([NormalizeUnicode(), Shout()])
    assert pipe("café") == "CAFÉ"
    # NFC ran first: a decomposed 'é' is composed before upper-casing.
    decomposed_e = "e" + chr(0x0301)  # e + combining acute
    assert pipe(decomposed_e) == unicodedata.normalize("NFC", decomposed_e).upper()
