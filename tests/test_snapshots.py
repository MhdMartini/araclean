"""Golden snapshots of the profiles over small corpora — the regression net (syrupy).

Inputs are built from code points so the corpus is deterministic regardless of how this file
is saved. The snapshot is the contract every later slice extends.
"""

from syrupy.assertion import SnapshotAssertion

from araclean import normalize

# (label, input) pairs covering what LIGHT (now complete) must and must not touch.
CORPUS: list[tuple[str, str]] = [
    # decomposed alef + combining hamza -> composes to alef-with-hamza ("Ahmad")
    ("decomposed-hamza", chr(0x0627) + chr(0x0654) + chr(0x062D) + chr(0x0645) + chr(0x062F)),
    # vocalized text: the tashkeel mark survives (encoding repair never strips vocalization)
    ("vocalized", chr(0x0646) + chr(0x0635) + chr(0x0651)),
    # multi-mark in NON-canonical order is reordered to canonical NFC by LIGHT's closing pass
    # (ADR-0009): beh + shadda (ccc 33) + fatha (ccc 30) -> beh + fatha + shadda
    ("canonicalized-marks", chr(0x0628) + chr(0x0651) + chr(0x064E)),
    # tatweel is now removed (RemoveTatweel): a letter + tatweel + a letter -> the two letters
    ("tatweel", chr(0x0645) + chr(0x0640) + chr(0x062D)),
    # plain lam-alef ligature -> lam + bare alef
    ("lam-alef-plain", chr(0xFEFB)),
    # lam-alef ligature keeps its alef variant -> lam + alef-with-hamza-above (NOT bare lam-alef)
    ("lam-alef-hamza", chr(0xFEF7)),
    # a word as presentation-form glyphs (beh-initial + heh-final) -> base letters
    ("presentation-letters", chr(0xFE91) + chr(0xFEEA)),
    # bidi/zero-width/BOM stripped (StripBidi): BOM + alef + RLM + beh -> alef + beh
    ("invisibles", chr(0xFEFF) + chr(0x0627) + chr(0x200F) + chr(0x0628)),
    # look-alike kaf/yeh/heh unified for Arabic (UnifyLookalikes): keheh+farsi-yeh+heh-goal
    ("lookalikes", chr(0x06A9) + chr(0x06CC) + chr(0x06C1)),
    # the one accepted residual: a Persian-keyboard yeh merges علی -> علي
    ("maqsura-residual", chr(0x0639) + chr(0x0644) + chr(0x06CC)),
    # an emoji ZWJ sequence survives WHOLE (the joiner is content inside emoji — roadmap 0.2);
    # a joiner between Arabic letters is still stripped
    (
        "emoji-zwj-sequence",
        chr(0x1F468) + chr(0x200D) + chr(0x1F469) + " " + chr(0x0645) + chr(0x200D) + chr(0x062D),
    ),
    # whitespace runs (NBSP + double space) collapse to one ASCII space (CollapseWhitespace)
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


# (label, input) pairs over realistic Arabic spanning what SEARCH folds for recall —
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
    # a legitimately DOUBLED letter is not elongation (roadmap 0.1): الله keeps its lams
    ("doubled-letter-preserved", chr(0x0627) + chr(0x0644) * 2 + chr(0x0647)),
    # the tanween-fath carrier alef folds away word-finally (roadmap Phase 1): كتاباً -> كتاب
    (
        "tanween-alef",
        chr(0x0643) + chr(0x062A) + chr(0x0627) + chr(0x0628) + chr(0x0627) + chr(0x064B),
    ),
    # SEARCH ⊋ LIGHT on lam-alef: LIGHT keeps ﻷ -> لأ, but SEARCH then folds the hamza alef -> لا
    ("lam-alef-then-folded", chr(0xFEF7)),
    # encoding repair still runs: tatweel is removed (محـــمد -> محمد)
    ("tatweel", chr(0x0645) + chr(0x062D) + chr(0x0640) * 3 + chr(0x0645) + chr(0x062F)),
    # line breaks are FLATTENED for SEARCH (ADR-0010, collapse_lines=True): unlike LIGHT, which
    # keeps the blank-line run as one newline, SEARCH flattens it to one space for recall
    ("line-breaks", "a  \n\n  b"),
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


# (label, input) pairs for ML: the conservative-on-letters profile. It removes what
# only hurts a tokenizer (vocalization, emphatic elongation) but PRESERVES every alef/hamza/maqsura/
# teh-marbuta distinction, every digit and every Arabic mark. This corpus is the contrast net to
# SEARCH: same inputs, but the letter-fold / digit / punctuation rows stay untouched here.
ML_CORPUS: list[tuple[str, str]] = [
    # vocalized MSA: every tashkeel mark is stripped (كَتَبَ -> كتب) — like SEARCH
    (
        "vocalized-msa",
        chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E) + chr(0x0628) + chr(0x064E),
    ),
    # dagger alef is a vocalization mark, so RemoveTashkeel drops it too (هٰذا -> هذا)
    ("dagger-alef", chr(0x0647) + chr(0x0670) + chr(0x0630) + chr(0x0627)),
    # emphatic elongation collapses to a single letter (جمييييل -> جميل) — like SEARCH
    ("elongation", chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)),
    # legitimately doubled letters are NOT elongation (roadmap 0.1): الله تتكلم ممكن مما unchanged
    (
        "doubled-letters-preserved",
        chr(0x0627)
        + chr(0x0644) * 2
        + chr(0x0647)  # الله
        + " "
        + chr(0x062A) * 2
        + chr(0x0643)
        + chr(0x0644)
        + chr(0x0645)  # تتكلم
        + " "
        + chr(0x0645) * 2
        + chr(0x0643)
        + chr(0x0646)  # ممكن
        + " "
        + chr(0x0645) * 2
        + chr(0x0627),  # مما
    ),
    # alef maqsura is PRESERVED (على stays على) — the headline contrast with SEARCH
    ("maqsura-preserved", chr(0x0639) + chr(0x0644) + chr(0x0649)),
    # alef variants are PRESERVED (أ إ آ ٱ unchanged) — none of the letter folds run
    ("alef-variants-preserved", " ".join((chr(0x0623), chr(0x0625), chr(0x0622), chr(0x0671)))),
    # hamza carriers are PRESERVED (مؤمن keeps its ؤ)
    ("hamza-preserved", chr(0x0645) + chr(0x0624) + chr(0x0645) + chr(0x0646)),
    # teh marbuta is PRESERVED (مدرسة stays مدرسة)
    ("teh-marbuta-preserved", chr(0x0645) + chr(0x062F) + chr(0x0631) + chr(0x0633) + chr(0x0629)),
    # digits are PRESERVED (Arabic-Indic ١٢٣ stays as written)
    ("digits-preserved", chr(0x0661) + chr(0x0662) + chr(0x0663)),
    # Arabic sentence punctuation is PRESERVED (نعم، لا؟ keeps its Arabic marks)
    (
        "punctuation-preserved",
        chr(0x0646)
        + chr(0x0639)
        + chr(0x0645)
        + chr(0x060C)
        + " "
        + chr(0x0644)
        + chr(0x0627)
        + chr(0x061F),
    ),
    # ML ⊊ SEARCH on lam-alef: LIGHT folds ﻷ -> لأ and ML stops there (SEARCH would fold -> لا)
    ("lam-alef-kept-variant", chr(0xFEF7)),
    # encoding repair still runs: tatweel is removed (محـــمد -> محمد)
    ("tatweel", chr(0x0645) + chr(0x062D) + chr(0x0640) * 3 + chr(0x0645) + chr(0x062F)),
    # Arabizi hazard respected: ASCII digits next to Latin letters are never touched
    ("arabizi-untouched", "3arab"),
    # plain ASCII passes through
    ("ascii", "Hello, world!"),
    # empty string
    ("empty", ""),
]


