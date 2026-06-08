# Commit-driven versioning with Commitizen

araclean derives its version and changelog from **Conventional Commits**, managed end-to-end by
**Commitizen** (`cz`). One tool both **enforces** the commit format — a `commit-msg` pre-commit hook
plus a CI `cz check` over every PR — and **computes** the SemVer bump from the commit log
(`cz bump`), updating `[project].version` in `pyproject.toml` and `uv.lock` together
(`version_provider = "uv"`), regenerating `CHANGELOG.md`, and creating the `vX.Y.Z` tag. The project
stays in `0.x` (`major_version_zero = true`): a `feat` bumps the minor, a `fix`/other bumps the
patch, and a breaking change bumps the **minor** (not `1.0.0`) until 1.0 is declared deliberately.
Bumps are **on-demand** — a maintainer or agent runs `cz bump` to cut a release; automated
publish-on-merge is deferred to release ops ([`issues/0024`](../../issues/0024-release-ops.md)).

Why: the task has two halves — *enforce* the commit convention and *derive* the version from it —
and Commitizen is the only mainstream tool that does both. It supersedes
**python-semantic-release** (the PRD's original pick): PSR does not lint commits, it only consumes
them, so it would force a second enforcement tool, and it writes only `pyproject.toml`, leaving
`uv.lock` stale. Commitizen is pure-Python (installs via uv — no second Node toolchain beyond
cspell's `npx`), slots into the existing `repo: local` + `uv run` hook pattern where the uv lockfile
is the single source of tool versions, and still covers the eventual PyPI publish (the tag it
creates triggers a standard `pypa/gh-action-pypi-publish` step), so it *replaces* rather than
*supplements* the PSR decision. `release-please`/`semantic-release` were rejected for the same
reasons plus a Node action and a weaker Python version-file story.

## Consequences

- **Every commit must be a valid Conventional Commit**: `type(scope): subject`, with `feat`, `fix`,
  `docs`, `refactor`, `test`, `chore`, `ci`, `build`, `perf`, `style` types; a breaking change is
  marked with `!` after the type (`feat!:`) or a `BREAKING CHANGE:` footer. Enforced locally by the
  `commit-msg` hook and in CI by `cz check --rev-range` on every PR — it cannot be bypassed.
- **Wire the hook**: `uv run pre-commit install` now installs the `commit-msg` hook type too
  (`default_install_hook_types: [pre-commit, commit-msg]`). Agents committing programmatically must
  run with hooks installed, or their commit messages are still caught by the CI `commits` job.
- **Releasing**: `uv run cz bump` computes the bump, updates `pyproject.toml` + `uv.lock` +
  `CHANGELOG.md`, commits as `chore(release): …`, and tags `vX.Y.Z`; `uv run cz changelog` previews
  the notes. **Never hand-edit `[project].version`** — Commitizen owns it.
- **Merge strategy**: use one that preserves Conventional Commits on `main` (rebase or merge, or a
  Conventional-Commit squash title), since `cz bump` reads `main`'s commit log to decide the bump.
- Automated tag→PyPI publish (OIDC), versioned docs (`mike`), and the contribution surface
  (`CONTRIBUTING`, code of conduct, PR templates) remain with
  [`issues/0024`](../../issues/0024-release-ops.md) — **HITL** (human PyPI/governance setup).
