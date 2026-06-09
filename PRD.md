# PRD — araclean: Arabic Text Normalization & Cleaning

> Status: ready for implementation. Decisions in this PRD are grounded in [`CONTEXT.md`](./CONTEXT.md)
> (ubiquitous language), [`GLOSSARY.md`](./GLOSSARY.md) (terminology), and
> [`docs/adr/0001`–`0010`](./docs/adr/). This PRD is intended to be sliced
> into independently-grabbable issues (tracer-bullet vertical slices); each issue is implemented with
> TDD.

---

## Problem Statement

Practitioners working with Arabic text for NLP have no modern, trustworthy preprocessing library.
The existing options force a bad trade-off:

- **They silently destroy signal.** Every popular recipe and library strips tashkeel (diacritics) and folds
  letters *by default*, collapsing real distinctions (grammatical case, gender, negation, and names
  like على "on" vs علي "Ali"). Practitioners apply these destructive steps by rote, with no per-step
  control, no record of what was done, and no awareness that they may be deleting the very signal
  their model needs.
- **They are painful to install and run.** The most capable suite needs a Rust/CMake/Boost build and
  a ~1.8 GB data download; another needs a Java runtime. People give up and paste fragile regex
  blocks instead.
- **They are unmaintained, untyped, and undocumented.** No incumbent is simultaneously maintained,
  fully type-hinted (with a `py.typed` marker), modern-documented, normalization-focused, well-tested,
  and easy to install. The best-engineered one is abandoned; the maintained ones are legacy-shaped.
- **Results aren't reproducible.** Two projects "doing standard Arabic preprocessing" produce
  different output, because there is no standard, versioned, shareable configuration.

The result: Arabic NLP work is harder, less reproducible, and quietly lossy.

## Solution

**araclean** — a modern, MIT-licensed, pure-Python library for Arabic text **Normalization** and
**Cleaning**, that is:

- **Non-destructive by default.** The bare call performs only lossless **Encoding repair**. Every
  information-losing **Linguistic folding** step is opt-in. (ADR-0004)
- **Trivial to install.** `pip install araclean` — pure Python, no compiler, no Java, no multi-GB
  download. (ADR-0006)
- **Type-first.** Fully type-hinted, ships `py.typed`; validation lives at the config boundary via
  pydantic + `@validate_call`, never on the per-string hot path. (ADR-0003)
- **Composable and reproducible.** A three-layer API: pure functions → a serializable `Pipeline` of
  `Step`s → one-call `normalize(text, profile=...)`. Profiles are named, versioned, shareable, and
  JSON-Schema-validated. (ADR-0003)
- **Fast.** Char-level maps run as fused `str.translate` passes (one C-level pass; faster than the
  char-by-char loop in the nearest incumbent). (ADR-0006)
- **Well-documented and well-tested.** mkdocs-material + mkdocstrings; full test rigor (parametrized
  Unicode tables, Hypothesis properties, golden snapshots, differential tests vs incumbents).

Casual users get a safe one-liner; power users compose and pin exact, auditable pipelines.

---

## User Stories

### Installation & first use
1. As an Arabic NLP practitioner, I want to `pip install araclean` with no compiler, Java, or data
   download, so that I can start in seconds on any machine or CI runner.
2. As a cautious user, I want `normalize(text)` with no arguments to only repair encoding (lossless),
   so that I never accidentally destroy linguistic signal.
3. As a new user, I want a 3-line quickstart that visibly works, so that I can evaluate the library
   immediately.
4. As a lean-dependency user, I want the core to pull in almost nothing, so that my environment stays
   small; heavier conveniences should be opt-in extras.

### Profiles (presets)
5. As a search/IR engineer, I want `normalize(text, profile="search")` to aggressively maximize recall
   (remove tashkeel, fold alef/hamza/teh-marbuta/maqsura, fold digits, strip tatweel, reduce elongation),
   so that query and document variants match.
6. As an ML engineer, I want `profile="ml"` to clean text for model input while *preserving*
   alef/hamza/maqsura distinctions, so that I don't raise language-model loss by over-folding.
