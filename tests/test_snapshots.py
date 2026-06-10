"""Golden snapshots of the profiles over small corpora — the regression net (syrupy).

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


# (label, input) pairs over realistic Arabic spanning what SEARCH (issue 0010) folds for recall —
# vocalized MSA, dialectal/noisy, digits, punctuation — plus the encoding repair it inherits from
# LIGHT. SEARCH is the maximal lossy profile, so this is the regression net for every fold at once.
SEARCH_CORPUS: list[tuple[str, str]] = [
    # vocalized MSA: every tashkeel mark is stripped (كَتَبَ -> كتب)
    (
        "vocalized-msa",
        chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E) + chr(0x0628) + chr(0x064E),
    ),
    # dagger alef -> the standard spelling (هٰذا -> هذا)
    ("dagger-alef", chr(0x0647) + chr(0x0670) + chr(0x0630) + chr(0x0627)),
    # every alef variant folds to bare alef (أ إ آ ٱ -> ا ا ا ا; spaced so the fold is isolated
    # from the elongation cap, which would otherwise collapse the adjacent identical alefs)
    ("alef-variants", " ".join((chr(0x0623), chr(0x0625), chr(0x0622), chr(0x0671)))),
    # hamza carriers fold (ؤ->و, ئ->ي); the standalone hamza ء is kept (light fold, SEARCH default)
    (
        "hamza-carriers",
        chr(0x0645)
        + chr(0x0624)
        + chr(0x0645)
        + chr(0x0646)
        + " "
        + chr(0x0633)
        + chr(0x0626)
        + chr(0x0644)
        + " "
        + chr(0x0621),
    ),
    # teh marbuta -> heh (مدرسة -> مدرسه)
    ("teh-marbuta", chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629)),
    # alef maqsura -> yeh, merging على with علي (the headline recall fold)
    ("maqsura", chr(0x0639) + chr(0x0644) + chr(0x0649)),
    # digit systems unify to ASCII: Arabic-Indic ١٢٣ and Extended ۴۵۶ -> 123 456
    (
        "digits",
        chr(0x0661) + chr(0x0662) + chr(0x0663) + " " + chr(0x06F4) + chr(0x06F5) + chr(0x06F6),
    ),
    # Arabic sentence punctuation -> Latin (نعم، لا؟ -> نعم, لا?)
    (
        "punctuation",
        chr(0x0646)
        + chr(0x0639)
        + chr(0x0645)
        + chr(0x060C)
        + " "
        + chr(0x0644)
        + chr(0x0627)
        + chr(0x061F),
    ),
    # number-separator-safe: an Arabic comma flanked by digits is a separator and is preserved,
    # even as the digits around it fold to ASCII (١٢٣،٤٥٦ -> 123،456)
    (
        "number-separator-preserved",
        chr(0x0661)
        + chr(0x0662)
        + chr(0x0663)
        + chr(0x060C)
        + chr(0x0664)
        + chr(0x0665)
        + chr(0x0666),
    ),
    # emphatic elongation collapses to a single letter (جمييييل -> جميل)
    ("elongation", chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)),
    # SEARCH ⊋ LIGHT on lam-alef: LIGHT keeps ﻷ -> لأ, but SEARCH then folds the hamza alef -> لا
    ("lam-alef-then-folded", chr(0xFEF7)),
    # encoding repair still runs: tatweel is removed (محـــمد -> محمد)
    ("tatweel", chr(0x0645) + chr(0x062D) + chr(0x0640) * 3 + chr(0x0645) + chr(0x062F)),
    # Arabizi hazard respected: an ASCII digit next to Latin letters is never corrupted
    ("arabizi-untouched", "3arab"),
    # plain ASCII passes through (its comma/question are already Latin)
    ("ascii", "Hello, world!"),
    # empty string
    ("empty", ""),
]


def test_search_profile_golden_snapshot(snapshot: SnapshotAssertion) -> None:
    result = {label: normalize(text, profile="search") for label, text in SEARCH_CORPUS}
    assert result == snapshot
