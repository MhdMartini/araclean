"""Behavior of the composition layer (`Pipeline`): compose, serialize, rehydrate."""

import unicodedata

from araclean import NormalizeUnicode, Pipeline, SafetyClass

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


def test_to_dict_is_json_serializable() -> None:
    # Reproducible profiles must serialize to plain JSON (story 14 / 40).
    import json

    data = Pipeline([NormalizeUnicode("NFC")]).to_dict()
    assert json.loads(json.dumps(data)) == data


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
