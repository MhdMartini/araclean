"""Safety classes — the lossless/lossy split that makes a pipeline auditable (ADR-0004)."""

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class SafetyReport:
    """The safety-class audit of a `Pipeline`: is it lossless, and if not, what does it lose?

    Story 41 / ADR-0004. Each field lists the names of the steps in that safety class, in pipeline
    order, so the report does not merely say *that* a pipeline is lossy but enumerates *which* steps
    lose information and of *what kind* — `linguistic_folding` (a distinction within the Arabic
    text) vs `cleaning` (non-linguistic noise removal). A pipeline is `lossless` iff it carries no
    step of either lossy class, i.e. every step is `ENCODING_REPAIR`.
    """

    encoding_repair: tuple[str, ...]
    linguistic_folding: tuple[str, ...]
    cleaning: tuple[str, ...]

    @property
    def lossless(self) -> bool:
        """True iff no lossy step is present (every step is `ENCODING_REPAIR`)."""
        return not self.linguistic_folding and not self.cleaning

    @property
    def lossy_steps(self) -> tuple[str, ...]:
        """Every lossy step — the linguistic folds followed by the cleaning steps."""
        return self.linguistic_folding + self.cleaning
