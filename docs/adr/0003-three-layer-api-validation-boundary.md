# Three-layer composable API with validation at the config boundary

The library exposes three layers over one core: (1) pure `str -> str` functions; (2) a
composable, reorderable, serializable `Pipeline` of lightweight `Step` callables; (3) one-call
`normalize(text, profile=...)` sugar with named `Profile`s. Modeled on HuggingFace `tokenizers`
(a composable `Sequence` of normalizers) for familiarity and to enable serializable/versioned
profiles and optional offset tracking.

Validation lives at the **configuration/trust boundary**, never in the per-string hot path:
`Config` and `Profile` are pydantic v2 models (validated on construction; can emit JSON Schema
for profile files); public construction/config-taking callables use `@validate_call`; internal
structures are `TypedDict`. The per-string execution surface (`pipe(text)`, `pipe.batch()`, bare
step functions) does **no** per-call validation, so `str.translate`-based throughput is
unaffected. Steps precompute their translate tables / regex at construction.

Python ≥ 3.12.

## Consequences

- pydantic v2 becomes a core dependency. Install stays trivial — it ships wheels; no compiler,
  Java, or data download. This is a deliberate, mild relaxation of the "stdlib-only core" goal,
  justified by first-class validated/serializable configs (a reproducibility differentiator).
- `@validate_call` must NOT be placed on the innermost per-string transforms (it validates per
  call); keep it on construction/config entry points only.
- Requiring 3.12 drops users on 3.10/3.11 in exchange for modern typing (PEP 695) and
  performance; the floor can be lowered later if adoption demands it.
