"""Render a :class:`ModelSchema` into the comment block.

Pure: ``ModelSchema`` + ``Config`` in, ``list[str]`` of ``#``-prefixed lines
out (no leading/trailing blank lines, no newlines). The writer is responsible
for splicing these into the file. Output is deterministic so ``generate`` is
idempotent and ``check`` can compare bytes.

A ``Renderer`` Protocol plus the ``sqlalchemy_annotate.renderers`` entry-point
group are defined as a seam for future formats (Markdown, ER, schema diff).
Only :class:`CommentRenderer` ships today.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.models import ColumnInfo, ModelSchema

START_MARKER = "# == Schema Information"
END_MARKER = "# == End Schema Information"


@runtime_checkable
class Renderer(Protocol):
    """Stable seam for alternative output formats (plugins, future commands)."""

    def render(self, schema: ModelSchema, config: Config) -> list[str]: ...


def _column_flags(col: ColumnInfo) -> str:
    parts: list[str] = [col.type_]
    if col.primary_key:
        parts.append("primary key")
    elif not col.nullable:
        parts.append("not null")
    if col.enum_values:
        parts.append("enum(" + ", ".join(col.enum_values) + ")")
    if col.default is not None:
        parts.append(f"default={col.default}")
    if col.server_default is not None:
        parts.append(f"server_default={col.server_default}")
    if col.fk_target is not None:
        parts.append(f"-> {col.fk_target}")
    return ", ".join(parts)


def _ordered_columns(schema: ModelSchema, config: Config) -> list[ColumnInfo]:
    cols = list(schema.columns)
    if config.sort == "alphabetical":
        cols.sort(key=lambda c: c.name)
    return cols


class CommentRenderer:
    """The built-in Rails-style ``# == Schema Information`` renderer."""

    def render(self, schema: ModelSchema, config: Config) -> list[str]:
        lines: list[str] = [START_MARKER, "#", f"# Table name: {schema.table_name}"]
        if schema.composite_pk:
            lines.append(f"# Composite primary key: {', '.join(schema.primary_key)}")
        lines.append("#")

        cols = _ordered_columns(schema, config)
        width = max((len(c.name) for c in cols), default=0)
        for col in cols:
            lines.append(f"# {col.name.ljust(width)} : {_column_flags(col)}")

        if config.include_indexes and (schema.indexes or schema.uniques):
            lines += ["#", "# Indexes"]
            for ix in schema.indexes:
                suffix = " UNIQUE" if ix.unique else ""
                lines.append(f"#   {ix.name} ({', '.join(ix.columns)}){suffix}")
            for uq in schema.uniques:
                name = uq.name or "(unnamed)"
                lines.append(f"#   {name} ({', '.join(uq.columns)}) UNIQUE")

        if config.include_foreign_keys and schema.foreign_keys:
            lines += ["#", "# Foreign Keys"]
            for fk in schema.foreign_keys:
                src = ", ".join(fk.columns)
                dst = fk.referred_table
                if fk.referred_columns:
                    dst += "." + ", ".join(fk.referred_columns)
                ondelete = f" (ON DELETE {fk.ondelete.upper()})" if fk.ondelete else ""
                lines.append(f"#   {src} -> {dst}{ondelete}")

        if config.include_relationships and schema.relationships:
            lines += ["#", "# Relationships"]
            for rel in schema.relationships:
                lines.append(f"#   {rel.name} ({rel.direction} {rel.target})")

        lines += ["#", END_MARKER]
        return lines


_DEFAULT_RENDERER = CommentRenderer()


def render_block(schema: ModelSchema, config: Config) -> list[str]:
    """Render with the built-in renderer."""
    return _DEFAULT_RENDERER.render(schema, config)
