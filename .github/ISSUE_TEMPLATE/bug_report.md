---
name: Bug report
about: A normalization step or the API produces the wrong output, or raises unexpectedly
title: "fix: "
labels: bug
assignees: ""
---

## What happened

A clear description of the bug.

## Reproduction

The smallest input + configuration that reproduces it. Please paste **text**, not a screenshot, so
the exact code points are preserved.

```python
from araclean import normalize  # or the profile / step you used

text = "..."            # the input string
result = normalize(text, profile="SEARCH")   # the call you made
```

## Expected vs. actual output

- **Expected:** `...`
- **Actual:** `...`

If it raised instead, paste the full traceback.

## Environment

- araclean version: <!-- python -c "import araclean; print(araclean.__version__)" -->
- Python version:
- OS:
- Extras installed (if any): `[cli]` / `[pandas]` / `[polars]` / `[emoji]` / none

## Anything else

Optional: the Unicode code points involved (`U+0640` …), the linguistic intent, or links.
