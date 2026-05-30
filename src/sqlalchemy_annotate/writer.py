"""Splice annotation blocks into source files via a single libcst transformer.

libcst round-trips byte-for-byte, so everything outside the markers (imports,
comments, blank lines, Black layout) is preserved by construction. ``check``
relies on this: it renders into memory and compares bytes.

Top-level classes are handled in ``leave_Module`` so the block can live either
above the class (``position = "top"``) or below it (``position = "bottom"``).
Nested mapped classes are rare; they keep the simpler top placement handled
in ``leave_ClassDef``.
"""

from __future__ import annotations

from dataclasses import dataclass

import libcst as cst

from sqlalchemy_annotate.config import Config
from sqlalchemy_annotate.formatter import render_block
from sqlalchemy_annotate.models import ModelSchema
from sqlalchemy_annotate.parser import (
    blank_line,
    comment_line,
    is_blank,
    parse_module,
    strip_block,
)


@dataclass(slots=True)
class FileResult:
    path: str
    changed: bool
    new_source: str
    error: str | None = None


def _render_lines(schema: ModelSchema, config: Config) -> list[cst.EmptyLine]:
    return [comment_line(t) for t in render_block(schema, config)]


class _Annotator(cst.CSTTransformer):
    def __init__(
        self,
        schemas: dict[str, ModelSchema],
        config: Config,
        *,
        remove: bool,
    ) -> None:
        self._schemas = schemas
        self._config = config
        self._remove = remove
        self._position = config.position
        self._stack: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self._stack.append(node.name.value)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        qualname = ".".join(self._stack)
        self._stack.pop()

        # Top-level classes are processed in leave_Module so we can place
        # blocks either above the class or after it (i.e. in the next
        # statement's leading_lines or in module.footer).
        if "." not in qualname:
            return updated_node

        # Nested mapped class: keep the simple "block above the class" form.
        leading = list(updated_node.leading_lines)
        cleaned = strip_block(leading)

        if self._remove or qualname not in self._schemas:
            if cleaned == leading:
                return updated_node
            return updated_node.with_changes(leading_lines=cleaned)

        block = _render_lines(self._schemas[qualname], self._config)
        new_leading = [*cleaned, *block, blank_line()]
        return updated_node.with_changes(leading_lines=new_leading)

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        body = list(updated_node.body)
        footer = list(updated_node.footer)
        # When the first statement is a class with a top-position block above,
        # libcst parks those lines in module.header (not in the class's
        # leading_lines), so they must be stripped and re-inserted there to
        # stay idempotent.
        header = list(updated_node.header)

        top_level = [
            (i, stmt.name.value)
            for i, stmt in enumerate(body)
            if isinstance(stmt, cst.ClassDef)
        ]

        # Strip stale top-position blocks (block + trailing blank we owned).
        for i, _name in top_level:
            if i == 0:
                cleaned = strip_block(header)
                if cleaned != header:
                    header = cleaned
            stmt = body[i]
            leading = list(stmt.leading_lines)
            cleaned = strip_block(leading)
            if cleaned != leading:
                body[i] = stmt.with_changes(leading_lines=cleaned)

        # Strip stale bottom-position blocks. They live either as the leading
        # content of the statement after the class, or in module.footer when
        # the class is the last top-level statement.
        for i, _name in top_level:
            j = i + 1
            if j < len(body):
                stmt = body[j]
                leading = list(stmt.leading_lines)
                cleaned = strip_block(
                    leading, leading_blank=True, trailing_blank=True
                )
                if cleaned != leading:
                    body[j] = stmt.with_changes(leading_lines=cleaned)
            else:
                cleaned = strip_block(
                    footer, leading_blank=True, trailing_blank=True
                )
                if cleaned != footer:
                    footer = cleaned

        if self._remove:
            return updated_node.with_changes(
                body=body, footer=footer, header=header
            )

        if self._position == "top":
            for i, name in top_level:
                if name not in self._schemas:
                    continue
                block = _render_lines(self._schemas[name], self._config)
                if i == 0:
                    header = [*header, *block, blank_line()]
                else:
                    stmt = body[i]
                    leading = list(stmt.leading_lines)
                    new_leading = [*leading, *block, blank_line()]
                    body[i] = stmt.with_changes(leading_lines=new_leading)
        else:  # "bottom"
            for i, name in top_level:
                if name not in self._schemas:
                    continue
                block = _render_lines(self._schemas[name], self._config)
                j = i + 1
                if j < len(body):
                    stmt = body[j]
                    existing = list(stmt.leading_lines)
                    new_leading = _bottom_insert(block, existing)
                    body[j] = stmt.with_changes(leading_lines=new_leading)
                else:
                    footer = _bottom_insert(block, footer)

        return updated_node.with_changes(
            body=body, footer=footer, header=header
        )


def _bottom_insert(
    block: list[cst.EmptyLine], existing: list[cst.EmptyLine]
) -> list[cst.EmptyLine]:
    """Place a block above ``existing`` with a single blank line on each side.

    If ``existing`` already starts with a blank, we re-use it as the
    block's trailing separator so the file does not accumulate blank lines
    on re-runs.
    """
    leading = [blank_line(), *block]
    if existing and is_blank(existing[0]):
        return [*leading, *existing]
    return [*leading, blank_line(), *existing]


def _apply(
    source: str,
    path: str,
    schemas: dict[str, ModelSchema],
    config: Config,
    *,
    remove: bool,
) -> FileResult:
    module = parse_module(source, path)
    new_source = module.visit(
        _Annotator(schemas, config, remove=remove)
    ).code
    return FileResult(
        path=path, changed=new_source != source, new_source=new_source
    )


def annotate_source(
    source: str,
    path: str,
    schemas: dict[str, ModelSchema],
    config: Config,
) -> FileResult:
    """Return the file rewritten with fresh annotation blocks."""
    return _apply(source, path, schemas, config, remove=False)


def remove_source(source: str, path: str, config: Config) -> FileResult:
    """Return the file with every annotation block stripped."""
    return _apply(source, path, {}, config, remove=True)
