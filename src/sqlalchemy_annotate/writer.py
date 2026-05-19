"""Splice annotation blocks into source files via a single libcst transformer.

libcst round-trips byte-for-byte, so everything outside the markers (imports,
comments, blank lines, Black layout) is preserved by construction. ``check``
relies on this: it renders into memory and compares bytes.
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
    parse_module,
    strip_block,
)


@dataclass(slots=True)
class FileResult:
    path: str
    changed: bool
    new_source: str
    error: str | None = None


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
        self._stack: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self._stack.append(node.name.value)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        qualname = ".".join(self._stack)
        self._stack.pop()

        leading = list(updated_node.leading_lines)
        cleaned = strip_block(leading)

        if self._remove or qualname not in self._schemas:
            if cleaned == leading:
                return updated_node
            return updated_node.with_changes(leading_lines=cleaned)

        # The block always sits immediately above the class; whatever blank
        # separation already preceded the class is preserved untouched.
        block = [comment_line(t) for t in render_block(self._schemas[qualname], self._config)]
        new_leading = [*cleaned, *block, blank_line()]
        return updated_node.with_changes(leading_lines=new_leading)


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
