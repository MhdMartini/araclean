# araclean

Arabic text normalization and cleaning — pure-Python, composable, reproducible.

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

## Documentation

Full documentation lives at **<https://mhdmartini.github.io/araclean/>**:

- [Getting started](https://mhdmartini.github.io/araclean/getting-started/) — install,
  first call, choosing a profile.
- [Profiles](https://mhdmartini.github.io/araclean/profiles/) — every step each profile
  applies, lossless vs lossy (generated from the code).
- Guides — the [CLI](https://mhdmartini.github.io/araclean/guides/cli/),
  [pandas & polars](https://mhdmartini.github.io/araclean/guides/dataframes/),
  [tuning](https://mhdmartini.github.io/araclean/guides/tuning-profiles/) and
  [composing](https://mhdmartini.github.io/araclean/guides/composing-pipelines/)
  pipelines, [custom steps](https://mhdmartini.github.io/araclean/guides/custom-steps/),
  [reproducibility](https://mhdmartini.github.io/araclean/guides/reproducibility/), and
  [stopwords](https://mhdmartini.github.io/araclean/guides/stopwords/).
- [Why araclean](https://mhdmartini.github.io/araclean/concepts/why-araclean/) — the
  rationale and what sets it apart.
- [API reference](https://mhdmartini.github.io/araclean/reference/) and
  [CLI reference](https://mhdmartini.github.io/araclean/reference/cli/).

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
