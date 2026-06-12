---
name: Feature request
about: Propose a new step, profile, or behavior
title: "feat: "
labels: enhancement
assignees: ""
---

## What's missing

The normalization/cleaning behavior you need and the use case behind it.

## Proposed behavior

Concrete input → output examples. For a new transformation, show a few representative strings and the
output you'd expect.

| input | expected output |
| ----- | --------------- |
| `...` | `...`           |

## Safety class

Is this lossless (`ENCODING_REPAIR`) or lossy (`LINGUISTIC_FOLDING`)? Which profiles should include
it? (A lossless profile — `LIGHT`, `CLASSICAL` — may only contain `ENCODING_REPAIR` steps.)

## Terminology (if it introduces a new concept)

araclean uses **Arabic-primary names** glossed to the English equivalent
([ADR-0007](../../docs/adr/0007-arabic-primary-terminology.md)). If your proposal names a new
operation, suggest the established Arabic term and its English gloss so it can be added to
[`GLOSSARY.md`](../../GLOSSARY.md).

## Alternatives considered

Existing steps/profiles you tried, and why they don't cover this.
