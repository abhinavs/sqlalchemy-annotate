"""Immutable value objects shared across the pipeline.

Extraction (``schema.py``) produces these; rendering (``formatter.py``) consumes
them. They carry no SQLAlchemy objects so the formatter stays trivially testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    name: str
    type_: str
    nullable: bool
    primary_key: bool
    autoincrement: bool = False
    default: str | None = None
    server_default: str | None = None
    fk_target: str | None = None  # "table.column"
    enum_values: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IndexInfo:
    name: str
    columns: tuple[str, ...]
    unique: bool


@dataclass(frozen=True, slots=True)
class UniqueInfo:
    name: str | None
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForeignKeyInfo:
    columns: tuple[str, ...]
    referred_table: str
    referred_columns: tuple[str, ...]
    ondelete: str | None = None


@dataclass(frozen=True, slots=True)
class RelationshipInfo:
    name: str
    target: str
    direction: str  # one-to-one | one-to-many | many-to-one | many-to-many


@dataclass(frozen=True, slots=True)
class ModelSchema:
    """Everything needed to render one model's annotation block."""

    class_qualname: str
    table_name: str
    source_file: str
    columns: tuple[ColumnInfo, ...] = ()
    indexes: tuple[IndexInfo, ...] = ()
    uniques: tuple[UniqueInfo, ...] = ()
    foreign_keys: tuple[ForeignKeyInfo, ...] = ()
    relationships: tuple[RelationshipInfo, ...] = ()
    primary_key: tuple[str, ...] = field(default_factory=tuple)

    @property
    def composite_pk(self) -> bool:
        return len(self.primary_key) > 1
