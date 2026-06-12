"""Docs-site guards (issue 0023).

The docs site's two machine-checkable invariants live here so they cannot rot:

  1. Each per-profile page enumerates exactly the steps the profile assembles, in order, each
     labelled with the safety class of the *actual* `Pipeline` step (the AC2 cross-check). This
     reads the committed markdown and compares it to a live `Pipeline.from_profile(...)`, so a
     profile edited in `profiles.py` without regenerating the docs fails here.
  2. The generated artifacts (per-profile pages, the glossary page, the abbreviations include) are
     in sync with their single source of truth (`araclean` + `GLOSSARY.md`) — the same
     commit-the-generated-output-and-test-it pattern the syrupy snapshots use. Regenerate with
     ``uv run python docs_gen.py``.

The doctested examples (every ``>>>`` on every published page) and the strict `mkdocs build` are
guarded further down; the build skips cleanly where the `docs` dependency group is absent (it is
not in the default `dev` group).
"""

from __future__ import annotations

import doctest
import json
import re
import subprocess
import sys
from pathlib import Path

import docs_gen
import pytest

from araclean.config import ProfileName
from araclean.pipeline import Pipeline
from araclean.safety import SafetyClass

# The closed set of named profiles, by canonical name (the public source of profile names).
PROFILE_NAMES = sorted(member.value for member in ProfileName)

# Map the safety-class value shown verbatim in a generated table back to the enum, so the parsed
# doc can be compared to the live pipeline without depending on the prose around it.
_SAFETY_BY_VALUE = {member.value: member for member in SafetyClass}

# A generated step row: | <n> | `StepName` | `safety_value` | <lossless marker> |
_STEP_ROW = re.compile(r"^\|\s*\d+\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")


def _parsed_step_rows(markdown: str) -> list[tuple[str, SafetyClass]]:
    """Extract the (step name, safety class) sequence from a generated profile page's table."""
    rows: list[tuple[str, SafetyClass]] = []
    for line in markdown.splitlines():
        match = _STEP_ROW.match(line)
        if match:
            name, safety_value = match.group(1), match.group(2)
            rows.append((name, _SAFETY_BY_VALUE[safety_value]))
    return rows


def _assembled_step_rows(profile_name: str) -> list[tuple[str, SafetyClass]]:
    """The (step name, safety class) sequence of the *actually assembled* pipeline, in order."""
    pipe = Pipeline.from_profile(profile_name)
    return [(docs_gen.step_name(step), step.safety) for step in pipe.steps]


@pytest.mark.parametrize("profile_name", PROFILE_NAMES)
def test_profile_page_enumerates_the_assembled_pipeline(profile_name: str) -> None:
    """AC2: the *published* profile page's step table matches the steps the profile assembles.

    Parses the committed markdown (not a fresh render), so the cross-check is against the doc a
    reader actually sees — catching a stale page or a hand-edit independently of the drift guard.
    """
    page = (docs_gen.DOCS_DIR / "profiles" / f"{profile_name}.md").read_text(encoding="utf-8")
    assert _parsed_step_rows(page) == _assembled_step_rows(profile_name)


# --- AC3/AC4: glossary tooltips are generated from GLOSSARY.md -----------------------------------


def _glossary_entries() -> list[docs_gen.GlossaryEntry]:
    return docs_gen.parse_glossary(docs_gen.GLOSSARY_PATH.read_text(encoding="utf-8"))


def test_glossary_parse_reads_only_the_arabic_terminology_table() -> None:
    """The canonical Arabic terms are parsed; the project's own coined-terms table is not."""
    terms = {entry.term for entry in _glossary_entries()}
    assert "Tashkeel" in terms  # from the Mapping table
    assert "Encoding repair" not in terms  # from the coined-terms table below it — excluded


def test_abbreviations_gloss_arabic_terms_from_the_glossary() -> None:
    """AC4: each Arabic term gets a `*[Term]: gloss` abbreviation generated from GLOSSARY.md."""
    entries = _glossary_entries()
    tashkeel = next(entry for entry in entries if entry.term == "Tashkeel")
    assert "diacritics" in tashkeel.english.lower()  # the English gloss the tooltip will show

    abbreviations = docs_gen.render_abbreviations(entries)
    # Capitalized (sentence-start) and lowercase (mid-sentence) spellings both resolve.
    assert f"*[Tashkeel]: {tashkeel.english}" in abbreviations
    assert f"*[tashkeel]: {tashkeel.english}" in abbreviations
    # A combined row (`Fatha / Damma / …`) is split so each part gets its own tooltip.
    assert "*[Fatha]:" in abbreviations


