"""Step registry: canonical name -> factory, so a serialized `Pipeline` can be rehydrated.

The registry is the deserialization adapter of the `Step` seam. Built-in steps register
themselves at import time; a custom step can only be reconstructed once registered (until then
it still *runs* inside a `Pipeline`; it just cannot be rebuilt from a dict).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from araclean.steps import Step

    StepFactory = Callable[[Mapping[str, Any]], Step]

_FACTORIES: dict[str, StepFactory] = {}


def register(name: str, factory: StepFactory) -> None:
    """Register a step factory under a canonical name (one name, no aliases)."""
    if name in _FACTORIES:
        raise ValueError(f"Step name {name!r} is already registered")
    _FACTORIES[name] = factory


def build(name: str, config: Mapping[str, Any]) -> Step:
    """Reconstruct a step from its registered name and config, or raise a clear error."""
    try:
        factory = _FACTORIES[name]
    except KeyError:
        raise ValueError(f"Unknown step {name!r}; registered steps: {sorted(_FACTORIES)}") from None
    return factory(config)


def registered_names() -> frozenset[str]:
    """The canonical names currently registered."""
    return frozenset(_FACTORIES)
