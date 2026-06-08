"""Golden snapshot of the LIGHT profile over a small corpus — the regression net (syrupy).

Inputs are built from code points so the corpus is deterministic regardless of how this file
is saved. The snapshot is the contract every later slice extends.
"""

from syrupy.assertion import SnapshotAssertion

from araclean import normalize

# (label, input) pairs covering what LIGHT (NFC only, for now) must and must not touch.
CORPUS: list[tuple[str, str]] = [
    # decomposed alef + combining hamza -> composes to alef-with-hamza ("Ahmad")
    ("decomposed-hamza", chr(0x0627) + chr(0x0654) + chr(0x062D) + chr(0x0645) + chr(0x062F)),
    # already-composed vocalized text: marks and their order are preserved
    ("vocalized", chr(0x0646) + chr(0x0635) + chr(0x0651)),
    # tatweel is preserved (removed only by a later step)
    ("tatweel", chr(0x0645) + chr(0x0640) + chr(0x062D)),
    # plain lam-alef ligature -> lam + bare alef
    ("lam-alef-plain", chr(0xFEFB)),
    # lam-alef ligature keeps its alef variant -> lam + alef-with-hamza-above (NOT bare lam-alef)
    ("lam-alef-hamza", chr(0xFEF7)),
    # a word as presentation-form glyphs (beh-initial + heh-final) -> base letters
    ("presentation-letters", chr(0xFE91) + chr(0xFEEA)),
    # plain ASCII passes through untouched
    ("ascii", "Hello, world!"),
    # empty string
    ("empty", ""),
]


def test_light_profile_golden_snapshot(snapshot: SnapshotAssertion) -> None:
    result = {label: normalize(text) for label, text in CORPUS}
    assert result == snapshot
