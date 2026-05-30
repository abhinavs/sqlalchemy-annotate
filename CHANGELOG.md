# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-05-30

### Changed
- Annotation blocks are now placed below the model class by default. Set
  `position = "top"` in `pyproject.toml` (or `--position top` on the CLI) to
  restore the previous placement.

### Added
- `position` config option / `--position` CLI flag (`top` | `bottom`).

### Fixed
- Top-position blocks above a class that is the first statement in a file
  are now idempotent (previously a re-run would stack a second block).

## [0.1.0] - 2026-05-20

### Added
- `generate`, `check`, and `remove` commands with a Rails-style
  `# == Schema Information` block.
- Metadata-only schema extraction (no database connection); a connection URL
  is parsed for its dialect only, with async drivers collapsing to their sync
  backend and a PostgreSQL fallback.
- Truthful type rendering by default with an opt-in `normalize_types`
  (Rails-style `bigint` / `varchar(255)`).
- Recursive model discovery via import-walking; broken or circular modules are
  reported and skipped, never fatal.
- libcst-based rewriting that preserves imports, comments, blank lines and
  Black formatting; idempotent output so `check` is reliable in CI.
- `pyproject.toml` configuration under `[tool.sqlalchemy-annotate]` with CLI
  override precedence.
- pre-commit hook definitions (`sqlalchemy-annotate`,
  `sqlalchemy-annotate-check`) and a GitHub Actions matrix.
- PEP 561 typing marker (`py.typed`).

[Unreleased]: https://github.com/abhinavs/sqlalchemy-annotate/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/abhinavs/sqlalchemy-annotate/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/abhinavs/sqlalchemy-annotate/releases/tag/v0.1.0
