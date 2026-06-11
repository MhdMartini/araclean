"""asv benchmark suite for araclean (issue 0019, ADR-0006).

This package is discovered and run by airspeed velocity (`asv`), configured in ``asv.conf.json`` at
the repo root. asv installs araclean into an isolated environment at each commit and imports these
modules, so every benchmark here imports ONLY ``araclean`` — never the test package, never the
dev-only pyarabic oracle. The cross-tool comparison vs pyarabic is a pytest-benchmark snapshot
(``tests/test_oracle_benchmarks.py``); this suite tracks araclean's own throughput over time.
"""
