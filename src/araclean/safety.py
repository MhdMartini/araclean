"""Safety classes — the lossless/lossy split that makes a pipeline auditable (ADR-0004)."""

from enum import StrEnum


class SafetyClass(StrEnum):
    """What kind of information a `Step` may discard.

    `ENCODING_REPAIR` is lossless and default-on (the `LIGHT` profile); the other two are lossy
    and opt-in, so only an all-`ENCODING_REPAIR` pipeline is lossless. The two lossy classes name
    *what* is discarded so the audit (story 41) can report it precisely: `LINGUISTIC_FOLDING`
    discards a linguistic distinction *within* the Arabic text (dediacritization, alef/hamza/teh-
    marbuta/maqsura folding, digit/punctuation mapping); `CLEANING` removes *non-linguistic noise*
    around it (URLs, mentions, HTML, emoji). The two are siblings, not synonyms — Cleaning is a
    distinct concern from Normalization (CONTEXT.md), so a URL strip is not "linguistic folding".
    See ADR-0011.
    """

    ENCODING_REPAIR = "encoding_repair"
    LINGUISTIC_FOLDING = "linguistic_folding"
    CLEANING = "cleaning"
