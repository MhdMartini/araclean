<!--
Thanks for contributing to araclean! Keep the PR focused on one change.
The title must be a Conventional Commit (e.g. `feat(steps): add ReduceElongation`) — it feeds the
version bump and changelog (ADR-0008).
-->

## What & why

What this changes and the motivation. Link any issue it closes (`Closes #NN`).

## How it behaves

Input → output (or the error) that demonstrates the change, ideally mirrored by a new test.

## Definition-of-done checklist

See [CONTRIBUTING.md](../CONTRIBUTING.md#the-test-bar-definition-of-done) for the full bar.

- [ ] Behavior test written **first** (TDD) and asserts **observable behavior through the public
      interface** — not internal tables, private attributes, or step order.
- [ ] New/changed `Step`s declare their `safety` class; any lossless profile (`LIGHT`, `CLASSICAL`)
      still contains only `ENCODING_REPAIR` steps.
- [ ] Steps precompute their `str.translate` table / compiled `re` at construction (no per-call setup
      or validation).
- [ ] Gate is green locally: `uv run pre-commit run --all-files` (ruff, mypy --strict, pyright,
      pytest, cspell).
- [ ] New Arabic term ⇒ added a [`GLOSSARY.md`](../GLOSSARY.md) row + docs abbreviation; public names
      are Arabic-primary with an English gloss in the docstring (ADR-0007).
- [ ] Commits are Conventional Commits; `[project].version` is **not** hand-edited.
- [ ] Docs/ADRs updated if behavior, terminology, or a decision changed.
