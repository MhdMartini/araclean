# Security Policy

## Supported versions

araclean is pre-1.0 (`0.x`). Only the **latest released version** on
[PyPI](https://pypi.org/p/araclean) is supported with security fixes. Pin a version for
reproducibility, but upgrade to the latest patch release to receive fixes.

## Reporting a vulnerability

**Please do not report security issues in public GitHub issues.**

Report privately through GitHub's
[private vulnerability reporting](https://github.com/MhdMartini/araclean/security/advisories/new)
(Security → Report a vulnerability). If you cannot use that, contact the maintainer at
`[INSERT CONTACT EMAIL]`.

Please include enough detail to reproduce: the input string, the configuration/profile, the araclean
and Python versions, and the observed vs. expected behavior. We aim to acknowledge a report within a
few days and will coordinate a fix and disclosure timeline with you.

## Scope

araclean is a pure-Python text-processing library whose only runtime dependency is pydantic
([ADR-0002](./docs/adr/0002-build-new-mit-library.md),
[ADR-0003](./docs/adr/0003-three-layer-api-validation-boundary.md)). The most relevant classes of
issue are pathological inputs that cause excessive CPU/memory (e.g. catastrophic backtracking in a
step's regex) and any case where a normalization step corrupts text in a way that could mislead a
downstream security control. Reports of either are in scope.
