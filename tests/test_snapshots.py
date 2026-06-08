"""Golden snapshot of the LIGHT profile over a small corpus — the regression net (syrupy).

Inputs are built from code points so the corpus is deterministic regardless of how this file
is saved. The snapshot is the contract every later slice extends.
"""

from syrupy.assertion import SnapshotAssertion

from araclean import normalize

# (label, input) pairs covering what LIGHT (now complete, 0002-0004) must and must not touch.
CORPUS: list[tuple[str, str]] = [
    # decomposed alef + combining hamza -> composes to alef-with-hamza ("Ahmad")
    ("decomposed-hamza", chr(0x0627) + chr(0x0654) + chr(0x062D) + chr(0x0645) + chr(0x062F)),
    # vocalized text: the tashkeel mark survives (encoding repair never strips vocalization)
    ("vocalized", chr(0x0646) + chr(0x0635) + chr(0x0651)),
    # multi-mark in NON-canonical order is reordered to canonical NFC by LIGHT's closing pass
    # (ADR-0009): beh + shadda (ccc 33) + fatha (ccc 30) -> beh + fatha + shadda
    ("canonicalized-marks", chr(0x0628) + chr(0x0651) + chr(0x064E)),
    # tatweel is now removed (RemoveTatweel, 0004): a letter + tatweel + a letter -> the two letters
    ("tatweel", chr(0x0645) + chr(0x0640) + chr(0x062D)),
    # plain lam-alef ligature -> lam + bare alef
    ("lam-alef-plain", chr(0xFEFB)),
    # lam-alef ligature keeps its alef variant -> lam + alef-with-hamza-above (NOT bare lam-alef)
    ("lam-alef-hamza", chr(0xFEF7)),
    # a word as presentation-form glyphs (beh-initial + heh-final) -> base letters
    ("presentation-letters", chr(0xFE91) + chr(0xFEEA)),
    # bidi/zero-width/BOM stripped (StripBidi, 0004): BOM + alef + RLM + beh -> alef + beh
    ("invisibles", chr(0xFEFF) + chr(0x0627) + chr(0x200F) + chr(0x0628)),
    # look-alike kaf/yeh/heh unified for Arabic (UnifyLookalikes, 0004): keheh+farsi-yeh+heh-goal
    ("lookalikes", chr(0x06A9) + chr(0x06CC) + chr(0x06C1)),
    # the one accepted residual: a Persian-keyboard yeh merges علی -> علي
    ("maqsura-residual", chr(0x0639) + chr(0x0644) + chr(0x06CC)),
    # whitespace runs (NBSP + double space) collapse to one ASCII space (CollapseWhitespace, 0004)
    ("whitespace", "a" + chr(0x00A0) + chr(0x0020) + "b"),
    # line breaks are preserved (ADR-0010): a blank-line run collapses to a single newline, while
    # the horizontal whitespace on each side is absorbed into it
    ("line-breaks", "a  \n\n  b"),
    # plain ASCII passes through untouched
    ("ascii", "Hello, world!"),
    # empty string
    ("empty", ""),
]


def test_light_profile_golden_snapshot(snapshot: SnapshotAssertion) -> None:
    result = {label: normalize(text) for label, text in CORPUS}
    assert result == snapshot
