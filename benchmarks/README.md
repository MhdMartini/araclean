# Benchmarks & differential oracles

araclean's performance claim (ADR-0006) is that fusing a profile's single-char `str.translate`
folds into **one** C-level pass beats applying each fold as its own scan. These benchmarks make
that claim measurable, and the differential tests keep araclean honest against an independent
implementation. There are three pieces.

## 1. Cross-tool snapshot — `pytest-benchmark` (runs in CI)

`tests/test_oracle_benchmarks.py` times araclean's single fused char pass against pyarabic's
multi-pass char normalization on a representative mixed corpus, and asserts araclean is faster:

```bash
uv run pytest tests/test_oracle_benchmarks.py
```

This runs as part of the ordinary `uv run pytest`, so CI emits the throughput comparison table
(araclean vs pyarabic, same group) on every run. The measured margin is ~1.7x in araclean's favour
on char-level normalization; the strict comparison uses an interleaved, GC-paused min-of-N so it
stays stable under CI noise. pyarabic applies each operation as a separate full-string pass (and
`strip_tashkeel` is a `str.replace` per mark), so the win is fusion collapsing N passes into one.

## 2. Regression-over-time — `asv` (run on demand)

`bench_normalize.py` is the [airspeed velocity](https://asv.readthedocs.io/) suite: per-profile
throughput plus the fused char engine. It tracks araclean against **itself** across commits, so a
future throughput regression is detectable. asv installs araclean into an isolated env at each
commit, so the suite imports only `araclean` — never the test package or the pyarabic oracle.

```bash
uv run asv check -E existing      # validate the suite imports and runs (fast; no build)
uv run asv run                    # record timings for the current commit
uv run asv continuous main HEAD   # compare HEAD against main, flag regressions
```

Config lives in [`../asv.conf.json`](../asv.conf.json); generated envs/results/html land in `.asv/`
(git-ignored). The ordinary test gate also runs `tests/test_benchmarks_suite.py`, which validates
the config and that the suite imports and runs — so a benchmark broken by an unrelated change fails
`pytest` immediately, without waiting for the next `asv run`.

## 3. Differential oracles — `tests/test_differential_oracles.py` (runs in CI)

For each char-level operation both libraries implement, the suite either **asserts agreement** on
the shared domain (so araclean drifting from established behavior is caught) or **asserts and
documents the divergence** where araclean deliberately differs — an intentional difference is never
left to pass silently.

| Operation | araclean vs pyarabic |
|---|---|
| tatweel removal | **agree** on every string (both delete U+0640) |
| dediacritization, core block U+064B–U+0652 | **agree** |
| dediacritization, full default | **diverge**: araclean also strips dagger alef, combining madda and the Qur'anic/extended marks pyarabic keeps (fuller coverage) |
| alef folding (أ إ آ ٱ) | **agree** |
| alef folding (ٲ ٳ) | **diverge**: araclean folds the wavy-hamza alefs pyarabic keeps |
| alef maqsura ى | **diverge**: araclean keeps it for `FoldAlefMaqsura` (→ yeh); pyarabic folds it into alef |
| teh marbuta ة → heh | **agree**; araclean also folds the goal form ۃ |
| presentation forms (ﻷ, ﷺ) | **diverge**: araclean's fold is **lossless** (ﻷ → لأ, keeps the hamza; ﷺ expands), pyarabic's is lossy (ﻷ → لا) |
| hamza on carriers (ؤ ئ) | **diverge**: opposite directions — araclean folds the carrier (→ و / ي), pyarabic standardizes to bare hamza ء |

## Oracles are dev-only, never dependencies (ADR-0002)

pyarabic is GPL-3.0 and is installed only in the dev group, so `pip install araclean` pulls none of
it; the differential and benchmark modules `pytest.importorskip` it and skip cleanly where it is
absent.

**CAMeL Tools is intentionally opt-in only.** Installing it drags in `torch` plus the full GPU
runtime stack (multiple GB, downloaded per job across the Python matrix) and pins an older `typer`,
so it is left out of every dependency group rather than bloating the CI matrix. A developer who
wants to compare against it can install it explicitly:

```bash
uv pip install camel-tools     # heavy: torch + GPU runtime; expect a large download
```

pyarabic covers the shared char-level operations this suite asserts; CAMeL's `dediac` is a natural
additional dediacritization oracle for anyone who opts into the heavier install.
