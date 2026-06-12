# Contributing to araclean

Thanks for your interest in araclean — an MIT-licensed, pure-Python library for Arabic text
normalization and cleaning. Contributions of every size are welcome: a bug report, a failing test, a
new `Step`, a doc fix, or a glossary correction.

By participating you agree to abide by our [Code of Conduct](./CODE_OF_CONDUCT.md).

## Ground rules in one minute

- **Arabic-primary terminology** ([ADR-0007](./docs/adr/0007-arabic-primary-terminology.md)): public
  names use the established Arabic term (`RemoveTashkeel`, not `RemoveDiacritics`), glossed to the
  English equivalent in the docstring. A new Arabic term means a new row in
  [`GLOSSARY.md`](./GLOSSARY.md) and a docs abbreviation — the spell-checker enforces this.
- **Lean MIT core** ([ADR-0002](./docs/adr/0002-build-new-mit-library.md),
  [ADR-0003](./docs/adr/0003-three-layer-api-validation-boundary.md)): the only runtime dependency is
  pydantic. Anything heavier (and anything GPL-licensed) stays isolated behind an `[extra]`; it must
  never be imported by the core.
- **Conventional Commits** ([ADR-0008](./docs/adr/0008-commit-driven-versioning-commitizen.md)): the
  version and changelog are derived from commit messages, so the format is enforced — see
  [Commits](#commits) below.

## Development setup

araclean uses [uv](https://docs.astral.sh/uv/) for environments and
[pre-commit](https://pre-commit.com/) for the quality gate.

```bash
git clone https://github.com/MhdMartini/araclean
cd araclean
uv sync                       # create the dev environment from the locked dependencies
uv run pre-commit install     # wire up the pre-commit + commit-msg hooks
```

Run the full gate at any time — it is exactly what CI runs:

```bash
uv run pre-commit run --all-files
```

The gate is `ruff` (lint + format), `mypy --strict`, `pyright`, `pytest`, and `cspell` (canonical
Arabic terminology per [`GLOSSARY.md`](./GLOSSARY.md)). The docs site is built separately under
`--strict`:

```bash
uv sync --group docs
uv run mkdocs build --strict
```

## The test bar (Definition of Done)

Every change must meet this bar — it is the same bar each implementation slice was built to, and CI
will not go green without it.

- **Failing behavior test written first** (TDD). See [`tests/`](./tests/) for the style.
- Tests assert **observable behavior through the module interface** — input string + config → output
  string, or the raised error — **never** internal representations (table contents, private
  attributes, step order). Tests must survive an internal refactor.
- Every `Step` declares its `safety` class (`ENCODING_REPAIR` lossless / `LINGUISTIC_FOLDING` lossy).
  Any "lossless" profile (`LIGHT`, `CLASSICAL`) is asserted to contain only `ENCODING_REPAIR` steps
  ([ADR-0011](./docs/adr/0011-cleaning-is-a-third-safety-class.md)).
- Steps precompute their `str.translate` table / compiled `re` at construction; the per-string
  `__call__` does no setup and no validation
  ([ADR-0003](./docs/adr/0003-three-layer-api-validation-boundary.md),
  [ADR-0006](./docs/adr/0006-pure-python-translate-engine.md)).
- `mypy --strict` + `pyright` clean; `ruff` clean; `cspell` clean. A new Arabic term ⇒ add a
  `GLOSSARY.md` row + a docs abbreviation ([ADR-0007](./docs/adr/0007-arabic-primary-terminology.md)).
- Arabic-primary public names with the English gloss in the docstring summary line (ADR-0007).
- Commits are **Conventional Commits** (see below); never hand-edit `[project].version`.

## Commits

Every commit must be a [Conventional Commit](https://www.conventionalcommits.org/). The version and
changelog are derived from these messages by [Commitizen](https://commitizen-tools.github.io/commitizen/),
so the format is enforced by a `commit-msg` hook locally and by CI on every PR — it cannot be
bypassed.

```
feat(steps): add RemoveTashkeel step      # → minor bump
fix(pipeline): preserve step order         # → patch bump
docs(readme): clarify the install extras   # → no release
feat(api)!: rename normalize() argument    # breaking → minor (pre-1.0)
```

`feat` bumps the minor, `fix`/others the patch, and a breaking change (`!` after the type or a
`BREAKING CHANGE:` footer) the minor — the project stays in `0.x` until 1.0 is declared deliberately.
If you commit programmatically, run with the hooks installed or your message is still caught by CI.

## Submitting a pull request

1. Branch off `main`.
2. Write the failing test first, then make it pass; keep the gate green (`uv run pre-commit run
   --all-files`).
3. Open a PR. The [pull request template](./.github/PULL_REQUEST_TEMPLATE.md) restates the test bar
   as a checklist — fill it in.
4. CI runs the gate, the type matrix (Python 3.12–3.14), the strict docs build, and a
   Conventional-Commit check over your commits. All must pass before review.

Use a merge strategy that keeps Conventional Commits on `main` (rebase, or a Conventional-Commit
squash title), since the release bump is computed from `main`'s commit log.

## Releases (maintainers)

Releases are **commit-driven** and **manual to trigger**
([ADR-0008](./docs/adr/0008-commit-driven-versioning-commitizen.md)):

```bash
uv run cz bump        # compute the bump, update pyproject.toml + uv.lock + CHANGELOG.md, tag vX.Y.Z
git push --follow-tags
```

Pushing the `vX.Y.Z` tag triggers CI to build the sdist/wheel, **publish to PyPI via Trusted
Publishing (OIDC)** — no stored token — and deploy the pinned docs version with `mike`. To rehearse
the build/publish pipeline without releasing, run the **CI workflow manually**
(`workflow_dispatch`): it builds and metadata-checks the artifacts without uploading them.

## License

By contributing, you agree that your contributions are licensed under the project's
[MIT License](./LICENSE).
