"""Iteration-zero smoke tests: the package installs, imports, and is typed."""

from __future__ import annotations

import importlib.util
import pathlib
from importlib.metadata import version


def test_araclean_is_importable() -> None:
    import araclean

    assert araclean.__name__ == "araclean"


def test_exposes_its_version() -> None:
    import araclean

    assert araclean.__version__ == version("araclean")


def test_ships_py_typed_marker() -> None:
    # The package advertises inline types (PEP 561); the marker must be packaged.
    spec = importlib.util.find_spec("araclean")
    assert spec is not None
    assert spec.submodule_search_locations is not None
    package_dir = spec.submodule_search_locations[0]
    assert (pathlib.Path(package_dir) / "py.typed").is_file()
