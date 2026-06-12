"""Guard the asv benchmark wiring (ADR-0006).

`asv` times the suite over time; this test guards that there is a well-formed config pointing at a
suite that actually imports and runs. So a benchmark broken by an unrelated change (a renamed
profile, a changed `build_plan` signature) fails the ordinary test gate immediately, instead of
silently rotting until someone next runs `asv run`. The timings are asv's job — here we only prove
asv has something valid to time.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ASV_CONF = _REPO_ROOT / "asv.conf.json"
_BENCH_MODULE = _REPO_ROOT / "benchmarks" / "bench_normalize.py"


def test_asv_config_points_at_the_benchmark_suite() -> None:
    conf: dict[str, Any] = json.loads(_ASV_CONF.read_text(encoding="utf-8"))
    assert conf["project"] == "araclean"
    assert conf["repo"] == "."  # benchmark this repo, in place
    assert conf["benchmark_dir"] == "benchmarks"
    assert "main" in conf["branches"]
    # The configured benchmark dir actually exists and holds the suite asv will discover.
    assert (_REPO_ROOT / conf["benchmark_dir"] / "bench_normalize.py").is_file()


def _load_bench_module() -> Any:
    """Import benchmarks/bench_normalize.py by path, the way asv imports it (no sys.path games)."""
    spec = importlib.util.spec_from_file_location("araclean_bench_normalize", _BENCH_MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_asv_benchmark_suite_imports_and_runs() -> None:
    module = _load_bench_module()

    profiles = module.NormalizeProfiles()
    assert profiles.params  # at least one profile is parametrized
    for profile in profiles.params:
        profiles.setup(profile)
        assert isinstance(profiles.pipe("نصٌّ مُشَكَّل"), str)  # setup wired a working pipeline
        profiles.time_normalize_each(profile)  # the timed methods run without error
        profiles.time_normalize_batch(profile)

    char_engine = module.FusedCharEngine()
    char_engine.setup()
    assert isinstance(char_engine.fused("نصٌّ مُشَكَّل"), str)  # the fused pass is a real transform
    char_engine.time_fused_char_pass()