def test_ml_profile_golden_snapshot(snapshot: SnapshotAssertion) -> None:
    result = {label: normalize(text, profile="ml") for label, text in ML_CORPUS}
    assert result == snapshot


# (label, input) pairs for CLASSICAL: the lossless profile for vocalized / Qur'anic
# text. It repairs encoding exactly as LIGHT does, but its contract is that NO vocalization or
# Qur'anic annotation mark is ever removed (the exact opposite of SEARCH on the same inputs). This
# corpus is the regression net for that preservation guarantee: the vocalized / marked rows must
# survive intact, while the pure encoding-repair rows (tatweel, invisibles, look-alike) are still
# cleaned.
CLASSICAL_CORPUS: list[tuple[str, str]] = [
    # vocalized MSA: every tashkeel mark is KEPT (كَتَبَ stays vocalized) — the SEARCH contrast
    (
        "vocalized-msa",
        chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E) + chr(0x0628) + chr(0x064E),
    ),
    # dagger alef is PRESERVED (هٰذا stays هٰذا) — the "dagger alef preserved" golden fixture
    ("dagger-alef-preserved", chr(0x0647) + chr(0x0670) + chr(0x0630) + chr(0x0627)),
    # tanween fath rides with its alef and is KEPT (كتابًا stays vocalized)
    (
        "tanween-preserved",
        chr(0x0643) + chr(0x062A) + chr(0x0627) + chr(0x0628) + chr(0x064B) + chr(0x0627),
    ),
    # shadda + fatha stack KEPT in canonical order (دّرّس-style gemination survives)
    ("shadda-fatha-preserved", chr(0x062F) + chr(0x064E) + chr(0x0651) + chr(0x0631)),
    # Qur'anic annotation KEPT: ر + dagger alef + small high seen; ح + shadda + small high mark
    (
        "quranic-annotation-preserved",
        chr(0x0631) + chr(0x0670) + chr(0x06DC) + " " + chr(0x062D) + chr(0x0651) + chr(0x06DA),
    ),
    # lam-alef ligature inside vocalized text decomposes (keeping its alef variant) WITHOUT
    # disturbing the surrounding marks: بَ + ﻷ + رِ -> بَ + لأ + رِ
    (
        "lam-alef-in-vocalized",
        chr(0x0628) + chr(0x064E) + chr(0xFEF7) + chr(0x0631) + chr(0x0650),
    ),
    # encoding repair still runs: tatweel is removed (محـــمد -> محمد)
    ("tatweel", chr(0x0645) + chr(0x062D) + chr(0x0640) * 3 + chr(0x0645) + chr(0x062F)),
    # encoding repair still runs: BOM + RLM stripped (BOM + alef + RLM + beh -> alef + beh)
    ("invisibles", chr(0xFEFF) + chr(0x0627) + chr(0x200F) + chr(0x0628)),
    # encoding repair still runs: look-alike kaf/yeh/heh unified (keheh+farsi-yeh+heh-goal)
    ("lookalikes", chr(0x06A9) + chr(0x06CC) + chr(0x06C1)),
    # plain ASCII passes through
    ("ascii", "Hello, world!"),
    # empty string
    ("empty", ""),
]


