"""Shared test helpers."""

from __future__ import annotations

import inspect
import textwrap
from pathlib import Path

import pytest

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.discovery import DiscoveredModel
from sqlalchemy_annotate.schema import build_schema, resolve_dialect


@pytest.fixture
def config() -> Config:
    return Config(include_indexes=True, include_foreign_keys=True)


@pytest.fixture
def pg_dialect():
    return resolve_dialect(Config())


def schema_for(cls, config: Config, dialect):
    """Build a ModelSchema for an already-mapped class."""
    model = DiscoveredModel(
        cls=cls,
        qualname=cls.__qualname__,
        source_file=inspect.getsourcefile(cls) or "<test>",
    )
    return build_schema(model, config, dialect)


def write_package(root: Path, files: dict[str, str]) -> None:
    """Materialise a package tree from {relative_path: source}."""
    for rel, src in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(src), encoding="utf-8")
