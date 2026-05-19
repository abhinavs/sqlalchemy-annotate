# Security Policy

## Supported versions

The latest released `0.x` line receives security fixes.

## Reporting a vulnerability

Please report suspected vulnerabilities privately via GitHub Security
Advisories ("Report a vulnerability" on the repository's Security tab) rather
than a public issue. Expect an acknowledgement within a few days.

## Threat model notes

`sqlalchemy-annotate` **imports your model package** to read SQLAlchemy
metadata (this is required; there is no safe static-only path for arbitrary
SQLAlchemy code). Run it only against code you trust, the same as `pytest` or
`alembic`. It never opens a database connection: a connection URL, if
provided, is parsed for its dialect string only.