def test_classical_profile_golden_snapshot(snapshot: SnapshotAssertion) -> None:
    result = {label: normalize(text, profile="classical") for label, text in CLASSICAL_CORPUS}
    assert result == snapshot


# (label, input) pairs for SOCIAL: make noisy user text tractable WITHOUT deleting the
# affective signal. It cleans the metadata noise (URL/mention -> Arabic placeholder, HTML strip +
# unescape), removes vocalization, and caps elongation at 2 (emphasis survives), but KEEPS emoji and
# — like ML — runs none of the letter folds, so letter distinctions are preserved. This corpus
# is the regression net for that whole recipe on realistic noisy tweets.
SOCIAL_CORPUS: list[tuple[str, str]] = [
    # the full worked example: cap-2 elongation, tashkeel gone, mention/URL -> Arabic token, emoji
    # kept (جمييييل جدًا يا @user 😍😍 https://example.com)
    (
        "worked-example",
        chr(0x062C)
        + chr(0x0645)
        + chr(0x064A) * 4
        + chr(0x0644)  # جمييييل
        + " "
        + chr(0x062C)
        + chr(0x062F)
        + chr(0x064B)
        + chr(0x0627)  # جدًا (tanween fath)
        + " "
        + chr(0x064A)
        + chr(0x0627)  # يا
        + " @user "
        + chr(0x1F60D) * 2  # 😍😍
        + " https://example.com",
    ),
    # emphatic elongation is capped at 2, not 1: جمييييل -> جمييل (emphasis retained)
    ("elongation-cap-2", chr(0x062C) + chr(0x0645) + chr(0x064A) * 4 + chr(0x0644)),
    # a *vocalized* elongation: tashkeel stripped first (ordering), then the bare run caps to جمييل
    (
        "vocalized-elongation",
        chr(0x062C) + chr(0x0645) + (chr(0x064A) + chr(0x064E)) * 3 + chr(0x0644),
    ),
    # vocalization is removed (كَتَبَ -> كتب)
    (
        "tashkeel-removed",
        chr(0x0643) + chr(0x064E) + chr(0x062A) + chr(0x064E) + chr(0x0628) + chr(0x064E),
    ),
    # @mention -> the Arabic placeholder token [مستخدم]
    ("mention-arabic-token", "@user"),
    # a Unicode handle is matched too (@محمد), and the whole handle -> [مستخدم]
    ("mention-arabic-handle", "@" + chr(0x0645) + chr(0x062D) + chr(0x0645) + chr(0x062F)),
    # URL -> the Arabic placeholder token [رابط]
    ("url-arabic-token", "https://example.com"),
    # an Arabic hashtag is SEGMENTED (roadmap Phase 1): drop '#', '_' -> space, words survive
    (
        "hashtag-segmented",
        "#"
        + chr(0x0627)
        + chr(0x0644)
        + chr(0x064A)
        + chr(0x0648)
        + chr(0x0645)  # اليوم
        + "_"
        + chr(0x0627)
        + chr(0x0644)
        + chr(0x0648)
        + chr(0x0637)
        + chr(0x0646)
        + chr(0x064A),  # الوطني
    ),
    # an email address survives verbatim (roadmap 0.5): it is an address, not a mention
    ("email-kept", "user@example.com"),
    # HTML: tags stripped, entity unescaped (<b>نص</b> &amp; X -> نص & X)
    ("html-strip-unescape", "<b>" + chr(0x0646) + chr(0x0635) + "</b> &amp; X"),
    # emoji is KEPT — the affective signal SOCIAL exists to preserve (أحبه 😍)
    ("emoji-kept", chr(0x0623) + chr(0x062D) + chr(0x0628) + chr(0x0647) + " " + chr(0x1F60D)),
    # letter distinctions are PRESERVED (no letter fold runs): على stays على, not folded to علي
    ("maqsura-preserved", chr(0x0639) + chr(0x0644) + chr(0x0649)),
    # encoding repair still runs: tatweel removed (محـــمد -> محمد)
    ("tatweel", chr(0x0645) + chr(0x062D) + chr(0x0640) * 3 + chr(0x0645) + chr(0x062F)),
    # plain ASCII passes through
    ("ascii", "Hello, world!"),
    # empty string
    ("empty", ""),
]


def test_social_profile_golden_snapshot(snapshot: SnapshotAssertion) -> None:
    result = {label: normalize(text, profile="social") for label, text in SOCIAL_CORPUS}
    assert result == snapshot
