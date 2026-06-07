"""Safety classes — the lossless/lossy split that makes a pipeline auditable (ADR-0004)."""

from enum import StrEnum


class SafetyClass(StrEnum):
    """How much information a `Step` may discard.

    `ENCODING_REPAIR` is lossless and default-on (the `LIGHT` profile); `LINGUISTIC_FOLDING`
    is lossy and opt-in. Every `Step` declares one so a `Pipeline` can be audited as lossless
    or have its lossy steps enumerated (story 41).
    """

    ENCODING_REPAIR = "encoding_repair"
    LINGUISTIC_FOLDING = "linguistic_folding"
