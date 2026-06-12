# Writing custom steps

A `Step` is the extension seam of the library. The contract is deliberately tiny — a readable
`safety` attribute plus a pure `str -> str` call — so your own transform drops into a `Pipeline`
next to the built-ins, participates in the [safety audit](../concepts/safety.md), and needs no
registration just to *run*.

## The minimal step

```pycon
>>> from dataclasses import dataclass
>>> from araclean import Pipeline, SafetyClass, Step
>>> @dataclass(frozen=True)
... class StripQuestionMarks:
...     safety = SafetyClass.LINGUISTIC_FOLDING
...     def __call__(self, s: str, /) -> str:
...         return s.replace("؟", "").replace("?", "")
>>> isinstance(StripQuestionMarks(), Step)  # a runtime-checkable Protocol — no base class needed
True

```

Pick the safety class honestly — it is what the audit reports:

- `ENCODING_REPAIR` if your step discards no linguistic signal (lossless),
- `LINGUISTIC_FOLDING` if it discards a distinction *within* the Arabic text,
- `CLEANING` if it removes non-linguistic noise *around* the text.

Compose it like any built-in, for example on top of LIGHT's encoding repair:

```pycon
>>> light = Pipeline.from_profile("light")
>>> pipe = Pipeline([*light.steps, StripQuestionMarks()])
>>> pipe("كيف الحال؟")
'كيف الحال'
>>> pipe.audit().lossy_steps  # the audit sees your step's declared safety class
('StripQuestionMarks',)

```

Two conventions the built-ins follow, worth copying:

- **Precompute at construction.** Build any table or regex in `__init__`/`__post_init__` so
  `__call__` does no setup and no validation — it runs once per string.
- **Stay pure and idempotent.** A step should be a pure function of its input, and running it twice
  should equal running it once; that is what keeps whole profiles idempotent.

## Making it serializable

A pipeline containing your step can be serialized once the step can describe itself, and rebuilt
once a factory is registered under its name:

```pycon
>>> from typing import ClassVar
>>> from araclean.registry import register
>>> @dataclass(frozen=True)
... class MaskNumbers:
...     safety = SafetyClass.LINGUISTIC_FOLDING
...     name: ClassVar[str] = "MaskNumbers"
...     def __call__(self, s: str, /) -> str:
...         return "".join("#" if ch.isdigit() else ch for ch in s)
...     def to_dict(self):
...         return {"name": self.name, "config": {}}
...     @classmethod
...     def from_dict(cls, config):
...         return cls(**config)
>>> register(MaskNumbers.name, MaskNumbers.from_dict)
>>> pipe = Pipeline([MaskNumbers()])
>>> rebuilt = Pipeline.from_dict(pipe.to_dict())
>>> rebuilt("غرفة 101")
'غرفة ###'

```

The `name` doubles as the step's address in `repr`, `select`/`drop`, and the audit (a step without
one is named by its class). Registry names are canonical and unique — registering a taken name
raises.

## Declaring an ordering contract

If your step's matching assumes earlier transforms (the way `RemoveStopwords` assumes the letter
folds), declare `requires_before` — a tuple of step names — and `Pipeline` will reject any
construction where they do not precede it. The check runs once at construction, never per string.

```python
@dataclass(frozen=True)
class MyFoldedMatcher:
    requires_before: ClassVar[tuple[str, ...]] = ("RemoveTashkeel", "FoldAlef")
    ...
```

## Advanced: joining the fused engine

Consecutive steps whose entire behavior is one `str.translate` over a static table are fused into a
single C-level pass (see [Architecture & performance](../concepts/architecture.md)). A custom step
opts in by exposing the precomputed table its `__call__` applies:

```python
@dataclass(frozen=True)
class MyFold:
    safety = SafetyClass.LINGUISTIC_FOLDING

    @property
    def translate_table(self) -> dict[int, str | None]:
        return self._table  # what __call__ does: s.translate(self._table)

    def __call__(self, s: str, /) -> str:
        return s.translate(self._table)
```

Only do this when the property is *exactly* equivalent to your `__call__` — the planner trusts it.
Contextual steps (regexes, position-dependent rules) should not implement it; they simply stay
their own pass.
