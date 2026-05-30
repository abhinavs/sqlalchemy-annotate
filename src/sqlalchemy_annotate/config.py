"""Configuration: built-in defaults <- pyproject.toml <- CLI overrides.

``tomllib`` is stdlib on the supported Python versions (>=3.11), so reading
config adds no import cost and no third-party dependency.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from sqlalchemy_annotate.errors import ConfigError

_SECTION = ("tool", "sqlalchemy-annotate")
_VALID_SORT = {"definition", "alphabetical"}
_VALID_POSITION = {"top", "bottom"}


@dataclass(slots=True)
class Config:
    models: str | None = None
    engine: str | None = None
    dialect: str | None = None  # explicit override, else derived from engine
    include_indexes: bool = True
    include_foreign_keys: bool = True
    include_relationships: bool = False
    normalize_types: bool = False
    sort: str = "definition"
    position: str = "bottom"
    exclude: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.sort not in _VALID_SORT:
            raise ConfigError(
                f"sort must be one of {sorted(_VALID_SORT)}, got {self.sort!r}"
            )
        if self.position not in _VALID_POSITION:
            raise ConfigError(
                f"position must be one of {sorted(_VALID_POSITION)}, "
                f"got {self.position!r}"
            )


_FIELD_NAMES = {f.name for f in fields(Config)}


def find_pyproject(start: Path | None = None) -> Path | None:
    """Walk upward from ``start`` looking for a pyproject.toml."""
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _read_section(pyproject: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"could not read {pyproject}: {exc}") from exc
    node: Any = data
    for key in _SECTION:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    if not isinstance(node, dict):
        raise ConfigError(f"[tool.sqlalchemy-annotate] in {pyproject} is not a table")
    unknown = set(node) - _FIELD_NAMES
    if unknown:
        raise ConfigError(
            f"unknown key(s) in [tool.sqlalchemy-annotate]: {', '.join(sorted(unknown))}"
        )
    return node


def load_config(
    *,
    config_path: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> Config:
    """Resolve effective config. CLI overrides win over file, file over defaults."""
    cfg = Config()
    pyproject = config_path or find_pyproject()
    if pyproject is not None and pyproject.is_file():
        for key, value in _read_section(pyproject).items():
            setattr(cfg, key, tuple(value) if isinstance(value, list) else value)

    for key, value in (cli_overrides or {}).items():
        if value is not None and key in _FIELD_NAMES:
            setattr(cfg, key, tuple(value) if isinstance(value, list) else value)

    cfg.validate()
    return cfg
