"""Typed exceptions surfaced as clean CLI messages (no tracebacks for user error)."""

from __future__ import annotations


class AnnotateError(Exception):
    """Base class for all expected, user-facing failures."""


class ConfigError(AnnotateError):
    """Invalid or unreadable configuration."""


class DiscoveryError(AnnotateError):
    """A models package could not be imported or contained no mapped classes."""


class ParseError(AnnotateError):
    """A source file could not be parsed as Python and was left untouched."""
