# araclean

Arabic text normalization and cleaning — pure-Python, composable, reproducible.

> **Status:** early development. The package installs and imports; normalization
> behavior is being built slice by slice (see the implementation issues).

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