# --- drift guard: the committed generated files are in sync with the source of truth -------------


@pytest.mark.parametrize(
    "path", sorted(docs_gen.generated_files()), ids=lambda p: str(p.relative_to(docs_gen.REPO_ROOT))
)
def test_generated_docs_are_committed_and_in_sync(path: Path) -> None:
    """Every generated docs file is committed and matches a fresh render of its source of truth.

    Fails (with the regenerate command) if a profile or `GLOSSARY.md` changed without regenerating,
    so the published docs can never silently drift — the syrupy-snapshot discipline for docs.
    """
    expected = docs_gen.generated_files()[path]
    assert path.exists(), f"{path} is missing — run `uv run python docs_gen.py`"
    assert path.read_text(encoding="utf-8") == expected, (
        f"{path} is stale — run `uv run python docs_gen.py` to regenerate it"
    )


# --- AC1: every Python example on every docs page is executed as a doctest, so none can rot ------

# Every site page that contains a `>>>` example. ADRs and the abbreviations include are not site
# pages (mkdocs.yml `exclude_docs`), so they are skipped; everything published is doctested.
_EXCLUDED_DOC_DIRS = {"adr", "includes"}
DOC_PAGES_WITH_EXAMPLES = sorted(
    path
    for path in docs_gen.DOCS_DIR.rglob("*.md")
    if not _EXCLUDED_DOC_DIRS.intersection(path.relative_to(docs_gen.DOCS_DIR).parts)
    and ">>> " in path.read_text(encoding="utf-8")
)


def test_homepage_quickstart_has_doctested_examples() -> None:
    """AC1: the homepage quickstart carries executable `>>>` examples (run by the test below)."""
    assert docs_gen.DOCS_DIR / "index.md" in DOC_PAGES_WITH_EXAMPLES


@pytest.mark.parametrize(
    "page", DOC_PAGES_WITH_EXAMPLES, ids=lambda p: str(p.relative_to(docs_gen.DOCS_DIR))
)
def test_docs_page_examples_run_as_doctests(page: Path) -> None:
    """Every `>>>` example on a published docs page executes and matches its shown output."""
    results = doctest.testfile(
        str(page),
        module_relative=False,
        encoding="utf-8",
        optionflags=doctest.ELLIPSIS,
    )
    assert results.attempted > 0, f"{page} matched the '>>> ' probe but doctest found no examples"
    assert results.failed == 0


# --- AC1/AC3: the site builds cleanly under --strict, with tooltips and an English↔Arabic index ---


def _build_site(site_dir: Path) -> None:
    """Build the docs site under `--strict` into `site_dir`; fail loudly on any mkdocs warning."""
    result = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(site_dir)],
        cwd=docs_gen.REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"`mkdocs build --strict` failed:\n{result.stdout}\n{result.stderr}"
    )


def test_site_builds_strict_with_tooltips_and_search(tmp_path: Path) -> None:
    """AC1 + AC3: `mkdocs build --strict` is clean; Arabic terms get hover glosses; English indexes
    to the Arabic-primary step (searching "diacritics" finds `RemoveTashkeel`)."""
    pytest.importorskip("mkdocs", reason="docs dependency group not installed")
    pytest.importorskip("material", reason="mkdocs-material not installed")

    site = tmp_path / "site"
    _build_site(site)

    # AC3 (tooltips): an Arabic term renders as an <abbr> carrying its English gloss.
    glossary_html = (site / "glossary" / "index.html").read_text(encoding="utf-8")
    assert '<abbr title="Diacritics / vocalization marks">Tashkeel</abbr>' in glossary_html

    # AC3 (search): the English jargon "diacritics" indexes to the Arabic-primary `RemoveTashkeel`.
    index = json.loads((site / "search" / "search_index.json").read_text(encoding="utf-8"))
    matches = [
        doc
        for doc in index["docs"]
        if "diacritics" in (doc.get("text", "") + doc.get("title", "")).lower()
        and "RemoveTashkeel" in doc.get("location", "") + doc.get("text", "")
    ]
    assert matches, "searching 'diacritics' should surface RemoveTashkeel"
