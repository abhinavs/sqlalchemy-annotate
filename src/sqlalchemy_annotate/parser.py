"""libcst helpers: build comment lines and locate an existing block.

Kept separate from the transformer so the region-detection logic (the part
that must stay stable for idempotent ``generate`` and reliable ``check``) is
unit-testable in isolation.
"""

from __future__ import annotations

import libcst as cst

from sqlalchemy_annotate.errors import ParseError
from sqlalchemy_annotate.formatter import END_MARKER, START_MARKER


def parse_module(source: str, path: str) -> cst.Module:
    try:
        return cst.parse_module(source)
    except Exception as exc:  # noqa: BLE001 - libcst raises various parse errors
        raise ParseError(f"{path}: not valid Python, left untouched ({exc})") from exc


def comment_line(text: str) -> cst.EmptyLine:
    """A single ``#`` comment as a leading EmptyLine at the block's indent."""
    return cst.EmptyLine(
        indent=True,
        whitespace=cst.SimpleWhitespace(""),
        comment=cst.Comment(text),
        newline=cst.Newline(),
    )


def blank_line() -> cst.EmptyLine:
    return cst.EmptyLine(
        indent=True, whitespace=cst.SimpleWhitespace(""), comment=None,
        newline=cst.Newline(),
    )


def is_blank(line: cst.EmptyLine) -> bool:
    return line.comment is None


def _marker(line: cst.EmptyLine) -> str | None:
    if line.comment is None:
        return None
    return line.comment.value.strip()


def find_block(lines: list[cst.EmptyLine]) -> tuple[int, int] | None:
    """Return inclusive ``(start, end)`` of our marked block, or ``None``.

    Indices point at the START_MARKER / END_MARKER comment lines themselves.
    """
    start: int | None = None
    for idx, line in enumerate(lines):
        m = _marker(line)
        if m == START_MARKER and start is None:
            start = idx
        elif m == END_MARKER and start is not None:
            return (start, idx)
    return None


def strip_block(lines: list[cst.EmptyLine]) -> list[cst.EmptyLine]:
    """Remove the block and the single trailing blank we own after it.

    Leading blank lines are deliberately preserved: they are the user's (or
    Black's) separation from the preceding code. The block always sits
    immediately above the class, so re-adding ``block + [blank]`` after this
    reproduces the exact same leading_lines -- which is what makes ``generate``
    idempotent and ``check`` trustworthy.
    """
    region = find_block(lines)
    if region is None:
        return lines
    start, end = region
    hi = end
    if hi + 1 < len(lines) and is_blank(lines[hi + 1]):
        hi += 1
    return lines[:start] + lines[hi + 1 :]
