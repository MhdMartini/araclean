# Profiles

A **profile** is a named, serializable preset that assembles a sequence of steps into a `Pipeline`.
Picking a profile is how you choose the normalization trade-off: how much to repair versus how much
to fold away.

araclean is **non-destructive by default** (ADR-0004). Each step declares a *safety class*, and a
profile is only as lossy as its steps:

- **`encoding_repair`** — lossless. Repairs the encoding (Unicode form, presentation forms, tatweel,
  bidi/zero-width controls, look-alike letters, whitespace) without discarding any linguistic
  signal. The default `LIGHT` profile is *only* encoding repair.
- **`linguistic_folding`** — lossy. Discards a linguistic distinction *within* the Arabic text
  (dediacritization, alef/hamza/teh-marbuta/alef-maqsura folding, digit/punctuation mapping).
- **`cleaning`** — lossy. Removes *non-linguistic noise* around the text (URLs, mentions,
  hashtags, HTML, foreign-script spans).

Each profile page below enumerates exactly the steps it applies, in order, and labels each one
lossless or lossy — so you can choose with full knowledge of the trade-off.

| Profile | Lossless? | For |
|---------|-----------|-----|
| [LIGHT](light.md) | ✓ lossless | the safe default — encoding repair for any corpus |
| [CLASSICAL](classical.md) | ✓ lossless | vocalized / Qur'anic text: repair while preserving every mark |
| [ML](ml.md) | ✗ lossy | model input: dediacritize + cap elongation, but keep letter distinctions |
| [SEARCH](search.md) | ✗ lossy | search / IR recall: fold spelling & vocalization variants together |
| [SOCIAL](social.md) | ✗ lossy | noisy user text: clean URLs/mentions/HTML, keep emoji |

The lossless/lossy labels and the per-profile step lists are generated from the assembled pipeline
itself, so they always match what the code actually does.

A profile is a starting point, not a take-it-or-leave-it bundle: per-knob overrides adjust one
behavior with loud validation (see [Tuning profiles](../guides/tuning-profiles.md)), and `drop`/
`select`/explicit construction give you full control of the step sequence (see
[Composing pipelines](../guides/composing-pipelines.md)).