7. As a social-media analyst, I want `profile="social"` to handle URLs, mentions, emoji, and
   elongation, so that noisy user text becomes tractable without deleting affective signal.
8. As a scholar of classical/Qur'anic text, I want `profile="classical"` to repair encoding while
   *keeping* tashkeel and Qur'anic annotation marks, so that vocalization and structure survive.
9. As any user, I want the default to equal the `LIGHT` profile (lossless), so that the safe path is
   the default path.
10. As a user, I want each profile documented with exactly which steps it applies and whether each is
    lossless or lossy, so that I can choose with full knowledge of the trade-off.

### Composable pipeline (power users)
11. As a power user, I want to build a `Pipeline` from an explicit, ordered list of `Step`s, so that I
    control precisely what happens and in what order.
12. As a power user, I want to call a pipeline like a function (`pipe(text)`), so that it drops into
    `map`/`apply` naturally.
13. As a data engineer, I want `pipe.batch(iterable)` with streaming, so that I can process corpora
    larger than memory.
14. As a reproducibility-minded user, I want `pipe.to_dict()` / `Pipeline.from_dict(...)`, so that I
    can serialize, pin, version, and share the exact transformation.
15. As a user, I want a readable `repr(pipe)`, so that I can see at a glance what a pipeline does.
16. As a user, I want to reorder or subset steps, so that I can adapt a profile without starting over.
17. As a user, I want pipelines built from a profile (`Pipeline.from_profile("search")`), so that I
    can start from a preset and then customize.

### Individual normalization steps (Encoding repair — lossless, default-on)
18. As a user, I want a step that applies a Unicode normalization form, so that combining marks and
    canonical forms are deterministic.
19. As a user, I want presentation-form glyphs (Arabic Presentation Forms-A/-B) folded back to base
    letters, so that OCR/legacy/copy-paste text matches normally.
20. As a user, I want **lam-alef ligatures** (the single glyphs U+FEF5–U+FEFC, e.g. ﻻ U+FEFB) decomposed
    to their two letters — lam + the matching alef variant — so that text that looks identical actually
    matches, tokenizes, and counts correctly. Each ligature keeps its alef variant: ﻻ (U+FEFB) → لا,
    ﻷ (U+FEF7) → لأ (hamza above), ﻹ (U+FEF9) → لإ (hamza below), ﻵ (U+FEF5) → لآ (madda); they must
    **not** all collapse to bare لا.
21. As a user, I want tatweel (ـ, U+0640) removed, so that elongated spellings collapse to one
    form. (Safe, always applicable.)
22. As a user, I want bidi control characters and zero-width characters (RLM/LRM, ZWJ/ZWNJ, BOM)
    stripped, so that invisible noise stops breaking string equality and tokenization.
23. As a user, I want look-alike letters from other Arabic-script languages unified for Arabic text
    (Persian kaf U+06A9 → Arabic kaf U+0643; Farsi yeh U+06CC → yeh U+064A; heh variants → U+0647), so
    that keyboard/encoding artifacts stop silently breaking matches. (Correct under the Arabic-language
    assumption — araclean is Arabic-only. One accepted residual: U+06CC is dotless word-finally, so an
    alef-maqsura word typed on a Persian keyboard can merge على→علي; this is the only look-alike fold
    that is not strictly lossless.)
24. As a user, I want horizontal whitespace normalized (NBSP and other Unicode spaces collapsed to a
    single space) while **line breaks are preserved** (each run collapsed to a single newline), so
    that spacing differences don't create duplicate tokens without flattening document structure.
    Flattening lines to spaces is opt-in (`collapse_lines`, set by `SEARCH`). (ADR-0010)

### Individual normalization steps (Linguistic folding — lossy, opt-in)
25. As a user, I want a step to remove tashkeel (the diacritical marks), so that vocalized and
    unvocalized spellings match — *only when I ask for it*.
