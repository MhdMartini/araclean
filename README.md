# araclean

[![CI](https://github.com/MhdMartini/araclean/actions/workflows/ci.yml/badge.svg)](https://github.com/MhdMartini/araclean/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/araclean.svg)](https://pypi.org/project/araclean/)
[![Python versions](https://img.shields.io/pypi/pyversions/araclean.svg)](https://pypi.org/project/araclean/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Docs](https://img.shields.io/badge/docs-online-teal.svg)](https://mhdmartini.github.io/araclean/)

Arabic text normalization and cleaning — pure-Python, composable, reproducible, offset-preserving.

> **Status:** pre-release (`0.x`). The v1 normalization core is complete and fully
> tested; the API may still shift before 1.0.

araclean is **non-destructive by default**: the bare call is lossless *encoding repair*
(Unicode form, presentation forms, tatweel, bidi/zero-width characters, look-alike
letters, whitespace) and never silently strips tashkeel or folds letters. Everything
lossy is opt-in through named, serializable **profiles** (`SEARCH`, `ML`, `SOCIAL`,
`CLASSICAL`), so the exact preprocessing a corpus went through can be published and
reproduced.

```python
>>> from araclean import normalize
>>> normalize("العـــربية")                          # lossless encoding repair (default)
'العربية'
>>> normalize("اَلسّلامُ عليكم", profile="search")   # opt-in lossy folds for recall
'السلام عليكم'
```

For span-level work — RAG citation, NER projection — `apply_aligned` returns the normalized
text *and* a map back to every original position:

```python
>>> from araclean import Pipeline, RemoveTatweel, FoldAlef
>>> pipe = Pipeline([RemoveTatweel(), FoldAlef()])
>>> normalized, omap = pipe.apply_aligned("أحمـد")
>>> normalized
'احمد'
>>> omap.to_original((0, 4))   # where does the whole normalized word sit in the original?
(0, 5)
```

No other Arabic NLP library exposes this. See
[Offset-preserving normalization](https://mhdmartini.github.io/araclean/latest/guides/offset-preserving/).

## Documentation

Full documentation lives at **<https://mhdmartini.github.io/araclean/>**:

- [Getting started](https://mhdmartini.github.io/araclean/latest/getting-started/) — install,
  first call, choosing a profile.
- [Profiles](https://mhdmartini.github.io/araclean/latest/profiles/) — every step each profile
  applies, lossless vs lossy (generated from the code).
- Guides — the [CLI](https://mhdmartini.github.io/araclean/latest/guides/cli/),
  [pandas & polars](https://mhdmartini.github.io/araclean/latest/guides/dataframes/),
  [tuning](https://mhdmartini.github.io/araclean/latest/guides/tuning-profiles/) and
  [composing](https://mhdmartini.github.io/araclean/latest/guides/composing-pipelines/)
  pipelines, [custom steps](https://mhdmartini.github.io/araclean/latest/guides/custom-steps/),
  [reproducibility](https://mhdmartini.github.io/araclean/latest/guides/reproducibility/), and
  [stopwords](https://mhdmartini.github.io/araclean/latest/guides/stopwords/).
- [Why araclean](https://mhdmartini.github.io/araclean/latest/concepts/why-araclean/) — the
  rationale and what sets it apart.
- [API reference](https://mhdmartini.github.io/araclean/latest/reference/) and
  [CLI reference](https://mhdmartini.github.io/araclean/latest/reference/cli/).

Every Python example in the docs is executed as a doctest in CI, and the generated pages
(profiles, glossary, CLI reference) are drift-checked against the code.

## Install

```bash
pip install araclean
```

Optional extras (declared now, populated by later slices):

```bash
pip install "araclean[cli]"     # command-line interface
pip install "araclean[pandas]"  # pandas Series accessor
pip install "araclean[polars]"  # polars accessor
pip install "araclean[all]"     # everything
```

The core install is lean: it requires only [pydantic](https://docs.pydantic.dev/)
v2 — no compiler, Java, or data download.

## Development

This project uses [uv](https://docs.astral.sh/uv/) for environments and
[pre-commit](https://pre-commit.com/) for the quality gate.

```bash
uv sync                       # create the dev environment
uv run pre-commit install     # wire up the pre-commit hooks
uv run pre-commit run --all-files
```

The gate runs `ruff`, `mypy --strict`, `pyright`, `pytest`, and `cspell`
(canonical Arabic terminology per [`GLOSSARY.md`](./GLOSSARY.md)).

## Commits & versioning

The version and changelog are **derived from commit messages** by
[Commitizen](https://commitizen-tools.github.io/commitizen/) — see
[ADR-0008](./docs/adr/0008-commit-driven-versioning-commitizen.md). Every commit must be a
[Conventional Commit](https://www.conventionalcommits.org/); the format is enforced by a
`commit-msg` hook (wired by `uv run pre-commit install`) and in CI on every PR.

```
feat(steps): add RemoveTashkeel step     # → minor bump
fix(pipeline): preserve step order        # → patch bump
feat(api)!: rename normalize() argument   # breaking → minor (we are pre-1.0)
```

`feat` bumps the minor, `fix`/others the patch, and a breaking change (`!` or a `BREAKING CHANGE:`
footer) the minor — the project stays in `0.x` until 1.0 is declared. To cut a release:

```bash
uv run cz bump        # compute the bump, update pyproject.toml + uv.lock + CHANGELOG.md, tag vX.Y.Z
uv run cz changelog   # preview release notes without bumping
```

Never hand-edit `[project].version` — Commitizen owns it.

## License

[MIT](./LICENSE)
