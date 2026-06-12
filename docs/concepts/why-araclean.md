# Why araclean

Arabic text arrives broken, and the standard fixes break it further. araclean exists to make both
problems boring.

## The two problems

**Arabic text arrives encoded inconsistently.** OCR, PDFs, legacy systems and copy-paste leave
letters as presentation-form glyphs (ﻣﺮﺣﺒﺎ), sprinkle invisible bidi controls and zero-width
characters through strings, stretch words with tatweel, and mix in look-alike letters from Persian
and Urdu keyboards (ک for ك, ی for ي). Two visually identical strings then fail to compare equal,
tokenize differently, and split your vocabulary. None of this is linguistic variation — it is
encoding damage, and repairing it loses nothing.

**The standard preprocessing recipes are destructive by default.** The pipelines the Arabic NLP
community copy-pastes strip tashkeel, fold alef and hamza, and delete characters wholesale as an
unconditional first step. That erases real signal: vocalization disambiguates, على and علي are
different words, and once the marks are gone no downstream step can get them back. The position
paper [*Don't Touch My Diacritics*](https://aclanthology.org/2025.naacl-short.25/) (NAACL 2025)
names exactly this failure mode — routine preprocessing silently degrading diacritic-dependent
orthographies through inconsistent encoding handling and blanket diacritic removal — and the
pattern shows up as user pain across existing tools' issue trackers ("how do I turn normalization
*off*?"). araclean is built to be the reference implementation of the paper's advice.

## The design answer

araclean splits the two problems apart and treats them differently:

- **Encoding repair is lossless and default-on.** The bare `normalize(text)` call fixes the Unicode
  form, presentation forms, tatweel, invisible controls, look-alike letters and whitespace — and
  nothing else. It is safe on any corpus, including vocalized and Qur'anic text.
- **Everything lossy is opt-in and labelled.** Linguistic folding (dediacritization, letter folds,
  digit mapping) and cleaning (URLs, mentions, HTML, emoji, foreign spans) are reachable only
  through named profiles or explicit steps, each declaring a [safety class](safety.md) that the
  pipeline can report back to you (`pipe.audit()`).

This is the core bet: **the user should choose what to discard, with full knowledge — the library
should never decide for them.**

## What sets it apart

As of mid-2026, no other Arabic preprocessing library offers this combination:

| | araclean |
|---|---|
| **Non-destructive default** | The bare call is lossless encoding repair; every lossy fold is opt-in. Incumbent recipes and toolkits are destructive by default or à-la-carte with no safe default. |
| **Reproducible profiles** | Named, versioned, serializable presets (with JSON round-trip and schema). A paper can publish its exact preprocessing; no incumbent can say that. |
| **Auditable safety** | Every step declares lossless/lossy; `audit()` reports what a pipeline discards. Unique to araclean. |
| **Trivial install** | `pip install araclean`, one dependency (pydantic). The big academic suites need a Rust/C++ toolchain, torch, and multi-gigabyte model downloads to install at all. |
| **Typed** | Full type hints with `py.typed` — IDE and type-checker support end to end. None of the established Arabic libraries ship `py.typed`. |
| **Arabic-primary, dual-audience naming** | Steps are named by the established transliteration (`RemoveTashkeel`) and every term is glossed to English in the [glossary](../glossary.md) and on hover — native speakers and NLP practitioners both find what they know. |
| **MIT-licensed, clean** | The closest functional competitor is GPL; the most-copied recipe has no license at all. araclean's core (and its CC0 stopword list) carries no copyleft. |
| **Engineered hot path** | Consecutive character maps fuse into single C-level `str.translate` passes (see [Architecture & performance](architecture.md)) — measured against the incumbents in the repo's benchmark suite. |

The transforms themselves are commodity — every library folds an alef. The differentiation is the
**safety contract, the reproducibility story, and the engineering quality**.

## What araclean is not

Scope discipline is part of the design; these are deliberate boundaries, not gaps:

- **No morphology.** Stemming, lemmatization, clitic segmentation, POS — out of scope. They need
  lexicons or models, which would forfeit the trivial-install core. Compose downstream instead
  (e.g. `snowballstemmer`'s Arabic algorithm after an araclean profile).
- **No tokenizer.** A naive one adds nothing; a real one needs the morphology above.
- **No dialect ID, Arabizi transliteration, or diacritization restoration.** All require model
  weights and data downloads.
- **Not a renderer.** `arabic-reshaper` maps logical text *to* presentation forms for display;
  araclean is the inverse direction (presentation forms back to logical text) — they complement.
- **Not generic mojibake repair.** `ftfy` fixes Latin-centric encoding damage and has no Arabic
  logic; araclean's encoding repair is Arabic-script Unicode hygiene. Run both if you have both
  problems.

## The honest caveats

- **Arabic-only assumption.** Look-alike unification is correct *for Arabic-language text*. If your
  corpus is Persian, Urdu, or mixed Arabic-script, the LIGHT fold of ک→ك / ی→ي is not what you
  want — see the [FAQ](../faq.md).
- **Lossless means canonically equivalent, not byte-identical.** Output is NFC; a non-canonical
  input's mark *ordering* may change while every mark is preserved (see
  [the safety contract](safety.md)).
- **One residual in LIGHT:** a Farsi yeh ی typed word-finally is indistinguishable from alef
  maqsura, so such text can merge على→علي under encoding repair — an accepted, documented residual
  of the Arabic-language assumption.