26. As a user, I want the tashkeel-removal step to be configurable — **selecting which mark classes to
    remove (harakat/short vowels, tanween, shadda, madda, dagger alef, Qur'anic annotation marks)
    independently** — so that I can control how deep tashkeel removal goes. Sukun is formally the
    *absence* of a haraka (not a haraka) but rides with the harakat: it is always removed together with
    them and never on its own, since stripping the vowels while leaving a bare sukun is never wanted.
    (This selective control is a deliberate edge: no incumbent offers it cleanly — see
    [`docs/competitive-landscape.md`](./docs/competitive-landscape.md).)
27. As a user, I want alef variants (أ إ آ ٱ) folded to bare alef ا, so that initial-hamza
    inconsistency stops hurting recall — opt-in.
28. As a user, I want hamza-carrier folding (ؤ→و, ئ→ي, and optionally dropping standalone ء) as a
    *separate, more aggressive* toggle, so that I can fold lightly or heavily.
29. As a user, I want teh marbuta (ة) → heh (ه) as an opt-in step with a configurable target
    (ه vs ت vs keep), so that I match the convention my task needs.
30. As a user, I want alef maqsura (ى) → yeh (ي) as an opt-in step, so that Egyptian/informal spelling
    variants match — while knowing it merges على/علي.
31. As a user, I want digits converted between Arabic-Indic, Extended (Persian/Urdu), and ASCII with a
    chosen target, so that numbers parse and match consistently.
32. As a user, I want Arabic punctuation mapped to Latin equivalents (، ؛ ؟ → , ; ?) as an opt-in step,
    so that a single tokenizer/sentence-splitter works — with number separators handled safely.
33. As a social-media user, I want word-lengthening reduced (جمييييل → جميل), with the cap configurable
    (1 or 2), so that vocabulary doesn't explode while I can keep emphasis if I want.

### Cleaning steps (noise removal)
34. As a user, I want URLs, @mentions, and HTML **either removed or replaced with a configurable
    placeholder token** (e.g. `[URL]`/`[رابط]`, `[MENTION]`/`[مستخدم]`), so that metadata noise doesn't
    pollute features. (Replace-with-placeholder must be first-class, not just delete: it is the
    entrenched expectation set by AraBERT's widely-copied recipe — see
    [`docs/competitive-landscape.md`](./docs/competitive-landscape.md). HTML cleaning must also unescape
    entities, e.g. `&amp;` → `&`.)
35. As a sentiment analyst, I want emoji handling that can keep, strip, or demojize emoji, so that I
    can preserve affective signal when it matters.

### Stopwords
36. As a user, I want a curated, versioned Arabic stopword list and a `RemoveStopwords` step, so that I
    get reproducible stopword removal without hunting for a list.
37. As a careful user, I want the stopword list documented as flat (not clitic-aware) and the negation
    risk called out, so that I don't accidentally strip ما/لا/لم before a sentiment task.

### Typing, reproducibility & safety
38. As a typed-codebase developer, I want full type hints and a `py.typed` marker, so that mypy/pyright
    check my usage and my editor autocompletes options.
39. As a user, I want option values constrained (e.g. unicode form, digit target, profile name) so that
    typos are caught statically and at the config boundary, not silently ignored.
40. As a researcher, I want to emit/validate a profile as JSON (with a JSON Schema), so that I can
    publish the exact preprocessing alongside a paper and others can reproduce it.
41. As an auditor, I want each step to declare its safety class (Encoding repair vs Linguistic folding),
    so that I can verify a pipeline is lossless or enumerate exactly what it loses.

### Performance & integration
42. As a data engineer, I want char-level normalization to run as a single fused pass, so that
    million-row corpora process quickly in pure Python.
43. As a pandas user, I want `df["text"].araclean.normalize(profile=...)`, so that preprocessing is one
    idiomatic call in my dataframe workflow.
44. As a polars user, I want an equivalent accessor, so that I get the same ergonomics on polars.
45. As a shell user, I want a CLI (`araclean normalize --profile search FILE`, stdin/stdout, JSONL
    batch), so that I can clean corpora without writing Python.
46. As a performance-conscious user, I want published benchmarks vs CAMeL Tools/pyarabic on a realistic
    mixed corpus, so that I can trust the speed claims.

### Extensibility & contribution
47. As an advanced user, I want to write my own `Step` (a `str→str` callable) and drop it into a
    pipeline, so that I can extend behavior without forking.
48. As a future maintainer, I want the `Step` contract to already allow optional offset/alignment
    tracking, so that span-mapping can be added later without a breaking change. (ADR-0005)
49. As an open-source contributor, I want CONTRIBUTING docs, a code of conduct, issue/PR templates,
    CI, and a clear test bar, so that I can contribute confidently via pull request.
50. As a maintainer, I want automated, convention-driven releases, so that versioning, changelog, and
    PyPI publishing are consistent and hands-off.

### Documentation, terminology & orthographic conventions
51. As an Arabic-speaking user who knows the script but not the English jargon, I want each operation
    named with its established Arabic term (e.g. `RemoveTashkeel`) and glossed to the English equivalent
    ("diacritics"), backed by a bidirectional glossary, so that I can use the library without first
    learning NLP jargon — while an English-speaking practitioner searching "diacritics" still finds it.
    (Convention fixed in [`CONTEXT.md`](./CONTEXT.md) + [`GLOSSARY.md`](./GLOSSARY.md); binds all
    contributors and future agents. Docs render glosses as mkdocs-material hover tooltips.)
52. As a user pinning a specific araclean version, I want versioned documentation (via `mike`), so that
    the docs I read always match the version I installed.

---

## Implementation Decisions

Grounded in the ADRs; see each referenced ADR for rationale.

### Architecture — three-layer API (ADR-0003)
- **Layer 1 — pure functions:** each `Step`'s behavior is also exported as a free `str → str`
  function for standalone use.
- **Layer 2 — `Pipeline`:** an ordered, reorderable, **serializable** sequence of `Step`s; modeled
  on HuggingFace `tokenizers` (`Sequence` of normalizers).
- **Layer 3 — facade:** `normalize(text, profile=..., config=..., **overrides)` one-call sugar +
  named `Profile`s. Default profile = `LIGHT`.

Interface sketches (type shapes that encode decisions; final signatures may refine):

```python
class SafetyClass(StrEnum):
    ENCODING_REPAIR = "encoding_repair"   # lossless, default-on
    LINGUISTIC_FOLDING = "linguistic_folding"  # lossy, opt-in

@runtime_checkable
class Step(Protocol):
    safety: SafetyClass
    def __call__(self, s: str, /) -> str: ...
    # reserved, optional (ADR-0005); absence => offsets unsupported by this step:
    # def apply_aligned(self, s: str, /) -> tuple[str, OffsetMap]: ...

class Pipeline:
    def __init__(self, steps: Sequence[Step]) -> None: ...
    def __call__(self, text: str, /) -> str: ...
    def batch(self, texts: Iterable[str]) -> Iterator[str]: ...   # streaming
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "Pipeline": ...
    @classmethod
    def from_profile(cls, name: str | Profile) -> "Pipeline": ...

def normalize(
    text: str, *,
    profile: str | Profile | None = None,   # None => LIGHT
    config: NormalizeConfig | None = None,
    **overrides: object,
) -> str: ...
```

### Validation boundary (ADR-0003)
- `NormalizeConfig` and `Profile` are **pydantic v2 models** (validated on construction; can emit
  JSON Schema). Closed option sets use `Literal`/`StrEnum` (e.g. unicode form, digit target).
- Public **construction/config-taking** callables use `@validate_call`. The per-string execution
  surface (`pipe(text)`, `pipe.batch()`, bare step functions) does **no** per-call validation.
- Internal structures are `TypedDict`.
- **Python ≥ 3.12.**

### Modules (deep vs thin)
- **`chars` (deep):** all Unicode code-point sets and the `str.maketrans` table / precompiled-regex
  **builders**. Single source of truth for code points. Interface: functions returning translate
  tables / compiled patterns. Stable.
- **`steps` (deep):** the `Step` family; each precomputes its table/regex at construction, exposes a
  `safety` class, and is a pure `str → str` callable. Compatible single-char steps must be designed
  so a profile can **fuse** them into one `translate` pass (ADR-0006).
- **`pipeline` (deep):** composition engine — invoke, stream/batch, (de)serialize, reorder; reserved
  optional offset hook.
- **`profiles` + `config` (deep):** pydantic trust boundary + the named presets that assemble
  pipelines.
- **`api` (thin):** the `normalize` facade and `@validate_call` entry points.
- **`cli` (thin):** Typer app behind the `[cli]` extra; stdin/stdout, `--profile`, JSONL batch.
- **`integrations` (thin):** pandas/polars accessors behind `[pandas]`/`[polars]` extras.
- **`stopwords` (thin/data):** curated, versioned list + lookup; backs `RemoveStopwords`.

### Profiles — intended composition (safety class fixed; exact folding sets finalized per-issue)
- **`LIGHT`** (default, **all Encoding repair / lossless**): Unicode form (NFC); fold presentation
  forms incl. lam-alef; remove tatweel; strip bidi/zero-width/BOM; unify look-alike kaf/yeh/heh for
  Arabic; collapse whitespace. **No** tashkeel removal, letter folding, or digit/punctuation mapping.
- **`SEARCH`** (aggressive recall, lossy): `LIGHT` + remove tashkeel (harakat/tanween/shadda/madda/dagger
  alef/Qur'anic marks) + fold alef + fold hamza carriers + teh-marbuta→heh + alef-maqsura→yeh + digits
  → ASCII + map punctuation → Latin + reduce elongation.
- **`ML`** (model input, lossy but conservative on letters per the *AraToken* finding): `LIGHT` +
  remove tashkeel + reduce elongation (+ optional digit fold); **preserve** alef/hamza/maqsura/
  teh-marbuta distinctions.
- **`SOCIAL`** (social media): `LIGHT` + URL/mention/HTML → placeholders + emoji handling
  (keep/strip/demojize, default keep) + reduce elongation + remove tashkeel. Configurable.
- **`CLASSICAL`** (classical/Qur'anic): `LIGHT`-style encoding repair that **preserves** tashkeel and
  Qur'anic annotation marks; lam-alef/presentation-form handling must preserve combining-mark order.

### Cross-cutting decisions
- **Ordering contract:** Unicode form → strip invisibles → fold presentation forms / lam-alef →
  remove tatweel → remove tashkeel → letter folding → digit/punctuation mapping → social/whitespace
  cleanup. Steps and profiles must respect this; document the two classic hazards (NFKC-after-tashkeel
  reordering; ASCII-digit conversion before Arabizi detection — Arabizi is out of scope but the digit
  step must not assume Arabizi-free input silently).
- **Lossless/lossy split is a hard contract.** Every `Step` declares `safety`; `LIGHT` and any
  "lossless" profile must contain only `ENCODING_REPAIR` steps (enforced/asserted).
- **Reference oracles (not dependencies):** CAMeL Tools and pyarabic are used only for differential
  tests and benchmarks (ADR-0002).

### Packaging, tooling, ops
- Build: hatchling; env/installer: uv; lint/format: ruff; spelling: cspell (project dictionary of the
  canonical Arabic terms, enforcing the GLOSSARY); types: mypy `--strict` + pyright; hooks:
  pre-commit; docs: mkdocs-material + mkdocstrings (Google docstrings, doctested), **versioned with
  `mike`** (each release publishes a pinned docs version with a `latest` alias, so the docs a user
  reads match the version they installed — a reproducibility requirement, not a nicety).
- CI: GitHub Actions matrix (Python 3.12–3.14 × Linux/macOS/Windows).
- Releases: Conventional Commits → python-semantic-release → PyPI Trusted Publishing (OIDC).
- Extras: `[cli]` (typer, rich), `[pandas]`, `[polars]`, `[all]`; GPL-licensed deps (if any, e.g.
  unidecode for any future transliteration) must stay isolated behind an extra to protect the MIT core.

---

## Testing Decisions

**What makes a good test here:** assert **external behavior** — given input string and configuration,
the output string (or the raised error) — never internal representations (table contents, private
attributes, call order). Tests must pin *what* a transform guarantees, not *how* it is implemented, so
the fused-`translate` engine can change without breaking tests. This PRD will be sliced into issues;
each issue is built **TDD** (write the failing behavior test first, then implement).

**Modules with dedicated isolation suites** (confirmed): `chars`, `steps`, `pipeline`, `profiles`+`config`.

- **`chars`** — **Parametrized Unicode case tables**: for every relevant code point/class (all alef,
  hamza-carrier, yeh/maqsura, teh-marbuta variants; harakat/tanween/shadda/madda; dagger alef & Qur'anic
  marks; tatweel; lam-alef & presentation forms FEF5–FEFC and the FE70–FEFF / FB50–FDFF ranges; digit
  sets U+0660–0669 / U+06F0–06F9; punctuation; look-alike kaf/yeh/heh; bidi & zero-width sets),
  assert the produced mapping. Raw `"\uXXXX"` escapes in tables so failures are unambiguous.
- **`steps`** — per-step **parametrized cases** + **Hypothesis properties**: idempotence
  (`f(f(x)) == f(x)`), total/no-crash on arbitrary Unicode (`st.text()` incl. surrogates), and the
  **safety-class invariant** (a `lossless` step never removes a code point outside the
  encoding-repair set). Edge cases: empty, whitespace-only, already-normalized, RTL/LTR mix, emoji,
  combining-mark stacking order.
- **`pipeline`** — **Hypothesis properties**: composition-equivalence (`Pipeline([A, B])(x) ==
  B(A(x))`), idempotence of idempotent profiles, `to_dict`/`from_dict` round-trip equality, and
  `batch(xs) == [pipe(x) for x in xs]`.
- **`profiles` + `config`** — **golden/snapshot tests** (syrupy) of each profile on realistic Arabic
  corpora (vocalized/Qur'anic, MSA news, dialectal social, mixed Arabizi/Latin) as the regression
  net; **invariants**: `LIGHT` is a lossless fixed point, `SEARCH`-output is also `LIGHT`-stable
  (search ⊇ light); config validation rejects bad options and round-trips through JSON Schema;
  **differential tests** vs CAMeL/pyarabic for operations that should agree (e.g. tashkeel removal),
  with intentional divergences documented.

**Canonical linguistic cases (golden fixtures)** — concrete, behavior-level fixtures that pin the
terminology/safety rulings in `GLOSSARY.md` + `CONTEXT.md` (the exact cases naive implementations get
wrong); each is the regression anchor for the issue that implements its step:

| Case | Input | Config / profile | Expected | Pins |
|---|---|---|---|---|
| maqsura not folded by default | `على` / `علي` | `LIGHT`, `ML` | `على` / `علي` (kept distinct) | ى→ي is opt-in; `ML` preserves the distinction |
| maqsura folds under search | `على` | `SEARCH` | `علي` | the documented على/علي merge |
| lam-alef ligature keeps its alef variant | `ﻷ` (U+FEF7) | `LIGHT` (Encoding repair) | `لأ` (U+0644 U+0623) — **not** `لا` | hamza/madda must survive decomposition |
| plain lam-alef ligature | `ﻻ` (U+FEFB) | `LIGHT` | `لا` (U+0644 U+0627) | presentation-form fold under NFC, not NFKC |
| selective shadda | `دَرَّس` | remove harakat, **keep** shadda | `درّس` | dropping shadda conflates درّس / درس |
| tanween fath keeps its alef | `كتابًا` (…ب + U+064B + ا) | remove tanween | `كتابا` | remove the U+064B mark, **not** the alef letter |
| dagger alef → standard spelling | `هٰذا` (+ U+0670) | `SEARCH` / remove dagger alef | `هذا` | it's normal MSA, not Qur'anic-only |
| dagger alef preserved | `هٰذا` | `CLASSICAL` | `هٰذا` (unchanged) | CLASSICAL keeps vocalization |
| sukun rides with harakat | `مِنْ` | remove harakat | `من` | sukun isn't a haraka but always rides with them, never alone |
| Farsi yeh residual (accepted) | `علی` (…ل + U+06CC) | `LIGHT` (Encoding repair) | `علي` | the one look-alike fold that isn't strictly lossless |

**Thin modules** (`api`, `cli`, `integrations`, `stopwords`) are covered by **integration tests**
through the facade (e.g. `normalize(text, profile=...)` end-to-end; CLI invoked on sample stdin;
accessor on a small DataFrame/Series; stopword list integrity + removal behavior).

**Prior art / oracles:** CAMeL Tools and pyarabic test suites (and their dediac/normalize behavior)
as differential oracles; HuggingFace `tokenizers` normalizer tests as a model for composable-step
testing; Hypothesis's documented strength at finding Unicode/normalization bugs.

---

## Out of Scope

Deferred (architecture must allow these later without breaking the core — ADR-0001, ADR-0005):

- **Morphology:** stemming, clitic/morphological tokenization, lemmatization.
- **Dialect modeling** and **Arabizi/Franco-Arabic transliteration** (note: the digit step must not
  silently corrupt Arabizi, but detecting/handling Arabizi is out of scope).
- **Trained spaCy/HuggingFace pipelines** (a spaCy tokenizer/component is a candidate *later*).
- **A general tokenizer** (a naive one adds little; a real one needs the deferred morphology).
- **Orthographic respacing** (e.g. re-attaching a space-separated conjunction waw, `أنا و أخي` →
  `أنا وأخي`). The proclitic-attachment rule itself is firm, but reliably identifying which standalone
  و is the proclitic is heuristic — revisit later as an opt-in Linguistic-folding step.
- **Offset/alignment tracking** (interface reserved via the optional `apply_aligned` Protocol; not
  implemented in v1 — ADR-0005).
- **Rust/native acceleration** (pure-Python v1; escalation path only, behind a fallback — ADR-0006).
- **Calendar/date conversion** (Hijri↔Gregorian) and currency/number *extraction* — normalization may
  unify digit scripts and separators, but structured extraction is a separate concern.

## Further Notes

- **The language spine** (`CONTEXT.md`): **Encoding repair** (lossless, default-on) vs **Linguistic
  folding** (lossy, gated). This split is the safety contract that makes "non-destructive by default"
  enforceable and auditable, and it is the project's core differentiator.
- **The *AraToken* finding** drives the `SEARCH` vs `ML` divergence: aggressive letter-folding raises
  language-model loss because hamza/alef/maqsura variants are disambiguating — so `ML` cleans without
  folding those, while `SEARCH` folds for recall.
- **Positioning:** directly answers the two loudest, best-documented community complaints —
  install/deploy friction and silent over-normalization (cf. Gorman & Pinter, "Don't Touch My
  Diacritics", arXiv:2410.24140, 2024; NAACL 2025 — a position paper that names the problem and ships
  no tool, so araclean can be its reference implementation). See [`docs/competitive-landscape.md`](./docs/competitive-landscape.md).
- **Parking lot to settle during slicing/implementation:** the exact code-point set each folding step
  touches; the default digit behavior for `LIGHT` (recommend `keep`); the stopword list's source and
  curation method (**resolved during competitive review**: curate fresh, MIT/CC0, **negation-safe by
  default** — exclude particles like ما/لا/لم/لن/ليس so `RemoveStopwords` can't silently flip sentiment;
  do **not** reuse the GPL `Arabic-Stopwords`; see [`docs/competitive-landscape.md`](./docs/competitive-landscape.md));
  `SOCIAL`'s precise emoji/URL/mention defaults; ZWNJ handling default for Arabic
  (recommend strip, configurable to keep/space for Persian-mixed text); the CLI flag surface.
- **Downstream:** this PRD will be broken into issues (tracer-bullet vertical slices); each issue is
  implemented TDD. A natural first vertical slice: `chars` lam-alef/presentation-form table + a
  `FixUnicode`/`FoldPresentationForms` step + the `LIGHT` profile + the facade, with full tests —
  proving the whole stack end-to-end while remaining lossless.
```
