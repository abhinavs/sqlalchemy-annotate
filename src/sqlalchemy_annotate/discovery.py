"""Locate SQLAlchemy model classes by importing a package and walking it.

Strategy:
  1. import the configured dotted path,
  2. if it is a package, recursively import every submodule so every model
     registers on its metadata,
  3. collect classes that ``sqlalchemy.inspect`` recognises as mapped.

We deliberately never reference a ``Base``: inspecting each object works with
single/multiple/legacy declarative bases and ``Column()`` or ``mapped_column()``
alike. Import failures are collected per module, not raised, so a circular
import or one broken module does not abort the whole run.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass
from types import ModuleType

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapper

from sqlalchemy_annotate.errors import DiscoveryError


@dataclass(slots=True)
class DiscoveredModel:
    cls: type
    qualname: str
    source_file: str


@dataclass(slots=True)
class DiscoveryResult:
    models: list[DiscoveredModel]
    import_errors: dict[str, str]  # module name -> error message


def _iter_submodules(pkg: ModuleType) -> list[tuple[str, str | None]]:
    """Return (module_name, error) pairs after importing the whole package."""
    results: list[tuple[str, str | None]] = []
    paths = getattr(pkg, "__path__", None)
    if paths is None:  # a plain module, nothing to walk
        return results
    prefix = pkg.__name__ + "."
    for mod in pkgutil.walk_packages(paths, prefix):
        try:
            importlib.import_module(mod.name)
            results.append((mod.name, None))
        except Exception as exc:  # noqa: BLE001 - report, never abort
            results.append((mod.name, f"{type(exc).__name__}: {exc}"))
    return results


def _is_mapped(obj: object) -> bool:
    if not inspect.isclass(obj):
        return False
    try:
        return isinstance(sa_inspect(obj, raiseerr=False), Mapper)
    except Exception:  # noqa: BLE001 - non-mapped or unrelated class
        return False


def discover_models(models_path: str) -> DiscoveryResult:
    """Import ``models_path`` and return every mapped class found within it."""
    import os
    import sys

    # Console scripts do not put the project root on sys.path the way
    # ``python script.py`` does; add it so ``--models app.models`` resolves
    # when run from the project directory (same convention as alembic).
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    try:
        root = importlib.import_module(models_path)
    except Exception as exc:  # noqa: BLE001
        raise DiscoveryError(
            f"could not import models package {models_path!r}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    import_errors: dict[str, str] = {}
    for name, err in _iter_submodules(root):
        if err is not None:
            import_errors[name] = err

    seen: set[int] = set()
    found: list[DiscoveredModel] = []
    # Re-scan loaded modules whose name starts with the root package so we see
    # classes that were imported transitively too.
    import sys

    candidates = [root, *(
        m for n, m in list(sys.modules.items())
        if m is not None and (n == root.__name__ or n.startswith(root.__name__ + "."))
    )]
    for module in candidates:
        for _, obj in inspect.getmembers(module, _is_mapped):
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            try:
                src = inspect.getsourcefile(obj) or inspect.getfile(obj)
            except (TypeError, OSError):
                continue  # dynamically generated class, cannot annotate a file
            found.append(
                DiscoveredModel(cls=obj, qualname=obj.__qualname__, source_file=src)
            )

    if not found and not import_errors:
        raise DiscoveryError(
            f"no SQLAlchemy mapped classes found under {models_path!r}"
        )
    found.sort(key=lambda m: (m.source_file, m.qualname))
    return DiscoveryResult(models=found, import_errors=import_errors)
