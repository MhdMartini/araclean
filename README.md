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

## License

[MIT](./LICENSE)
