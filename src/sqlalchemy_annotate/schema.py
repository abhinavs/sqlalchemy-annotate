"""Turn a mapped class into a :class:`ModelSchema` from metadata alone.

No engine is ever connected. A connection URL, when present, is parsed only for
its backend name so column types can be compiled against the right dialect
offline (SQLAlchemy dialect objects render DDL without a DBAPI). Async drivers
(``+asyncpg``, ``+aiomysql``) collapse to their sync backend for compilation.
"""

from __future__ import annotations

import fnmatch

from sqlalchemy import Enum as SAEnum
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import make_url
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.types import TypeEngine

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.discovery import DiscoveredModel
from sqlalchemy_annotate.models import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    ModelSchema,
    RelationshipInfo,
    UniqueInfo,
)

_BACKEND_DIALECTS = {
    "postgresql": "sqlalchemy.dialects.postgresql",
    "mysql": "sqlalchemy.dialects.mysql",
    "mariadb": "sqlalchemy.dialects.mysql",
    "sqlite": "sqlalchemy.dialects.sqlite",
    "mssql": "sqlalchemy.dialects.mssql",
    "oracle": "sqlalchemy.dialects.oracle",
}


def resolve_dialect(config: Config):
    """Return a dialect instance for offline type compilation.

    Order: explicit ``dialect`` config, else the backend of ``engine``, else
    PostgreSQL (the dominant backend for the target audience).
    """
    import importlib

    backend = config.dialect
    if backend is None and config.engine:
        try:
            backend = make_url(config.engine).get_backend_name()
        except Exception:  # noqa: BLE001 - unparseable URL -> default
            backend = None
    module_path = _BACKEND_DIALECTS.get(backend or "", _BACKEND_DIALECTS["postgresql"])
    return importlib.import_module(module_path).dialect()


def _render_type(type_: TypeEngine, dialect) -> str:
    try:
        return type_.compile(dialect=dialect).lower()
    except Exception:  # noqa: BLE001 - unsupported type for dialect
        return str(type_).lower()


def _normalize(rendered: str, col, *, single_pk: bool) -> str:
    """Apply opt-in Rails-style fabrication on top of the truthful rendering."""
    base = rendered.split("(")[0]
    if single_pk and col.primary_key and base in {"integer", "int", "serial"} \
            and col.autoincrement in (True, "auto"):
        return "bigint"
    if base == "varchar" and "(" not in rendered:
        return "varchar(255)"
    return rendered


def _summarize_default(col) -> str | None:
    default = col.default
    if default is None:
        return None
    arg = getattr(default, "arg", None)
    if arg is None:
        return None
    import enum

    if isinstance(arg, enum.Enum):
        return f"{arg.__class__.__name__}.{arg.name}"
    if callable(arg):
        name = getattr(arg, "__name__", arg.__class__.__name__)
        return f"{name}()"
    return repr(arg)


def _summarize_server_default(col) -> str | None:
    sd = col.server_default
    if sd is None:
        return None
    arg = getattr(sd, "arg", sd)
    text = str(getattr(arg, "text", arg)).strip()
    return text[:60] + ("..." if len(text) > 60 else "")


def _fk_target(col) -> str | None:
    for fk in col.foreign_keys:
        return fk.target_fullname
    return None


def _columns(table, dialect, *, normalize: bool) -> tuple[ColumnInfo, ...]:
    pk_names = list(table.primary_key.columns.keys())
    single_pk = len(pk_names) == 1
    out: list[ColumnInfo] = []
    for col in table.columns:
        rendered = _render_type(col.type, dialect)
        if normalize:
            rendered = _normalize(rendered, col, single_pk=single_pk)
        enum_values: tuple[str, ...] = ()
        if isinstance(col.type, SAEnum) and col.type.enums:
            enum_values = tuple(col.type.enums)
        out.append(
            ColumnInfo(
                name=col.name,
                type_=rendered,
                nullable=bool(col.nullable),
                primary_key=bool(col.primary_key),
                autoincrement=col.autoincrement in (True, "auto") and col.primary_key,
                default=_summarize_default(col),
                server_default=_summarize_server_default(col),
                fk_target=_fk_target(col),
                enum_values=enum_values,
            )
        )
    return tuple(out)


def _indexes(table) -> tuple[IndexInfo, ...]:
    items = [
        IndexInfo(
            name=ix.name or "",
            columns=tuple(c.name for c in ix.columns),
            unique=bool(ix.unique),
        )
        for ix in table.indexes
    ]
    items.sort(key=lambda i: i.name)
    return tuple(items)


def _uniques(table) -> tuple[UniqueInfo, ...]:
    items = [
        UniqueInfo(name=c.name, columns=tuple(col.name for col in c.columns))
        for c in table.constraints
        if isinstance(c, UniqueConstraint) and len(c.columns) > 0
    ]
    items.sort(key=lambda u: (u.name or "", u.columns))
    return tuple(items)


def _split_target(target_fullname: str) -> tuple[str, str]:
    """``"schema.table.col"`` -> ``("schema.table", "col")`` without resolving."""
    table, _, column = target_fullname.rpartition(".")
    return table, column


def _foreign_keys(table) -> tuple[ForeignKeyInfo, ...]:
    items = []
    for fkc in sorted(table.foreign_key_constraints, key=lambda f: f.name or ""):
        elements = list(fkc.elements)
        # Use the declared target string, never ``e.column`` -- resolving the
        # remote Column requires the referenced table to be importable, which
        # breaks on forward/cross-package or intentionally dangling FKs.
        targets = [_split_target(e.target_fullname) for e in elements]
        items.append(
            ForeignKeyInfo(
                columns=tuple(e.parent.name for e in elements),
                referred_table=targets[0][0] if targets else "",
                referred_columns=tuple(col for _, col in targets),
                ondelete=fkc.ondelete,
            )
        )
    return tuple(items)


def _relationships(mapper) -> tuple[RelationshipInfo, ...]:
    items = []
    for rel in mapper.relationships:
        target = rel.mapper.class_.__name__
        direction = rel.direction.name.lower().replace("onetomany", "one-to-many")
        if rel.direction.name == "ONETOMANY":
            direction = "one-to-many"
        elif rel.direction.name == "MANYTOONE":
            direction = "many-to-one"
        elif rel.direction.name == "MANYTOMANY":
            direction = "many-to-many"
        elif getattr(rel, "uselist", True) is False:
            direction = "one-to-one"
        items.append(
            RelationshipInfo(name=rel.key, target=target, direction=direction)
        )
    items.sort(key=lambda r: r.name)
    return tuple(items)


def _excluded(table_name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(table_name, p) for p in patterns)


def build_schema(model: DiscoveredModel, config: Config, dialect) -> ModelSchema | None:
    """Extract a :class:`ModelSchema`, or ``None`` if excluded/unmapped."""
    mapper = sa_inspect(model.cls)
    table = mapper.local_table
    if table is None:  # abstract / inherited without its own table
        return None
    if _excluded(table.name, tuple(config.exclude)):
        return None

    return ModelSchema(
        class_qualname=model.qualname,
        table_name=table.name,
        source_file=model.source_file,
        columns=_columns(table, dialect, normalize=config.normalize_types),
        indexes=_indexes(table) if config.include_indexes else (),
        uniques=_uniques(table) if config.include_indexes else (),
        foreign_keys=_foreign_keys(table) if config.include_foreign_keys else (),
        relationships=(
            _relationships(mapper) if config.include_relationships else ()
        ),
        primary_key=tuple(table.primary_key.columns.keys()),
    )
